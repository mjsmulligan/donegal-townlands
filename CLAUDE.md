# Donegal townlands: instructions for any assistant

This repo holds townland-centred studies for the Barnesmore area of Donegal, with family histories providing the human narrative. Several assistants work on it across sessions. Do not rely on chat history or project memory. This file, STATUS.md files and DECISIONS.md are the shared context. Update them as you work.

## Working with other assistants

Read [`docs/SHARED_ASSISTANT_PROTOCOL.md`](docs/SHARED_ASSISTANT_PROTOCOL.md) as well as these project-specific instructions. The shared protocol governs cross-assistant collaboration; this file remains authoritative for Donegal-specific research, publishing, privacy, and validation rules.

## Research principles

Before undertaking research, analysis, data work, writing, presentation, or development for Donegal Townlands, read and follow [`docs/RESEARCH_PRINCIPLES.md`](docs/RESEARCH_PRINCIPLES.md). It is the authoritative statement of the project's purpose and research philosophy.

The townland is the primary unit of research and presentation. Family histories provide the human narrative within that townland framework. Present direct documentary evidence distinctly from analysis, interpretation, and conclusions. Preserve original recorded details, identify the evidence supporting interpretations, and retain uncertainty and conflicting evidence. Do not make identity matching the organising purpose of the project.

## Story voice

