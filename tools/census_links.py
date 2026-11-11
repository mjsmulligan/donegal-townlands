#!/usr/bin/env python3
"""Propose links between one person's rows in consecutive census returns (WP18).

A census row is an observation. This tool proposes that a row in one return and a row in
the next are the same person, with a method and a confidence, so that Mike can review the
proposals. It decides nothing: every link is a proposal until Mike accepts it (WP19), and
no inference is drawn from absence. See docs/CENSUS_GEDCOM_SPEC.md.

Usage:
    python tools/census_links.py propose [--census-dir DIR] [--ded NAME] [--townland NAME]
                                         [--surname NAME] [--out DIR] [--config FILE]
    python tools/census_links.py check   [--census-dir DIR] [--decisions FILE] [--config FILE]
    python tools/census_links.py accept  FILE|- [--reviewer NAME] [--date YYYY-MM-DD] [--dry-run]

`propose` writes one review CSV per DED to data/processed/census_links/ (not committed).
`accept` records the decisions Mike copied from the review page (or an edited review CSV) in
data/research/associations/census_links.csv (WP19). Only accepted and rejected rows are kept.
Later runs of `propose` keep accepted links, never propose a rejected pair again, and do not
let an accepted row compete for another link.
`check` runs the matcher against the links Mike accepted between the tree and the census
(data/research/associations/gedcom_census.csv) and reports how many it recovers and at what
confidence, and whether any known link is replaced by a wrong one.

Matching is within one DED. Surnames match only when identical or in a verified family in
data/reference/surname_variants.csv. A given name variant counts as verified, or as a lead
only, according to data/reference/given_name_variants.csv (verified rows only, unless --include-proposed-given-names, and
then a link is capped at medium). Thresholds are in
data/reference/census_link_config.json. Original spellings are kept. Normalisation is used
only to compare.
"""
from __future__ import annotations

import argparse
import ast
import collections
import csv
import datetime
import json
import re
import sys
from pathlib import Path

import tree_census_links  # place_key only, as the base of townland_key
import given_names_reference
import variants_reference

ROOT = Path(__file__).resolve().parent.parent
CENSUS_DIR = ROOT / "data" / "source" / "census"
OUT_DIR = ROOT / "data" / "processed" / "census_links"
CONFIG = ROOT / "data" / "reference" / "census_link_config.json"
GIVEN = ROOT / "data" / "reference" / "given_name_variants.csv"
TREE = ROOT / "data" / "research" / "associations" / "gedcom_census.csv"
DECISIONS = ROOT / "data" / "research" / "associations" / "census_links.csv"
DECISION_FIELDS = ["from_obs", "to_obs", "status", "reviewer", "date", "confidence", "from_name", "to_name", "note"]
STATUSES = {"accepted", "rejected"}
SUCCESSIVE = [(1901, 1911), (1911, 1926)]
SKIP = (1901, 1926)
RANK = {"high": 0, "medium": 1, "low": 2}
# A trailing word that makes a townland a different place from the bare name or from its sister
# townlands (Keadew Upper and Keadew Lower are two places). It is never folded away or swapped.
PLACE_SUFFIXES = {"upper", "lower", "middle", "east", "west", "north", "south", "beg", "more", "mor",
                  "big", "little", "inner", "outer"}

DEFAULTS = {
    "age_tolerance": 3, "age_tolerance_wide": 6, "wide_age_before_birth_year": 1864, "margin": 2,
    "married_name_max_candidates": 3, "married_name_extra_years": 1,
    "old_age_from": 60, "age_drift_max_old": 12, "place_variants": [],
    "household_min_supporters": 2, "household_support_min_confidence": "medium",
    "weights": {
        "given_exact": 3, "given_verified": 2, "given_proposed": 1, "surname_exact": 2,
        "surname_variant": 1, "age_drift_0_1": 3, "age_drift_2_3": 2, "age_drift_wide": 1,
        "household_support_each": 1, "household_support_max": 3, "household_conflict_each": -1,
        "household_conflict_max": 2, "same_townland": 1,
        "same_house": 1, "implausible_relation": -3, "marital_regress": -3, "surname_change": -2,
    },
}

FIELDS = [
    "status", "confidence", "group", "from_obs", "from_name", "from_age", "from_relation",
    "from_townland", "to_obs", "to_name", "to_age", "to_relation", "to_townland", "years",
    "method", "flags", "ambiguous_with", "chain", "reviewer", "date", "note",
]


# ------------------------------------------------------------------ configuration

def load_config(path: Path = CONFIG) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    if Path(path).is_file():
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        for k, v in user.items():
            if k == "weights":
                cfg["weights"].update(v)
            elif not k.startswith("_"):
                cfg[k] = v
    return cfg


# ------------------------------------------------------------------ townland identity

_VARIANTS: dict = {}


def _variant_map(path: Path = CONFIG) -> dict:
    """Spelling to canonical base spelling, from "place_variants" in the config (groups Mike verified)."""
    key = str(path)
    if key not in _VARIANTS:
        out = {}
        for group in load_config(path).get("place_variants", []):
            ks = sorted(re.sub(r"[^a-z ]", "", g.lower()).strip() for g in group)
            for k in ks:
                out[k] = ks[0]
        _VARIANTS[key] = out
    return _VARIANTS[key]


