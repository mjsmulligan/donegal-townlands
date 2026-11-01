#!/usr/bin/env python3
"""Create and verify the preserved census-source manifest.

Usage:
    python tools/source_manifest.py create
    python tools/source_manifest.py verify

The manifest identifies the exact local files held in data/source/census/. It
never edits or copies source files. Creation is refused if a manifest already
exists, so changed files cannot silently acquire new trusted checksums.
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
    if not match:
        raise ValueError(f"Unexpected census source filename: {path.name}")
    year, ded = match.groups()
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
    if len(rows) != EXPECTED_FILES:
        errors.append(f"Manifest has {len(rows)} entries; expected {EXPECTED_FILES}.")
    if len(names) != len(set(names)):
        errors.append("Manifest contains duplicate filenames.")
    actual = {p.name: p for p in census_files()}
    listed = set(names)
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
        if row.get("upstream_generation_commit") != "unknown":
            errors.append(f"Upstream generation commit must remain 'unknown' unless evidenced: {name}")
        if row.get("repository_reference_commit") != GRA_REFERENCE_COMMIT:
            errors.append(f"Unexpected Grá repository reference commit: {name}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"source manifest: ok ({len(rows)} files, SHA-256 verified)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "verify"))
    args = parser.parse_args()
    try:
        return create_manifest() if args.command == "create" else verify_manifest()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
