
#!/usr/bin/env python3
"""
Create or update one research case for every Logainm townland in places.csv.

Usage:
    python tools/create_townland_cases.py

Input:
    data/processed/places/places.csv

Generated outputs:
    townlands/<case-name>/place.json
    townlands/<case-name>/STATUS.md  (created only if absent)
    data/processed/places/townland_cases.csv

Identity is based on Logainm ID, never on the townland name or folder name.

Existing cases are recognised by Logainm ID, found in place.json or in
townland.json. A legacy case with no recorded ID (the original Clogher
and Cullionboy folders) is adopted once, by a name match that must be
unique and must agree with its recorded DED. The ID is then written to
place.json, so later runs never depend on the name again.

The script never deletes a case and never overwrites authored research files.
"""

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLACES_CSV = ROOT / "data" / "processed" / "places" / "places.csv"
TOWNLANDS_DIR = ROOT / "townlands"
INDEX_CSV = ROOT / "data" / "processed" / "places" / "townland_cases.csv"

INDEX_FIELDS = [
    "logainm_id",
    "case_path",
    "name_en",
    "snapshot_date",
    "in_latest_snapshot",
]

GENERATED_MARKER = "donegal-townlands.create_townland_cases"


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def normalise_name(value):
    """Normalise a name for comparison only. Never alter source spellings."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(value.casefold().split())


def make_slug(value):
    """Create a safe directory name from a townland name."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "unnamed-townland"


ded_names = {}


def read_places():
    if not PLACES_CSV.is_file():
        fail(f"Places file not found: {PLACES_CSV}")

    with PLACES_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        required = {
            "logainm_id",
            "name_en",
            "place_type",
            "snapshot_date",
        }
        missing = required - set(reader.fieldnames or [])

        if missing:
            fail(
                "places.csv is missing required columns: "
                + ", ".join(sorted(missing))
            )

        places = []
        seen_ids = set()
        ded_names.clear()

        for row in reader:
            kind = (row.get("place_type") or "").strip().casefold()

            if kind == "ded":
                ded_names[(row.get("logainm_id") or "").strip()] = (
                    row.get("name_en") or ""
                ).strip()
                continue

            if kind != "townland":
                continue

            logainm_id = (row.get("logainm_id") or "").strip()
            name_en = (row.get("name_en") or "").strip()

            if not logainm_id:
                fail("A townland row has no Logainm ID.")

            if not name_en:
                fail(f"Townland {logainm_id} has no English name.")

            if logainm_id in seen_ids:
                fail(f"Duplicate Logainm ID in places.csv: {logainm_id}")

            seen_ids.add(logainm_id)
            places.append(row)

    if not places:
        fail("No townland rows were found in places.csv.")

    return places


def read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read {path}: {exc}")


def scan_cases():
    """
    Read every existing case directory once. Nothing is written.

    Returns (by_id, legacy):
      by_id:  Logainm ID -> case directory, from place.json or townland.json
      legacy: case directories that record no Logainm ID anywhere
    """
    by_id = {}
    legacy = []

    if not TOWNLANDS_DIR.is_dir():
        return by_id, legacy

    for case_dir in sorted(TOWNLANDS_DIR.iterdir()):
        if not case_dir.is_dir():
            continue

        recorded = None

        for filename in ("place.json", "townland.json"):
            path = case_dir / filename
            if not path.is_file():
                continue
            value = read_json(path).get("logainm_id")
            if value not in (None, ""):
                value = str(value).strip()
                if recorded is not None and recorded != value:
                    fail(
                        f"{case_dir} records two different Logainm IDs "
                        f"({recorded} and {value})."
                    )
                recorded = value

        if recorded is None:
            if (case_dir / "townland.json").is_file():
                legacy.append(case_dir)
            continue

        if recorded in by_id:
            fail(
                f"Logainm ID {recorded} is claimed by two case "
                f"directories: {by_id[recorded].name} and {case_dir.name}"
            )
        by_id[recorded] = case_dir

    return by_id, legacy


def find_existing_case(place, by_id, legacy, ded_names, places):
    """
    Find the case for a place. The Logainm ID decides.

    A legacy case (no recorded ID) is adopted by name only when:
    - exactly one legacy case has that name,
    - exactly one townland in the register has that name, and
    - the DED in its townland.json, if given, matches the place's DED.
    Anything else is left alone and a new case is created, never a guess.
    """
    logainm_id = place["logainm_id"].strip()

    if logainm_id in by_id:
        return by_id[logainm_id]

    target = normalise_name(place["name_en"])

    same_name_places = [
        p for p in places if normalise_name(p["name_en"]) == target
    ]
    if len(same_name_places) != 1:
        return None

    matches = []
    for case_dir in legacy:
        metadata = read_json(case_dir / "townland.json")
        if normalise_name(metadata.get("name")) != target:
            continue
        case_ded = normalise_name(metadata.get("ded"))
        place_ded = normalise_name(
            ded_names.get((place.get("ded_id") or "").strip(), "")
        )
        if case_ded and place_ded and case_ded != place_ded:
            continue
        matches.append(case_dir)

    if len(matches) > 1:
        paths = ", ".join(str(path.relative_to(ROOT)) for path in matches)
        fail(
            f"More than one existing case matches "
            f"{place['name_en']!r}: {paths}"
        )

    if matches:
        legacy.remove(matches[0])
        return matches[0]

    return None