def townland_key(name: str) -> str:
    """The key townlands are compared by. It comes from the original `townland` value, lower case and
    without punctuation. Verified spelling variants of the base name are treated as one (Keadew and
    Keadue). A suffix word (Upper, Lower, Middle, East, West and so on) is kept as it is and is never
    folded away, so Keadew Upper, Keadew Lower and a bare Keadew stay three different places."""
    k = re.sub(r"[^a-z ]", "", (name or "").lower().replace(" or ", " ")).strip()
    parts = k.split()
    suffix = ""
    if len(parts) > 1 and parts[-1] in PLACE_SUFFIXES:
        suffix = parts[-1]
        k = " ".join(parts[:-1])
    base = tree_census_links.place_key(k)
    base = _variant_map().get(base, base)
    return (base + " " + suffix).strip()


# ------------------------------------------------------------------ census rows

def _int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _clean(x) -> str:
    x = "" if x is None else str(x).strip()
    return "" if x.lower() in ("nan", "none") else x


def marital_class(s: str) -> str:
    s = _clean(s).lower()
    if "widow" in s:
        return "widowed"
    if "not married" in s or "single" in s:
        return "single"
    if "married" in s:
        return "married"
    return ""


def rel_class(s: str) -> str:
    s = re.sub(r"[^a-z ]", "", _clean(s).lower())
    if "in law" in s:
        return "inlaw"
    for word, cls in (("grand son", "grandson"), ("grandson", "grandson"), ("grand daughter", "granddaughter"),
                      ("granddaughter", "granddaughter"), ("head", "head"), ("wife", "wife"),
                      ("husband", "husband"), ("son", "son"), ("daughter", "daughter"),
                      ("mother", "mother"), ("father", "father"), ("sister", "sister"),
                      ("brother", "brother"), ("servant", "servant"), ("boarder", "boarder"),
                      ("visitor", "visitor"), ("nephew", "nephew"), ("niece", "niece")):
        if word in s:
            return cls
    return "other"


def _first_image(images) -> str:
    try:
        return ast.literal_eval(images or "[]")[0]["id"]
    except (ValueError, SyntaxError, IndexError, KeyError, TypeError):
        return ""


def load_census(directory: Path) -> list[dict]:
    """Census rows for 1901, 1911 and 1926. Observation IDs follow DATA_ARCHITECTURE 5.2 and are
    identical to the IDs used by tools/tree_census_links.py."""
    rows, seen = [], set()
    for f in sorted(Path(directory).glob("*.csv")):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if "aform_name" in r:
                    row = {
                        "year": 1926, "ded": r["ded"], "townland": r["townland"],
                        "first": r["first_name"], "surname": r["surname"], "age": _int(r["updated_age"]),
                        "sex": _clean(r["updated_sex"]).upper()[:1], "house": "", "form": r["aform_name"],
                        "rel": _clean(r["updated_relationship_to_head"]) or _clean(r["relationship_to_head"]),
                        "marital": marital_class(r["updated_marriage"]), "marr_years": _int(r["years_married"]),
                        "born": _int(r["children_born_alive"]), "loc": r["a_id"],
                        "marital_raw": _clean(r["updated_marriage"]), "occ": "",
                        "birth": _clean(r["birthplace_county"]), "ref": r["aform_name"],
                    }
                else:
                    row = {
                        "year": int(r["census_year"]), "ded": r["ded"],
                        # The original value only. The curated townland_clean (absent from NAI's files) folded
                        # Keadew Lower into Keadew Upper, so it is never used for matching or for places.
                        "townland": r["townland"],
                        "first": r["firstname"], "surname": r["surname"], "age": _int(r["age"]),
                        "sex": _clean(r["sex"]).upper()[:1], "house": str(_int(r["house_number"]) or ""),
                        "form": "", "rel": _clean(r.get("relation_to_head_updated")) or _clean(r["relation_to_head"]),
                        "marital": marital_class(r["marriage_status"]), "marr_years": _int(r["marriage_years"]),
                        "born": _int(r["children_born"]), "loc": r["id"],
                        "marital_raw": _clean(r["marriage_status"]),
                        "occ": _clean(r.get("occupation_updated")) or _clean(r.get("occupation")),
                        "birth": _clean(r.get("birthplace")), "ref": _first_image(r.get("images")),
                    }
                row["obs"] = f"census{row['year']}:{row['ded'].lower()}:{row['loc']}"
                if row["obs"] in seen:
                    continue
                seen.add(row["obs"])
                row["tkey"] = townland_key(row["townland"])
                row["relc"] = rel_class(row["rel"])
                row["hh"] = ((row["year"], "form", row["form"]) if row["year"] == 1926 else
                             (row["year"], row["tkey"], row["house"] or "row" + row["loc"]))
                rows.append(row)
    return rows


# ------------------------------------------------------------------ name comparison

def first_key(first: str) -> str:
    parts = re.sub(r"[^a-z ]", "", (first or "").lower()).split()
    return parts[0] if parts else ""


