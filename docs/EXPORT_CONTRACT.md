# Export contract: GRA to donegal-townlands (SUPERSEDED)

Status: superseded on 2026-11-01. Donegal Townlands is independent of GRA and there is no export contract between the projects (see `DECISIONS.md` and `docs/DATA_ARCHITECTURE.md`). This file is kept unchanged below as a historical record of the earlier proposal. Do not implement it.

Status: proposal. Nothing in GRA has been changed. GRA requires a design agreed before work, so this is that design.

## Principle
GRA fetches, links and holds the rules. This repo stores only townland-level outputs and publishes them. Data flows one way.

## Command (GRA side, to be written)
`python -m src.cli export-townland --townland "Cullionboy" --ded "Clogher" --out <path-to-donegal-townlands>/townlands/cullionboy/records`

## Files written
1. `census.json` (exists today, produced here by `tools/extract_census.py`). Keys 1901, 1911, 1926, each a list of rows:
   - h house number, s surname, f first name, a age (int or null), x sex, r relation to head, m marriage status, o occupation, i 1 if Irish spoken
   - 1926 rows also carry fo, the original form number. The 1926 townland is spelled Collinboy in the source.
2. `persons.json` (new). One entry per linked Person: person_id, display name, list of census appearances (year, house, row index into census.json), link confidence, and any GRA review flags. This is what lets a family plate follow a person across 1901, 1911 and 1926 without hand matching.
3. `events.csv` (later). Columns person, event, year, source. Feeds the 100/75/50 check in `tools/validate.py`. GRA must withhold rows that fail the rule or mark them so.

## Open questions
- Where the GRA PostgreSQL database runs, and who runs the export.
- Whether Person ids are stable across re-linking runs (needed so family files can refer to them).
- Place ids: use logainm ids for the townland so the parish index can be built from GRA's place data.
