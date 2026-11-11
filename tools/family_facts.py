#!/usr/bin/env python3
"""Family fact sheet (WP21): everything the evidence says about one family in one townland.

    python tools/family_facts.py cullionboy Kelly

Writes townlands/<townland>/records/facts/<family>.json. Every fact carries a tier that says
how firmly it stands, and a `usable` flag. A story may rest only on usable facts
(docs/STORY_SPEC.md: "Use only links Mike has accepted").

Tiers:
  tree      Mike's family tree (secondary source, research). Already filtered by 100/75/50.
  census    a census return as recorded, one return at a time (custodian published).
  griffiths a row of Griffith's Valuation as transcribed for the townland.
  accepted  a census link Mike accepted (WP19), or a census row he tied to a tree person.
  derived   worked out from usable facts above (an age at a wedding, a count of children).
  media     a caption in media.csv.
  proposed  a census link the matcher proposes and Mike has not accepted. NOT usable. It carries
            the matcher's confidence (high, medium, low, ambiguous) so the weight is visible.

Conflicts between records (an age that drifts, an age at death that does not fit the dates) are
listed under `conflicts` and never resolved here. They belong in the townland STATUS.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import census_links as cl  # noqa: E402
import tree_census_links  # noqa: E402
import given_names_reference  # noqa: E402
import variants_reference  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DATE = re.compile(r"^\s*(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})\s*$")
YEAR = re.compile(r"(\d{4})")
DRIFT_LIMIT = 3
USABLE = {"tree", "census", "griffiths", "accepted", "derived", "media"}
TREE_CENSUS_URL = {1901: "", 1911: "", 1926: ""}


def parse_date(s: str):
    """(day, month number, year, exact) from a tree date. 'about 1840' gives (None, None, 1840, False)."""
    m = DATE.match(s or "")
    if m and m[2].lower() in MONTHS:
        return int(m[1]), MONTHS.index(m[2].lower()) + 1, int(m[3]), True
    y = YEAR.search(s or "")
    return (None, None, int(y[1]), False) if y else None


def age_between(born, when):
    """(age, exact). Exact only when both dates are full."""
    if not born or not when:
        return None
    if born[3] and when[3]:
        a = when[2] - born[2] - ((when[1], when[0]) < (born[1], born[0]))
        return a, True
    return when[2] - born[2], False


def clean_place(p: str) -> str:
    return re.sub(r",?\s*County Donegal, Ireland$", "", p or "").strip()


class Sheet:
    def __init__(self):
        self.facts, self.conflicts = [], []

    def add(self, kind, tier, text, **kw):
        f = {"id": "F%03d" % (len(self.facts) + 1), "kind": kind, "tier": tier,
             "usable": tier in USABLE, "text": text}
        f.update({k: v for k, v in kw.items() if v not in (None, "", [])})
        self.facts.append(f)
        return f


def surname_ok(name: str, canon: str, names: cl.Names) -> bool:
    return any(names.surname_canon(w) == canon for w in re.findall(r"[A-Za-z']+", name or ""))


def load_overrides(path: Path):
    out = {}
    if Path(path).is_file():
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                out[r["person"]] = r["decision"]
    return out


def cleared(person: dict, this_year: int, overrides: dict) -> tuple[bool, str]:
    """100/75/50 for a tree person. people.json is already filtered, so this is a second look."""
    if overrides.get(person["name"]) == "allow":
        return True, "override"
    b = parse_date(person["birth"].get("date", ""))
    d = parse_date((person.get("death") or {}).get("date", ""))
    if d and this_year - d[2] >= 50:
        return True, "died 50 or more years ago"
    if b and this_year - b[2] >= 100:
        return True, "born 100 or more years ago"
    return False, "not cleared by 100/75/50"


def build(townland: str, family: str, root: Path = ROOT, census_dir: Path = cl.CENSUS_DIR,
          decisions: Path = cl.DECISIONS, this_year: int | None = None, with_proposals: bool = True) -> dict:
    this_year = this_year or datetime.date.today().year
    case = Path(root) / "townlands" / townland
    names = cl.Names(given_names_reference.load(), variants_reference.load())
    canon = names.surname_canon(family)
    sh = Sheet()
    tkey = cl.townland_key(townland.replace("-", " "))

    # ---------------------------------------------------------------- tree
    pj = case / "records" / "people.json"
    people, refs = [], {}
    if pj.is_file():
        data = json.loads(pj.read_text(encoding="utf-8"))
        people, refs = data.get("people", []), data.get("refs", {})
    by_ptr = {p["ptr"]: p for p in people}
    keep = {p["ptr"] for p in people if surname_ok(p["surname"], canon, names)}
    for p in people:  # spouses, parents and children of the family
        if p["ptr"] in keep:
            continue
        if any(m["spouse"] in keep for m in p.get("marriages", [])) or set(p.get("parents", [])) & keep \
                or set(p.get("children", [])) & keep:
            keep.add(p["ptr"])
    overrides = load_overrides(Path(root) / "privacy_overrides.csv")
    alias, extra = {}, {}
    ages, rel = [], []   # ages: (name, age, year, exact, basis); rel: (relation, who, of)
    tree = {}
    for p in people:
        if p["ptr"] not in keep:
            continue
        ok, why = cleared(p, this_year, overrides)
        tree[p["ptr"]] = p
        b, d = p["birth"], p.get("death") or {}
        bits = ["%s" % p["name"]]
        if b.get("date"):
            bits.append("born %s%s" % (b["date"], " at " + clean_place(b["place"]) if b.get("place") else ""))
        if d.get("date"):
            bits.append("died %s%s" % (d["date"], " at " + clean_place(d["place"]) if d.get("place") else ""))
        sh.add("person", "tree", "; ".join(bits), who=p["name"], ptr=p["ptr"], sex=p.get("sex"),
               born=b.get("date"), born_place=clean_place(b.get("place", "")), died=d.get("date"),
               died_place=clean_place(d.get("place", "")), occupations=p.get("occupations"),
               cleared=ok, cleared_because=why, nick=p.get("nick"))
        for n in p.get("notes", []):
            sh.add("note", "tree", n, who=p["name"], ptr=p["ptr"])
        for m in p.get("marriages", []):
            sp = by_ptr.get(m["spouse"]) or refs.get(m["spouse"], {})
            if p.get("sex") == "M" or m["spouse"] not in tree and m["spouse"] not in keep:   # each marriage once
                sh.add("marriage", "tree", "%s married %s on %s at %s" % (
                    p["name"], sp.get("name", "?"), m["date"], clean_place(m.get("place", ""))),
                    who=[p["name"], sp.get("name", "")], date=m["date"], place=clean_place(m.get("place", "")))
            rel.append(("spouse", sp.get("name", ""), p["name"]))
            rel.append(("wife" if by_ptr.get(m["spouse"], {}).get("sex") == "F" or p.get("sex") == "M" else "husband",
                        sp.get("name", ""), p["name"]))
        for c in p.get("children", []):
            cn = (by_ptr.get(c) or refs.get(c, {})).get("name", "")
            cs = (by_ptr.get(c) or {}).get("sex", "")
            if cn:
                rel.append(("father" if p.get("sex") == "M" else "mother", p["name"], cn))
                rel.append(("son" if cs == "M" else "daughter" if cs == "F" else "child", cn, p["name"]))
        for pr in p.get("parents", []):
            pn = (by_ptr.get(pr) or refs.get(pr, {})).get("name", "")
            if pn:
                rel.append(("parent", pn, p["name"]))
    # siblings and grandparents, from the tree's parent links
    kids = {}
    for ptr, p in tree.items():
        for pr in p.get("parents", []):
            kids.setdefault(pr, []).append(ptr)
    for ptr, p in tree.items():
        for pr in p.get("parents", []):
            for sib in kids.get(pr, []):
                if sib != ptr:
                    rel.append(("brother" if tree[sib].get("sex") == "M" else "sister", tree[sib]["name"], p["name"]))
            for gp in (by_ptr.get(pr) or {}).get("parents", []):
                g = by_ptr.get(gp) or refs.get(gp, {})
                if g.get("name"):
                    rel.append(("grandparent", g["name"], p["name"]))
    related = set()
    for p in tree.values():
        related |= set(p.get("parents", [])) | set(p.get("children", [])) | {m["spouse"] for m in p.get("marriages", [])}
        related |= {g for pr in p.get("parents", []) for g in (by_ptr.get(pr) or {}).get("parents", [])}
    for ptr in sorted(related - set(tree)):
        r = refs.get(ptr)
        if r and r.get("name") and ptr not in by_ptr:
            bits = [r["name"]] + (["born " + r["born"]] if r.get("born") else []) + (["died " + r["died"]] if r.get("died") else [])
            sh.add("person", "tree", "; ".join(bits), who=r["name"], ptr=ptr, born=r.get("born"), died=r.get("died"),
                   cleared=True, cleared_because="named by a person who passed 100/75/50 (people.json)")
    NOTE_REL = re.compile(r"\b(?:paternal |maternal )?(grandfather|grandmother|father|mother|brother|sister) ([A-Z][a-z]+(?: [A-Z][a-zA-Z]+)?)")
    for ptr, p in tree.items():
        for n in p.get("notes", []):
            for m in NOTE_REL.finditer(n):
                if not re.match(r"(and|of|in|was|is)\b", m[2]):
                    rel.append((m[1], m[2], p["name"]))
        if p.get("nick"):
            alias[p["name"]] = p["nick"]
    # ages at events, from the tree's own dates
    for ptr, p in tree.items():
        b = parse_date(p["birth"].get("date", ""))
        for m in p.get("marriages", []):
            r = age_between(b, parse_date(m["date"]))
            if r:
                ages.append((p["name"], r[0], parse_date(m["date"])[2], r[1], "age at marriage"))
                sh.add("age", "derived", "%s was %d at the marriage on %s" % (p["name"], r[0], m["date"]),
                       who=p["name"], age=r[0], exact=r[1], year=parse_date(m["date"])[2])
        dd = (p.get("death") or {}).get("date")
        if dd:
            r = age_between(b, parse_date(dd))
            stated = [int(x) for n in p.get("notes", []) for x in re.findall(r"\baged (\d{1,3})\b", n)]
            if r and r[1]:
                ages.append((p["name"], r[0], parse_date(dd)[2], True, "age at death"))
                sh.add("age", "derived", "%s was %d at death on %s" % (p["name"], r[0], dd), who=p["name"],
                       age=r[0], exact=True, year=parse_date(dd)[2])
            for s in stated:
                if r and s != r[0]:
                    sh.conflicts.append("%s: a tree note gives age %d at death, but the birth and death dates give %d."
                                        % (p["name"], s, r[0]))
        # children
        nkids = len([c for c in p.get("children", [])])
        if nkids and p.get("sex") == "M":
            sh.add("count", "derived", "%s and %s had %d children in the tree" % (
                p["name"], next((by_ptr.get(m["spouse"], {}).get("name", "") for m in p.get("marriages", [])), ""), nkids),
                who=p["name"], count=nkids)
    places = {}
    for ptr, p in tree.items():
        pl = clean_place(p["birth"].get("place", ""))
        if pl and not p.get("children") and p.get("parents"):
            places.setdefault(pl, []).append(p["name"])
    for pl, who in places.items():
        if len(who) > 1:
            sh.add("count", "derived", "%d children in the tree were born at %s: %s" % (len(who), pl, ", ".join(who)),
                   who=who, count=len(who), place=pl)
    # tree census entries are rows Mike tied to the person (accepted anchors)
    for ptr, p in tree.items():
        seen = []
        for c in p.get("census", []):
            sh.add("anchor", "accepted", "%s is %s %s, aged %s, in the %s return" % (
                p["name"], c["f"], c["s"], c["a"], c["year"]), who=p["name"], year=int(c["year"]), age=c["a"],
                recorded_name="%s %s" % (c["f"], c["s"]))
            ages.append((p["name"], c["a"], int(c["year"]), True, "census anchor"))
            seen.append((int(c["year"]), c["a"]))
            alias.setdefault(p["name"], "")
            if c["f"].split()[0] != p["given"]:
                extra.setdefault(p["name"], set()).add("%s %s" % (c["f"], c["s"]))
        seen.sort()
        for (y1, a1), (y2, a2) in zip(seen, seen[1:]):
            drift = (a2 - a1) - (y2 - y1)
            if abs(drift) >= DRIFT_LIMIT:
                sh.conflicts.append("%s: aged %d in %d and %d in %d, a drift of %+d years against the %d between returns."
                                    % (p["name"], a1, y1, a2, y2, drift, y2 - y1))

    # ---------------------------------------------------------------- census rows
    rows = [r for r in cl.load_census(census_dir) if r["tkey"] == tkey]
    fam_rows = [r for r in rows if names.surname_canon(r["surname"]) == canon]
    hh_ids = {(r["year"], r["hh"]) for r in fam_rows}
    hh_rows = [r for r in rows if (r["year"], r["hh"]) in hh_ids]
    for r in sorted(hh_rows, key=lambda r: (r["year"], str(r["house"]), r["rel"] != "Head", r["surname"], r["first"])):
        bits = ["%s %s, %s, in the %d return" % (r["first"], r["surname"], r["age"] if r["age"] is not None else "age not given", r["year"])]
        if r["rel"]:
            bits.append("recorded as %s" % r["rel"])
        if r["marital_raw"]:
            bits.append(r["marital_raw"])
        if r["occ"]:
            bits.append(r["occ"])
        if r["birth"]:
            bits.append("born " + r["birth"])
        if r["marr_years"] is not None:
            bits.append("%s years married" % r["marr_years"])
        if r["born"] is not None:
            bits.append("%s children born" % r["born"])
        sh.add("census", "census", "; ".join(bits), who="%s %s" % (r["first"], r["surname"]), year=r["year"],
               age=r["age"], relation=r["rel"], household=str(r["house"] or r["form"]), obs=r["obs"],
               in_family=r in fam_rows)
        if r["age"] is not None:
            ages.append(("%s %s" % (r["first"], r["surname"]), r["age"], r["year"], True, "census"))
        if r["rel"]:
            head = next((h for h in hh_rows if h["hh"] == r["hh"] and h["relc"] == "head"), None)
            if head and r is not head:
                rel.append((r["rel"].lower(), "%s %s" % (r["first"], r["surname"]), "%s %s" % (head["first"], head["surname"])))
    for (year, hh) in sorted(hh_ids, key=lambda k: (k[0], str(k[1]))):
        members = [r for r in hh_rows if (r["year"], r["hh"]) == (year, hh)]
        head = next((r for r in members if r["relc"] == "head"), None)
        sons = [r for r in members if r["relc"] == "son"]
        kids = [r for r in members if r["relc"] in ("son", "daughter")]
        if head:
            sh.add("count", "derived", "In %d the %s household held %d people: %d sons and %d children of the head" % (
                year, head["surname"], len(members), len(sons), len(kids)), year=year, count=len(members),
                counts=[len(members), len(sons), len(kids)], who="%s %s" % (head["first"], head["surname"]))
            for r in members:
                if r["marital_raw"] and re.search(r"\d+ children", r["marital_raw"]):
                    n = int(re.search(r"(\d+) children", r["marital_raw"])[1])
                    sh.add("count", "derived", "%s %s recorded %d children living in %d" % (r["first"], r["surname"], n, year),
                           year=year, count=n, who="%s %s" % (r["first"], r["surname"]))

    # ---------------------------------------------------------------- Griffith's
    content = json.loads((case / "content.json").read_text(encoding="utf-8")) if (case / "content.json").is_file() else {}
    lessor = ""
    sh.add("source", "griffiths", "Griffith's Valuation, mid 1850s, townland of %s" % townland.title(), year=1850)
    for g in (content.get("griffiths") or {}).get("rows", []):
        if g.get("les") and g["les"].lower() != "same":
            lessor = g["les"]
        occ = " ".join([g.get("names", ""), g.get("occ", "")])
        if surname_ok(occ, canon, names):
            sh.add("griffiths", "griffiths", "%s held %s acres roods perches (lot %s, %s) from %s, valued at %s" % (
                g.get("names") or g.get("occ"), g.get("area", ""), g.get("lot", ""), g.get("desc", ""),
                g.get("les") if g.get("les", "").lower() != "same" else lessor, g.get("tot", "")),
                who=g.get("names") or g.get("occ"), acres=g.get("ac"), lot=g.get("lot"), lessor=lessor)

    # ---------------------------------------------------------------- media
    mc = case / "media" / "media.csv"
    label = next((f.get("name") for f in content.get("families", []) if canon in
                  [names.surname_canon(k) for k in f.get("keys", [])]), "")
    if mc.is_file():
        with open(mc, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["scope"] == "family" and r["family"] == label:
                    sh.add("media", "media", "Photograph: %s" % r["caption"], file=r["file"], caption=r["caption"])

    # ---------------------------------------------------------------- census links
    all_rows = cl.load_census(census_dir)
    by_obs = {r["obs"]: r for r in all_rows}
    fam_obs = {r["obs"] for r in fam_rows}
    dec = cl.load_decisions(decisions) if Path(decisions).is_file() else {}
    for (fo, to), d in sorted(dec.items()):
        if d["status"] == "accepted" and (fo in fam_obs or to in fam_obs) and fo in by_obs and to in by_obs:
            a, b = by_obs[fo], by_obs[to]
            sh.add("link", "accepted", "%s %s (%s, %s) is %s %s (%s, %s)" % (
                a["first"], a["surname"], a["age"], a["year"], b["first"], b["surname"], b["age"], b["year"]),
                obs=[fo, to], confidence=d.get("confidence"), reviewer=d.get("reviewer"))
    proposed = 0
    if with_proposals and fam_rows:
        cfg = cl.load_config()
        for ded in sorted({r["ded"] for r in fam_rows}):
            drows = [r for r in all_rows if r["ded"] == ded]
            links, _ = cl.propose_ded(drows, names, cfg, dec)
            for c in links:
                if c.get("decision") or not (c["a"]["obs"] in fam_obs or c["b"]["obs"] in fam_obs):
                    continue
                a, b = c["a"], c["b"]
                proposed += 1
                sh.add("link", "proposed", "Proposed, not accepted: %s %s (%s, %s) may be %s %s (%s, %s); matcher confidence %s" % (
                    a["first"], a["surname"], a["age"], a["year"], b["first"], b["surname"], b["age"], b["year"],
                    c["confidence"]), obs=[a["obs"], b["obs"]], confidence=c["confidence"], flags=c.get("flags"))

    full = set(rel)
    for relname, who, of in list(full):          # the same person under a recorded or preferred name
        for a_, names_ in extra.items():
            if who == a_:
                full |= {(relname, n, of) for n in names_}
            if of == a_:
                full |= {(relname, who, n) for n in names_}
    for relname, who, of in sorted(full):
        if who and of:
            sh.add("relation", "tree" if relname in ("spouse", "wife", "husband", "father", "mother", "parent", "brother",
                                                     "sister", "grandfather", "grandmother", "grandparent", "son", "daughter", "child")
                   and any(f["kind"] == "person" for f in sh.facts) else "census",
                   "%s is %s of %s" % (who, relname, of), relation=relname, who=who, of=of)

    tiers = {}
    for f in sh.facts:
        tiers[f["tier"]] = tiers.get(f["tier"], 0) + 1
    return {"_generated_by": "tools/family_facts.py", "townland": townland, "family": family,
            "surname_family": canon, "year": this_year,
            "tiers": dict(sorted(tiers.items())),
            "accepted_census_links": sum(1 for f in sh.facts if f["kind"] == "link" and f["tier"] == "accepted"),
            "proposed_census_links": proposed,
            "conflicts": sh.conflicts, "facts": sh.facts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("townland")
    ap.add_argument("family")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--no-proposals", action="store_true", help="skip the matcher (faster)")
    a = ap.parse_args(argv)
    sheet = build(a.townland, a.family, with_proposals=not a.no_proposals)
    out = a.out or ROOT / "townlands" / a.townland / "records" / "facts" / ("%s.json" % re.sub(r"[^a-z0-9]+", "_", a.family.lower()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sheet, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Fact sheet for %s in %s: %d facts" % (a.family, a.townland, len(sheet["facts"])))
    for t, n in sheet["tiers"].items():
        print("  %-10s %d%s" % (t, n, "" if t in USABLE else "  (not usable in a story)"))
    for c in sheet["conflicts"]:
        print("  conflict: " + c)
    print("Written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
