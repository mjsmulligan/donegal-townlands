"""Census GEDCOM writer (WP20): a GEDCOM test file for one townland, one family or one DED.

    python tools/census_gedcom.py --townland cullionboy
    python tools/census_gedcom.py --family Kelly
    python tools/census_gedcom.py --ded Clogher

The file is built from the census returns, the census links Mike accepted (WP19,
`data/research/associations/census_links.csv`) and the links he accepted from his own tree
(`data/research/associations/gedcom_census.csv`). Nothing is stated that the returns do not state:
one person per chain of accepted links, every recorded spelling as a name, one census event per
return, a derived birth year from the age in the earliest return, and families only where a return
shows the relationship. No marriage, death or emigration is inferred.

Whole households are included for each return a chain touches, so the families read correctly. A
person with no accepted link appears with the one return that shows them.

The files are derived test files. They are regenerated when needed and are not committed.
Design: docs/CENSUS_GEDCOM_SPEC.md, section 6.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import census_links as cl  # noqa: E402
import gedcom_census  # noqa: E402
import given_names_reference  # noqa: E402
import variants_reference  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "processed" / "census_gedcom"
COUNTY = "County Donegal, Ireland"
SOURCES = {1901: "Census of Ireland 1901", 1911: "Census of Ireland 1911", 1926: "Census of Ireland 1926"}
MAX_MARRIED_YEARS = 70  # a larger value is a transcription error and is ignored
LINE_LIMIT = 200


# ------------------------------------------------------------------ chains

class Chains:
    """Rows joined into people. A join is refused if it would put two rows of one return in one
    person, or join two people the tree says are different."""

    def __init__(self, rows: list[dict], anchors: dict[str, str]):
        self.parent = {r["obs"]: r["obs"] for r in rows}
        self.years = {r["obs"]: {r["year"]: r["obs"]} for r in rows}
        self.anchor = {r["obs"]: ({anchors[r["obs"]]} if r["obs"] in anchors else set()) for r in rows}
        self.by_obs = {r["obs"]: r for r in rows}
        self.refused: list[str] = []

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def join(self, a: str, b: str, why: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        clash = sorted(set(self.years[ra]) & set(self.years[rb]))
        if clash:
            self.refused.append("%s: not joined, both already have a row in %s (%s and %s)"
                                % (why, clash[0], self._label(a), self._label(b)))
            return False
        if self.anchor[ra] and self.anchor[rb] and self.anchor[ra] != self.anchor[rb]:
            self.refused.append("%s: not joined, the tree says these are different people (%s and %s)"
                                % (why, self._label(a), self._label(b)))
            return False
        self.parent[rb] = ra
        self.years[ra].update(self.years.pop(rb))
        self.anchor[ra] |= self.anchor.pop(rb)
        return True

    def _label(self, obs: str) -> str:
        r = self.by_obs[obs]
        return "%s %s, %s, %s" % (r["first"], r["surname"], r["age"], r["year"])

    def groups(self) -> dict[str, list[dict]]:
        out = collections.defaultdict(list)
        for obs, r in self.by_obs.items():
            out[self.find(obs)].append(r)
        named = {}
        for members in out.values():
            members.sort(key=lambda r: (r["year"], r["obs"]))
            named["chain:" + members[0]["obs"]] = members
        return named


def load_anchors(path: Path = cl.TREE) -> dict[str, str]:
    """Census row to tree person pointer, from the links Mike accepted in his tree."""
    out = {}
    if Path(path).is_file():
        for r in gedcom_census.read_decisions(path):
            if r["status"] == "accepted":
                out[r["obs_id"]] = r["person_ptr"].strip("@")
    return out


def build_chains(rows, accepted_pairs, anchors, tentative=(), tent_used=None):
    """Returns (chain id to member rows, row to chain id, report lines, accepted links used).

    `tentative` is a list of matcher links Mike has not reviewed, each a dict with fo, to,
    confidence and flags. They are joined last, strongest first, so tree anchors and accepted
    links always win a clash. The ones that join are appended to `tent_used`."""
    present = {r["obs"] for r in rows}
    ch = Chains(rows, {o: p for o, p in anchors.items() if o in present})
    by_person = collections.defaultdict(list)
    for o, p in sorted(ch.anchor.items()):
        for ptr in p:
            by_person[ptr].append(ch.by_obs[o])
    report = []
    for ptr, rs in sorted(by_person.items()):
        rs.sort(key=lambda r: (r["year"], r["obs"]))
        for a, b in zip(rs, rs[1:]):
            if a["year"] == b["year"]:
                report.append("tree person %s has two rows in %d (%s and %s)" % (ptr, a["year"], ch._label(a["obs"]), ch._label(b["obs"])))
            else:
                ch.join(a["obs"], b["obs"], "tree person %s" % ptr)
    used = 0
    for fo, to in sorted(accepted_pairs, key=lambda p: (ch.by_obs[p[0]]["year"], p[0], p[1])):
        if fo in present and to in present:
            used += ch.join(fo, to, "accepted link %s > %s" % (fo, to))
    ordered = sorted(tentative or [], key=lambda t: (cl.RANK[t["confidence"]], t["fo"], t["to"]))
    for t in ordered:
        if t["fo"] in present and t["to"] in present:
            if ch.find(t["fo"]) == ch.find(t["to"]):
                continue   # already one person through the tree or an accepted link, so nothing tentative about it
            if ch.join(t["fo"], t["to"], "tentative link %s > %s" % (t["fo"], t["to"])) and tent_used is not None:
                tent_used.append(t)
    report = ch.refused + report
    groups = ch.groups()
    chain_of = {r["obs"]: cid for cid, members in groups.items() for r in members}
    return groups, chain_of, report, used


# ------------------------------------------------------------------ scope

def scope_filter(kind: str, value: str, names: cl.Names):
    if kind == "ded":
        return lambda r: r["ded"].lower() == value.lower()
    if kind == "townland":
        key = gedcom_census.place_key(value)
        return lambda r: r["tkey"] == key
    canon = names.surname_canon(value)
    return lambda r: names.surname_canon(r["surname"]) == canon


def hh_key(r: dict):
    return (r["ded"], r["hh"])


# ------------------------------------------------------------------ GEDCOM text

def ptr(prefix: str, text: str) -> str:
    return "@%s%s@" % (prefix, hashlib.sha1(text.encode("utf-8")).hexdigest()[:10].upper())


def line(level: int, tag: str, value: str = "", pointer: str = "") -> list[str]:
    value = re.sub(r"[\r\n]+", " ", value or "")
    head = "%d %s%s" % (level, pointer + " " if pointer else "", tag)
    if not value:
        return [head]
    out = ["%s %s" % (head, value[:LINE_LIMIT])]
    rest = value[LINE_LIMIT:]
    while rest:
        out.append("%d CONC %s" % (level + 1, rest[:LINE_LIMIT]))
        rest = rest[LINE_LIMIT:]
    return out


def note(level: int, text: str) -> list[str]:
    parts = text.split("\n")
    out = line(level, "NOTE", parts[0])
    for p in parts[1:]:
        out += line(level + 1, "CONT", p)
    return out


def valid_years(r: dict):
    y = r.get("marr_years")
    return y if isinstance(y, int) and 0 <= y <= MAX_MARRIED_YEARS else None


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("/", " ")).strip()


def person_names(members: list[dict]) -> list[tuple[str, str]]:
    seen, out = set(), []
    for r in members:
        first, sur = clean_name(r["first"]), clean_name(r["surname"])
        k = (first.casefold(), sur.casefold())
        if (first or sur) and k not in seen:
            seen.add(k)
            out.append((first, sur))
    return out


def event_note(r: dict) -> str:
    bits = ["Recorded as %s." % clean_name("%s %s" % (r["first"], r["surname"]))]
    for label, key in (("Relation to head", "rel"), ("Marital status", "marital_raw"), ("Occupation", "occ"), ("Birthplace", "birth")):
        if r.get(key):
            bits.append("%s: %s." % (label, r[key]))
    if r.get("marr_years") is not None:
        bits.append("Years married as recorded: %s." % r["marr_years"])
    if r.get("born") is not None:
        bits.append("Children born alive as recorded: %s." % r["born"])
    bits.append("Household: %s." % cl._hh_label(r))
    return " ".join(bits)


# ------------------------------------------------------------------ families

def chain_years(members, own: dict, year: int):
    """Years married for a wife in the return of `year`. Her own return is used if it states them.
    Otherwise the nearest return in her chain that does, moved by the years between the two
    returns (the 1901 and 1926 returns do not ask). Returns (years or None, note or None)."""
    v = valid_years(own)
    if v is not None:
        return v, None
    best = None
    for r in members or []:
        w = valid_years(r)
        if w is None or r["year"] == year:
            continue
        here = w + (year - r["year"])
        if 0 <= here <= MAX_MARRIED_YEARS and (best is None or abs(r["year"] - year) < best[0]):
            best = (abs(r["year"] - year), here, r["year"], w)
    if best is None:
        return None, None
    return best[1], "years married for the wife taken from her %d return (%d, so %d in %d)" % (best[2], best[3], best[1], year)


def chain_born(members, own: dict, year: int):
    """Children born alive: her own return, else the next later return that states it, which is an
    upper bound for the earlier return. Never taken from an earlier return, since it can only grow."""
    if own.get("born") is not None:
        return own["born"]
    later = sorted((r for r in members or [] if r["year"] > year and r.get("born") is not None), key=lambda r: r["year"])
    return later[0]["born"] if later else None


def household_families(hh_rows: dict, chain_of: dict, wife_parent: str, notes: list[str], groups=None):
    """Couples and children from the relationship each return states. Returns
    (couples: key -> (husb chain, wife chain), child options: chain -> list of (year, key, couple?))."""
    couples, options = {}, collections.defaultdict(list)
    for key in sorted(hh_rows, key=lambda k: (k[1][0], str(k))):
        members = sorted(hh_rows[key], key=lambda r: r["loc"])
        head = next((r for r in members if r["relc"] == "head"), None)
        if not head:
            continue
        spouse = next((r for r in members if r["relc"] in ("wife", "husband")), None)
        kids = [r for r in members if r["relc"] in ("son", "daughter") and "step" not in r["rel"].lower()]
        year = head["year"]
        h = chain_of[head["obs"]]
        fkey, wife_row = None, None
        if spouse and head["sex"] != spouse["sex"] and head["sex"] in "MF" and spouse["sex"] in "MF":
            husb, wife = (head, spouse) if head["sex"] == "M" else (spouse, head)
            fkey = (chain_of[husb["obs"]], chain_of[wife["obs"]])
            wife_row = wife
            couples[fkey] = fkey
        single = (h, None) if head["sex"] == "M" else (None, h)
        couples.setdefault(single, single)
        eligible = set()
        if fkey:
            wmembers = (groups or {}).get(chain_of[wife_row["obs"]])
            yrs, ynote = chain_years(wmembers, wife_row, year)
            if ynote:
                notes.append("%d %s: %s" % (year, cl._hh_label(head), ynote))
            if wife_parent == "assume":
                eligible = {c["obs"] for c in kids if yrs is None or c["age"] is None or c["age"] <= yrs + 1}
            else:
                eligible = {c["obs"] for c in kids if yrs is not None and c["age"] is not None and c["age"] <= yrs + 1}
            born = chain_born(wmembers, wife_row, year)
            if born is not None and len(eligible) > born:
                notes.append("%d %s: %d children are shown with %s but she recorded %d born alive, so none is attached to her"
                             % (year, cl._hh_label(head), len(eligible), clean_name(wife_row["first"] + " " + wife_row["surname"]), born))
                eligible = set()
        for c in kids:
            cc = chain_of[c["obs"]]
            if cc in (h, chain_of[spouse["obs"]] if spouse else None):
                continue
            if fkey and c["obs"] in eligible:
                options[cc].append((year, fkey, True))
            else:
                options[cc].append((year, single, False))
    return couples, options


def choose_family(opts: list, notes: list[str], label: str, parents=None):
    couple = [o for o in opts if o[2]]
    pick = min(couple) if couple else min(opts)
    chosen = {x for x in pick[1] if x}
    others = {o[1] for o in opts if not {x for x in o[1] if x} <= chosen}
    if others:
        who = lambda k: " and ".join(parents(c) for c in k if c) if parents else "different parents"
        notes.append("%s is shown with different parents: %s. The earliest is used. They may be the same people once their links are reviewed."
                     % (label, "; ".join("%s in %d" % (who(o[1]), o[0]) for o in sorted(opts) if {x for x in o[1] if x} - chosen)
                        + "; " + "%s in %d" % (who(pick[1]), pick[0])))
    return pick[1]


# ------------------------------------------------------------------ build

def build_gedcom(rows, accepted_pairs, anchors, kind, value, names, wife_parent="evidence", tentative=()):
    """Returns (text, report lines, counts). `tentative` is a list of unreviewed matcher links (see
    build_chains); with none, the file is built from accepted links and tree anchors only."""
    tent_used: list[dict] = []
    groups, chain_of, report, joined = build_chains(rows, accepted_pairs, anchors, tentative, tent_used)
    tent_by_chain = collections.defaultdict(list)
    for t in tent_used:
        tent_by_chain[chain_of[t["fo"]]].append(t)
    in_scope = scope_filter(kind, value, names)
    selected = {cid for cid, members in groups.items() if any(in_scope(r) for r in members)}
    hh_all = collections.defaultdict(list)
    for r in rows:
        hh_all[hh_key(r)].append(r)
    hh_in = {hh_key(r) for cid in selected for r in groups[cid]}
    hh_rows = {k: hh_all[k] for k in hh_in}
    people = set(selected) | {chain_of[r["obs"]] for rs in hh_rows.values() for r in rs}
    notes: list[str] = []
    couples, options = household_families(hh_rows, chain_of, wife_parent, notes, groups)

    child_family = {}
    for cc, opts in options.items():
        if cc in people:
            child_family[cc] = choose_family(opts, notes, person_label(groups[cc]), lambda c: person_label(groups[c], False))
    fams = {k: v for k, v in couples.items() if (k[0] in people or k[0] is None) and (k[1] in people or k[1] is None)}
    kids_of = collections.defaultdict(list)
    for cc, k in child_family.items():
        kids_of[k].append(cc)
    fams = {k: v for k, v in fams.items() if (k[0] and k[1]) or kids_of.get(k)}
    spouse_in = collections.defaultdict(list)
    for k in fams:
        for c in k:
            if c:
                spouse_in[c].append(k)

    def ip(cid):
        return ptr("I", cid)

    def fp(k):
        return ptr("F", "%s|%s" % (k[0] or "", k[1] or ""))

    out = ["0 HEAD"]
    out += line(1, "SOUR", "DONEGAL-TOWNLANDS") + line(2, "NAME", "Donegal Townlands census GEDCOM")
    out += ["1 GEDC", "2 VERS 5.5.1", "2 FORM LINEAGE-LINKED", "1 CHAR UTF-8", "1 SUBM @U1@"]
    out += note(1, "Derived test file for %s %s. It is built from the 1901, 1911 and 1926 census returns, the census links "
                   "accepted by the researcher, and links accepted from the researcher's own tree. Birth years are derived from the "
                   "age in the earliest return and are not recorded dates. No marriage, death or emigration is stated. "
                   "Regenerate it rather than editing it." % (kind, value))
    if tentative:
        out += note(1, "TENTATIVE LINKS: this file also joins returns by links proposed by a matching program and NOT reviewed or "
                       "accepted by the researcher. Each such person carries a note starting TENTATIVE LINK with the matcher's "
                       "confidence. Use the file to test hints, not as a record of identity.")
    out += ["0 @U1@ SUBM", "1 NAME Donegal Townlands"]
    for y, title in sorted(SOURCES.items()):
        out += ["0 @S%d@ SOUR" % y] + line(1, "TITL", title) + line(1, "AUTH", "National Archives of Ireland")

    n_events = 0
    for cid in sorted(people, key=lambda c: (groups[c][0]["year"], c)):
        members = groups[cid]
        names_ = person_names(members)
        out.append("0 %s INDI" % ip(cid))
        for i, (first, sur) in enumerate(names_):
            out += line(1, "NAME", "%s /%s/" % (first, sur))
            if i:
                out += ["2 TYPE aka"]
        sex = members[0]["sex"]
        if sex in ("M", "F"):
            out += ["1 SEX " + sex]
        anchors_here = sorted({anchors[r["obs"]] for r in members if r["obs"] in anchors})
        for a in anchors_here:
            out += line(1, "REFN", a) + ["2 TYPE Tree person"]
        first_age = next((r for r in members if r["age"] is not None), None)
        if first_age:
            out += ["1 BIRT", "2 DATE ABT %d" % (first_age["year"] - first_age["age"])]
            out += note(2, "Derived from age %d in the %d return. Not a recorded date." % (first_age["age"], first_age["year"]))
        for t in sorted(tent_by_chain.get(cid, []), key=lambda t: (chain_of[t["fo"]], t["fo"], t["to"])):
            ra, rb = [r for r in members if r["obs"] == t["fo"]][0], [r for r in members if r["obs"] == t["to"]][0]
            out += note(1, "TENTATIVE LINK, not accepted by the researcher: %s is the same person as %s. Matcher confidence %s%s."
                           % (ra_label(ra), ra_label(rb), t["confidence"],
                              "; " + ", ".join(t["flags"]) if t.get("flags") else ""))
        for r in members:
            n_events += 1
            out += ["1 CENS", "2 DATE %d" % r["year"]]
            out += line(2, "PLAC", ", ".join([r["townland"], r["ded"], COUNTY]))
            if r["age"] is not None:
                out += ["2 AGE %d" % r["age"]]
            out += note(2, event_note(r))
            out += ["2 SOUR @S%d@" % r["year"]] + line(3, "PAGE", r["obs"])
            if r.get("url"):
                out += note(3, r["url"])
        if cid in child_family and child_family[cid] in fams:
            out += ["1 FAMC " + fp(child_family[cid])]
        for k in sorted(spouse_in.get(cid, []), key=fp):
            out += ["1 FAMS " + fp(k)]
    for k in sorted(fams, key=fp):
        out.append("0 %s FAM" % fp(k))
        if k[0]:
            out += ["1 HUSB " + ip(k[0])]
        if k[1]:
            out += ["1 WIFE " + ip(k[1])]
        for cc in sorted(kids_of.get(k, []), key=lambda c: (groups[c][0]["age"] is None, -(groups[c][0]["year"] - (groups[c][0]["age"] or 0)), c)):
            out += ["1 CHIL " + ip(cc)]
    out.append("0 TRLR")

    counts = {"people": len(people), "families": len(fams), "events": n_events,
              "chains of two or more rows": sum(1 for c in people if len(groups[c]) > 1),
              "households": len(hh_rows), "accepted links used": joined}
    if tentative:
        used_in_scope = [t for cc in people for t in tent_by_chain.get(cc, [])]
        counts["tentative links used"] = len(used_in_scope)
        for conf in cl.RANK:
            counts["tentative %s" % conf] = sum(1 for t in used_in_scope if t["confidence"] == conf)
        by_obs = {r["obs"]: r for r in rows}
        for t in sorted(used_in_scope, key=lambda t: (cl.RANK[t["confidence"]], t["fo"], t["to"])):
            notes.append("tentative link, matcher confidence %s%s: %s is %s" % (
                t["confidence"], " (" + ", ".join(t["flags"]) + ")" if t.get("flags") else "",
                ra_label(by_obs[t["fo"]]), ra_label(by_obs[t["to"]])))
    return "\n".join(out) + "\n", report + notes, counts


def ra_label(r: dict) -> str:
    return "%s %s (age %s, %d, %s)" % (clean_name(r["first"]), clean_name(r["surname"]),
                                       r["age"] if r["age"] is not None else "not given", r["year"], r["townland"])


def person_label(members, with_age=True):
    r = members[0]
    if not with_age:
        return clean_name("%s %s" % (r["first"], r["surname"]))
    return "%s %s (%s, %d)" % (r["first"], r["surname"], r["age"], r["year"])


# ------------------------------------------------------------------ check

def check_gedcom(text: str) -> list[str]:
    """Structure checks on the generated text. An empty list means it is sound."""
    errs, defined, refs = [], {}, []
    prev = 0
    for n, raw in enumerate(text.split("\n"), 1):
        if not raw:
            continue
        m = re.match(r"^(\d+) (@[^@\s]+@ )?([A-Z_]+)(?: (.*))?$", raw)
        if not m:
            errs.append("line %d is not GEDCOM: %r" % (n, raw[:60]))
            continue
        lvl, p, tag, val = int(m.group(1)), (m.group(2) or "").strip(), m.group(3), m.group(4) or ""
        if lvl > prev + 1:
            errs.append("line %d: level jumps from %d to %d" % (n, prev, lvl))
        if len(raw) > 255:
            errs.append("line %d is longer than 255 characters" % n)
        prev = lvl
        if lvl == 0 and p:
            if p in defined:
                errs.append("pointer %s is defined twice" % p)
            defined[p] = tag
        elif re.match(r"^@[^@]+@$", val) and tag in ("HUSB", "WIFE", "CHIL", "FAMC", "FAMS", "SOUR", "SUBM"):
            refs.append((n, tag, val))
    for n, tag, val in refs:
        want = {"HUSB": "INDI", "WIFE": "INDI", "CHIL": "INDI", "FAMC": "FAM", "FAMS": "FAM", "SOUR": "SOUR", "SUBM": "SUBM"}[tag]
        if defined.get(val) != want:
            errs.append("line %d: %s points at %s, which is not a %s" % (n, tag, val, want))
    if not text.rstrip().endswith("0 TRLR"):
        errs.append("the file does not end with TRLR")
    return errs


# ------------------------------------------------------------------ run

def load_accepted_pairs(path: Path = cl.DECISIONS) -> list[tuple[str, str]]:
    return sorted(k for k, d in cl.load_decisions(path).items() if d["status"] == "accepted")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def tentative_links(rows, names, decisions: Path, min_confidence: str = "low"):
    """Links the matcher proposes that Mike has not reviewed, for a test file. Ambiguous links and
    rejected pairs are left out, and nothing here is written to the decisions file. Returns
    (links, number of ambiguous links left out)."""
    cfg = cl.load_config()
    reviewed = cl.load_decisions(decisions) if Path(decisions).is_file() else {}
    by_ded = collections.defaultdict(list)
    for r in rows:
        by_ded[r["ded"]].append(r)
    out, ambiguous = [], 0
    for ded in sorted(by_ded):
        links, _ = cl.propose_ded(by_ded[ded], names, cfg, reviewed)
        for c in links:
            if c.get("decision"):
                continue
            if c.get("ambiguous_with"):
                ambiguous += 1
            elif cl.RANK[c["confidence"]] <= cl.RANK[min_confidence]:
                out.append({"fo": c["a"]["obs"], "to": c["b"]["obs"], "confidence": c["confidence"],
                            "flags": list(c.get("flags") or [])})
    return out, ambiguous


def run(kind: str, value: str, census_dir: Path, out_dir: Path, decisions: Path, tree: Path, wife_parent: str, out=sys.stdout,
        tentative: bool = False, min_confidence: str = "low") -> int:
    rows = cl.load_census(census_dir)
    for r in rows:
        r["url"] = ""
    try:
        from census_review import CENSUS_URLS
        for r in rows:
            if r["ref"]:
                r["url"] = CENSUS_URLS[r["year"]] % r["ref"]
    except ImportError:
        pass
    names = cl.Names(given_names_reference.load(), variants_reference.load())
    pairs = load_accepted_pairs(decisions)
    anchors = load_anchors(tree)
    tent, n_ambiguous = tentative_links(rows, names, decisions, min_confidence) if tentative else ([], 0)
    text, report, counts = build_gedcom(rows, pairs, anchors, kind, value, names, wife_parent, tentative=tent)
    if counts["people"] == 0:
        out.write("No people found for %s %s.\n" % (kind, value))
        return 1
    errs = check_gedcom(text)
    if errs:
        out.write("The generated file failed its own checks:\n" + "\n".join("  " + e for e in errs[:20]) + "\n")
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "%s_%s%s" % (kind, slug(value), "_tentative" if tentative else "")
    (out_dir / (stem + ".ged")).write_text(text, encoding="utf-8")
    lines = ["Census GEDCOM for %s %s%s" % (kind, value, " (TENTATIVE LINKS, a test file)" if tentative else ""),
             "Accepted census links on record: %d. Tree anchors: %d." % (len(pairs), len(anchors))]
    if tentative:
        lines += ["Tentative links are matcher proposals that have not been reviewed. Minimum confidence: %s. Ambiguous proposals "
                  "left out (all returns read): %d." % (min_confidence, n_ambiguous)]
    lines += ["%s: %s" % (k, v) for k, v in counts.items()]
    shown = len(lines)
    lines += ["", "For review (%d):" % len(report)] + ["  " + r for r in report]
    (out_dir / (stem + "_report.txt")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    out.write("\n".join(lines[:shown]) + "\n")
    if report:
        out.write("%d items for review are in %s_report.txt\n" % (len(report), stem))
    if not pairs and not tentative:
        out.write("No census links have been accepted yet, so people appear once per return unless your tree ties them.\n")
    out.write("Written: %s\n" % (out_dir / (stem + ".ged")))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--townland")
    g.add_argument("--family", help="a surname; its verified spellings are included")
    g.add_argument("--ded")
    ap.add_argument("--census-dir", type=Path, default=cl.CENSUS_DIR)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--decisions", type=Path, default=cl.DECISIONS)
    ap.add_argument("--tree", type=Path, default=cl.TREE)
    ap.add_argument("--wife-parent", choices=("evidence", "assume"), default="evidence",
                    help="evidence: a child is attached to the wife only where years married allow it (default). "
                         "assume: attach unless the return contradicts it")
    ap.add_argument("--tentative", action="store_true",
                    help="also join returns by matcher links Mike has not reviewed (ambiguous ones are left out), so the file can be "
                         "tried in Ancestry. Nothing is written to the decisions file, and the output is named *_tentative.ged")
    ap.add_argument("--min-confidence", choices=tuple(cl.RANK), default="low",
                    help="with --tentative, the weakest matcher confidence to use (default low, which means all)")
    a = ap.parse_args(argv)
    kind, value = ("townland", a.townland) if a.townland else ("family", a.family) if a.family else ("ded", a.ded)
    return run(kind, value, a.census_dir, a.out, a.decisions, a.tree, a.wife_parent,
               tentative=a.tentative, min_confidence=a.min_confidence)


if __name__ == "__main__":
    sys.exit(main())