class Names:
    """Given names from the reference file and surnames from the verified surname families."""

    def __init__(self, given_rows=None, surname_rows=None, include_proposed=False):
        self.surname_family = {}
        self.given_map, self.given_proposed = given_names_reference.groups(include_proposed, given_rows or [])
        self.family_keys = collections.defaultdict(set)
        for k, fam in self.given_map.items():
            self.family_keys[fam].add(k)
        for r in (surname_rows or []):
            if r["status"] == "verified":
                for sp in r["spellings"]:
                    self.surname_family[variants_reference.key(sp)] = r["family_id"]

    def given(self, a: str, b: str) -> str:
        ka, kb = first_key(a), first_key(b)
        if not ka or not kb:
            return ""
        if ka == kb:
            return "exact"
        fa = self.given_map.get(ka)
        if fa and fa == self.given_map.get(kb):
            return "proposed" if fa in self.given_proposed else "verified"
        return ""

    def given_keys(self, first: str) -> set:
        """The first name key and every name in its family, for looking up candidates."""
        k = first_key(first)
        fam = self.given_map.get(k)
        return {k} | (self.family_keys[fam] if fam else set())

    def surname_canon(self, s: str) -> str:
        k = variants_reference.key(s)
        fam = self.surname_family.get(k)
        return "family:" + fam if fam else k

    def surname(self, a: str, b: str) -> str:
        ka, kb = variants_reference.key(a), variants_reference.key(b)
        if not ka or not kb:
            return ""
        if ka == kb:
            return "exact"
        return "variant" if self.surname_canon(a) == self.surname_canon(b) and self.surname_canon(a).startswith("family:") else ""


def implausible_relation(a: str, b: str) -> bool:
    if a in ("wife", "mother") and b in ("daughter", "sister", "granddaughter"):
        return True
    if a in ("head", "father", "husband") and b in ("son", "daughter", "grandson", "granddaughter"):
        return True
    if a in ("son", "daughter", "grandson", "granddaughter") and b in ("father", "mother"):
        return True
    return False


# ------------------------------------------------------------------ matching

def _tolerance(a: dict, cfg: dict) -> int:
    birth = a["year"] - a["age"]
    return cfg["age_tolerance_wide"] if birth < cfg["wide_age_before_birth_year"] else cfg["age_tolerance"]


def candidates(rows_a, rows_b, names: Names, cfg: dict, skip: bool = False):
    """Candidate pairs between two returns of one DED, and a count of rows left out for want of
    an age or because a woman had too many married name candidates."""
    ya, yb = rows_a[0]["year"], rows_b[0]["year"]
    gap = yb - ya
    by_surname = collections.defaultdict(list)
    married_f = collections.defaultdict(list)
    for b in rows_b:
        if b["age"] is None or not b["sex"]:
            continue
        by_surname[(b["sex"], names.surname_canon(b["surname"]))].append(b)
        if b["sex"] == "F" and b["marital"] in ("married", "widowed"):
            married_f[first_key(b["first"])].append(b)
    out, skipped = [], collections.Counter()
    for a in rows_a:
        if a["age"] is None or not a["sex"]:
            skipped["no age or sex"] += 1
            continue
        tol = _tolerance(a, cfg)
        found = []
        for b in by_surname.get((a["sex"], names.surname_canon(a["surname"])), []):
            c = _pair(a, b, gap, tol, names, cfg, skip, change=False)
            if c:
                found.append(c)
        if a["sex"] == "F" and a["marital"] == "single":
            married = []
            for key in sorted(names.given_keys(a["first"])):
                for b in married_f.get(key, []):
                    if names.surname_canon(b["surname"]) == names.surname_canon(a["surname"]):
                        continue
                    c = _pair(a, b, gap, tol, names, cfg, skip, change=True)
                    if c:
                        married.append(c)
            if len(married) > cfg["married_name_max_candidates"]:
                skipped["married name: too many candidates"] += 1
            else:
                found += married
        out += found
    return out, skipped


def _pair(a, b, gap, tol, names, cfg, skip, change):
    given = names.given(a["first"], b["first"])
    if not given:
        return None
    drift = abs((b["age"] - a["age"]) - gap)
    # Ages of older people drift upwards (the old age pension began in 1909), so a later age of 60 or
    # more that is higher than expected is allowed a larger drift. Beyond the normal limit it grades low.
    older = b["age"] >= cfg["old_age_from"] and (b["age"] - a["age"]) - gap > 0
    if drift > (max(tol, cfg["age_drift_max_old"]) if older else tol):
        return None
    if change:
        years = b["marr_years"]
        if years is not None and years > gap + cfg["married_name_extra_years"]:
            return None
        surname = "change"
    else:
        surname = names.surname(a["surname"], b["surname"])
        if not surname:
            return None
    regress = a["marital"] in ("married", "widowed") and b["marital"] == "single"
    fell = a["born"] is not None and b["born"] is not None and b["born"] < a["born"]
    return {
        "a": a, "b": b, "given": given, "surname": surname, "drift": drift, "limit": tol, "tol": cfg["age_tolerance"],
        "same_townland": a["tkey"] == b["tkey"],
        "same_house": bool(a["year"] != 1926 and b["year"] != 1926 and a["tkey"] == b["tkey"]
                           and a["house"] and a["house"] == b["house"]),
        "implausible": implausible_relation(a["relc"], b["relc"]), "regress": regress,
        "children_fell": fell, "skip": skip, "support": 0, "supporters": [], "conflicts": [],
    }


PARENT_ROLES = ("head", "wife", "husband")


def _member_text(c: dict) -> str:
    return "%s %s to %s" % (_name(c["a"]), c["a"]["age"], c["b"]["age"])


