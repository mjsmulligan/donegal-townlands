#!/usr/bin/env python3
"""
Attach census returns to townland cases, Clogher DED only.

Usage:
    python tools/attach_census.py

Inputs:
    data/census/{1901,1911,1926}_Clogher.csv
    data/processed/places/places.csv
    data/processed/places/townland_cases.csv   (python tools/create_townland_cases.py)

Outputs, per matched case:
    townlands/<case>/records/census.json         census rows, as transcribed
    townlands/<case>/records/census_match.json   how the rows were matched
Output for the whole run:
    data/processed/places/census_spelling_review.csv

Matching rule. A census townland string is attached to a Logainm townland only
when the two names are identical apart from case, accents and spacing. Every
such match is recorded as PROPOSED, never as confirmed. Any other spelling
(Collinboy, Druminin, Finny Cahill and so on) is attached to nothing. It is
listed in the review CSV for Mike to decide. To accept a spelling, set its
status to accepted and fill accepted_logainm_id, then run this script again.
Decisions made in the review CSV are never overwritten.

Safety.
- A case that already has records/census.json written by someone else (Clogher
  and Cullionboy) is left untouched.
- Their census_spelling entries in townland.json count as already accepted.
- Rows for anyone born less than 100 years ago, or whose age is unknown in
  1926, are withheld (100/75/50 rule) and counted.
- The original CSV files are only read.
"""

import ast
import csv
import datetime
import difflib
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES_CSV = ROOT / "data" / "processed" / "places" / "places.csv"
CASES_CSV = ROOT / "data" / "processed" / "places" / "townland_cases.csv"
REVIEW_CSV = ROOT / "data" / "processed" / "places" / "census_spelling_review.csv"
CENSUS_DIR = ROOT / "data" / "census"

DED_NAME = "Clogher"
YEARS = (1901, 1911, 1926)
GENERATED_MARKER = "donegal-townlands.attach_census"
THIS_YEAR = datetime.date.today().year

