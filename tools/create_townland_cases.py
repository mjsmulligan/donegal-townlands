
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

Existing cases are adopted by matching the name in their townland.json.
This allows the existing Clogher and Cullionboy research folders to be
retained without moving or replacing their authored files.

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

        for row in reader:
            if (row.get("place_type") or "").strip().casefold() != "townland":
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


def read_case_name(case_dir):
    """
    Return the name recorded in townland.json, if present.

    Existing townland.json files are read only. They are never rewritten.
    """
    metadata_path = case_dir / "townland.json"

    if not metadata_path.is_file():
        return None

    try:
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read {metadata_path}: {exc}")

    return metadata.get("name")


def find_existing_case(place):
    """
    Find an existing case by its townland.json name.

    More than one match is ambiguous and stops the run.
    """
    target = normalise_name(place["name_en"])
    matches = []

    if not TOWNLANDS_DIR.is_dir():
        return None

    for case_dir in sorted(TOWNLANDS_DIR.iterdir()):
        if not case_dir.is_dir():
            continue

        existing_name = read_case_name(case_dir)

        if existing_name and normalise_name(existing_name) == target:
            matches.append(case_dir)

    if len(matches) > 1:
        paths = ", ".join(str(path.relative_to(ROOT)) for path in matches)
        fail(
            f"More than one existing case matches "
            f"{place['name_en']!r}: {paths}"
        )

    return matches[0] if matches else None


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

    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
    """Choose a new directory without colliding with another townland."""
    slug = make_slug(place["name_en"])

    if slug in used_slugs:
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

    used_slugs = set()
    index_rows = []
    created = 0
    adopted = 0
    refreshed = 0

    for place in places:
        logainm_id = place["logainm_id"].strip()

        case_dir = find_existing_case(place)

        if case_dir is None:
            case_dir = choose_new_case_path(place, used_slugs)
            case_dir.mkdir(parents=True, exist_ok=False)
            created += 1
            action = "created"
        else:
            adopted += 1
            action = "adopted"

        write_place_record(case_dir, place)

        status_created = create_status_file(case_dir, place)

        if status_created:
            refreshed += 1

        case_path = case_dir.relative_to(ROOT).as_posix()

        index_rows.append({
            "logainm_id": logainm_id,
            "case_path": case_path,
            "name_en": place["name_en"].strip(),
            "snapshot_date": place["snapshot_date"].strip(),
        })

        print(f"{action}: {place['name_en']} ({logainm_id}) -> {case_path}")

    write_index(index_rows)

    print()
    print(f"Townlands processed: {len(places)}")
    print(f"New cases created: {created}")
    print(f"Existing cases adopted: {adopted}")
    print(f"Starter status files created: {refreshed}")
    print(f"Index written: {INDEX_CSV.relative_to(ROOT)}")
    print("No existing research files or cases were deleted.")


if __name__ == "__main__":
    main()