def add_support(cands, hh_size, cfg):
    """Household continuity as corroboration (WP18, 2026-11-11).

    Individual links come first. A link can support the others in its household pair only when it is
    sound on its own evidence: not a surname change, no relationship or marital contradiction, and at
    least `household_support_min_confidence` before any household term is added (so no severe flag and
    at most one weak one). A link with an odd relationship can receive support but never gives it. A household pair counts as continuing only when `household_min_supporters`
    or more distinct members agree on it, and one later person cannot corroborate two earlier ones.
    Weak links therefore never prop each other up. Support is worked out from the individual evidence
    alone, so it cannot feed back on itself. A link that is ambiguous against rivals in other
    households can still count, because a household is exactly what separates cousins with the same
    names, but then its rivals in the same pair of households gain nothing from it.

    Members who left, arrived, married or died are simply not counted. Only contradictions count against
    a link (the two rules below) and they are recorded for the review rationale."""
    margin, need_n = cfg["margin"], cfg["household_min_supporters"]
    min_rank = RANK[cfg["household_support_min_confidence"]]
    for c in cands:
        c["support"], c["supporters"], c["conflicts"] = 0, [], []
        c["score"] = score(c, cfg)          # the person's own evidence only
    by_a, by_b = collections.defaultdict(list), collections.defaultdict(list)
    for c in cands:
        by_a[c["a"]["obs"]].append(c)
        by_b[c["b"]["obs"]].append(c)
    pair = lambda c: (c["a"]["hh"], c["b"]["hh"])  # noqa: E731
    sound = collections.defaultdict(list)
    risky = collections.defaultdict(list)
    for c in cands:
        if c["surname"] == "change":
            continue
        if c["implausible"] or c["regress"]:
            # Only a risky link that is that person's best candidate says anything about the household.
            if _lead(c, by_a[c["a"]["obs"]]) > 0 and _lead(c, by_b[c["b"]["obs"]]) > 0:
                risky[pair(c)].append(c)
        elif RANK[grade(c, household=False)[0]] <= min_rank:
            sound[pair(c)].append(c)

    def agreeing(p, skip_a=None, skip_b=None):
        """The distinct earlier members of pair p with a sound link, one link each (the strongest), and
        no later person used twice. Returns the list of links."""
        used_b, out = set(), []
        for c in sorted(sound.get(p, []), key=lambda c: (-c["score"], c["a"]["obs"], c["b"]["obs"])):
            if c["a"]["obs"] in (skip_a, ) or c["b"]["obs"] in (skip_b, ):
                continue
            if c["b"]["obs"] in used_b or any(o["a"]["obs"] == c["a"]["obs"] for o in out):
                continue
            used_b.add(c["b"]["obs"])
            out.append(c)
        return out

    continuing = {p for p in sound if len(agreeing(p)) >= need_n}
    for c in cands:
        c["hh_sizes"] = (hh_size[c["a"]["hh"]], hh_size[c["b"]["hh"]])
        if c["surname"] == "change":
            continue
        p = pair(c)
        coherent = not (c["implausible"] or c["regress"])
        if p in continuing:
            # A link with an odd relationship (a head who is a son in 1926, say) still receives the household's
            # support. Dropping it would hide a real household merge, and it stays low for review through its own flag.
            others = agreeing(p, c["a"]["obs"], c["b"]["obs"])
            c["support"] = len(others)
            c["supporters"] = [_member_text(s) for s in others]
        # Rule 1: a head or spouse whose other household members continue together in a different household.
        if c["a"]["relc"] in PARENT_ROLES and not (p in continuing and c in sound[p]):
            for q in sorted(sound, key=str):
                if q[0] == c["a"]["hh"] and q[1] != c["b"]["hh"] and q in continuing:
                    rest = agreeing(q, c["a"]["obs"])
                    if len(rest) >= need_n:
                        c["conflicts"].append({"severe": True, "text": "the other members of the %d household (%s) continue together in %s in %d"
                                               % (c["a"]["year"], "; ".join(_member_text(s) for s in rest),
                                                  _hh_label(rest[0]["b"]), rest[0]["b"]["year"])})
        # Rule 2: in a household that otherwise continues, another member's best link reverses a relationship
        # or marital status.
        if coherent and p in continuing:
            for r in risky.get(p, []):
                if r["a"]["obs"] != c["a"]["obs"]:
                    c["conflicts"].append({"severe": False, "text": "%s is %s in %d but %s in %d, which does not fit the same household"
                                           % (_name(r["a"]), r["a"]["rel"] or "?", r["a"]["year"], r["b"]["rel"] or "?", r["b"]["year"])})


def score(c: dict, cfg: dict) -> int:
    w = cfg["weights"]
    s = w["given_" + c["given"]]
    s += {"exact": w["surname_exact"], "variant": w["surname_variant"], "change": w["surname_change"]}[c["surname"]]
    d = c["drift"]
    s += w["age_drift_0_1"] if d <= 1 else w["age_drift_2_3"] if d <= cfg["age_tolerance"] else w["age_drift_wide"]
    s += min(c["support"], w["household_support_max"]) * w["household_support_each"]
    s += min(len(c.get("conflicts", ())), w["household_conflict_max"]) * w["household_conflict_each"]
    s += w["same_townland"] if c["same_townland"] else 0
    s += w["same_house"] if c["same_house"] else 0
    s += w["implausible_relation"] if c["implausible"] else 0
    s += w["marital_regress"] if c["regress"] else 0
    return s