REVIEW_FIELDS = [
    "ded",
    "census_year",
    "census_spelling",
    "rows",
    "status",
    "accepted_logainm_id",
    "similar_places_not_confirmed",
]
HUMAN_STATUSES = {"accepted", "rejected"}


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def normalise_name(value):
    """For comparison only. Never alters a recorded spelling."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(value.casefold().split())


def read_csv(path):
    if not path.is_file():
        fail(f"File not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def num(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def first_image_id(images):
    """First image ID in the 1901 and 1911 images field, or empty."""
    try:
        items = ast.literal_eval(images or "[]")
        return items[0]["id"]
    except (ValueError, SyntaxError, IndexError, KeyError, TypeError):
        return ""


def row_1901_1911(x):
    return {
        "h": num(x.get("house_number")),
        "s": x.get("surname", ""),
        "f": x.get("firstname", ""),
        "a": num(x.get("age")),
        "x": x.get("sex", ""),
        "r": x.get("relation_to_head_updated", ""),
        "m": x.get("marriage_status", ""),
        "o": x.get("occupation_updated", ""),
        "i": 1 if "Irish" in (x.get("language_updated") or "") else 0,
        "ref": first_image_id(x.get("images")),
    }


def row_1926(x):
    form = (x.get("aform_name") or "").split("_")
    house = form[3] if len(form) > 3 else ""
    children = x.get("children_living") or ""
    marriage = x.get("updated_marriage") or (
        f"{children} children living" if children.isdigit() else ""
    )
    return {
        "h": house,
        "s": x.get("surname", ""),
        "f": x.get("first_name", ""),
        "a": num(x.get("updated_age")),
        "x": x.get("updated_sex", ""),
        "r": x.get("updated_relationship_to_head") or x.get("relationship_to_head", ""),
        "m": marriage,
        "o": "",
        "i": 1 if "Irish" in (x.get("updated_irish_language") or "") else 0,
        "ref": x.get("aform_name", ""),
    }


def withheld(year, row):
    """100/75/50 rule for census persons: born within the last 100 years."""
    if row["a"] is None:
        return year >= THIS_YEAR - 100
    return (year - row["a"]) > THIS_YEAR - 100


def build_row(year, raw):
    return row_1926(raw) if year == 1926 else row_1901_1911(raw)


def read_case_index():
    return {r["logainm_id"]: r["case_path"] for r in read_csv(CASES_CSV)}


def read_review():
    if not REVIEW_CSV.is_file():
        return {}
    with REVIEW_CSV.open("r", encoding="utf-8", newline="") as handle:
        return {
            (r["census_year"], r["census_spelling"]): r
            for r in csv.DictReader(handle)
        }


def accepted_in_case(places, index):
    """(year, normalised spelling) -> logainm_id, from existing townland.json."""
    accepted = {}
    for place in places:
        case_path = index.get(place["logainm_id"])
        meta_path = ROOT / case_path / "townland.json" if case_path else None
        if not meta_path or not meta_path.is_file():
            continue
        with meta_path.open("r", encoding="utf-8") as handle:
            spellings = json.load(handle).get("census_spelling", {})
        for year, spelling in spellings.items():
            accepted[(str(year), normalise_name(spelling))] = place["logainm_id"]
    return accepted


def write_json(path, data, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def main():
    places_all = read_csv(PLACES_CSV)
    ded_ids = [r["logainm_id"] for r in places_all
               if r["place_type"] == "ded" and r["name_en"] == DED_NAME]
    if len(ded_ids) != 1:
        fail(f"Expected exactly one {DED_NAME} DED in places.csv, found {len(ded_ids)}.")
    places = [r for r in places_all
              if r["place_type"] == "townland" and r["ded_id"] == ded_ids[0]]
    by_id = {p["logainm_id"]: p for p in places}
    index = read_case_index()

    missing = [p["name_en"] for p in places if p["logainm_id"] not in index]
    if missing:
        fail("No case for: " + ", ".join(missing)
             + ". Run python tools/create_townland_cases.py first.")

    by_name = {}
    for p in places:
        by_name.setdefault(normalise_name(p["name_en"]), []).append(p)

    accepted_case = accepted_in_case(places, index)
    review_old = read_review()

    matches = {}      # logainm_id -> year -> {"rows": [...], "spellings": [...], "withheld": n}
    review_rows = []

    for year in YEARS:
        source = CENSUS_DIR / f"{year}_{DED_NAME}.csv"
        by_spelling = {}
        for raw in read_csv(source):
            by_spelling.setdefault(raw.get("townland", ""), []).append(raw)

        for spelling, raws in sorted(by_spelling.items()):
            key = normalise_name(spelling)
            old = review_old.get((str(year), spelling))
            target, method, status = None, None, "unreviewed"

            if key in by_name and len(by_name[key]) == 1:
                target, method = by_name[key][0]["logainm_id"], "exact_name"
            elif key in by_name:
                status = "ambiguous"
            elif (str(year), key) in accepted_case:
                status = "accepted_in_case"
            elif old and old["status"] == "accepted" and old["accepted_logainm_id"] in by_id:
                target, method, status = old["accepted_logainm_id"], "reviewed_variant", "accepted"
            elif old and old["status"] in HUMAN_STATUSES:
                status = old["status"]

            if target:
                slot = matches.setdefault(target, {}).setdefault(
                    year, {"rows": [], "spellings": [], "withheld": 0})
                slot["spellings"].append({"spelling": spelling, "method": method, "rows": len(raws)})
                for raw in raws:
                    row = build_row(year, raw)
                    if withheld(year, row):
                        slot["withheld"] += 1
                    else:
                        slot["rows"].append(row)

            if method != "exact_name":
                names = [p["name_en"] for p in places]
                similar = difflib.get_close_matches(spelling, names, n=3, cutoff=0.75)
                review_rows.append({
                    "ded": DED_NAME,
                    "census_year": year,
                    "census_spelling": spelling,
                    "rows": len(raws),
                    "status": status,
                    "accepted_logainm_id": (old or {}).get("accepted_logainm_id", "")
                    if status in HUMAN_STATUSES else (target or ""),
                    "similar_places_not_confirmed": "; ".join(similar),
                })

    attached = skipped_authored = 0
    for logainm_id, years in sorted(matches.items()):
        case_dir = ROOT / index[logainm_id]
        census_path = case_dir / "records" / "census.json"
        match_path = case_dir / "records" / "census_match.json"

        mine = False
        if match_path.is_file():
            with match_path.open("r", encoding="utf-8") as handle:
                mine = json.load(handle).get("_generated_by") == GENERATED_MARKER

        if census_path.is_file() and not mine:
            skipped_authored += 1
            print(f"authored, untouched: {by_id[logainm_id]['name_en']} ({logainm_id})")
            continue

        rows = {str(y): years[y]["rows"] for y in sorted(years)}
        write_json(census_path, rows, compact=True)
        write_json(match_path, {
            "_generated_by": GENERATED_MARKER,
            "status": "proposed",
            "note": "Matched by identical name only. Not reviewed.",
            "ded": DED_NAME,
            "years": {
                str(y): {
                    "spellings": years[y]["spellings"],
                    "people": len(years[y]["rows"]),
                    "withheld": years[y]["withheld"],
                }
                for y in sorted(years)
            },
        })
        attached += 1
        print(f"attached: {by_id[logainm_id]['name_en']} ({logainm_id}) -> "
              + ", ".join(f"{y}: {len(years[y]['rows'])}" for y in sorted(years)))

    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(review_rows, key=lambda r: (r["census_year"], r["census_spelling"])))

    print()
    print(f"{DED_NAME} DED townlands: {len(places)}")
    print(f"Cases with census attached: {attached}")
    print(f"Authored cases left untouched: {skipped_authored}")
    print(f"Spellings listed for review: {len(review_rows)}")
    print(f"Review file: {REVIEW_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
