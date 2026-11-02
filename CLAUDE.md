# Donegal townlands: instructions for any assistant

This repo holds townland-centred studies for the Barnesmore area of Donegal, with family histories providing the human narrative. Several assistants work on it across sessions. Do not rely on chat history or project memory. This file, STATUS.md files and DECISIONS.md are the shared context. Update them as you work.

## Working with other assistants

Read [`docs/SHARED_ASSISTANT_PROTOCOL.md`](docs/SHARED_ASSISTANT_PROTOCOL.md) as well as these project-specific instructions. The shared protocol governs cross-assistant collaboration; this file remains authoritative for Donegal-specific research, publishing, privacy, and validation rules.

## Research principles

Before undertaking research, analysis, data work, writing, presentation, or development for Donegal Townlands, read and follow [`docs/RESEARCH_PRINCIPLES.md`](docs/RESEARCH_PRINCIPLES.md). It is the authoritative statement of the project's purpose and research philosophy.

The townland is the primary unit of research and presentation. Family histories provide the human narrative within that townland framework. Present direct documentary evidence distinctly from analysis, interpretation, and conclusions. Preserve original recorded details, identify the evidence supporting interpretations, and retain uncertainty and conflicting evidence. Do not make identity matching the organising purpose of the project.

## Owner and working style

- Owner: Mike (genealogist, limited Python, relies on you for implementation).
- No em dashes anywhere, in any file. `tools/validate.py` fails the commit if it finds one.
- Metric units. Keep spelling as in the sources (Cullionboy, Collinboy, Dimon, Dunnion).
- Light, non-heavy palettes. No brown.
- Do not delete files or published pages without being asked.

## Scope

- Donegal only. Place model: townland, civil parish, barony, DED, county.
- Study order: Cullionboy (first), Clogher next, then townlands in Drumholm and neighbouring Drumhome.

## Data architecture

The central working specification is [`docs/DATA_ARCHITECTURE.md`](docs/DATA_ARCHITECTURE.md). The place authority is specified in [`docs/GAZETTEER_SPEC.md`](docs/GAZETTEER_SPEC.md). Read both before data design, ETL, identifier or GEDCOM work. In short: original sources are preserved unchanged; each source gets its own ETL and import specification; source observations, place associations, established research entities and assertions are kept distinct; one master GEDCOM serves the whole project; identity and association decisions are made by human review. Both documents are drafts and record their open decisions explicitly.

## Relationship with GRA

`mjsmulligan/irish-genealogy-research` (GRA) is a separate project with a different organising purpose. GRA is person-centred: its pipelines are built around linking records into persons. Donegal Townlands is townland-centred and must stay independent of that approach.

- Donegal Townlands owns its own data, identifiers, source acquisition and processing. It does not depend on GRA, GRA record IDs or GRA's person-matching engine.
- There is no export contract and no required data flow between the repositories. The earlier export contract proposal was removed from `docs/` on 2026-11-01 and survives only in git history.
- Elements of GRA's design may be reused where useful, for example its source catalogue, provenance architecture, source definitions and URL patterns, and ETL for particular source data files. Reuse is a deliberate choice made case by case, not an obligation, and not a gateway every source must pass through.
- Always distinguish a source that is specified in a catalogue from one whose ingestion is implemented and one for which records have actually been ingested.
- Check `docs/repositories.md` in GRA for a source's licence before committing anything from it. Never commit Historic Graves data.
- Do not treat any GRA person match as a confirmed Townlands identity.
- Any code, data or design taken from GRA is copied or referenced explicitly, with provenance and licence checked. Any future interface between the two projects needs design discussion and Mike's approval.
- The local copy `data/census/1926_Clogher.csv` is the verified source. GRA's `data/Clogher_1926.csv` lacks about 500 researcher-filled relationship values.

## Method

- Baseline source is Griffith's Valuation (mid 1850s). Tithe Applotment before it, then revision books, civil BMD (1864 on), parish records, censuses 1901, 1911, 1926.
- GRA `src/genealogy/names.py` is a reference for surname and name variant rules, not a dependency. Working groups so far (Gildea/Guildea, Colhoun/Coulhoun, Sweeny/Sweeney/McSwyne, Dunleavy/Dunlevy). Dimon to Dunnion is a working hypothesis, Hallaghy possibly Gallagher.
- Tolerate age drift between censuses. Hold discrepancies open and record them in the townland STATUS.md. Never resolve a conflict silently.
- Separate documents from oral tradition and say which is which.
- Report numbers that do not add up (for example the Griffith's area sum one acre over the printed total in Cullionboy) and keep them open.

## Living people: 100/75/50 rule

Publish only births and baptisms 100 or more years old, marriages 75 or more, deaths and burials 50 or more, measured against the current year. A person born in the last 100 years with no death record is presumed living and is excluded. Overrides go in `privacy_overrides.csv`. Run `python tools/validate.py` before every commit. No recent photographs of identifiable people.

## Layout

- `engine/walk.html`: page template (scenes, plates, HUD, drawer). Holds no townland content. Placeholders: `__TITLE__`, `__BRAND__`, `__DATA__`.
- `townlands/<name>/`: `townland.json` (name, page title, storage key, census spellings), `content.json` (family stories, Griffith's rows, open questions, plate copy), `records/` (census.json, corrections.json, later events.csv), `media/` (web-sized images with captions), `STATUS.md`.
- `data/census/`: source census CSVs for the Clogher DED.
- `tools/extract_census.py <name>`, `tools/build.py <name>`, `tools/validate.py`.
- `docs/<name>/index.html`: built output, served by GitHub Pages from /docs. Never edit by hand; run build. Every recognised place has a page (a place page until it has a study). `docs/index.html` lists them all, is regenerated by every build and is never edited by hand.

## Current state of the engine

Family stories, the Griffith's transcription and plate copy live in `townlands/<name>/content.json`, so a new townland needs no engine edits: add `townland.json`, `content.json` and corrections, run `python tools/extract_census.py <name>`, then `python tools/build.py <name>`. Researcher corrections to census rows go in `records/corrections.json` with a reason, never in code. The mountain plate is optional: omit `plates.mountain` and `griffiths.mountain_acres` and `griffiths.water_acres` and the plate and its treemap tiles are skipped.

## Standing rules for images

Originals stay outside the repo. Commit web-sized copies (about 1600 px). Each image needs a caption record: source, reference, date, people shown, family.