def assign(cands, cfg):
    """Greedy assignment. A pair is chosen only when it beats every competing pair for either row
    by at least the margin. Pairs that cannot be separated stay as ambiguous proposals."""
    margin = cfg["margin"]
    for c in cands:
        c["score"] = score(c, cfg)
    remaining = list(cands)
    chosen = []
    while True:
        by_a, by_b = collections.defaultdict(list), collections.defaultdict(list)
        for c in remaining:
            by_a[c["a"]["obs"]].append(c)
            by_b[c["b"]["obs"]].append(c)
        clear = [c for c in remaining if _lead(c, by_a[c["a"]["obs"]]) >= margin
                 and _lead(c, by_b[c["b"]["obs"]]) >= margin]
        if not clear:
            break
        chosen += clear
        used_a = {c["a"]["obs"] for c in clear}
        used_b = {c["b"]["obs"] for c in clear}
        remaining = [c for c in remaining if c["a"]["obs"] not in used_a and c["b"]["obs"] not in used_b]
    by_a, by_b = collections.defaultdict(list), collections.defaultdict(list)
    for c in remaining:
        by_a[c["a"]["obs"]].append(c)
        by_b[c["b"]["obs"]].append(c)
    ambiguous = []
    for c in remaining:
        if _lead(c, by_a[c["a"]["obs"]]) > -margin and _lead(c, by_b[c["b"]["obs"]]) > -margin:
            rivals = {o["b"]["obs"] for o in by_a[c["a"]["obs"]] if o is not c}
            rivals |= {o["a"]["obs"] for o in by_b[c["b"]["obs"]] if o is not c}
            c["ambiguous_with"] = sorted(rivals)
            ambiguous.append(c)
    return chosen, ambiguous


def _lead(c, group) -> int:
    others = [o["score"] for o in group if o is not c]
    return c["score"] - max(others) if others else 10 ** 6


def grade(c: dict, household: bool = True) -> tuple[str, list[str]]:
    """Confidence and flags. With household False only the person's own evidence is used, which is how
    a link is judged before it is allowed to support others (add_support)."""
    severe, weak = [], []
    if c.get("ambiguous_with"):
        severe.append("ambiguous")
    if c["surname"] == "change":
        severe.append("surname change")
    if c["regress"]:
        severe.append("marital status moves backwards")
    if c["implausible"]:
        severe.append("relationship unlikely")
    if c["given"] == "verified":
        weak.append("given name variant")
    if c["given"] == "proposed":
        weak.append("given name variant not verified")
    if c["drift"] > c["limit"]:
        severe.append("age drift %d, beyond the limit for an older age at the later return" % c["drift"])
    elif c["drift"] > c["tol"]:
        weak.append("age drift %d" % c["drift"])
    if not c["same_townland"] and c["surname"] != "change":
        weak.append("moved townland")
    if household:
        if c["support"] < 1 and c["hh_sizes"] != (1, 1):
            weak.append("no household continuity")
        for k in c.get("conflicts", ()):
            (severe if k["severe"] else weak).append("household contradiction: " + k["text"])
    if c["skip"]:
        weak.append("skips 1911")
    if c["children_fell"]:
        weak.append("children count fell")
    conf = "low" if severe or len(weak) >= 2 else "medium" if weak else "high"
    return conf, severe + weak


def method_text(c: dict) -> str:
    bits = ["given " + {"exact": "exact", "verified": "verified variant", "proposed": "variant not verified"}[c["given"]],
            "surname " + {"exact": "exact", "variant": "verified family", "change": "differs, single in earlier return"}[c["surname"]],
            "age drift %d" % c["drift"]]
    bits.append("same townland" if c["same_townland"] else "different townland")
    if c["same_house"]:
        bits.append("same house number")
    # The person's own evidence and the household's corroboration are kept apart so a reviewer can see
    # which carries the link.
    if c["support"]:
        hh = "%d other member%s into the same household (%s)" % (
            c["support"], " continues" if c["support"] == 1 else "s continue", "; ".join(c["supporters"]))
    elif c["hh_sizes"] == (1, 1):
        hh = "one person in each household, nothing to corroborate"
    else:
        hh = "not corroborated, fewer than 2 sound links agree on this household"
    for k in c.get("conflicts", ()):
        hh += "; contradiction: " + k["text"]
    return "Individual: %s. Household: %s." % ("; ".join(bits), hh)


# ------------------------------------------------------------------ one DED

