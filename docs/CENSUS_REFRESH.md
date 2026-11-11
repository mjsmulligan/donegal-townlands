# Census refresh from NAI (1901, 1911, 1926)

Status: 1926 run live 2026-11-10 (PR 55). 1901 and 1911 run live the same day (workflow run 42895407366, review branch `census-refresh-1901-1911-20261110T202812Z`, run record `data/source/census_refresh/20261110T202721Z/`).

NAI publishes transcription corrections to its census data from time to time. `tools/refresh_census.py` replaces the preserved source files for the years chosen with the current NAI data, all DEDs and years chosen together or none.

## The rule

The CSV saved is what NAI supplied. No column is added, removed, renamed or reordered, no value is cleaned, nothing is merged or corrected, and the format is not converted. The API returns one CSV per page, each with a header line. The saved file is page 1 as received followed by the data lines of the later pages. Only the repeated header lines are dropped. Acquisition facts go in a manifest, never in the CSV. Analysis, corrections and enrichment belong in downstream files (DATA_ARCHITECTURE.md, section 4).

## What is replaced and what is never touched

| Path | Treatment |
|---|---|
| `data/source/census/<DED>_<year>.csv` | Replaced. The manifest-covered original. One file per DED already held. |
| `data/source/manifest.csv` | The rows for the refreshed files are updated in the same transaction (provenance, date, SHA-256). Other rows are untouched. |
| Years not chosen | Never touched. The workflow guard fails the run if another year's file would change. |
| `townlands/`, `docs/`, `data/processed/` | Never touched. Derived census records are not regenerated (see below). |

DEDs are discovered from the existing `*_1926.csv` files and their Logainm IDs are resolved from `data/processed/places/places.csv`. The place register holds the county only as an ID, so the tool maps 100013 to Donegal and checks that name against each existing file.

The Clogher request returns both the Clogher and Magheraclogher DEDs (the search is a substring match). The source file keeps the whole response, as it did before, so it holds 3627 rows, not the 665 Clogher rows.

## Run it

Local (needs `pip install requests`):

    python tools/refresh_census.py --year 1901 --year 1911 --all           # dry run: stage, validate, report
    python tools/refresh_census.py --year 1901 --year 1911 --all --apply   # replace everything, or nothing
    python tools/refresh_census.py --year 1926 --ded-id 1372439            # stage and report one DED (never replaces)

GitHub: Actions, "Refresh census from NAI", Run workflow. Choose the years, and leave "apply" ticked to replace and commit, or untick it for a dry run. "allow_schema_change" stays unticked unless Mike has seen a dry run that reports a column difference. On success the workflow pushes a branch named `census-refresh-<years>-<UTC stamp>` for review (the Logainm snapshot convention). It fails with nothing changed if any DED fails. The manifest and comparison report are attached to the run as an artifact. No secret is needed.

Both paths run `python tools/validate.py` after replacing. The workflow also fails if any file outside the list above would change.

## How a download is checked

Every DED is staged outside the repository and checked before anything is replaced:

