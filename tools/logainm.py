#!/usr/bin/env python3
"""Fetch a dated Logainm snapshot and build the derived place table (WP3).

Provenance: the response parsing and the child-townland query are adapted from
GRA `src/ingest/fetch_places.py` (mjsmulligan/irish-genealogy-research, commit
1dab647, PolyForm Noncommercial; Mike is the copyright holder). The database
code, the person-matching context and the CSV schema were not carried over.

Commands:
    python tools/logainm.py fetch --id 111482 [--id ...] [--date YYYY-MM-DD]
    python tools/logainm.py check [--date YYYY-MM-DD]
    python tools/logainm.py build [--date YYYY-MM-DD]

The API key is read from the LOGAINM_API_KEY environment variable and is never
written to disk. Raw responses are saved byte for byte under
data/source/logainm/<date>/raw/ (ignored by git until the licence question in
docs/GAZETTEER_SPEC.md section 7 is settled). The snapshot manifest, which holds
a SHA-256 for every raw file, is committed. The place table is derived only from
the raw files, so it can be regenerated at any time.

Logainm data: Government of Ireland, CC BY 4.0. Logainm's explanatory notes and
collected citations are outside that licence; `check` reports any such fields.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT_ROOT = ROOT / "data" / "source" / "logainm"
PLACES_CSV = ROOT / "data" / "processed" / "places" / "places.csv"
BASE_URL = "https://www.logainm.ie/api/v1.1/"
PAGE_SIZE = 1000

PLACE_FIELDS = [
    "logainm_id", "name_en", "name_ga", "place_type",
    "ded_id", "civil_parish_id", "barony_id", "county_id",
    "latitude", "longitude", "snapshot_date",
]
MANIFEST_FIELDS = ["file", "kind", "logainm_id", "query", "retrieved_at", "sha256", "licence_note"]
LICENCE_NOTE = (
    "Logainm placename data CC BY 4.0 (Government of Ireland). Logainm notes and "
    "collected citations are excluded from that licence."
)

API_TYPE_MAP = {
    "electoral division": "ded",
    "townland": "townland",
    "civil parish": "civil_parish",
    "barony": "barony",
    "county": "county",
    "province": "province",
    "town": "town",
    "village": "town",
}
# Keys whose presence in a raw response means text outside the CC BY licence.
SUSPECT_KEY = re.compile(r"note|citation|source|reference|etymolog", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Parsing (pure functions, adapted from GRA fetch_places.py)
# ---------------------------------------------------------------------------

def _safe_get(data, key, default=None):
    if not isinstance(data, dict):
        return default
    for k, v in data.items():
        if k.lower() == key.lower():
            return v
    return default


def name_en(place: dict) -> str:
    name = _safe_get(place, "nameEN") or _safe_get(place, "defaultName") or ""
    if not name:
        placenames = _safe_get(place, "placenames", []) or []
        for pn in placenames:
            if _safe_get(pn, "language", "") == "en":
                name = _safe_get(pn, "wording", "") or ""
                if name:
                    break
        if not name and placenames:
            name = _safe_get(placenames[0], "wording", "") or ""
    return name.strip()


def name_ga(place: dict) -> str:
    name = _safe_get(place, "nameGA") or ""
    if not name:
        for pn in _safe_get(place, "placenames", []) or []:
            if _safe_get(pn, "language", "") == "ga":
                name = _safe_get(pn, "wording", "") or ""
                if name:
                    break
    return name.strip()


def place_type(place: dict) -> str:
    categories = _safe_get(place, "categories", [])
    if categories and isinstance(categories, list):
        raw = (_safe_get(categories[0], "nameEN", "") or "").lower().strip()
        return API_TYPE_MAP.get(raw, raw)
    return ""


def coordinates(place: dict):
    geo = _safe_get(place, "geography", {})
    coords = _safe_get(geo, "coordinates", [])
    if isinstance(coords, list) and coords:
        coords = coords[0]
    lat = _safe_get(coords, "latitude")
    lon = _safe_get(coords, "longitude")
    try:
        return (float(lat) if lat else None), (float(lon) if lon else None)
    except (TypeError, ValueError):
        return None, None


def parents(place: dict) -> dict:
    """Parent Logainm IDs from `includedIn`, keyed by level."""
    out = {"county_id": None, "barony_id": None, "civil_parish_id": None, "ded_id": None}
    for item in _safe_get(place, "includedIn", []) or []:
        category = _safe_get(item, "category", {})
        cat_id = str(_safe_get(category, "id", "")).upper()
        cat_name = (_safe_get(category, "nameEN", "") or "").lower()
        try:
            item_id = int(_safe_get(item, "id"))
        except (TypeError, ValueError):
            continue
        if cat_id == "CON" or cat_name == "county":
            out["county_id"] = item_id
        elif cat_id == "BAR" or cat_name == "barony":
            out["barony_id"] = item_id
        elif cat_id == "PAR" or cat_name == "civil parish":
            out["civil_parish_id"] = item_id
        elif cat_id in ("TR", "ED") or cat_name == "electoral division":
            out["ded_id"] = item_id
    return out


def place_row(place: dict, logainm_id: int, snapshot_date: str, root_id=None, root_type=""):
    lat, lon = coordinates(place)
    par = parents(place)
    ptype = place_type(place)
    # As in GRA: when the fetch root is a DED, it is the DED of its children.
    if root_type == "ded" and not par["ded_id"] and ptype == "townland":
        par["ded_id"] = root_id
    return {
        "logainm_id": logainm_id,
        "name_en": name_en(place),
        "name_ga": name_ga(place),
        "place_type": ptype,
        "ded_id": par["ded_id"] or "",
        "civil_parish_id": par["civil_parish_id"] or "",
        "barony_id": par["barony_id"] or "",
        "county_id": par["county_id"] or "",
        "latitude": "" if lat is None else lat,
        "longitude": "" if lon is None else lon,
        "snapshot_date": snapshot_date,
    }


def suspect_paths(data, prefix=""):
    """Paths of keys that look like notes, citations or sources, with non-empty values."""
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if SUSPECT_KEY.search(str(k)) and v not in (None, "", [], {}):
                found.append(path)
            found.extend(suspect_paths(v, path))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            found.extend(suspect_paths(v, f"{prefix}[{i}]"))
    return found


# ---------------------------------------------------------------------------
# Snapshot files
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot_dir(date: str) -> pathlib.Path:
    return SNAPSHOT_ROOT / date


def read_manifest(date: str) -> list[dict]:
    path = snapshot_dir(date) / "snapshot_manifest.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_manifest(date: str, rows: list[dict]) -> None:
    path = snapshot_dir(date) / "snapshot_manifest.csv"
    rows = sorted(rows, key=lambda r: r["file"])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def verify_snapshot(date: str) -> list[str]:
    errors = []
    base = snapshot_dir(date)
    for row in read_manifest(date):
        path = base / row["file"]
        if not path.is_file():
            errors.append(f"missing raw file: {row['file']}")
        elif sha256_bytes(path.read_bytes()) != row["sha256"]:
            errors.append(f"SHA-256 mismatch: {row['file']}")
    return errors


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch(ids: list[int], date: str, rate_delay: float = 0.1) -> int:
    import requests  # imported here so tests and `build` need no network library

    api_key = os.environ.get("LOGAINM_API_KEY")
    if not api_key:
        print("Set the LOGAINM_API_KEY environment variable. The key is never saved.", file=sys.stderr)
        return 1
    base = snapshot_dir(date)
    raw = base / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    manifest = {r["file"]: r for r in read_manifest(date)} if (base / "snapshot_manifest.csv").exists() else {}
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "X-Api-Key": api_key})
    failures = []

    def save(name: str, kind: str, lid, query: str, content: bytes) -> None:
        (raw / name).write_bytes(content)
        manifest[f"raw/{name}"] = {
            "file": f"raw/{name}", "kind": kind, "logainm_id": lid, "query": query,
            "retrieved_at": stamp, "sha256": sha256_bytes(content), "licence_note": LICENCE_NOTE,
        }

    def get_place(lid: int):
        name = f"place_{lid}.json"
        if (raw / name).exists():  # resumable: never refetch inside one snapshot
            return json.loads((raw / name).read_text(encoding="utf-8"))
        resp = session.get(f"{BASE_URL}{lid}")
        resp.raise_for_status()
        save(name, "place", lid, f"GET {lid}", resp.content)
        time.sleep(rate_delay)
        return resp.json()

    for root in ids:
        root_data = get_place(root)
        page = 1
        while True:
            name = f"children_{root}_p{page}.json"
            params = {"PlaceID": root, "CategoryID": "BF", "Page": page}
            if (raw / name).exists():
                data = json.loads((raw / name).read_text(encoding="utf-8"))
            else:
                resp = session.get(BASE_URL, params=params)
                resp.raise_for_status()
                save(name, "children", root, f"GET ?PlaceID={root}&CategoryID=BF&Page={page}", resp.content)
                data = resp.json()
                time.sleep(rate_delay)
            results = _safe_get(data, "results", []) or []
            for summary in results:
                try:
                    cid = int(_safe_get(summary, "id"))
                except (TypeError, ValueError):
                    failures.append(f"unparseable child id under {root}: {_safe_get(summary, 'id')}")
                    continue
                try:
                    get_place(cid)
                except Exception as exc:  # keep going, report at the end
                    failures.append(f"{cid}: {exc}")
            total = _safe_get(data, "count") or _safe_get(data, "total")
            if not results or len(results) < PAGE_SIZE:
                break
            if total is not None and page * PAGE_SIZE >= int(total):
                break
            page += 1
        print(f"root {root} ({name_en(root_data)}): done")
    write_manifest(date, list(manifest.values()))
    for line in failures:
        print(f"WARNING: {line}", file=sys.stderr)
    print(f"snapshot {date}: {len(manifest)} files; run `check` before committing anything")
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# Check and build
# ---------------------------------------------------------------------------

def check(date: str) -> int:
    errors = verify_snapshot(date)
    base = snapshot_dir(date)
    flagged = {}
    for row in read_manifest(date):
        path = base / row["file"]
        if path.is_file():
            paths = suspect_paths(json.loads(path.read_text(encoding="utf-8")))
            if paths:
                flagged[row["file"]] = sorted(set(re.sub(r"\[\d+\]", "[]", p) for p in paths))
    for err in errors:
        print(err, file=sys.stderr)
    if flagged:
        keys = sorted({p for v in flagged.values() for p in v})
        print(f"{len(flagged)} raw files hold fields that may be notes or citations (outside CC BY 4.0):")
        for key in keys:
            print(f"  {key}")
        print("Do not commit raw files until Mike has decided.")
    elif not errors:
        print("snapshot ok: checksums match, no note or citation fields found")
    return 1 if errors else 0


def build_rows(date: str) -> list[dict]:
    base = snapshot_dir(date)
    manifest = read_manifest(date)
    roots = {}
    for row in manifest:
        if row["kind"] == "children":
            roots[int(row["logainm_id"])] = True
    rows = {}
    for row in manifest:
        if row["kind"] != "place":
            continue
        lid = int(row["logainm_id"])
        data = json.loads((base / row["file"]).read_text(encoding="utf-8"))
        rows[lid] = (data, row)
    out = {}
    root_types = {lid: place_type(rows[lid][0]) for lid in roots if lid in rows}
    parent_of = {}
    for row in manifest:  # child -> root, from the child list files
        if row["kind"] == "children":
            data = json.loads((base / row["file"]).read_text(encoding="utf-8"))
            for item in _safe_get(data, "results", []) or []:
                try:
                    parent_of.setdefault(int(_safe_get(item, "id")), int(row["logainm_id"]))
                except (TypeError, ValueError):
                    pass
    for lid, (data, _) in rows.items():
        root = parent_of.get(lid)
        out[lid] = place_row(data, lid, date, root, root_types.get(root, ""))
    return [out[k] for k in sorted(out)]


def write_places(rows: list[dict], path: pathlib.Path = PLACES_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PLACE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(date: str) -> int:
    errors = verify_snapshot(date)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    rows = build_rows(date)
    write_places(rows)
    print(f"wrote {PLACES_CSV.relative_to(ROOT)}: {len(rows)} places")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("fetch", "check", "build"))
    parser.add_argument("--id", type=int, action="append", help="Logainm ID of a DED (repeatable)")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="snapshot date, YYYY-MM-DD")
    parser.add_argument("--rate-delay", type=float, default=0.1)
    args = parser.parse_args()
    if args.command == "fetch":
        if not args.id:
            parser.error("fetch needs at least one --id")
        return fetch(args.id, args.date, args.rate_delay)
    return check(args.date) if args.command == "check" else build(args.date)


if __name__ == "__main__":
    raise SystemExit(main())