def propose_ded(rows: list[dict], names: Names, cfg: dict, decisions: dict | None = None):
    """Links for the rows of one DED. Returns (links, stats). Decisions are Mike's reviewed
    links: an accepted link is kept as it is and its rows do not compete for other links, and a
    rejected pair is never proposed again."""
    by_year = collections.defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r)
    hh_size = collections.Counter(r["hh"] for r in rows)
    links, stats = [], collections.Counter()
    linked_from, linked_to = set(), set()
    by_obs = {r["obs"]: r for r in rows}
    rejected, accepted = set(), []
    for (fo, to), d in (decisions or {}).items():
        if fo not in by_obs or to not in by_obs:
            continue
        if d["status"] == "rejected":
            rejected.add((fo, to))
        elif d["status"] == "accepted":
            accepted.append((by_obs[fo], by_obs[to], d))
    for ra, rb, d in sorted(accepted, key=lambda x: (x[0]["obs"], x[1]["obs"])):
        links.append({"a": ra, "b": rb, "confidence": d["confidence"] if d["confidence"] in RANK else "high",
                      "flags": [], "decision": d})
        linked_from.add(ra["obs"])
        linked_to.add(rb["obs"])
    stats["accepted"], stats["rejected"] = len(accepted), len(rejected)
    for ya, yb in SUCCESSIVE:
        if not by_year.get(ya) or not by_year.get(yb):
            continue
        cands, skipped = candidates(by_year[ya], by_year[yb], names, cfg)
        cands = [c for c in cands if (c["a"]["obs"], c["b"]["obs"]) not in rejected
                 and c["a"]["obs"] not in linked_from and c["b"]["obs"] not in linked_to]
        stats.update(skipped)
        add_support(cands, hh_size, cfg)
        chosen, ambiguous = assign(cands, cfg)
        for c in chosen + ambiguous:
            links.append(c)
            linked_from.add(c["a"]["obs"])
            linked_to.add(c["b"]["obs"])
    if by_year.get(SKIP[0]) and by_year.get(SKIP[1]):
        left_a = [r for r in by_year[SKIP[0]] if r["obs"] not in linked_from]
        left_b = [r for r in by_year[SKIP[1]] if r["obs"] not in linked_to]
        if left_a and left_b:
            cands, skipped = candidates(left_a, left_b, names, cfg, skip=True)
            cands = [c for c in cands if (c["a"]["obs"], c["b"]["obs"]) not in rejected]
            add_support(cands, hh_size, cfg)
            chosen, ambiguous = assign(cands, cfg)
            links += chosen + ambiguous
    for c in links:
        if not c.get("decision"):
            c["confidence"], c["flags"] = grade(c)
    stats["rows"] = len(rows)
    return links, stats