- Complete: an empty page ends the data, and the pages must add up to the rows in the file. A short page does not end it, so a server that caps the page size is still read in full. A page that repeats the previous one stops the run.
- Valid CSV: UTF-8, every row has the header's field count.
- Same schema: column names and order equal the existing file. Any change stops the run and must be reported to Mike, who can then allow it with `--allow-schema-change`. The one exception: for 1901 and 1911 the absence of `townland_clean` and `ded_clean` (columns GRA added, not NAI's) is expected and is only reported.
- Expected DED and county are present. Any other DED value must contain the query name (as Magheraclogher does for Clogher). The record id (`a_id` for 1926, `id` for 1901 and 1911) is present and unique.
- Not suspiciously small: more than 10% fewer records than before is treated as incomplete. Use `--allow-shrink` once checked.
- Retries with backoff on network errors, 429 and 5xx. 60 second timeout. One second between requests.

Replacement keeps a backup of every file, verifies each SHA-256 and the source manifest afterwards, and restores everything if any step fails.

## 1901 and 1911

NAI serves both years from `https://api-census.nationalarchives.ie/census/query/census-records.csv`, in one response with a `census_year` column. The tool downloads the response once per DED and splits it by `census_year`. The split only selects whole rows, each kept byte for byte (it is quote-aware, so a row with a line break inside a field stays whole). A row with any other `census_year` stops the run. The earlier files carried two GRA columns, `townland_clean` and `ded_clean`, that NAI does not supply. Under the as-supplied principle they are not recreated. `tools/census_links.py` and `tools/gedcom_census.py` fall back to the raw `townland` where `townland_clean` is absent, so townland names will be NAI's own spellings. As with Clogher 1926, the Clogher files hold the Clogher and Magheraclogher DEDs.

First live run (2026-11-10): the endpoint, parameters and column names behaved as assumed. Every DED returned exactly the records already held: 1901 and 1911 for Clogher, Donegal, Laghy, Tawnawully and Tullynaught, none added, none removed. Almost every difference is serialisation (`nan` for a blank, floats for whole numbers). The only substantive differences are about 10 values that GRA's files had as `nan` and NAI writes as the text `None` (language, education, occupation, deafdumb), all in Donegal 1901 and Tullynaught 1901. The two GRA columns are gone from the files, as expected.

There are no working copies. Until 2026-11-11 `data/census/` held byte-identical copies of the originals; it was removed and every tool now reads `data/source/census/`. `tools/attach_census.py` ignores rows whose `ded` is not the file's DED, so the Magheraclogher rows in the Clogher files are not attached to Clogher townlands or listed for spelling review.

## Outputs

`refresh_manifest.csv` and `comparison_report.md` are written to `data/source/census_refresh/<UTC stamp>/` and committed. All three files below are in the workflow artifact `census-refresh-report` (kept 90 days):

- `refresh_manifest.csv`: timestamp, endpoint, query, DED name and Logainm ID, county, census year, records, pages, SHA-256 of the download, previous and new hash, row counts, validation status.
- `comparison_report.md`: per DED, previous and new counts, added, removed, changed and unchanged rows (matched on `a_id`).
- `changes.csv`: every added, removed and changed value, each changed value labelled `serialisation` or `substantive`. It is 7 to 13 MB a run, so it is not committed (decided 2026-11-11). The two runs of 2026-11-10 keep theirs. For any later run it can be regenerated by comparing the source files across the two commits.

The comparison reads both files and writes nothing to either.

## What the first refresh changed (2026-11-10)

The first live run (workflow run of 2026-11-10, branch `census-1926-refresh-20261110T082929Z`, merged in PR 55) replaced all five DEDs. The record is in `data/source/census_refresh/20261110T082907Z/`.

| DED | Logainm ID | Before | After | Added | Removed |
|---|---|---|---|---|---|
| Clogher | 1372439 | 3627 | 3622 | 0 | 5 |
| Donegal | 1372456 | 2352 | 2366 | 15 | 1 |
| Laghy | 1372507 | 994 | 994 | 0 | 0 |
| Tawnawully | 1372542 | 512 | 512 | 0 | 0 |
| Tullynaught | 111482 | 894 | 901 | 17 | 10 |

Nearly every row differs, and almost none of that is formatting. The earlier files came from an older NAI release that GRA had also passed through pandas (the text `nan` for blanks, floats such as `70.0`). Only 0 to 51 changed rows per DED differ in those ways alone. The substantive differences are NAI's own: in the current release `relationship_to_head` is empty and `updated_relationship_to_head`, `updated_religion` and `updated_marriage` are filled for every person, while the stray text in `years_married` and `children_*` (for example `y`, `Own Account`) is mostly gone. NAI's files use CRLF line endings, so line endings are not a difference. The new files contain no `nan`.

Downstream effect: the code reads `updated_relationship_to_head` first, and `tools/validate.py` and the test suite pass. The derived `townlands/*/records/census.json` files were not regenerated. When they are, expect the 1926 relationship, religion and marriage fields to fill in and the `years_married` and `children_*` values to thin out, so census link proposals may change. Review that diff before accepting it.

Clogher: an older file, `data/census/1926_Clogher.csv`, was removed on 2026-11-10. It was thought to hold researcher-filled relationship values. Mike confirmed there were never any researcher annotations in it, so the difference from NAI's release was a misreading of NAI data, not project work. NAI's release in `data/source/census/Clogher_1926.csv` is the only 1926 Clogher source.

## Live service behaviour (confirmed 2026-11-10)

The first run confirmed the endpoint, the `county`, `ded__icontains`, `limit` and `offset` parameters and the paging, that the tool's User-Agent is accepted, and that no API key is needed. Column names and order matched the previous files. If NAI changes its schema, the run stops with nothing changed.
