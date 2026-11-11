#!/usr/bin/env python3
"""Export the GEDCOM people who appear in a townland's census returns (WP17).

Reads Mike's private GEDCOM (kept outside the repository) and the reviewed links in
data/research/associations/tree_census_links.csv, and writes
townlands/<case>/records/people.json for every case that holds a linked census row:
dates, relationships and Mike's research notes, filtered by the 100/75/50 rule.
The page builder reads only that file. The GEDCOM is a secondary source: the page
labels it as research, apart from the census returns, which are the evidence.

Usage:
    python tools/gedcom_people.py export GEDCOM [--year 2026] [--dry-run]
    python tools/gedcom_people.py check

Privacy (CLAUDE.md, 100/75/50), applied per person and per event:
  - a person is included only if born 100 or more years ago, or died 50 or more years ago
  - a birth date is shown at 100 years, a marriage at 75, a death at 50
  - a relative is named only if that relative also passes
  - a note that names a year inside the last 50 years is withheld and listed for review
Nothing here invents or normalises a recorded fact. Dates keep the tree's own wording.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

try:
    from tools import tree_census_links as gc
except ImportError:  # run as a script: python tools/gedcom_people.py
    import tree_census_links as gc

ROOT = Path(__file__).resolve().parent.parent
THIS_YEAR = datetime.date.today().year
BIRTH_YEARS, MARRIAGE_YEARS, DEATH_YEARS = 100, 75, 50
AHNEN = re.compile(r"^\s*Ahnentafel\s+\d+\.?\s*", re.I)
AHN_REF = re.compile(r"\s*\(Ahn\.?\s*\d+\)|\bAhn\.?\s*\d+\b", re.I)   # the tree's own numbering
FAMILY_NOTE = re.compile(r"^\s*Family Note:\s*", re.I)
QUALIFIER = {"ABT": "about", "EST": "about", "CAL": "about", "BEF": "before", "AFT": "after"}


# ---------------------------------------------------------------- reading
def _text(n) -> list[str]:
    """Paragraphs of a NOTE node: CONC joins, CONT starts a new line, blanks are dropped."""
    out = n.val
    for k in n.kids:
        if k.tag == "CONC":
            out += k.val
        elif k.tag == "CONT":
            out += "\n" + k.val
    out = gc.html.unescape(out)
    return [re.sub(r"\s+", " ", p).strip() for p in out.split("\n") if p.strip()]


def year_of(date: str):
    m = re.search(r"\b(\d{4})\b", date or "")
    return int(m[1]) if m else None


def show_date(raw: str) -> str:
    """Display wording only: ABT 1855 becomes about 1855. The recorded value stays in 'raw'."""
    raw = (raw or "").strip()
    m = re.match(r"([A-Z]{3})\s+(.*)$", raw)
    if m and m[1] in QUALIFIER:
        return f"{QUALIFIER[m[1]]} {m[2]}"
    return raw


def _event(node, tag):
    ev = gc.child(node, tag)
    if ev is None:
        return None
    d, p = gc.child(ev, "DATE"), gc.child(ev, "PLAC")
    date = d.val.strip() if d else ""
    place = gc.html.unescape(p.val).strip() if p else ""
    return {"raw": date, "date": show_date(date), "year": year_of(date), "place": place} if (date or place) else None


def read_tree(path: Path) -> dict:
    roots = gc.parse_gedcom(Path(path).read_text(encoding="utf-8-sig"))
    people, fams = {}, {}
    for r in roots:
        if r.tag == "FAM":
            fams[r.ptr] = {
                "husb": (gc.child(r, "HUSB").val if gc.child(r, "HUSB") else ""),
                "wife": (gc.child(r, "WIFE").val if gc.child(r, "WIFE") else ""),
                "chil": [k.val for k in r.kids if k.tag == "CHIL"],
                "marr": _event(r, "MARR"),
            }
    for r in roots:
        if r.tag != "INDI":
            continue
        nm = gc.child(r, "NAME")
        g, s, nick = (gc.child(nm, t) for t in ("GIVN", "SURN", "NICK")) if nm else (None, None, None)
        given = gc.html.unescape(g.val) if g else ""
        surname = gc.html.unescape(s.val) if s else ""
        notes = []
        for k in r.kids:
            if k.tag == "NOTE":
                notes += _text(k)
        notes = [AHN_REF.sub("", AHNEN.sub("", p)).replace("  ", " ").strip() for p in notes]
        notes = [p for p in notes if p and not re.fullmatch(r"Subject of this family tree\.?", p, re.I)]
        people[r.ptr] = {
            "ptr": r.ptr, "given": given, "surname": surname,
            "name": f"{given} {surname}".strip() or "Unnamed",
            "nick": nick.val.strip() if nick else "",
            "sex": (gc.child(r, "SEX").val if gc.child(r, "SEX") else ""),
            "birth": _event(r, "BIRT"), "death": _event(r, "DEAT"),
            "occupations": [k.val.strip() for k in r.kids if k.tag == "OCCU" and k.val.strip()],
            "famc": [k.val for k in r.kids if k.tag == "FAMC"],
            "fams": [k.val for k in r.kids if k.tag == "FAMS"],
            "notes": notes,
        }
    return {"people": people, "fams": fams}


# ---------------------------------------------------------------- privacy
def passes(p: dict, this_year: int = THIS_YEAR) -> bool:
    """A person may be named only if born 100 or more years ago or dead 50 or more years."""
    by = p["birth"]["year"] if p.get("birth") else None
    dy = p["death"]["year"] if p.get("death") else None
    if by is not None and this_year - by >= BIRTH_YEARS:
        return True
    return dy is not None and this_year - dy >= DEATH_YEARS


def recent_year_in(text: str, this_year: int = THIS_YEAR):
    """The first year in a note that falls inside the last 50 years, if any."""
    for m in re.finditer(r"\b(1[89]\d\d|20\d\d)\b", text):
        if this_year - int(m[1]) < DEATH_YEARS:
            return int(m[1])
    return None


def _shown(ev, years: int, this_year: int):
    if not ev:
        return None
    y = ev["year"]
    if y is None or this_year - y < years:   # no year, or too recent: not shown
        return None
    return {k: ev[k] for k in ("date", "raw", "place")}


# ---------------------------------------------------------------- linking
def case_spellings(root: Path) -> dict:
    """{(year, normalised spelling): case slug} from each case's census_match.json."""
    out = {}
    for f in sorted((root / "townlands").glob("*/records/census_match.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        for y, info in (m.get("years") or {}).items():
            for sp in info.get("spellings", []):
                out[(int(y), gc.place_key(sp["spelling"]))] = f.parents[1].name
    return out


def case_row(case_rows: dict, row: dict):
    """Find the census.json row of a case that a source row corresponds to."""
    y = str(row["year"])
    for r in case_rows.get(y, []):
        if y == "1926":
            if r.get("ref") == row["form"] and r.get("f") == row["first"] and r.get("s") == row["surname"]:
                return r
        elif (str(r.get("h")) == row["house"] and r.get("s") == row["surname"] and r.get("f") == row["first"]
              and (r.get("a") == row["age"])):
            return r
    return None


def build(tree: dict, decisions: list[dict], rows: list[dict], root: Path, this_year: int = THIS_YEAR):
    """Return ({case: people.json payload}, report)."""
    by_obs = {r["obs"]: r for r in rows}
    spell = case_spellings(root)
    census = {}
    for f in (root / "townlands").glob("*/records/census.json"):
        census[f.parents[1].name] = json.loads(f.read_text(encoding="utf-8"))
    per_case: dict[str, dict] = {}
    report = {"withheld_people": [], "held_notes": [], "unmapped": [], "no_case": []}
    for d in decisions:
        if d["status"] != "accepted":
            continue
        row = by_obs.get(d["obs_id"])
        p = tree["people"].get(d["person_ptr"])
        if row is None or p is None:
            report["unmapped"].append(d["obs_id"])
            continue
        case = spell.get((row["year"], gc.place_key(row["townland"])))
        if case is None or case not in census:
            report["no_case"].append((d["person_name"], row["year"], row["townland"]))
            continue
        crow = case_row(census[case], row)
        if crow is None:
            report["unmapped"].append(d["obs_id"])
            continue
        if not passes(p, this_year):
            report["withheld_people"].append(p["name"])
            continue
        c = per_case.setdefault(case, {"links": {}})
        c["links"].setdefault(p["ptr"], []).append(
            {"year": str(row["year"]), "h": crow["h"], "s": crow["s"], "f": crow["f"], "a": crow.get("a")})
    out = {}
    for case, c in per_case.items():
        people, refs, family_notes = [], {}, []

        def ref(ptr):
            q = tree["people"].get(ptr)
            if not q or not passes(q, this_year):
                return None
            refs.setdefault(ptr, {"name": q["name"], "nick": q["nick"],
                                  "born": (_shown(q["birth"], BIRTH_YEARS, this_year) or {}).get("date", ""),
                                  "died": (_shown(q["death"], DEATH_YEARS, this_year) or {}).get("date", "")})
            return ptr

        for ptr, links in c["links"].items():
            p = tree["people"][ptr]
            parents, spouses, kids = [], [], []
            for fid in p["famc"]:
                fm = tree["fams"].get(fid)
                if fm:
                    parents += [x for x in (ref(fm["husb"]), ref(fm["wife"])) if x]
            marriages = []
            for fid in p["fams"]:
                fm = tree["fams"].get(fid)
                if not fm:
                    continue
                sp = fm["wife"] if fm["husb"] == ptr else fm["husb"]
                spref = ref(sp) if sp else None
                kids += [x for x in (ref(k) for k in fm["chil"]) if x]
                mev = _shown(fm["marr"], MARRIAGE_YEARS, this_year)
                if spref or mev:
                    marriages.append({"spouse": spref, "date": (mev or {}).get("date", ""),
                                      "raw": (mev or {}).get("raw", ""), "place": (mev or {}).get("place", "")})
            notes = []
            for para in p["notes"]:
                ry = recent_year_in(para, this_year)
                if ry:
                    report["held_notes"].append((p["name"], ry, para[:100]))
                elif FAMILY_NOTE.match(para):          # one note shared by several people: shown once
                    fn = FAMILY_NOTE.sub("", para).strip()
                    if fn not in family_notes:
                        family_notes.append(fn)
                else:
                    notes.append(para)
            b, dth = _shown(p["birth"], BIRTH_YEARS, this_year), _shown(p["death"], DEATH_YEARS, this_year)
            people.append({
                "ptr": ptr, "name": p["name"], "given": p["given"], "surname": p["surname"], "nick": p["nick"], "sex": p["sex"],
                "birth": b, "death": dth, "occupations": p["occupations"],
                "parents": parents, "marriages": marriages, "children": kids, "notes": notes, "census": links,
            })
        people.sort(key=lambda x: ((tree["people"][x["ptr"]]["birth"] or {}).get("year") or 9999, x["name"]))
        out[case] = {
            "_generated_by": "tools/gedcom_people.py",
            "source": "Mike's family tree (GEDCOM), a secondary source built from research. Census returns are the evidence.",
            "privacy": "100/75/50 rule applied (CLAUDE.md). Generated for year %d." % this_year,
            "people": people, "refs": refs, "family_notes": family_notes,
        }
    return out, report


# ---------------------------------------------------------------- check
def check_file(path: Path, this_year: int = THIS_YEAR) -> list[str]:
    errs = []
    data = json.loads(path.read_text(encoding="utf-8"))
    for p in data.get("people", []):
        for ev, yrs in (("birth", BIRTH_YEARS), ("death", DEATH_YEARS)):
            e = p.get(ev)
            y = year_of((e or {}).get("raw", ""))
            if e and (y is None or this_year - y < yrs):
                errs.append(f"{path}: {p['name']} {ev} date is inside the {yrs} year rule")
        for m in p.get("marriages", []):
            y = year_of(m.get("raw", ""))
            if m.get("date") and (y is None or this_year - y < MARRIAGE_YEARS):
                errs.append(f"{path}: {p['name']} marriage date is inside the {MARRIAGE_YEARS} year rule")
        for para in p.get("notes", []):
            if recent_year_in(para, this_year):
                errs.append(f"{path}: {p['name']} note names a year inside the last {DEATH_YEARS} years")
        if AHN_REF.search(" ".join(p.get("notes", []))) or "Ahnentafel" in " ".join(p.get("notes", [])):
            errs.append(f"{path}: {p['name']} note still carries a tree number")
    for para in data.get("family_notes", []):
        if recent_year_in(para, this_year):
            errs.append(f"{path}: a family note names a year inside the last {DEATH_YEARS} years")
    for ptr, r in data.get("refs", {}).items():
        for k, yrs in (("born", BIRTH_YEARS), ("died", DEATH_YEARS)):
            y = year_of(r.get(k, ""))
            if r.get(k) and (y is None or this_year - y < yrs):
                errs.append(f"{path}: relative {r['name']} {k} date is inside the {yrs} year rule")
    return errs


def check_repo(root: Path = ROOT) -> list[str]:
    errs = []
    for f in sorted((root / "townlands").glob("*/records/people.json")):
        errs += check_file(f)
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("gedcom", type=Path)
    e.add_argument("--year", type=int, default=THIS_YEAR)
    e.add_argument("--dry-run", action="store_true")
    sub.add_parser("check")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        errs = check_repo()
        print("\n".join(errs) if errs else "gedcom_people check: ok")
        return 1 if errs else 0
    tree = read_tree(a.gedcom)
    out, rep = build(tree, gc.read_decisions(), gc.load_census(gc.CENSUS_DIR), ROOT, a.year)
    for case, payload in sorted(out.items()):
        n_notes = sum(len(p["notes"]) for p in payload["people"])
        print(f"{case}: {len(payload['people'])} people, {n_notes} notes, {len(payload['refs'])} relatives named")
        if not a.dry_run:
            (ROOT / "townlands" / case / "records" / "people.json").write_text(
                json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"withheld by privacy rule: {len(set(rep['withheld_people']))} people; held notes: {len(rep['held_notes'])}")
    for n, y, t in rep["held_notes"]:
        print(f"  held note ({n}, year {y}): {t}")
    if rep["no_case"]:
        print(f"no case with census returns yet: {len(rep['no_case'])} links, "
              f"townlands {sorted({t for _, _, t in rep['no_case']})}")
    if rep["unmapped"]:
        print("links not found in the case census rows:", rep["unmapped"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
