# 1926 census refresh from NAI

Status: implemented 2026-11-10 (WP22). Not yet run against the live NAI service. See "Assumptions to confirm on the first live run".

NAI publishes transcription corrections to the 1926 census from time to time. `tools/refresh_census_1926.py` replaces the preserved 1926 source files with the current NAI data, all DEDs together or none.

## The rule

The CSV saved is what NAI supplied. No column is added, removed, renamed or reordered, no value is cleaned, nothing is merged or corrected, and the format is not converted. The API returns one CSV per page, each with a header line. The saved file is page 1 as received followed by the data lines of the later pages. Only the repeated header lines are dropped. Acquisition facts go in a manifest, never in the CSV. Analysis, corrections and enrichment belong in downstream files (DATA_ARCHITECTURE.md, section 4).

## What is replaced and what is never touched

| Path | Treatment |
|---|---|
| `data/source/census/<DED>_1926.csv` | Replaced. The manifest-covered original. One file per DED already held. |
| `data/census/<DED>_1926.csv` | Replaced, where it exists and is byte-identical to the original (Donegal, Laghy, Tawnawully, Tullynaught). If it differs the run stops. |
| `data/source/manifest.csv` | The rows for the refreshed files are updated in the same transaction (provenance, date, SHA-256). Other rows are untouched. |
| `data/census/1926_<DED>.csv` | Never touched. `1926_Clogher.csv` holds about 500 researcher-filled relationship values. |
| 1901 and 1911 files | Never touched. |
| `townlands/`, `docs/`, `data/processed/` | Never touched. Derived census records are not regenerated (see below). |

DEDs are discovered from the existing `*_1926.csv` files and their Logainm IDs are resolved from `data/processed/places/places.csv`. The place register holds the county only as an ID, so the tool maps 100013 to Donegal and checks that name against each existing file.

The Clogher request returns both the Clogher and Magheraclogher DEDs (the search is a substring match). The source file keeps the whole response, as it did before, so it holds 3627 rows, not the 665 Clogher rows.

## Run it

Local (needs `pip install requests`):

    python tools/refresh_census_1926.py --all            # dry run: stage, validate, report
    python tools/refresh_census_1926.py --all --apply    # replace everything, or nothing
    python tools/refresh_census_1926.py --ded-id 1372439 # stage and report one DED (never replaces)

GitHub: Actions, "Refresh 1926 census from NAI", Run workflow. Leave "apply" ticked to replace and commit, or untick it for a dry run. On success the workflow pushes a branch named `census-1926-refresh-<UTC stamp>` for review (the Logainm snapshot convention). It fails with nothing changed if any DED fails. The manifest and comparison report are attached to the run as an artifact. No secret is needed.

Both paths run `python tools/validate.py` after replacing. The workflow also fails if any file outside the list above would change.

## How a download is checked

Every DED is staged outside the repository and checked before anything is replaced:

- Complete: an empty page ends the data, and the pages must add up to the rows in the file. A short page does not end it, so a server that caps the page size is still read in full. A page that repeats the previous one stops the run.
- Valid CSV: UTF-8, every row has the header's field count.
- Same schema: column names and order equal the existing file. Any change stops the run and must be reported to Mike.
- Expected DED and county are present. Any other DED value must contain the query name (as Magheraclogher does for Clogher). `a_id` is present and unique.
- Not suspiciously small: more than 10% fewer records than before is treated as incomplete. Use `--allow-shrink` once checked.
- Retries with backoff on network errors, 429 and 5xx. 60 second timeout. One second between requests.

Replacement keeps a backup of every file, verifies each SHA-256 and the source manifest afterwards, and restores everything if any step fails.

## Outputs

Written to `data/source/census_refresh/<UTC stamp>/` (and to the workflow artifact):

- `refresh_manifest.csv`: timestamp, endpoint, query, DED name and Logainm ID, county, census year, records, pages, SHA-256 of the download, previous and new hash, row counts, validation status.
- `comparison_report.md`: per DED, previous and new counts, added, removed, changed and unchanged rows (matched on `a_id`). For Clogher it also compares the new NAI rows with the working copy `1926_Clogher.csv`, for review only.
- `changes.csv`: every added, removed and changed value, each changed value labelled `serialisation` or `substantive`.

The comparison reads both files and writes nothing to either.

## The first refresh will look large

The existing 1926 files in `data/source/census/` were written by GRA through pandas, so they are not exactly as NAI supplied. They use CRLF line endings, write the text `nan` for blanks and write whole numbers as floats (`70.0`). The refreshed files will not. So on the first refresh every hash changes and most rows show as changed. The report labels a difference that is only `nan` against blank, or `70.0` against `70`, as serialisation only. Review the substantive changes: those are NAI's corrections.

Effect downstream, measured on a rehearsal with simulated NAI data: re-running `python tools/attach_census.py` afterwards changes about 100 `townlands/*/records/census.json` files. Apart from real corrections, the changes are the removal of the text `nan` from the 1926 marriage, relationship and sex fields (it is currently carried through), and a marriage text such as "2 children living" appearing where `children_living` is now a plain number. The refresh does not regenerate these files. Regenerate, review the diff and rebuild as a separate step after the refresh branch is accepted. `tools/validate.py` and the test suite pass with or without that regeneration.

## Assumptions to confirm on the first live run

The build environment could not reach `c26-api.nationalarchives.ie` (its proxy refused the connection), so the live service was not checked. The tool follows GRA's working fetcher (`src/ingest/fetch_census.py`) and the response shape recorded in GAZETTEER_SPEC.md. These points are unconfirmed:

1. The endpoint `https://c26-api.nationalarchives.ie/api/census/query_c26a/census-records.csv` and the parameters `county`, `ded__icontains`, `limit` and `offset`.
2. A request past the end returns an empty body or a header-only CSV, not an error.
3. The service accepts the tool's User-Agent. GRA sent a browser one. If requests are refused, run with `--user-agent`.
4. Whether the response ends with a newline and uses CRLF or LF (the tool keeps whatever it receives).
5. No API key is needed. If the live service asks for one, report it.

A failure on any of these stops the run safely with nothing changed.