def chains(links) -> dict[str, str]:
    """Row to chain ID, from links that are not ambiguous. The ID is the earliest row's ID."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    order = {}
    for c in links:
        if c.get("ambiguous_with"):
            continue
        for r in (c["a"], c["b"]):
            order[r["obs"]] = (r["year"], r["obs"])
        parent[find(c["a"]["obs"])] = find(c["b"]["obs"])
    groups = collections.defaultdict(list)
    for o in order:
        groups[find(o)].append(o)
    out = {}
    for members in groups.values():
        first = min(members, key=lambda o: order[o])
        for o in members:
            out[o] = "chain:" + first
    return out


# ------------------------------------------------------------------ review report

def _name(r):
    return ("%s %s" % (r["first"], r["surname"])).strip()


def _hh_label(r):
    if r["year"] == 1926:
        m = re.match(r"^(.*?_\d{4}_\d{4}_\d{4})", r["form"])
        return "form " + (m.group(1) if m else r["form"])
    return "house " + (r["house"] or "?")


def _house_sort(r):
    return int(r["house"]) if r["house"].isdigit() else 0


def link_records(links, hh_members) -> list[dict]:
    chain_of = chains(links)
    out = []
    for c in sorted(links, key=lambda c: (c["a"]["tkey"], c["a"]["year"], c["b"]["year"], _house_sort(c["a"]),
                                          c["a"]["form"], RANK[c["confidence"]], c["a"]["surname"],
                                          c["a"]["first"], c["a"]["obs"], c["b"]["obs"])):
        a, b = c["a"], c["b"]
        head = next((m for m in hh_members[a["hh"]] if m["relc"] == "head"), None)
        d = c.get("decision") or {}
        out.append({
            "status": d.get("status", ""), "confidence": c["confidence"],
            "group": "%s | %s %s (%s) to %s %s" % (a["townland"], a["year"], _hh_label(a),
                                                   _name(head) if head else "no head", b["year"], _hh_label(b)),
            "from_obs": a["obs"], "from_name": _name(a), "from_age": a["age"], "from_relation": a["rel"],
            "from_townland": a["townland"], "to_obs": b["obs"], "to_name": _name(b), "to_age": b["age"],
            "to_relation": b["rel"], "to_townland": b["townland"], "years": "%d to %d" % (a["year"], b["year"]),
            "method": ("Accepted by %s on %s" % (d["reviewer"], d["date"])) if d else method_text(c),
            "flags": "; ".join(c["flags"]),
            "ambiguous_with": " ".join(c.get("ambiguous_with", [])),
            "chain": chain_of.get(a["obs"], "") if not c.get("ambiguous_with") else "",
            "reviewer": d.get("reviewer", ""), "date": d.get("date", ""), "note": d.get("note", ""),
        })
    return out


def write_csv(path: Path, recs: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(recs)


def surname_matches(rec: dict, wanted: str, names: Names) -> bool:
    k = names.surname_canon(wanted)
    return any(names.surname_canon(n.split()[-1]) == k for n in (rec["from_name"], rec["to_name"]) if n)


def run_propose(census_dir: Path, out: Path, cfg: dict, only_ded=None, townland=None, surname=None, names=None,
                include_proposed=False, decisions: Path | None = DECISIONS) -> dict:
    names = names or Names(given_names_reference.load(GIVEN), variants_reference.load(), include_proposed)
    rows = load_census(census_dir)
    reviewed = load_decisions(decisions) if decisions else {}
    per_ded = collections.defaultdict(list)
    for r in rows:
        if not only_ded or r["ded"].lower() == only_ded.lower():
            per_ded[r["ded"]].append(r)
    summary = {}
    for ded in sorted(per_ded):
        links, stats = propose_ded(per_ded[ded], names, cfg, reviewed)
        hh_members = collections.defaultdict(list)
        for r in per_ded[ded]:
            hh_members[r["hh"]].append(r)
        recs = link_records(links, hh_members)
        if townland:
            tk = townland_key(townland)
            recs = [x for x in recs if townland_key(x["from_townland"]) == tk
                    or townland_key(x["to_townland"]) == tk]
        if surname:
            recs = [x for x in recs if surname_matches(x, surname, names)]
        write_csv(Path(out) / (ded.lower() + "_links.csv"), recs)
        conf = collections.Counter(x["confidence"] for x in recs)
        amb = sum(1 for x in recs if x["ambiguous_with"])
        summary[ded] = {"rows": stats["rows"], "links": len(recs), "ambiguous": amb,
                        "accepted": stats["accepted"], "rejected": stats["rejected"], **{k: conf.get(k, 0) for k in RANK},
                        "left out": {k: v for k, v in stats.items() if k not in ("rows", "accepted", "rejected")}}
    return summary


# ------------------------------------------------------------------ reviewed decisions (WP19)

def load_decisions(path: Path = DECISIONS) -> dict:
    """Reviewed links keyed by (from_obs, to_obs). An absent file means nothing is reviewed yet."""
    path = Path(path)
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return {(r["from_obs"], r["to_obs"]): {k: (r.get(k) or "") for k in DECISION_FIELDS} for r in csv.DictReader(fh)}


def _problems(decisions: dict, rows_by_obs: dict) -> list[str]:
    """Why a set of reviewed links cannot stand: unknown rows, wrong order, or a row linked twice."""
    errs = []
    taken_from, taken_to = {}, {}
    for (fo, to), d in sorted(decisions.items()):
        where = "census_links.csv %s > %s" % (fo, to)
        if d["status"] not in STATUSES:
            errs.append("%s: status must be accepted or rejected, not %r" % (where, d["status"]))
        for o in (fo, to):
            if o not in rows_by_obs:
                errs.append("%s: no census row has the ID %s" % (where, o))
        if fo in rows_by_obs and to in rows_by_obs:
            a, b = rows_by_obs[fo], rows_by_obs[to]
            if a["year"] >= b["year"]:
                errs.append("%s: the link must run from an earlier return to a later one" % where)
            if a["ded"] != b["ded"]:
                errs.append("%s: links across DEDs are not recorded yet" % where)
            if d["status"] == "accepted":
                if (fo, b["year"]) in taken_from:
                    errs.append("%s: %s is already linked to %s in %d" % (where, fo, taken_from[(fo, b["year"])], b["year"]))
                if (to, a["year"]) in taken_to:
                    errs.append("%s: %s is already linked from %s in %d" % (where, to, taken_to[(to, a["year"])], a["year"]))
                taken_from[(fo, b["year"])] = to
                taken_to[(to, a["year"])] = fo
    return errs


def check_decisions(path: Path = DECISIONS, census_dir: Path = CENSUS_DIR) -> list[str]:
    """For validate.py. Returns a list of problems, empty when the file is sound or absent."""
    if not Path(path).is_file():
        return []
    decisions = load_decisions(path)
    return _problems(decisions, {r["obs"]: r for r in load_census(census_dir)})


def run_accept(text: str, path: Path = DECISIONS, census_dir: Path = CENSUS_DIR, reviewer: str = "",
               date: str = "", dry_run: bool = False, out=sys.stdout) -> int:
    """Record decisions pasted from the review page. Only accepted and rejected rows are kept; a later
    decision on the same pair replaces the earlier one. Nothing is written if any row is unsound."""
    import io
    reviewer = reviewer or "Mike"
    date = date or datetime.date.today().isoformat()
    incoming = {}
    for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        status = (r.get("status") or "").strip().lower()
        if status not in STATUSES:
            continue
        key = ((r.get("from_obs") or "").strip(), (r.get("to_obs") or "").strip())
        incoming[key] = {"from_obs": key[0], "to_obs": key[1], "status": status,
                         "reviewer": (r.get("reviewer") or "").strip() or reviewer,
                         "date": (r.get("date") or "").strip() or date,
                         "confidence": (r.get("confidence") or "").strip(),
                         "from_name": (r.get("from_name") or "").strip(), "to_name": (r.get("to_name") or "").strip(),
                         "note": (r.get("note") or "").strip()}
    if not incoming:
        out.write("No accepted or rejected rows found. Nothing recorded.\n")
        return 1
    existing = load_decisions(path)
    merged = dict(existing)
    new = changed = 0
    for k, d in incoming.items():
        if k not in existing:
            new += 1
        elif existing[k]["status"] != d["status"]:
            changed += 1
        merged[k] = d
    errs = _problems(merged, {r["obs"]: r for r in load_census(census_dir)})
    if errs:
        out.write("Nothing recorded. Problems:\n" + "\n".join("  " + e for e in errs[:20]) + "\n")
        return 1
    n_acc = sum(1 for d in incoming.values() if d["status"] == "accepted")
    out.write("%d accepted, %d rejected (%d new, %d changed, %d already recorded).\n"
              % (n_acc, len(incoming) - n_acc, new, changed, len(incoming) - new - changed))
    if dry_run:
        out.write("Dry run: nothing written.\n")
        return 0
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DECISION_FIELDS, lineterminator="\n")
        w.writeheader()
        for k in sorted(merged):
            w.writerow(merged[k])
    out.write("Recorded in %s (%d rows).\n" % (Path(path).name, len(merged)))
    return 0


# ------------------------------------------------------------------ check against the tree

def tree_pairs(path: Path = TREE):
    """Consecutive census pairs for each tree person with an accepted link, from the reviewed
    decisions file. The private GEDCOM is not needed."""
    by_person = collections.defaultdict(list)
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["status"] == "accepted":
                by_person[r["person_ptr"]].append((int(r["obs_id"].split(":")[0].replace("census", "")), r["obs_id"], r["person_name"]))
    pairs = []
    for ptr, items in sorted(by_person.items()):
        items.sort()
        for (y1, o1, name), (y2, o2, _) in zip(items, items[1:]):
            pairs.append({"person": ptr, "name": name, "from": o1, "to": o2, "y1": y1, "y2": y2})
    return pairs


def run_check(census_dir: Path, cfg: dict, decisions: Path = TREE, names=None, out=sys.stdout, include_proposed=False) -> dict:
    names = names or Names(given_names_reference.load(GIVEN), variants_reference.load(), include_proposed)
    rows = load_census(census_dir)
    per_ded = collections.defaultdict(list)
    for r in rows:
        per_ded[r["ded"].lower()].append(r)
    proposals = {}
    for ded, rs in per_ded.items():
        links, _ = propose_ded(rs, names, cfg)
        for c in links:
            proposals.setdefault(c["a"]["obs"], []).append(c)
    pairs = tree_pairs(decisions)
    result = collections.Counter()
    lines = []
    for p in pairs:
        d1, d2 = p["from"].split(":")[1], p["to"].split(":")[1]
        if d1 != d2:
            result["across DEDs (out of scope)"] += 1
            lines.append("  across DEDs   %s: %s to %s" % (p["name"], p["from"], p["to"]))
            continue
        mine = proposals.get(p["from"], [])
        hit = next((c for c in mine if c["b"]["obs"] == p["to"]), None)
        if hit:
            label = "found, ambiguous" if hit.get("ambiguous_with") else "found, " + hit["confidence"]
            result[label] += 1
            lines.append("  %-18s %s (%d to %d)" % (label, p["name"], p["y1"], p["y2"]))
        elif mine:
            best = sorted(mine, key=lambda c: (RANK[c["confidence"]], -c["score"]))[0]
            label = "other partner, " + ("ambiguous" if best.get("ambiguous_with") else best["confidence"])
            result[label] += 1
            lines.append("  %-18s %s (%d to %d): proposed %s" % (label, p["name"], p["y1"], p["y2"], best["b"]["obs"]))
        else:
            result["not found"] += 1
            lines.append("  not found          %s (%d to %d)" % (p["name"], p["y1"], p["y2"]))
    print("Tree pairs from accepted links: %d" % len(pairs), file=out)
    for k, v in sorted(result.items()):
        print("  %s: %d" % (k, v), file=out)
    print("Detail:", file=out)
    print("\n".join(lines), file=out)
    return dict(result)


# ------------------------------------------------------------------ command line

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("propose", help="write review CSVs of proposed links")
    p2 = sub.add_parser("check", help="compare the matcher with the links Mike accepted in the tree")
    p3 = sub.add_parser("accept", help="record decisions copied from the review page")
    p3.add_argument("file", help="CSV of decisions, or - to read from standard input")
    p3.add_argument("--reviewer", default="")
    p3.add_argument("--date", default="")
    p3.add_argument("--dry-run", action="store_true")
    p3.add_argument("--census-dir", type=Path, default=CENSUS_DIR)
    p3.add_argument("--records", type=Path, default=DECISIONS)
    for p in (p1, p2):
        p.add_argument("--census-dir", type=Path, default=CENSUS_DIR)
        p.add_argument("--config", type=Path, default=CONFIG)
        p.add_argument("--include-proposed-given-names", action="store_true",
                       help="also treat proposed given-name families as equivalent, capped at medium")
    p1.add_argument("--out", type=Path, default=OUT_DIR)
    p1.add_argument("--ded")
    p1.add_argument("--townland", help="only links that involve this townland")
    p1.add_argument("--surname", help="only links whose names have this surname or a verified spelling of it")
    p2.add_argument("--decisions", type=Path, default=TREE)
    args = ap.parse_args(argv)
    if args.cmd == "accept":
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        return run_accept(text, args.records, args.census_dir, args.reviewer, args.date, args.dry_run)
    cfg = load_config(args.config)
    if args.cmd == "propose":
        summary = run_propose(args.census_dir, args.out, cfg, args.ded, args.townland, args.surname,
                              include_proposed=args.include_proposed_given_names)
        for ded, s in summary.items():
            print("%s: %d rows, %d links (high %d, medium %d, low %d; %d ambiguous; %d accepted and %d rejected by review)"
                  % (ded, s["rows"], s["links"], s["high"], s["medium"], s["low"], s["ambiguous"], s["accepted"], s["rejected"]))
            for k, v in sorted(s["left out"].items()):
                print("  left out: %s: %d" % (k, v))
        print("Review files are in %s. Nothing is accepted by this tool." % args.out)
        return 0
    run_check(args.census_dir, cfg, args.decisions, include_proposed=args.include_proposed_given_names)
    return 0


if __name__ == "__main__":
    sys.exit(main())
