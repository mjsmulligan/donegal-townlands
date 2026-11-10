#!/usr/bin/env python3
"""Refresh the preserved 1926 census source files from the National Archives of Ireland (NAI).

Usage:
    python tools/refresh_census_1926.py --all                 # stage, validate, report (nothing replaced)
    python tools/refresh_census_1926.py --all --apply         # as above, then replace every file or none
    python tools/refresh_census_1926.py --ded-id 1372439      # stage and report one DED (never replaces)

Source integrity (docs/DATA_ARCHITECTURE.md, "preserve the original unchanged"):
    The CSV saved is the NAI response as supplied. No column is added, removed,
    renamed or reordered and no value is cleaned. The API returns one CSV per page,
    each with its own header line. The saved file is the first page as received,
    followed by the data lines of each later page. Only the repeated header lines
    are dropped, which is the one unavoidable step in joining pages. Acquisition
    metadata is kept in a separate manifest, never in the CSV.

What is replaced (Mike, 2026-11-10):
    data/source/census/<DED>_1926.csv     the manifest-covered original
    data/census/<DED>_1926.csv            its byte-identical working copy, where one exists
    data/source/manifest.csv              rows for the refreshed files only
    data/census/1926_<DED>.csv            NEVER touched. It carries researcher-filled values
                                          (Clogher). The comparison report shows how the new
                                          NAI rows differ from it, for review only.

Transaction: every DED is downloaded to a staging directory outside the repository and
validated first. Nothing in the repository changes unless every DED passes. If any step
of the replacement fails, every file is restored from backup.

Reference: the pagination, retry and endpoint approach is adapted from GRA
`src/ingest/fetch_census.py` (mjsmulligan/irish-genealogy-research, commit 1dab647;
Mike is the copyright holder). Its database and place_authority code, its pandas
re-serialisation and its census_year filtering were not carried over, because they
would alter the file as supplied.

NAI 1926 Census data: CC BY 4.0. Attribution to the National Archives of Ireland is
required, and modifications must be identified when sharing.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import os
import pathlib
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

ENDPOINT = "https://c26-api.nationalarchives.ie/api/census/query_c26a/census-records.csv"
CENSUS_YEAR = 1926
PAGE_SIZE = 1000
MAX_PAGES = 200
# The place register stores the county only as a Logainm ID. The project is Donegal
# only (CLAUDE.md, Scope). The name is cross-checked against every existing snapshot.
COUNTY_NAMES = {"100013": "Donegal"}
RETRY_STATUSES = {429, 500, 502, 503, 504}
USER_AGENT = "donegal-townlands-census-refresh (+https://github.com/mjsmulligan/donegal-townlands)"
SHRINK_LIMIT = 0.9
REQUIRED_COLUMNS = ("county", "ded", "a_id")

MANIFEST_FIELDS = [
    "run_id", "acquired_utc", "source_endpoint", "query", "ded_name", "logainm_ded_id",
    "county", "census_year", "records_retrieved", "pages", "sha256_downloaded",
    "previous_sha256", "new_sha256", "byte_identical_to_previous", "rows_added",
    "rows_removed", "rows_changed", "rows_changed_serialisation_only", "rows_unchanged", "deds_in_file",
    "validation_status", "replaced",
]
CHANGE_FIELDS = ["ded", "a_id", "change", "field", "old_value", "new_value",
                 "first_name", "surname", "townland", "kind"]


class RefreshError(Exception):
    """A download, validation or replacement problem. The run aborts safely."""


class TransientError(Exception):
    """A network failure that is worth retrying."""


@dataclass
class Paths:
    source_dir: pathlib.Path
    working_dir: pathlib.Path
    manifest: pathlib.Path
    refresh_dir: pathlib.Path
    places: pathlib.Path


def default_paths() -> Paths:
    return Paths(
        source_dir=ROOT / "data" / "source" / "census",
        working_dir=ROOT / "data" / "census",
        manifest=ROOT / "data" / "source" / "manifest.csv",
        refresh_dir=ROOT / "data" / "source" / "census_refresh",
        places=ROOT / "data" / "processed" / "places" / "places.csv",
    )


@dataclass
class Response:
    status: int
    headers: dict
    content: bytes


@dataclass
class Dataset:
    ded_name: str
    ded_id: str
    county: str
    filename: str
    source_path: pathlib.Path
    mirrors: list = field(default_factory=list)
    working_copy: pathlib.Path | None = None


@dataclass
class Download:
    content: bytes
    pages: int
    page_rows: list


@dataclass
class Result:
    dataset: Dataset
    status: str = "pending"
    staged: pathlib.Path | None = None
    records: int = 0
    pages: int = 0
    sha256: str = ""
    previous_sha256: str = ""
    byte_identical: bool = False
    added: int = 0
    removed: int = 0
    changed: int = 0
    changed_serialisation: int = 0
    unchanged: int = 0
    deds_in_file: dict = field(default_factory=dict)
    changes: list = field(default_factory=list)
    working_compare: dict | None = None
    error: str = ""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------- place register

def load_deds(places_csv: pathlib.Path) -> list[dict]:
    with places_csv.open(encoding="utf-8", newline="") as stream:
        return [r for r in csv.DictReader(stream) if r.get("place_type") == "ded"]


def discover_datasets(paths: Paths) -> list[Dataset]:
    """Find every existing 1926 DED file and resolve its Logainm ID and county."""
    if not paths.source_dir.is_dir():
        raise RefreshError(f"Source directory not found: {paths.source_dir}")
    deds = load_deds(paths.places)
    datasets = []
    for path in sorted(paths.source_dir.glob(f"*_{CENSUS_YEAR}.csv")):
        name = path.name[: -len(f"_{CENSUS_YEAR}.csv")]
        matches = [d for d in deds if d["name_en"].casefold() == name.casefold()]
        if len(matches) != 1:
            raise RefreshError(
                f"{path.name}: expected exactly one DED named {name!r} in the place register, found {len(matches)}")
        ded = matches[0]
        county = COUNTY_NAMES.get(ded["county_id"])
        if not county:
            raise RefreshError(f"{path.name}: county ID {ded['county_id']!r} is not known to this tool")
        ds = Dataset(ded_name=ded["name_en"], ded_id=ded["logainm_id"], county=county,
                     filename=path.name, source_path=path)
        mirror = paths.working_dir / path.name
        if mirror.exists():
            if sha256_file(mirror) != sha256_file(path):
                raise RefreshError(
                    f"{mirror} exists but is not identical to {path}. It is not a plain copy, so it will not be "
                    "overwritten. Report this to Mike before refreshing.")
            ds.mirrors.append(mirror)
        wc = paths.working_dir / f"{CENSUS_YEAR}_{name}.csv"
        if wc.exists():
            ds.working_copy = wc
        datasets.append(ds)
    if not datasets:
        raise RefreshError(f"No *_{CENSUS_YEAR}.csv files found in {paths.source_dir}")
    return datasets


# ---------------------------------------------------------------------- download

def make_http_get(url: str = ENDPOINT, user_agent: str = USER_AGENT, timeout: float = 60.0
                  ) -> Callable[[dict], Response]:
    import requests  # imported here so tests and the other tools need no network library

    def get(params: dict) -> Response:
        try:
            r = requests.get(url, params=params, headers={"User-Agent": user_agent}, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            raise TransientError(str(exc)) from exc
        return Response(r.status_code, dict(r.headers), r.content)
    return get


def request_with_retries(get: Callable[[dict], Response], params: dict, retries: int,
                         sleep: Callable[[float], None]) -> Response:
    last = ""
    for attempt in range(retries):
        try:
            resp = get(params)
        except TransientError as exc:
            last = str(exc)
        else:
            if resp.status == 200:
                return resp
            snippet = resp.content[:200].decode("utf-8", "replace").strip()
            if resp.status not in RETRY_STATUSES:
                raise RefreshError(f"HTTP {resp.status} from NAI for {params}: {snippet}")
            last = f"HTTP {resp.status}: {snippet}"
        if attempt < retries - 1:
            sleep(2 ** attempt)
    raise RefreshError(f"NAI request failed after {retries} attempts for {params}: {last}")


def parse_csv(content: bytes) -> list[list[str]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RefreshError(f"Response is not valid UTF-8: {exc}") from exc
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        raise RefreshError(f"Response is not valid CSV: {exc}") from exc
    return [r for r in rows if r]


def check_page(resp: Response) -> None:
    ctype = next((v for k, v in resp.headers.items() if k.lower() == "content-type"), "")
    head = resp.content[:1].strip()
    if "json" in ctype.lower() or "html" in ctype.lower() or head in (b"{", b"<", b"["):
        raise RefreshError(f"NAI returned an error or non-CSV body (content-type {ctype!r}): "
                           f"{resp.content[:200].decode('utf-8', 'replace')!r}")


def download_ded(ded_name: str, county: str, get: Callable[[dict], Response], *,
                 page_size: int = PAGE_SIZE, delay: float = 1.0, retries: int = 4,
                 sleep: Callable[[float], None] = time.sleep, max_pages: int = MAX_PAGES) -> Download:
    """Fetch every page. The end of the data is an empty page, never a short page,
    so a server that caps the page size below the requested limit is still read in full."""
    content = b""
    header = None
    previous = None
    page_rows: list[int] = []
    offset = 0
    for _ in range(max_pages):
        params = {"county": county, "ded__icontains": ded_name, "limit": page_size, "offset": offset}
        resp = request_with_retries(get, params, retries, sleep)
        body = resp.content
        if not body.strip():
            break
        check_page(resp)
        newline = body.find(b"\n")
        if newline == -1:
            break  # a header with no data
        page_header, data = body[: newline + 1], body[newline + 1:]
        rows = len(parse_csv(body)) - 1
        if rows <= 0:
            break
        if header is None:
            header = page_header
        elif page_header != header:
            raise RefreshError(f"Page at offset {offset} has a different header from page 1")
        if previous is not None and data == previous:
            raise RefreshError(f"Page at offset {offset} repeats the previous page: the server ignored the offset")
        previous = data
        if not content:
            content = body
        else:
            if not content.endswith(b"\n"):
                content += b"\r\n" if header.endswith(b"\r\n") else b"\n"
            content += data
        page_rows.append(rows)
        offset += rows
        sleep(delay)
    else:
        raise RefreshError(f"Pagination did not finish within {max_pages} pages")
    return Download(content=content, pages=len(page_rows), page_rows=page_rows)


# -------------------------------------------------------------------- validation

def validate_download(dl: Download, ds: Dataset, previous: bytes, allow_shrink: bool = False) -> dict:
    """Return the parsed facts about a download, or raise RefreshError."""
    if not dl.content:
        raise RefreshError("NAI returned no records")
    rows = parse_csv(dl.content)
    header, data = rows[0], rows[1:]
    old_rows = parse_csv(previous)
    if header != old_rows[0]:
        raise RefreshError(
            "NAI column names or order differ from the preserved snapshot. This is a schema change that "
            "affects downstream code and must be reported to Mike before any file is replaced. "
            f"Old: {old_rows[0]} New: {header}")
    for column in REQUIRED_COLUMNS:
        if column not in header:
            raise RefreshError(f"Required column {column!r} is missing")
    bad = [i for i, r in enumerate(data, start=2) if len(r) != len(header)]
    if bad:
        raise RefreshError(f"{len(bad)} rows do not have {len(header)} fields (first at line {bad[0]})")
    if sum(dl.page_rows) != len(data):
        raise RefreshError(f"Pages reported {sum(dl.page_rows)} rows but the file holds {len(data)}")
    idx = {name: header.index(name) for name in REQUIRED_COLUMNS}
    counties = {r[idx["county"]] for r in data}
    if {c.casefold() for c in counties} != {ds.county.casefold()}:
        raise RefreshError(f"Unexpected county values {sorted(counties)}; expected {ds.county!r}")
    deds: dict[str, int] = {}
    for r in data:
        deds[r[idx["ded"]]] = deds.get(r[idx["ded"]], 0) + 1
    if ds.ded_name.casefold() not in {d.casefold() for d in deds}:
        raise RefreshError(f"DED {ds.ded_name!r} is not represented; found {sorted(deds)}")
    stray = [d for d in deds if ds.ded_name.casefold() not in d.casefold()]
    if stray:
        raise RefreshError(f"DED values that do not match the query {ds.ded_name!r}: {stray}")
    ids = [r[idx["a_id"]] for r in data]
    if any(not i.strip() for i in ids):
        raise RefreshError("Blank a_id values found")
    if len(set(ids)) != len(ids):
        raise RefreshError("Duplicate a_id values found, which suggests overlapping pages")
    old_count = len(old_rows) - 1
    if not allow_shrink and len(data) < SHRINK_LIMIT * old_count:
        raise RefreshError(
            f"{len(data)} records is more than 10% fewer than the previous {old_count}. "
            "Treated as an incomplete download. Re-run with --allow-shrink once checked.")
    return {"header": header, "records": len(data), "deds": deds}


# ------------------------------------------------------------------- comparison

def keyed(content: bytes) -> tuple[list[str], dict[str, list[str]]]:
    rows = parse_csv(content)
    key = rows[0].index("a_id")
    return rows[0], {r[key]: r for r in rows[1:]}


def serialisation_only(old: str, new: str) -> bool:
    """True where two values differ only in how they were written: the string 'nan' for a
    blank, or a whole number written as a float ('70.0' for '70'). The existing snapshots
    were written through pandas, which produced both. Used to label differences in the
    audit report. It never alters data."""
    def norm(value: str) -> str:
        return "" if value.strip().lower() == "nan" else value
    a, b = norm(old), norm(new)
    if a == b:
        return True
    try:
        return a != "" and b != "" and float(a) == float(b)
    except ValueError:
        return False


def compare(old: bytes, new: bytes, ded_label: str, new_filter: Callable[[list, list], bool] | None = None) -> dict:
    """Audit comparison by a_id. Reads both files, writes nothing."""
    header, old_rows = keyed(old)
    new_header, new_rows = keyed(new)
    if new_filter:
        new_rows = {k: r for k, r in new_rows.items() if new_filter(new_header, r)}
    added = sorted(set(new_rows) - set(old_rows))
    removed = sorted(set(old_rows) - set(new_rows))
    changes, changed, unchanged, ser_rows = [], 0, 0, 0
    field_counts: dict[str, int] = {}
    ctx = [header.index(c) for c in ("first_name", "surname", "townland")]
    for a_id in sorted(set(old_rows) & set(new_rows)):
        o, n = old_rows[a_id], new_rows[a_id]
        if o == n:
            unchanged += 1
            continue
        changed += 1
        diffs = [i for i in range(len(header)) if o[i] != n[i]]
        if all(serialisation_only(o[i], n[i]) for i in diffs):
            ser_rows += 1
        for i in diffs:
            name = header[i]
            kind = "serialisation" if serialisation_only(o[i], n[i]) else "substantive"
            if kind == "substantive":
                field_counts[name] = field_counts.get(name, 0) + 1
            changes.append([ded_label, a_id, "changed", name, o[i], n[i], *(n[c] for c in ctx), kind])
    for a_id in added:
        changes.append([ded_label, a_id, "added", "", "", "", *(new_rows[a_id][c] for c in ctx), ""])
    for a_id in removed:
        changes.append([ded_label, a_id, "removed", "", "", "", *(old_rows[a_id][c] for c in ctx), ""])
    return {"added": len(added), "removed": len(removed), "changed": changed, "unchanged": unchanged,
            "changed_serialisation": ser_rows, "old_count": len(old_rows), "new_count": len(new_rows),
            "field_counts": field_counts, "changes": changes}


# ------------------------------------------------------------- staging and runs

def stage_all(datasets: list[Dataset], get, staging: pathlib.Path, *, delay: float, retries: int,
              allow_shrink: bool, sleep: Callable[[float], None] = time.sleep,
              page_size: int = PAGE_SIZE) -> list[Result]:
    """Download and validate every dataset. Failures are recorded, not raised, so the
    report can show all of them, but any failure blocks replacement."""
    staging.mkdir(parents=True, exist_ok=True)
    results = []
    for n, ds in enumerate(datasets):
        res = Result(dataset=ds)
        results.append(res)
        if n:
            sleep(delay)
        try:
            print(f"Fetching {ds.ded_name} (Logainm {ds.ded_id}, {ds.county}) ...", flush=True)
            previous = ds.source_path.read_bytes()
            check_county_against_snapshot(ds, previous)
            dl = download_ded(ds.ded_name, ds.county, get, page_size=page_size, delay=delay,
                              retries=retries, sleep=sleep)
            facts = validate_download(dl, ds, previous, allow_shrink)
            staged = staging / ds.filename
            staged.write_bytes(dl.content)
            if staged.read_bytes() != dl.content:
                raise RefreshError("Staged file does not match the downloaded bytes")
            cmp = compare(previous, dl.content, ds.ded_name)
            res.staged = staged
            res.records, res.pages = facts["records"], dl.pages
            res.sha256 = sha256_bytes(dl.content)
            res.previous_sha256 = sha256_bytes(previous)
            res.byte_identical = dl.content == previous
            res.added, res.removed = cmp["added"], cmp["removed"]
            res.changed, res.unchanged = cmp["changed"], cmp["unchanged"]
            res.changed_serialisation = cmp["changed_serialisation"]
            res.changes = cmp["changes"]
            res.deds_in_file = facts["deds"]
            if ds.working_copy is not None:
                exact = lambda h, r, name=ds.ded_name.casefold(): r[h.index("ded")].casefold() == name  # noqa: E731
                wc = compare(ds.working_copy.read_bytes(), dl.content, f"{ds.ded_name} (working copy)", exact)
                res.working_compare = wc
            res.status = "passed"
        except (RefreshError, OSError) as exc:
            res.status = "failed"
            res.error = str(exc)
            print(f"  FAILED: {exc}", file=sys.stderr, flush=True)
    return results


def check_county_against_snapshot(ds: Dataset, previous: bytes) -> None:
    rows = parse_csv(previous)
    col = rows[0].index("county")
    counties = {r[col].casefold() for r in rows[1:]}
    if counties != {ds.county.casefold()}:
        raise RefreshError(f"County {ds.county!r} does not match the existing snapshot values {sorted(counties)}")


# ----------------------------------------------------------------------- outputs

def manifest_rows(results: list[Result], run_id: str, acquired: str, replaced: str) -> list[dict]:
    rows = []
    for r in results:
        ds = r.dataset
        ok = r.status == "passed"
        rows.append({
            "run_id": run_id, "acquired_utc": acquired, "source_endpoint": ENDPOINT,
            "query": f"county={ds.county}&ded__icontains={ds.ded_name}&limit={PAGE_SIZE} (all pages)",
            "ded_name": ds.ded_name, "logainm_ded_id": ds.ded_id, "county": ds.county,
            "census_year": CENSUS_YEAR, "records_retrieved": r.records if ok else "",
            "pages": r.pages if ok else "", "sha256_downloaded": r.sha256,
            "previous_sha256": r.previous_sha256,
            "new_sha256": r.sha256 if (ok and replaced == "yes") else "",
            "byte_identical_to_previous": ("yes" if r.byte_identical else "no") if ok else "",
            "rows_added": r.added if ok else "", "rows_removed": r.removed if ok else "",
            "rows_changed": r.changed if ok else "",
            "rows_changed_serialisation_only": r.changed_serialisation if ok else "", "rows_unchanged": r.unchanged if ok else "",
            "deds_in_file": "; ".join(f"{d}={n}" for d, n in sorted(r.deds_in_file.items())),
            "validation_status": "passed" if ok else f"failed: {r.error}", "replaced": replaced,
        })
    return rows


def render_csv(fields: list[str], rows: list[list]) -> str:
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(fields)
    writer.writerows(rows)
    return out.getvalue()


def render_report(results: list[Result], run_id: str, acquired: str, replaced: str) -> str:
    L = [f"# 1926 census refresh {run_id}", "",
         f"- Acquired (UTC): {acquired}",
         f"- Source: {ENDPOINT}",
         f"- Files replaced in the repository: {replaced}",
         "- Source: National Archives of Ireland 1926 Census, CC BY 4.0. The CSVs are saved as supplied by NAI.",
         "- This report is an audit aid. It does not modify any data.", "",
         "## Summary", "",
         "| DED | Logainm ID | Previous records | New records | Added | Removed | Changed | of which serialisation only | Unchanged | Bytes identical | Status |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        ok = r.status == "passed"
        prev = r.removed + r.changed + r.unchanged if ok else "n/a"
        L.append(f"| {r.dataset.ded_name} | {r.dataset.ded_id} | {prev} | {r.records if ok else 'n/a'} | "
                 f"{r.added if ok else 'n/a'} | {r.removed if ok else 'n/a'} | {r.changed if ok else 'n/a'} | "
                 f"{r.changed_serialisation if ok else 'n/a'} | {r.unchanged if ok else 'n/a'} | {('yes' if r.byte_identical else 'no') if ok else 'n/a'} | "
                 f"{'passed' if ok else 'FAILED'} |")
    L += ["", "Rows are matched on `a_id`. The previous snapshots were written by GRA through pandas, which "
          "used CRLF line endings, wrote the text `nan` for blanks and wrote whole numbers as floats "
          "(`70.0`). NAI's own file has none of these. A difference that is only that is labelled "
          "serialisation only and is not a correction by NAI. Hashes change on a first refresh regardless. "
          "Substantive differences are the ones to review.", ""]
    for r in results:
        L += [f"## {r.dataset.ded_name}", ""]
        if r.status != "passed":
            L += [f"Validation failed: {r.error}", ""]
            continue
        L.append("DEDs in the file: " + ", ".join(f"{d} ({n})" for d, n in sorted(r.deds_in_file.items())))
        L.append("")
        if r.added or r.removed or r.changed:
            L.append(f"Added {r.added}, removed {r.removed}, changed {r.changed} "
                     f"({r.changed_serialisation} serialisation only). First substantive changes "
                     "(full list in changes.csv, column kind):")
            L.append("")
            shown = [c for c in r.changes if c[2] == "changed" and c[9] == "substantive"][:20]
            for c in shown:
                L.append(f"- a_id {c[1]} {c[6]} {c[7]} ({c[8]}): {c[3]} was {c[4]!r}, now {c[5]!r}")
            L.append("")
        else:
            L += ["No row differs from the previous snapshot.", ""]
        wc = r.working_compare
        if wc is not None:
            L += [f"### New NAI rows against the working copy {r.dataset.working_copy.name}", "",
                  "The working copy is never modified. It holds researcher-filled values, so differences are expected "
                  "and are listed here for review only.", "",
                  f"- Working copy records: {wc['old_count']}. NAI records for this DED: {wc['new_count']}.",
                  f"- In NAI only: {wc['added']}. In the working copy only: {wc['removed']}. "
                  f"Rows that differ: {wc['changed']} ({wc['changed_serialisation']} serialisation only). "
                  f"Identical rows: {wc['unchanged']}.", ""]
            if wc["field_counts"]:
                L.append("Substantively differing fields (count of rows):")
                L.append("")
                for name, n in sorted(wc["field_counts"].items(), key=lambda kv: -kv[1]):
                    L.append(f"- {name}: {n}")
                L.append("")
    return "\n".join(L) + "\n"


def all_change_rows(results: list[Result]) -> list[list]:
    rows = []
    for r in results:
        rows += r.changes
        if r.working_compare:
            rows += r.working_compare["changes"]
    return rows


def write_outputs(results: list[Result], directory: pathlib.Path, run_id: str, acquired: str, replaced: str) -> list[pathlib.Path]:
    directory.mkdir(parents=True, exist_ok=True)
    mrows = manifest_rows(results, run_id, acquired, replaced)
    files = {
        "refresh_manifest.csv": render_csv(MANIFEST_FIELDS, [[m[f] for f in MANIFEST_FIELDS] for m in mrows]),
        "comparison_report.md": render_report(results, run_id, acquired, replaced),
        "changes.csv": render_csv(CHANGE_FIELDS, all_change_rows(results)),
    }
    out = []
    for name, text in files.items():
        path = directory / name
        path.write_bytes(text.encode("utf-8"))
        out.append(path)
    return out


# ------------------------------------------------------ transactional replacement

def updated_source_manifest(paths: Paths, results: list[Result], acquired_date: str) -> bytes:
    import source_manifest
    with paths.manifest.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        if reader.fieldnames != source_manifest.FIELDS:
            raise RefreshError("data/source/manifest.csv does not have the expected columns")
    by_file = {r.dataset.filename: r for r in results}
    seen = set()
    for row in rows:
        res = by_file.get(row["file"])
        if res is None:
            continue
        seen.add(row["file"])
        ds = res.dataset
        row.update({
            "source": "National Archives of Ireland 1926 census data, downloaded directly from the NAI API",
            "origin_repository": ENDPOINT,
            "origin_path": f"county={ds.county}&ded__icontains={ds.ded_name} (all pages, limit {PAGE_SIZE})",
            "repository_reference_commit": "not applicable (direct NAI download)",
            "upstream_generation_commit": "not applicable (direct NAI download)",
            "retrieval_method": ("Direct download from the NAI 1926 census API by tools/refresh_census_1926.py. "
                                 "Saved as supplied; pages joined with the repeated header lines dropped."),
            "date_acquired": acquired_date,
            "sha256": res.sha256,
        })
    missing = set(by_file) - seen
    if missing:
        raise RefreshError(f"Refreshed files missing from data/source/manifest.csv: {sorted(missing)}")
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=source_manifest.FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def apply_replacement(replacements: list[tuple[pathlib.Path, pathlib.Path]],
                      outputs: list[tuple[pathlib.Path, pathlib.Path]],
                      verify: Callable[[], bool] | None, backup_dir: pathlib.Path) -> None:
    """Replace every target or none. replacements and outputs are (target, new_content_file).
    Outputs are new files in the refresh folder. Any failure restores every file."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    done: list[tuple[pathlib.Path, pathlib.Path | None]] = []
    created_dirs: list[pathlib.Path] = []

    def put(target: pathlib.Path, source: pathlib.Path, n: int) -> None:
        backup = None
        if target.exists():
            backup = backup_dir / f"{n}_{target.name}"
            shutil.copy2(target, backup)
        if not target.parent.exists():
            target.parent.mkdir(parents=True)
            created_dirs.append(target.parent)
        done.append((target, backup))
        tmp = target.with_name(target.name + ".refresh-tmp")
        shutil.copyfile(source, tmp)
        os.replace(tmp, target)
        if sha256_file(target) != sha256_file(source):
            raise RefreshError(f"{target} does not match the validated file after replacement")

    try:
        n = 0
        for target, source in replacements:
            put(target, source, n)
            n += 1
        if verify is not None and not verify():
            raise RefreshError("Source manifest verification failed after replacement")
        for target, source in outputs:
            put(target, source, n)
            n += 1
    except Exception:
        for target, backup in reversed(done):
            if backup is not None:
                shutil.copyfile(backup, target)
            elif target.exists():
                target.unlink()
            tmp = target.with_name(target.name + ".refresh-tmp")
            if tmp.exists():
                tmp.unlink()
        for d in reversed(created_dirs):
            try:
                d.rmdir()
            except OSError:
                pass
        raise