def make_place_record(place):
    """Build the generated place identity and snapshot record."""
    fields = [
        "logainm_id",
        "name_en",
        "name_ga",
        "place_type",
        "ded_id",
        "civil_parish_id",
        "barony_id",
        "county_id",
        "latitude",
        "longitude",
        "snapshot_date",
    ]

    record = {
        field: (place.get(field) or "").strip()
        for field in fields
    }
    record["_generated_by"] = GENERATED_MARKER

    return record


def write_place_record(case_dir, place):
    """
    Create or refresh place.json.

    A file created by this script can be refreshed on later runs.
    An existing file without this script's marker is left untouched and
    causes an error rather than being overwritten.
    """
    path = case_dir / "place.json"
    record = make_place_record(place)

    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                existing = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"Cannot read {path}: {exc}")

        if existing.get("_generated_by") != GENERATED_MARKER:
            fail(
                f"{path} already exists but is not marked as generated "
                "by this script. It has not been changed."
            )

        if str(existing.get("logainm_id")) != str(place["logainm_id"]):
            fail(
                f"Identity conflict in {path}: existing Logainm ID "
                f"{existing.get('logainm_id')}, incoming ID "
                f"{place['logainm_id']}."
            )

    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"

    if path.exists() and path.read_text(encoding="utf-8") == text:
        return

    path.write_text(text, encoding="utf-8")


def create_status_file(case_dir, place):
    """Create a minimal research status file, but never replace one."""
    path = case_dir / "STATUS.md"

    if path.exists():
        return False

    content = f"""# {place['name_en']} status

Logainm ID: {place['logainm_id']}

## Place record

This case was created from the Logainm place register.

The place identity and current place-register details are held in
`place.json`. The case exists independently of the availability of
historical records.

## Research status

No historical evidence has yet been added to this case.

This is an initial state, not a conclusion about the history of the
townland. Evidence can be added incrementally as sources are researched.

## Open questions

- Confirm historical spellings and any relevant variations.
- Establish historical place relationships where the evidence permits.
- Add historical records with references to their original sources.
"""

    path.write_text(content, encoding="utf-8")
    return True


def choose_new_case_path(place, used_slugs):
    """
    Choose a new directory without colliding with another townland.

    If the plain name is taken (by another townland or by any directory
    already on disk) the Logainm ID is appended. An existing directory is
    never reused for a place that was not matched to it by ID.
    """
    slug = make_slug(place["name_en"])

    if slug in used_slugs or (TOWNLANDS_DIR / slug).exists():
        slug = f"{slug}-{place['logainm_id']}"

    candidate = TOWNLANDS_DIR / slug

    if candidate.exists():
        fail(
            f"Cannot create case directory {candidate}: it already exists "
            "but was not matched to this townland. Please review it manually."
        )

    used_slugs.add(slug)
    return candidate


def write_index(rows):
    """Write the current Logainm townland-to-case index."""
    INDEX_CSV.parent.mkdir(parents=True, exist_ok=True)

    temp_path = INDEX_CSV.with_suffix(".csv.tmp")

    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    temp_path.replace(INDEX_CSV)


def main():
    places = read_places()

    TOWNLANDS_DIR.mkdir(parents=True, exist_ok=True)

    by_id, legacy = scan_cases()

    used_slugs = set()
    index_rows = []
    current_ids = set()
    created = 0
    adopted = 0
    existing = 0
    status_created_count = 0

    for place in places:
        logainm_id = place["logainm_id"].strip()
        current_ids.add(logainm_id)

        case_dir = find_existing_case(place, by_id, legacy, ded_names, places)

        if case_dir is None:
            case_dir = choose_new_case_path(place, used_slugs)
            case_dir.mkdir(parents=True, exist_ok=False)
            created += 1
            action = "created"
        elif logainm_id in by_id:
            existing += 1
            action = "existing"
        else:
            adopted += 1
            action = "adopted"

        by_id[logainm_id] = case_dir

        write_place_record(case_dir, place)

        if create_status_file(case_dir, place):
            status_created_count += 1

        case_path = case_dir.relative_to(ROOT).as_posix()

        index_rows.append({
            "logainm_id": logainm_id,
            "case_path": case_path,
            "name_en": place["name_en"].strip(),
            "snapshot_date": place["snapshot_date"].strip(),
            "in_latest_snapshot": "yes",
        })

        print(f"{action}: {place['name_en']} ({logainm_id}) -> {case_path}")

    # Cases whose townland is absent from this snapshot are kept and listed.
    retained = 0
    for logainm_id, case_dir in sorted(by_id.items()):
        if logainm_id in current_ids:
            continue
        place_path = case_dir / "place.json"
        record = read_json(place_path) if place_path.is_file() else {}
        index_rows.append({
            "logainm_id": logainm_id,
            "case_path": case_dir.relative_to(ROOT).as_posix(),
            "name_en": record.get("name_en", ""),
            "snapshot_date": record.get("snapshot_date", ""),
            "in_latest_snapshot": "no",
        })
        retained += 1
        print(f"retained: {logainm_id} -> {case_dir.name} (not in snapshot)")

    write_index(index_rows)

    print()
    print(f"Townlands processed: {len(places)}")
    print(f"New cases created: {created}")
    print(f"Legacy cases adopted by ID: {adopted}")
    print(f"Cases already known by ID: {existing}")
    print(f"Cases retained, absent from snapshot: {retained}")
    print(f"Starter status files created: {status_created_count}")
    print(f"Index written: {INDEX_CSV.relative_to(ROOT)}")
    print("No existing research files or cases were deleted.")


if __name__ == "__main__":
    main()