Family stories are written in a plain, lay person's tone, as one account that draws on the records and the family tree without citations, IDs or "the records show". State what the evidence shows and stop there: no speculation, no leads, no open questions on the page, and no second-guessing of the tree (DECISIONS.md, 2026-11-07). The evidence stays reachable in the closed "The records behind this" panel. The draft spec is [`docs/STORY_SPEC.md`](docs/STORY_SPEC.md). The draft census linking and GEDCOM design is [`docs/CENSUS_GEDCOM_SPEC.md`](docs/CENSUS_GEDCOM_SPEC.md).

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
- Surname spelling variants are common and no spelling is the correct one. `data/reference/surname_variants.csv` is the single surname dictionary (DECISIONS.md, 2026-11-06). Only Mike verifies a row, using local knowledge, and a verified row applies to every townland and puts the family on its page under one label. Never group spellings on a page on your own: add a family as `proposed`, which changes nothing, and tell Mike. Evidence rows always keep the spelling as recorded. Review with `python tools/variants_report.py` and `--unassigned`.
- Tolerate age drift between censuses. Hold discrepancies open and record them in the townland STATUS.md. Never resolve a conflict silently.
- Separate documents from oral tradition and say which is which.
- Report numbers that do not add up (for example the Griffith's area sum one acre over the printed total in Cullionboy) and keep them open.

## Living people: 100/75/50 rule

Publish only births and baptisms 100 or more years old, marriages 75 or more, deaths and burials 50 or more, measured against the current year. A person born in the last 100 years with no death record is presumed living and is excluded. Overrides go in `privacy_overrides.csv`. Run `python tools/validate.py` before every commit. No recent photographs of identifiable people.

The rule applies to information the project holds that is not itself taken from a published source: people and events entered in the GEDCOM from family knowledge, oral accounts, unpublished records and photographs. A record taken unchanged from a source published by its custodian, such as the National Archives census releases (1926 and earlier), has already passed that custodian's privacy review, so the project does not withhold it a second time. `tools/validate.py` still refuses census files after 1926. Decided 2026-11-02.

## Layout

- `engine/walk.html`: the gallery walk (scenes, plates, HUD, drawer) that every townland page is built from, with no exceptions. Holds no townland content. Placeholders: `__TITLE__`, `__BRAND__`, `__DATA__`. A plate appears only when its content exists, so a townland with only a Logainm place record gets a short walk and one with census returns and an authored study gets the full one. A case with census returns but no authored families gets a generated plate per household-head surname (see DECISIONS.md, 2026-11-04). The treemap and open-questions plates were removed from the walk on 2026-11-04.
- `engine/place.html`: a plain, data-first place page template. Not used by the build now. Kept for a possible researcher view. Do not delete.
- `townlands/<name>/`: `townland.json` (name, page title, storage key, census spellings), `content.json` (family stories, Griffith's rows, open questions, plate copy), `records/` (census.json, corrections.json, name_families.json, griffiths_index.json, people.json from `tools/gedcom_people.py`, later events.csv), `media/` (images as supplied and `media.csv`, see `docs/MEDIA_SPEC.md`), `STATUS.md`.
- `data/census/`: source census CSVs for the five held DEDs (Clogher, Tullynaught, Donegal, Laghy, Tawnawully), as obtained.
- `data/source/griffiths/`: askaboutireland Griffith's index CSVs as retrieved (parish master plus one individuals file per townland). `tools/attach_griffiths.py` turns each into `records/griffiths_index.json` for its case. A case with an index and no authored transcription gets a names-only Griffith's plate (DECISIONS.md, 2026-11-04).
- `data/reference/surname_variants.csv`: the surname dictionary, checked by `tools/variants_reference.py` and `tools/validate.py` (DECISIONS.md, 2026-11-05).
- `tools/build.py <name>` (or `--all`) builds every case the same way, `tools/validate.py` checks before commit. `tools/extract_census.py` is superseded by `tools/attach_census.py` and kept for reference.
- `tools/create_townland_cases.py` makes a case for every Logainm townland. `tools/attach_census.py` attaches census returns to every case in each DED that is in the place layer (Clogher and Tullynaught so far; the other three wait for WP3), including Clogher and Cullionboy, by identical name or an accepted spelling, applies `records/corrections.json`, writes `records/census.json` and `records/census_match.json`, and lists other spellings in `data/processed/places/census_spelling_review.csv` for Mike's review.
- `tools/census_links.py` proposes links between the 1901, 1911 and 1926 returns (`propose`), compares them with the tree (`check`) and records Mike's decisions (`accept`) in `data/research/associations/census_links.csv`. `tools/census_review.py <townland>` builds the review page. `tools/census_gedcom.py` writes a GEDCOM test file for a townland, family or DED from accepted links to `data/processed/census_gedcom/` (not committed). Specified in `docs/CENSUS_GEDCOM_SPEC.md`.
- `tools/family_facts.py <townland> <family>` writes the family fact sheet (`townlands/<name>/records/facts/<family>.json`, committed) with a tier and `usable` flag on every fact. `tools/check_story.py <townland> <family>` fails any name, place, date, age, number or relationship in the family story that is not in a usable fact (WP21). Run it before a story is accepted.
- `engine/index.html`: the template for the map index (`docs/index.html`): a Leaflet map and one card per case, in name order, tagged Townland Study, Census Returns or Townland Record by the case's state. Placeholders: `__MARK__`, `__COUNT__`, `__FOOTER__`, `__GEOJSON__`, `__CARDS__`. Change the layout there, never in `docs/index.html`. Only cases appear, so a place with no case folder has no card (DECISIONS.md, 2026-11-08).
- `docs/<name>/index.html`: built output, served by GitHub Pages from /docs. Never edit by hand; run build. Every recognised place has a gallery walk page that grows as records are added. `docs/index.html` lists them all, is regenerated by every build and is never edited by hand.

## Current state of the engine

Family stories, the Griffith's transcription and plate copy live in `townlands/<name>/content.json`, so a new townland needs no engine edits. Every Logainm townland already has a case: add authored `townland.json` and `content.json` to enrich it, run `python tools/attach_census.py` for census returns, then `python tools/build.py <name>`. Content you do not author is generated honestly from what the case holds, and authored content always overrides it. Researcher corrections to census rows go in `records/corrections.json` with a reason, never in code. The mountain plate is optional: omit `plates.mountain` and `griffiths.mountain_acres` and `griffiths.water_acres` and the plate and its treemap tiles are skipped.

## Standing rules for images

Specified in [`docs/MEDIA_SPEC.md`](docs/MEDIA_SPEC.md) (draft, decided 2026-11-03). Images are committed as supplied, not resized, in `townlands/<name>/media/`, with a row for each in that folder's `media.csv`. Required per image: file, scope, caption, source. Date, reference, people shown and original link are optional. Photographs are shown whole in a frame, never cropped. Mike checks each photograph for privacy himself before adding it; the validator applies no 100/75/50 test to media.

