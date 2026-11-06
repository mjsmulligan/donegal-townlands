#!/usr/bin/env python3
"""Propose and check associations between GEDCOM people and census rows (WP16).

The GEDCOM is a secondary source: it records Mike's research. Census rows are
the primary evidence. This tool reads the census citations on each GEDCOM
person, proposes the census row each one refers to, and audits the tree's
birth years against the census ages. Nothing is accepted by the tool. Accepted
links are rows in data/research/associations/gedcom_census.csv, made by a human.

Usage:
    python tools/gedcom_census.py propose GEDCOM [--census-dir DIR] [--out DIR]
    python tools/gedcom_census.py accept --reviewer NAME --date YYYY-MM-DD [--out DIR]
    python tools/gedcom_census.py check [--gedcom GEDCOM] [--census-dir DIR]

The GEDCOM is read from outside the repository and is never copied into it.
Generated reports go to data/processed/gedcom/, which is not committed.
Original spellings are kept. Normalisation is used only to compare.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import difflib
import glob
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CENSUS_DIR = ROOT / "data" / "source" / "census"
OUT_DIR = ROOT / "data" / "processed" / "gedcom"
DECISIONS = ROOT / "data" / "research" / "associations" / "gedcom_census.csv"
DECISION_FIELDS = [
    "person_ptr", "person_name", "person_birth", "obs_id", "status",
    "reviewer", "date", "method", "proposed_confidence", "note",
]
STATUSES = {"accepted", "rejected"}
OBS_RE = re.compile(r"^census(1901|1911|1926):[a-z]+:\d+$")
THIS_YEAR = datetime.date.today().year
PRIVACY_YEARS = 100  # CLAUDE.md: births 100 or more years old


# ---------------------------------------------------------------- GEDCOM
class Node:
    __slots__ = ("lvl", "tag", "val", "kids", "ptr")

    def __init__(self, lvl, tag, val, ptr=None):
        self.lvl, self.tag, self.val, self.kids, self.ptr = lvl, tag, val, [], ptr


def parse_gedcom(text: str) -> list[Node]:
    roots: list[Node] = []
    stack: list[Node] = []
    for raw in text.split("\n"):
        raw = raw.rstrip("\r")
        m = re.match(r"(\d+) (@[^@]+@ )?(\S+)(?: (.*))?$", raw)
        if not m:
            continue
        lvl, ptr, tag, val = int(m[1]), m[2], m[3], m[4] or ""
        node = Node(lvl, tag, val, ptr.strip() if ptr else None)
        while stack and stack[-1].lvl >= lvl:
            stack.pop()
        if stack:
            stack[-1].kids.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def node_text(n: Node) -> str:
    """Node value with CONC and CONT continuation lines joined."""
    out = n.val
    for k in n.kids:
        if k.tag == "CONC":
            out += k.val
        elif k.tag == "CONT":
            out += " " + k.val
    return html.unescape(out)


def child(n: Node | None, tag: str) -> Node | None:
    if n is None:
        return None
    return next((k for k in n.kids if k.tag == tag), None)


def citations(n: Node, ctx: str = "INDI"):
    """Yield (event tag, PAGE text) for every citation with a PAGE below n."""
    for k in n.kids:
        if k.tag == "SOUR":
            page = child(k, "PAGE")
            if page is not None:
                yield ctx, node_text(page)
        elif k.tag not in ("NOTE", "CONC", "CONT"):
            yield from citations(k, k.tag)


CITE_RE = re.compile(r"\s*(1901|1911|1926) Census\b", re.I)
REL_WORDS = (
    "head of household|head|wife|husband|son|daughter|mother|father|brother|sister|servant|"
    "boarder|visitor|grandson|granddaughter|nephew|niece|lodger"
)


def parse_citation(page: str) -> dict | None:
    """Read year, townland, house, head, relationship, age and schedule file
    from a citation that begins '<year> Census, <townland>...'."""
    m = CITE_RE.match(page)
    if not m:
        return None
    rest = page[m.end():].lstrip(", ")
    segs = [s.strip() for s in re.split(r"[;,]", rest)]
    place = segs[0] if segs else ""
    if re.search(r"\bDED\b", place) and len(segs) > 1:
        place = segs[1]
    house = re.search(r"\bhouse (\d+)", page, re.I)
    head = re.search(r"household of ([^;.]+?)(?:;|\.|$)", page, re.I)
    listed = re.search(rf"\b(?:listed as|;)\s*({REL_WORDS})\b", page, re.I)
    age = re.search(r"\bage[d]? (\d+)", page, re.I)
    form = re.search(r"([\w\-]+_[\w\-]+\.pdf)", page)
    return {
        "year": int(m[1]), "townland": place, "house": house[1] if house else "",
        "head": head[1].strip() if head else "",
        "is_head": bool(re.search(r"head of household", page, re.I)),
        "rel": listed[1].lower() if listed else "",
        "age": int(age[1]) if age else None,
        "form": form[1] if form else "", "text": page,
    }


def load_people(path: Path) -> dict[str, dict]:
    people: dict[str, dict] = {}
    for r in parse_gedcom(Path(path).read_text(encoding="utf-8-sig")):
        if r.tag != "INDI":
            continue
        nm = child(r, "NAME")
        giv = child(nm, "GIVN")
        sur = child(nm, "SURN")
        nick = child(nm, "NICK")
        birt = child(r, "BIRT")
        bdate = child(birt, "DATE")
        bd = bdate.val if bdate else ""
        by = re.search(r"\d{4}", bd)
        cites, seen = [], set()
        for ctx, page in citations(r):
            c = parse_citation(page)
            if c and (c["year"], page) not in seen:
                seen.add((c["year"], page))
                c["event"] = ctx
                cites.append(c)
        people[r.ptr] = {
            "ptr": r.ptr, "given": html.unescape(giv.val) if giv else "",
            "surname": html.unescape(sur.val) if sur else "",
            "nick": nick.val if nick else "", "birth": bd,
            "birth_year": int(by[0]) if by else None, "cites": cites,
        }
        people[r.ptr]["name"] = f"{people[r.ptr]['given']} {people[r.ptr]['surname']}".strip()
    return people


# ---------------------------------------------------------------- census
def _int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _clean(x):
    return "" if x is None or x == "nan" else x


def load_census(directory: Path) -> list[dict]:
    rows, seen = [], set()
    for f in sorted(glob.glob(str(Path(directory) / "*.csv"))):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if "aform_name" in r:
                    row = {
                        "year": 1926, "ded": r["ded"], "townland": r["townland"],
                        "first": r["first_name"], "surname": r["surname"],
                        "age": _int(r["updated_age"]), "house": "", "form": r["aform_name"],
                        "rel": _clean(r["updated_relationship_to_head"]) or _clean(r["relationship_to_head"]),
                        "loc": r["a_id"],
                    }
                else:
                    row = {
                        "year": int(r["census_year"]), "ded": r["ded"],
                        "townland": r.get("townland_clean") or r["townland"],
                        "first": r["firstname"], "surname": r["surname"], "age": _int(r["age"]),
                        "house": str(_int(r["house_number"]) or ""), "form": "",
                        "rel": _clean(r.get("relation_to_head_updated")) or _clean(r["relation_to_head"]),
                        "loc": r["id"],
                    }
                # Observation ID pattern <source>:<scope>:<locator> (DATA_ARCHITECTURE 5.2)
                row["obs"] = f"census{row['year']}:{row['ded'].lower()}:{row['loc']}"
                if row["obs"] not in seen:
                    seen.add(row["obs"])
                    rows.append(row)
    return rows


# ---------------------------------------------------------------- comparison
# Working groups of spellings seen in the sources. Used to compare only.
PLACE_GROUPS = [
    {"collinboy", "cullionboy"}, {"townagh", "tawnagh"},
    {"mullinalamphry", "mullanalamphry", "mullinalamphery", "mullinalamphrey"},
    {"druminin", "druminnin"}, {"clarlougheask", "clarlougheske"},
    {"spearstown", "spierstown"},
]
NICK = [
    {"patrick", "pat", "packie", "paddy", "patk"}, {"mary", "minnie", "polly", "maria"},
    {"margaret", "maggie", "peggy", "meg", "marget"},
    {"catherine", "kate", "katie", "cassie", "kitty", "cathrine", "catharine"},
    {"bridget", "bridie", "biddy", "bridgit"}, {"john", "johnny", "jack", "jno"},
    {"michael", "mick", "micheal"}, {"james", "jim", "jas"},
    {"elizabeth", "eliza", "lizzie", "betty", "bessie"}, {"ann", "anne", "annie", "nancy", "anna"},
    {"daniel", "dan"}, {"thomas", "tom"}, {"william", "bill", "willie"},
    {"rose", "rosie", "rosanna", "rosey"}, {"sarah", "sally", "sadie"},
    {"charles", "charlie"}, {"edward", "ned", "eddie"}, {"hugh", "hughie"},
    {"neil", "neal", "niall"}, {"isabella", "isabel", "bella", "belle", "isabelle"},
    {"eugene", "owen", "eoghan"},
]
SURNAME_GROUPS = [
    {"mckenna", "mcanaw", "mcnaw", "mcnan", "mcana", "mcanna", "mcannaw"}, {"mcelhar", "carr"},
    {"mcgobrack", "mcgoldrick"}, {"dunleny", "dunlevy", "dunleavy"}, {"coyce", "joyce"},
    {"gallaghan", "callaghan"},
]


def place_key(s: str) -> str:
    k = re.sub(r"[^a-z ]", "", s.lower().replace(" or ", " ")).strip()
    for g in PLACE_GROUPS:
        if k in g:
            return sorted(g)[0]
    return k


def _surn(s: str) -> str:
    s = re.sub(r"[^a-z]", "", s.lower())
    return re.sub(r"^(mac|mc|m)(?=[a-z]{3})", "mc", s)


def surname_rel(a: str, b: str) -> str:
    if not a or not b:
        return ""
    if a.lower() == b.lower():
        return "exact"
    na, nb = _surn(a), _surn(b)
    if any(na in g and nb in g for g in SURNAME_GROUPS):
        return "variant"
    if na == nb or difflib.SequenceMatcher(None, na, nb).ratio() >= 0.84:
        return "variant"
    return ""


def given_rel(given: str, nick: str, row_first: str) -> str:
    rf = re.sub(r"[^a-z ]", "", row_first.lower()).split()
    cand = [re.sub(r"[^a-z]", "", w.lower()) for w in f"{given} {nick}".split() if w]
    if not rf or not cand:
        return ""
    r0 = rf[0]
    if r0 in cand:
        return "exact"
    if any(any(c in g and r0 in g for g in NICK) for c in cand):
        return "nickname"
    if any(difflib.SequenceMatcher(None, c, r0).ratio() >= 0.8 for c in cand):
        return "variant"
    return ""


def relation_ok(cite_rel: str, row_rel: str) -> bool:
    if not cite_rel or not row_rel:
        return False
    a, b = cite_rel.lower(), row_rel.lower()
    if a in ("head", "head of household"):
        return b in ("head", "head of family")
    return b.startswith(a) or a in b


# ---------------------------------------------------------------- matching
class Matcher:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.by_place = collections.defaultdict(list)
        self.by_form = collections.defaultdict(list)
        for r in rows:
            self.by_place[(r["year"], place_key(r["townland"]))].append(r)
            if r["form"]:
                self.by_form[r["form"].lower()].append(r)
        self.places = {place_key(r["townland"]) for r in rows}

    def match(self, p: dict, c: dict):
        """Return (best candidates, note, via). A note of 'tie' means several
        rows scored equally; other notes explain why nothing matched."""
        place = place_key(c["townland"])
        via = "townland"
        if c["form"] and c["form"].lower() in self.by_form:
            pool, via = self.by_form[c["form"].lower()], "schedule id"
        else:
            pool = self.by_place.get((c["year"], place), [])
        if not pool:
            return [], "place_not_loaded" if place not in self.places else "no_rows_that_year", via
        head_surn = c["head"].split()[-1] if c["head"] else ""
        scored = []
        for r in pool:
            g = given_rel(p["given"], p["nick"], r["first"])
            if not g:
                continue
            s_own = surname_rel(p["surname"], r["surname"])
            s_head = surname_rel(head_surn, r["surname"]) if head_surn else ""
            surname_free = not (s_own or s_head)
            sc = {"exact": 3, "nickname": 2, "variant": 1}[g]
            sc += 2 if s_own == "exact" else 1 if s_own else 0
            sc += 1 if (s_head and not s_own) else 0
            d, age_note = None, ""
            if r["age"] is not None:
                if c["age"] is not None:
                    d = abs(r["age"] - c["age"])
                    age_note = f"age {r['age']} vs cited {c['age']}"
                elif p["birth_year"]:
                    implied = c["year"] - p["birth_year"]
                    d = abs(implied - r["age"])
                    age_note = f"age {r['age']} vs birth-year implied {implied}"
                if d is not None:
                    sc += 3 if d <= 1 else 2 if d <= 3 else 1 if d <= 6 else -2
            house_match = bool(c["house"] and r["house"] and c["house"] == r["house"])
            if c["house"] and r["house"] and not house_match:
                sc -= 2
            sc += 2 if house_match else 0
            if relation_ok(c["rel"] or ("head" if c["is_head"] else ""), r["rel"]):
                sc += 1
            strong = house_match or via == "schedule id"
            if surname_free:
                # married name or surname variant: only with a tight locator and age
                ok_name = (g in ("exact", "nickname") and d is not None and d <= 3) or (
                    g == "variant" and d is not None and d <= 2 and strong)
                if not (ok_name and (strong or (c["year"] == 1926 and d <= 2))):
                    continue
            surname_how = ("none (married name or variant, review)" if surname_free
                           else (s_own or f"head-surname:{s_head}"))
            scored.append((sc, r, g, surname_how, age_note, strong))
        if not scored:
            return [], "no_name_match_in_pool", via
        scored.sort(key=lambda x: -x[0])
        best = [x for x in scored if x[0] == scored[0][0]]
        return best, "tie" if len(best) > 1 else "", via


def confidence(sc: int, strong: bool, given: str, surname_how: str, tie: bool) -> str:
    if tie:
        return "low"
    if surname_how.startswith("none"):
        return "medium" if strong else "low"
    if sc >= 9 and strong and given == "exact":
        return "high"
    return "medium" if sc >= 7 else "low"


def person_birth_floor(p: dict, links: list[dict]) -> int | None:
    """Latest plausible birth year: the tree year, else the census-implied year."""
    if p["birth_year"]:
        return p["birth_year"]
    implied = [l["cite_year"] - l["row_age"] for l in links if l["row_age"] != ""]
    return max(implied) if implied else None


def propose(people: dict, rows: list[dict]):
    m = Matcher(rows)
    assoc, pending, unresolved = [], [], []
    for p in people.values():
        for c in p["cites"]:
            best, note, via = m.match(p, c)
            base = {
                "person_ptr": p["ptr"], "person_name": p["name"], "person_birth": p["birth"],
                "cite_year": c["year"], "cite_townland": c["townland"], "cite_house": c["house"],
                "cite_head": c["head"], "cite_rel": c["rel"],
                "cite_age": c["age"] if c["age"] is not None else "", "cite_form": c["form"],
                "cite_text": c["text"],
            }
            if not best:
                (pending if note == "place_not_loaded" else unresolved).append({**base, "reason": note})
                continue
            for sc, r, g, how, age_note, strong in best:
                assoc.append({
                    **base, "obs_id": r["obs"], "row_ded": r["ded"], "row_townland": r["townland"],
                    "row_house": r["house"], "row_first": r["first"], "row_surname": r["surname"],
                    "row_age": r["age"] if r["age"] is not None else "", "row_relation": r["rel"],
                    "method": f"{via}; given {g}; surname {how}", "score": sc,
                    "confidence": confidence(sc, strong, g, how, note == "tie"),
                    "note": "; ".join(x for x in [age_note, "TIE: several rows score equally" if note == "tie" else ""] if x),
                    "n_citations": 1,
                })
    # one link per person and row; keep every citation text
    merged: dict[tuple, dict] = {}
    for a in assoc:
        k = (a["person_ptr"], a["obs_id"])
        if k in merged:
            merged[k]["cite_text"] += "  ||  " + a["cite_text"]
            merged[k]["n_citations"] += 1
        else:
            merged[k] = a
    assoc = list(merged.values())
    resolved = {(a["person_ptr"], a["cite_year"]) for a in assoc}
    pending = [u for u in pending if (u["person_ptr"], u["cite_year"]) not in resolved]
    unresolved = [u for u in unresolved if (u["person_ptr"], u["cite_year"]) not in resolved]
    return assoc, pending, unresolved


def privacy_filter(people: dict, assoc: list[dict], this_year: int = THIS_YEAR):
    """Drop links for anyone born within the last 100 years (CLAUDE.md, 100/75/50).
    Returns (kept, number of people withheld)."""
    by_person = collections.defaultdict(list)
    for a in assoc:
        by_person[a["person_ptr"]].append(a)
    kept, withheld = [], 0
    for ptr, links in by_person.items():
        floor = person_birth_floor(people[ptr], links)
        if floor is None or this_year - floor < PRIVACY_YEARS:
            withheld += 1
            continue
        kept.extend(links)
    return kept, withheld


# ---------------------------------------------------------------- audit
def audit(people: dict, assoc: list[dict]) -> list[dict]:
    """Compare tree birth years with census-implied birth years.

    Births before 1864 were not registered, so census ages are self-estimates and
    drift is expected: recorded as 'expected drift' for information. A conflict
    needs review: a person with an exact birth date from 1864 or later whose census
    ages disagree by more than 3 years, or any tree year more than 10 years from
    every census-implied year."""
    per = collections.defaultdict(list)
    for a in assoc:
        if a["row_age"] != "":
            per[a["person_ptr"]].append((a["cite_year"], int(a["row_age"])))
    out = []
    for ptr, L in per.items():
        p = people[ptr]
        implied = [y - age for y, age in L]
        mean = sum(implied) / len(implied)
        spread = max(implied) - min(implied)
        ty = p["birth_year"]
        reasons, tier = [], ""
        # a registered birth has an exact day; ABT, BEF and the like are estimates
        exact = bool(re.fullmatch(r"\d{1,2} [A-Za-z]{3,9} \d{4}", p["birth"].strip()))
        if ty and ty >= 1864 and exact:
            if spread > 3:
                reasons.append(f"census-implied births spread {min(implied)} to {max(implied)}")
            if abs(ty - mean) > 3:
                reasons.append(f"tree birth {p['birth']} vs census-implied mean {mean:.0f}")
            tier = "conflict" if reasons else ""
        else:
            if ty and all(abs(ty - i) > 10 for i in implied):
                reasons.append(f"tree birth {p['birth']} is more than 10 years from every census-implied year")
                tier = "conflict"
            elif spread > 10:
                reasons.append(f"census-implied births spread {min(implied)} to {max(implied)}")
                tier = "expected drift"
        if tier:
            out.append({"person_ptr": ptr, "person_name": p["name"], "person_birth": p["birth"],
                        "tier": tier, "reason": "; ".join(reasons),
                        "census_ages": "; ".join(f"{y}: {a}" for y, a in sorted(L))})
    return sorted(out, key=lambda r: (r["tier"], r["person_name"]))


# ---------------------------------------------------------------- decisions
def read_decisions(path: Path = DECISIONS) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def check_decisions(path: Path = DECISIONS, people: dict | None = None, rows: list[dict] | None = None) -> list[str]:
    """Static checks on the decisions file; with people and rows, also verify that
    each person ID still names the same person and each observation exists."""
    errors: list[str] = []
    if not Path(path).exists():
        return errors
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != DECISION_FIELDS:
            return [f"{Path(path).name}: header must be {','.join(DECISION_FIELDS)}"]
        recs = list(reader)
    seen = set()
    known = {r["obs"] for r in rows} if rows is not None else None
    for i, r in enumerate(recs, start=2):
        where = f"{Path(path).name} line {i}"
        key = (r["person_ptr"], r["obs_id"])
        if key in seen:
            errors.append(f"{where}: duplicate decision for {key}")
        seen.add(key)
        if r["status"] not in STATUSES:
            errors.append(f"{where}: status must be accepted or rejected")
        if not r["reviewer"].strip():
            errors.append(f"{where}: reviewer is required")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
            errors.append(f"{where}: date must be YYYY-MM-DD")
        if not OBS_RE.match(r["obs_id"]):
            errors.append(f"{where}: bad observation ID {r['obs_id']}")
        if known is not None and r["obs_id"] not in known:
            errors.append(f"{where}: observation {r['obs_id']} not in the census files")
        if people is not None:
            p = people.get(r["person_ptr"])
            if p is None:
                errors.append(f"{where}: person {r['person_ptr']} not in the GEDCOM")
            elif p["name"] != r["person_name"] or p["birth"] != r["person_birth"]:
                errors.append(f"{where}: {r['person_ptr']} is now {p['name']!r} born {p['birth']!r}, "
                              f"decision was for {r['person_name']!r} born {r['person_birth']!r}")
    return errors


# ---------------------------------------------------------------- output
def write_csv(path: Path, recs: list[dict], fields: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = fields or (list(recs[0].keys()) if recs else [])
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, keys, extrasaction="ignore")
        if keys:
            w.writeheader()
        w.writerows(recs)


def household_key(r: dict):
    return (r["year"], r["ded"], r["form"]) if r["form"] else (r["year"], r["ded"], place_key(r["townland"]), r["house"])


def run_propose(gedcom: Path, census_dir: Path, out: Path) -> dict:
    people = load_people(gedcom)
    rows = load_census(census_dir)
    assoc, pending, unresolved = propose(people, rows)
    assoc, withheld = privacy_filter(people, assoc)
    decided = {(d["person_ptr"], d["obs_id"]) for d in read_decisions()}
    review = [a for a in assoc if (a["person_ptr"], a["obs_id"]) not in decided]
    by_obs = {r["obs"]: r for r in rows}
    linked = {a["obs_id"] for a in assoc}
    touched = {household_key(by_obs[o]) for o in linked}
    members = [r for r in rows if household_key(r) in touched and r["obs"] not in linked]
    aud = audit(people, assoc)
    write_csv(out / "proposed_associations.csv", assoc)
    write_csv(out / "review.csv", review, list(assoc[0].keys()) if assoc else [])
    write_csv(out / "pending_place_not_loaded.csv", pending)
    write_csv(out / "unresolved_in_loaded_data.csv", unresolved)
    write_csv(out / "audit.csv", aud)
    write_csv(out / "household_members_not_in_gedcom.csv", [
        {"obs_id": r["obs"], "year": r["year"], "ded": r["ded"], "townland": r["townland"],
         "house": r["house"], "form": r["form"], "first": r["first"], "surname": r["surname"],
         "age": r["age"], "relation": r["rel"]} for r in members])
    return {"people": len(people), "with_citations": sum(1 for p in people.values() if p["cites"]),
            "citations": sum(len(p["cites"]) for p in people.values()), "census_rows": len(rows),
            "links": len(assoc), "by_confidence": dict(collections.Counter(a["confidence"] for a in assoc)),
            "pending": len(pending), "unresolved": len(unresolved), "withheld_people": withheld,
            "to_review": len(review), "audit": dict(collections.Counter(a["tier"] for a in aud)),
            "members_not_in_gedcom": len(members), "households": len(touched)}


def run_accept(reviewer: str, date: str, out: Path) -> int:
    path = out / "review.csv"
    if not path.exists():
        print("run propose first")
        return 1
    with open(path, encoding="utf-8", newline="") as fh:
        review = list(csv.DictReader(fh))
    existing = read_decisions()
    new = [{
        "person_ptr": a["person_ptr"], "person_name": a["person_name"], "person_birth": a["person_birth"],
        "obs_id": a["obs_id"], "status": "accepted", "reviewer": reviewer, "date": date,
        "method": a["method"], "proposed_confidence": a["confidence"], "note": a["note"],
    } for a in review]
    # append only: existing decisions are never rewritten
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    fresh = not DECISIONS.exists()
    with open(DECISIONS, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, DECISION_FIELDS)
        if fresh:
            w.writeheader()
        w.writerows(new)
    print(f"accepted {len(new)} links as {reviewer} on {date}; {len(existing)} earlier decisions kept")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("propose")
    p1.add_argument("gedcom", type=Path)
    p1.add_argument("--census-dir", type=Path, default=CENSUS_DIR)
    p1.add_argument("--out", type=Path, default=OUT_DIR)
    p2 = sub.add_parser("accept")
    p2.add_argument("--reviewer", required=True)
    p2.add_argument("--date", required=True)
    p2.add_argument("--out", type=Path, default=OUT_DIR)
    p3 = sub.add_parser("check")
    p3.add_argument("--gedcom", type=Path)
    p3.add_argument("--census-dir", type=Path, default=CENSUS_DIR)
    a = ap.parse_args(argv)
    if a.cmd == "propose":
        s = run_propose(a.gedcom, a.census_dir, a.out)
        for k, v in s.items():
            print(f"{k}: {v}")
        return 0
    if a.cmd == "accept":
        return run_accept(a.reviewer, a.date, a.out)
    people = load_people(a.gedcom) if a.gedcom else None
    rows = load_census(a.census_dir) if a.gedcom else None
    errs = check_decisions(DECISIONS, people, rows)
    print("\n".join(errs) or "gedcom_census check: ok")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