def run(paths: Paths, *, get, ded_ids: list[str] | None, apply: bool, staging: pathlib.Path,
        delay: float = 1.0, retries: int = 4, allow_shrink: bool = False,
        sleep: Callable[[float], None] = time.sleep, verify: Callable[[], bool] | None = None,
        now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
        page_size: int = PAGE_SIZE) -> int:
    datasets = discover_datasets(paths)
    if ded_ids:
        unknown = set(ded_ids) - {d.ded_id for d in datasets}
        if unknown:
            raise RefreshError(f"Logainm DED IDs with no existing 1926 file: {sorted(unknown)}")
        datasets = [d for d in datasets if d.ded_id in ded_ids]
    print(f"DEDs: {', '.join(f'{d.ded_name} ({d.ded_id})' for d in datasets)}")
    moment = now()
    run_id = moment.strftime("%Y%m%dT%H%M%SZ")
    acquired = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    results = stage_all(datasets, get, staging / "downloads", delay=delay, retries=retries,
                        allow_shrink=allow_shrink, sleep=sleep, page_size=page_size)
    failed = [r for r in results if r.status != "passed"]
    report_dir = staging / "report"
    if failed or not apply:
        write_outputs(results, report_dir, run_id, acquired, "no")
        print(f"Report written to {report_dir}")
        if failed:
            print(f"ABORTED: {len(failed)} of {len(results)} DEDs failed. No repository file was changed.",
                  file=sys.stderr)
            return 1
        print("All DEDs passed validation. Dry run: no repository file was changed. Use --all --apply to replace.")
        return 0
    try:
        replacements = []
        for r in results:
            replacements.append((r.dataset.source_path, r.staged))
            replacements += [(m, r.staged) for m in r.dataset.mirrors]
        manifest_new = staging / "source_manifest.new.csv"
        manifest_new.write_bytes(updated_source_manifest(paths, results, moment.strftime("%Y-%m-%d")))
        replacements.append((paths.manifest, manifest_new))
        written = write_outputs(results, staging / "report", run_id, acquired, "yes")
        target_dir = paths.refresh_dir / run_id
        outputs = [(target_dir / p.name, p) for p in written]
        apply_replacement(replacements, outputs, verify, staging / "backup")
    except Exception as exc:
        write_outputs(results, report_dir, run_id, acquired, "no (rolled back)")
        print(f"ABORTED during replacement: {exc}. Every file was restored.", file=sys.stderr)
        return 1
    print(f"Replaced {len(results)} DED files and the source manifest. Report: {paths.refresh_dir / run_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="every existing 1926 DED file")
    parser.add_argument("--ded-id", action="append", metavar="LOGAINM_ID",
                        help="one DED by Logainm ID (repeatable). Stages and reports only.")
    parser.add_argument("--apply", action="store_true", help="replace the files after every DED passes (needs --all)")
    parser.add_argument("--staging", type=pathlib.Path, help="staging directory outside the repository (default: a new temp dir)")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests (default 1)")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds per request (default 60)")
    parser.add_argument("--retries", type=int, default=4, help="attempts per request (default 4)")
    parser.add_argument("--user-agent", default=USER_AGENT)
    parser.add_argument("--allow-shrink", action="store_true",
                        help="accept a DED with more than 10%% fewer records than before")
    args = parser.parse_args(argv)
    if bool(args.all) == bool(args.ded_id):
        parser.error("give exactly one of --all or --ded-id")
    if args.apply and not args.all:
        parser.error("--apply needs --all, so the repository never holds a mixture of old and new snapshots")
    for value in args.ded_id or []:
        if not re.fullmatch(r"\d+", value):
            parser.error(f"Logainm ID must be digits: {value!r}")
    staging = args.staging or pathlib.Path(tempfile.mkdtemp(prefix="census-refresh-"))
    if staging.exists() and any(staging.iterdir()):
        parser.error(f"staging directory is not empty: {staging}")
    paths = default_paths()
    import source_manifest
    try:
        return run(paths, get=make_http_get(ENDPOINT, args.user_agent, args.timeout),
                   ded_ids=args.ded_id, apply=args.apply, staging=staging, delay=args.delay,
                   retries=args.retries, allow_shrink=args.allow_shrink,
                   verify=lambda: source_manifest.verify_manifest() == 0)
    except RefreshError as exc:
        print(f"ABORTED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
