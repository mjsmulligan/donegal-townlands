#!/usr/bin/env python3
"""Create and verify the preserved census-source manifest.

Usage:
    python tools/source_manifest.py create
    python tools/source_manifest.py verify

The manifest identifies the exact local files held in data/source/census/. It
never edits or copies source files. Creation is refused if a manifest already
exists, so changed files cannot silently acquire new trusted checksums.

Files refreshed directly from NAI by tools/refresh_census.py have their rows
updated by that tool as part of one all-or-nothing replacement. Their retrieval
method begins "Direct download from the NAI".

The manifest also covers our own transcriptions of parish registers, held in
data/source/nli_parish/<register>/raw/. Their rows name the file relative to
data/source (for example nli_parish/tawnawilly/raw/tawnawilly_baptisms_raw.csv)
and their retrieval method begins "Own transcription". Unlike census files they
change by reviewed adjudication, so after a review commit run:

    python tools/source_manifest.py register-update

which recomputes the SHA-256 of the listed register files only. It never adds a
row and never touches a census row. New register files are added by
`register-add`, which refuses to alter an existing row.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "source" / "census"
MANIFEST = ROOT / "data" / "source" / "manifest.csv"
EXPECTED_FILES = 15
FIRST_SEEN = "2026-07-10"
GRA_REFERENCE_COMMIT = "1dab647"
GRA_REPOSITORY = "https://github.com/mjsmulligan/irish-genealogy-research"
GRA_DATA_PATH = "data/{filename}"
ADOPTED_FROM_GRA = "Adopted from the Gra repository"
DIRECT_FROM_NAI = "Direct download from the NAI"
OWN_TRANSCRIPTION = "Own transcription"
REGISTER_DIR = "nli_parish"
NLI_PAGE_PATTERN = "https://registers.nli.ie/pages/vtls000631954_NNN"
REGISTER_LICENCE = (
    "The transcription is the project's own work. The register images are National "
    "Library of Ireland material and are not held in this repository. Confirm NLI "
    "terms before publishing images or extended extracts; this note is not a grant "
    "of permission."
)
# One entry per raw register file: what it is and which pages it covers.
REGISTER_DESCRIPTIONS = {
    "nli_parish/tawnawilly/raw/tawnawilly_baptisms_raw.csv": (
        "NLI Catholic parish register, Tawnawilly (Raphoe), baptisms: own transcription of the page images",
        "Microfilm 04599/04, baptisms, pages 004 to 036",
    ),
    "nli_parish/tawnawilly/raw/tawnawilly_marriages_raw.csv": (
        "NLI Catholic parish register, Tawnawilly (Raphoe), marriages: own transcription of the page images",
        "Microfilm 04599/04, marriages, pages 037 to 043",
    ),
}
FIELDS = [
    "file", "source", "county", "census_year", "ded",
    "origin_repository", "origin_path", "repository_reference_commit",
    "upstream_generation_commit", "retrieval_method", "date_acquired",
    "date_first_seen", "licence_note", "sha256",
]


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_metadata(path: Path) -> dict[str, str]:
    match = re.match(r"^(1901|1911|1926)_(.+)\.csv$", path.name, re.IGNORECASE)
    if match:
        year, ded = match.groups()
    else:
        # GRA's naming, <DED>_<year>.csv, which is how the adopted files are named.
        match = re.match(r"^(.+)_(1901|1911|1926)\.csv$", path.name, re.IGNORECASE)
        if not match:
            raise ValueError(f"Unexpected census source filename: {path.name}")
        ded, year = match.groups()
    if year == "1926":
        licence = (
            "National Archives of Ireland 1926 Census: CC BY 4.0. Include the "
            "NAI attribution and identify modifications when sharing. See "
            "https://nationalarchives.ie/search-the-1926-census-2/permission-to-reuse-census-1926/"
        )
    else:
        licence = (
            "National Archives of Ireland 1901/1911 census material. NAI "
            "copyright guidance states that permission is required for "
            "publication. Confirm permission and applicable terms before "
            "redistribution; this note is not a grant of permission. See "
            "https://nationalarchives.ie/help-with-research/copies-publication-and-copyright/permission-to-publish/"
        )
    return {
        "file": path.name,
        "source": "National Archives of Ireland census data, obtained via Gra",
        "county": "Donegal",
        "census_year": year,
        "ded": ded,
        "origin_repository": GRA_REPOSITORY,
        "origin_path": GRA_DATA_PATH.format(filename=path.name),
        "repository_reference_commit": GRA_REFERENCE_COMMIT,
        "upstream_generation_commit": "unknown",
        "retrieval_method": "Adopted from the Gra repository; original NAI download date and individual Gra generation commit unknown",
        "date_acquired": "unknown",
        "date_first_seen": FIRST_SEEN,
        "licence_note": licence,
        "sha256": sha256_file(path),
    }


def census_files() -> list[Path]:
    if not SOURCE_DIR.is_dir():
        raise FileNotFoundError(f"Source directory not found: {SOURCE_DIR.relative_to(ROOT)}")
    return sorted(p for p in SOURCE_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".csv")


def register_files() -> list[Path]:
    base = MANIFEST.parent / REGISTER_DIR
    if not base.is_dir():
        return []
    return sorted(base.glob("*/raw/*.csv"))


def register_name(path: Path) -> str:
    return path.relative_to(MANIFEST.parent).as_posix()


def register_metadata(path: Path, acquired: str) -> dict[str, str]:
    name = register_name(path)
    if name not in REGISTER_DESCRIPTIONS:
        raise ValueError(f"No description for register file {name}; add it to REGISTER_DESCRIPTIONS")
    source, locator = REGISTER_DESCRIPTIONS[name]
    return {
        "file": name,
        "source": source,
        "county": "Donegal",
        "census_year": "not applicable",
        "ded": "not applicable",
        "origin_repository": NLI_PAGE_PATTERN,
        "origin_path": locator,
        "repository_reference_commit": "not applicable (own transcription)",
        "upstream_generation_commit": "not applicable (own transcription)",
        "retrieval_method": (
            f"{OWN_TRANSCRIPTION} from the NLI page images: first reading by Claude, second reading by "
            "Gemini, differences adjudicated by the user. Changed only by reviewed adjudication commits; "
            "run register-update after each one. See data/source/nli_parish/tawnawilly/SCHEMA.md."
        ),
        "date_acquired": acquired,
        "date_first_seen": acquired,
        "licence_note": REGISTER_LICENCE,
        "sha256": sha256_file(path),
    }


def read_manifest() -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError("Manifest columns do not match the required schema.")
        return list(reader)


def write_manifest(rows: list[dict[str, str]]) -> None:
    with MANIFEST.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def register_add() -> int:
    rows = read_manifest()
    listed = {row["file"] for row in rows}
    today = date.today().isoformat()
    added = []
    for path in register_files():
        if register_name(path) not in listed:
            rows.append(register_metadata(path, today))
            added.append(register_name(path))
    if not added:
        print("No register files to add.")
        return 0
    write_manifest(rows)
    print(f"Added {len(added)} register file(s) to {display_path(MANIFEST)}: " + ", ".join(added))
    return 0


def register_update() -> int:
    rows = read_manifest()
    changed = []
    for row in rows:
        if not row["file"].startswith(REGISTER_DIR + "/"):
            continue
        path = MANIFEST.parent / row["file"]
        if not path.is_file():
            print(f"Register file is missing: {row['file']}", file=sys.stderr)
            return 1
        digest = sha256_file(path)
        if digest != row["sha256"]:
            row["sha256"] = digest
            changed.append(row["file"])
    if changed:
        write_manifest(rows)
    print(f"register-update: {len(changed)} checksum(s) updated" + (": " + ", ".join(changed) if changed else ""))
    return 0


def create_manifest() -> int:
    if MANIFEST.exists():
        print(f"Refusing to overwrite existing manifest: {display_path(MANIFEST)}", file=sys.stderr)
        print("Review it and use verify; do not recreate it to bless changed source files.", file=sys.stderr)
        return 1
    files = census_files()
    if len(files) != EXPECTED_FILES:
        print(f"Expected {EXPECTED_FILES} census CSV files, found {len(files)}.", file=sys.stderr)
        return 1
    rows = [source_metadata(path) for path in files]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Created {display_path(MANIFEST)} with {len(rows)} entries.")
    print("Source files were read only; no census file was modified.")
    return 0


def verify_manifest() -> int:
    if not MANIFEST.is_file():
        print(f"Manifest not found: {display_path(MANIFEST)}", file=sys.stderr)
        print("Run: python tools/source_manifest.py create", file=sys.stderr)
        return 1
    errors: list[str] = []
    with MANIFEST.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            errors.append("Manifest columns do not match the required schema.")
            rows = []
        else:
            rows = list(reader)
    names = [row.get("file", "") for row in rows]
    register_rows = [row for row in rows if row.get("file", "").startswith(REGISTER_DIR + "/")]
    rows = [row for row in rows if not row.get("file", "").startswith(REGISTER_DIR + "/")]
    if len(rows) != EXPECTED_FILES:
        errors.append(f"Manifest has {len(rows)} census entries; expected {EXPECTED_FILES}.")
    if len(names) != len(set(names)):
        errors.append("Manifest contains duplicate filenames.")
    actual = {p.name: p for p in census_files()}
    listed = {row.get("file", "") for row in rows}
    for name in sorted(set(actual) - listed):
        errors.append(f"Source file missing from manifest: {name}")
    for name in sorted(listed - set(actual)):
        errors.append(f"Manifest file is missing from source directory: {name}")
    for row in rows:
        name = row.get("file", "")
        path = actual.get(name)
        if path is None:
            continue
        expected = row.get("sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            errors.append(f"Invalid SHA-256 value for {name}")
        elif sha256_file(path) != expected:
            errors.append(f"SHA-256 mismatch: {name}")
        for field in FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"Blank manifest field {field!r} for {name}")
        # The two Grá provenance checks apply to files adopted from Grá. A file refreshed
        # directly from NAI by tools/refresh_census.py records its own provenance.
        if row.get("retrieval_method", "").startswith(ADOPTED_FROM_GRA):
            if row.get("upstream_generation_commit") != "unknown":
                errors.append(f"Upstream generation commit must remain 'unknown' unless evidenced: {name}")
            if row.get("repository_reference_commit") != GRA_REFERENCE_COMMIT:
                errors.append(f"Unexpected Grá repository reference commit: {name}")
        elif not row.get("retrieval_method", "").startswith(DIRECT_FROM_NAI):
            errors.append(f"Unrecognised retrieval method for {name}")
    # Own parish-register transcriptions: every raw file is listed and every listed file is present.
    actual_register = {register_name(p): p for p in register_files()}
    listed_register = {row.get("file", "") for row in register_rows}
    for name in sorted(set(actual_register) - listed_register):
        errors.append(f"Register file missing from manifest: {name}")
    for name in sorted(listed_register - set(actual_register)):
        errors.append(f"Manifest register file is missing from source directory: {name}")
    for row in register_rows:
        name = row.get("file", "")
        path = actual_register.get(name)
        if path is None:
            continue
        expected = row.get("sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            errors.append(f"Invalid SHA-256 value for {name}")
        elif sha256_file(path) != expected:
            errors.append(f"SHA-256 mismatch: {name} (after a review, run: python tools/source_manifest.py register-update)")
        for field in FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"Blank manifest field {field!r} for {name}")
        if not row.get("retrieval_method", "").startswith(OWN_TRANSCRIPTION):
            errors.append(f"Unrecognised retrieval method for {name}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"source manifest: ok ({len(rows)} census files, {len(register_rows)} register files, SHA-256 verified)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "verify", "register-add", "register-update"))
    args = parser.parse_args()
    try:
        return {"create": create_manifest, "verify": verify_manifest,
                "register-add": register_add, "register-update": register_update}[args.command]()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
