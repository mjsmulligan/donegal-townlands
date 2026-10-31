# Donegal townlands: instructions for any assistant

This repo holds family-centred townland studies for the Drumholm area of Donegal, published as immersive "gallery walk" web pages. Several assistants work on it across sessions. Do not rely on chat history or project memory. This file, STATUS.md files and DECISIONS.md are the shared context. Update them as you work.

## Owner and working style
- Owner: Mike (genealogist, limited Python, relies on you for implementation).
- No em dashes anywhere, in any file. `tools/validate.py` fails the commit if it finds one.
- Metric units. Keep spelling as in the sources (Cullionboy, Collinboy, Dimon, Dunnion).
- Light, non-heavy palettes. No brown.
- Do not delete files or published pages without being asked.

## Scope
- Donegal only. Place model: townland, civil parish, barony, DED, county.
- Study order: Cullionboy (first), Clogher next, then townlands in Drumholm and neighbouring Drumhome.

## Sister repo
`mjsmulligan/irish-genealogy-research` (GRA) is the research engine: source fetching, record linkage, Irish genealogical rules (`src/genealogy/`), source and licence list (`docs/repositories.md`). This repo is the publishing layer. GRA never knows about this repo. Rules:
- Check `docs/repositories.md` in GRA for a source's licence before committing anything from it. Never commit Historic Graves data.
- Do not re-implement fetching or linking here. Data flows GRA to here through the export contract in `docs/EXPORT_CONTRACT.md`.
- GRA's own rules require design agreement before changes to its schema or scoring.
- Known gap: GRA's `data/Clogher_1926.csv` lacks about 500 researcher-filled relationship values present in `data/census/1926_Clogher.csv` here. Local copies are the verified source until GRA is updated.

## Method
- Baseline source is Griffith's Valuation (mid 1850s). Tithe Applotment before it, then revision books, civil BMD (1864 on), parish records, censuses 1901, 1911, 1926.
- Surname and name variant rules live in GRA `src/genealogy/names.py`. Working groups so far (Gildea/Guildea, Colhoun/Coulhoun, Sweeny/Sweeney/McSwyne, Dunleavy/Dunlevy). Dimon to Dunnion is a working hypothesis, Hallaghy possibly Gallagher.
- Tolerate age drift between censuses. Hold discrepancies open and record them in the townland STATUS.md. Never resolve a conflict silently.
- Separate documents from oral tradition and say which is which.
- Report numbers that do not add up (for example the Griffith's area sum one acre over the printed total in Cullionboy) and keep them open.

## Living people: 100/75/50 rule
Publish only births and baptisms 100 or more years old, marriages 75 or more, deaths and burials 50 or more, measured against the current year. A person born in the last 100 years with no death record is presumed living and is excluded. Overrides go in `privacy_overrides.csv`. Run `python tools/validate.py` before every commit. No recent photographs of identifiable people.

## Layout
- `engine/walk.html`: page template (scenes, plates, HUD, drawer). Contains a `__DATA__` placeholder.
- `townlands/<name>/`: `records/` (census.json, later events.csv and Griffith's), `media/` (web-sized images with captions), `STATUS.md`.
- `data/census/`: source census CSVs for the Clogher DED.
- `tools/extract_census.py`, `tools/build.py <name>`, `tools/validate.py`.
- `docs/<name>/index.html`: built output, served by GitHub Pages from /docs. Never edit by hand; run build.

## Current state of the engine
Family stories and the Griffith's transcription are still written inside `engine/walk.html` (the `FAM` and `GR` blocks). Moving them into per-townland files is the next engineering job, so a new townland needs no engine edits.

## Standing rules for images
Originals stay outside the repo. Commit web-sized copies (about 1600 px). Each image needs a caption record: source, reference, date, people shown, family.
