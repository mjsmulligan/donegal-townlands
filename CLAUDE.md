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

- Owner: the user (genealogist, limited Python, relies on you for implementation).
- No em dashes anywhere, in any file. `tools/validate.py` fails the commit if it finds one.
- Metric units. Keep spelling as in the sources (Cullionboy, Collinboy, Dimon, Dunnion).
- Light, non-heavy palettes. No brown.
- Do not delete files or published pages without being asked.

## Scope

- Donegal only. Place model: townland, civil parish, barony, DED, county.
- Study order: Cullionboy (first), Clogher next, then townlands in Drumholm and neighbouring Drumhome.

## Source data principles

Decided by the user, 2026-11-10 (DECISIONS.md). They apply to every source, 1926 included.

1. Source data is ingested as supplied. It is not changed or annotated: no values edited, no columns added, removed, renamed or reordered, no metadata altered. Acquisition facts go in a separate manifest. Corrections, interpretations and researcher-filled values live in separate downstream files, never in the source file.
2. The custodian is the authority. For census data the National Archives of Ireland (NAI) is the source, so its latest published files are correct, and the project adjusts to them. When a refresh changes a value, a field or a column's content, derived data and code are updated to follow it. The source is not bent to fit the project, and an older local copy does not outrank the custodian's current release.

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
- Any code, data or design taken from GRA is copied or referenced explicitly, with provenance and licence checked. Any future interface between the two projects needs design discussion and the user's approval.

## Method

- Baseline source is Griffith's Valuation (mid 1850s). Tithe Applotment before it, then revision books, civil BMD (1864 on), parish records, censuses 1901, 1911, 1926.
- GRA `src/genealogy/names.py` is a reference for surname and name variant rules, not a dependency. Working groups so far (Gildea/Guildea, Colhoun/Coulhoun, Sweeny/Sweeney/McSwyne, Dunleavy/Dunlevy). Dimon to Dunnion is a working hypothesis, Hallaghy possibly Gallagher.
- Surname spelling variants are common and no spelling is the correct one. `data/reference/surname_variants.csv` is the single surname dictionary (DECISIONS.md, 2026-11-06). Only the user verifies a row, using local knowledge, and a verified row applies to every townland and puts the family on its page under one label. Never group spellings on a page on your own: add a family as `proposed`, which changes nothing, and tell the user. Evidence rows always keep the spelling as recorded. Review with `python tools/variants_report.py` and `--unassigned`.
- Tolerate age drift between censuses. Hold discrepancies open and record them in the townland STATUS.md. Never resolve a conflict silently.
- Separate documents from oral tradition and say which is which.
- Report numbers that do not add up (for example the Griffith's area sum one acre over the printed total in Cullionboy) and keep them open.

## Living people: 100/75/50 rule

Publish only births and baptisms 100 or more years old, marriages 75 or more, deaths and burials 50 or more, measured against the current year. A person born in the last 100 years with no death record is presumed living and is excluded. Overrides go in `privacy_overrides.csv`. Run `python tools/validate.py` before every commit. No recent photographs of identifiable people.

The rule applies to information the project holds that is not itself taken from a published source: people and events entered in the GEDCOM from family knowledge, oral accounts, unpublished records and photographs. A record taken unchanged from a source published by its custodian, such as the National Archives census releases (1926 and earlier), has already passed that custodian's privacy review, so the project does not withhold it a second time. `tools/validate.py` still refuses census files after 1926. Decided 2026-11-02.

## Layout

- `engine/story.html`: the story player, the one townland page. Every case with enough records has a story at `docs/<name>/story.html`, built by `tools/build_story.py`. Every townland story has the same shape: the townland's sources laid out briefly (one census milestone for all the returns, with a dot for each person counted, or the 1926 form images where they have been added), then a family thread for each surname, two told in the lean-back run and the rest in the explore hub. A case with a place record only has a card on the index and no page. Holds no townland content. The walk (`engine/walk.html`) and the townland and family timelines (`engine/timeline.html`) were removed on 2026-11-26 (DECISIONS.md).
- `engine/place.html`: a plain, data-first place page template. Not used by the build now. Kept for a possible researcher view. Do not delete.
- `townlands/<name>/`: `townland.json` (name, page title, storage key, census spellings), `content.json` (authored family stories and Griffith's rows), `records/` (census.json, corrections.json, griffiths_index.json, people.json from `tools/gedcom_people.py`, later events.csv, story.json generated), `media/` (images as supplied and `media.csv`, see `docs/MEDIA_SPEC.md`), `STATUS.md`.
- `data/source/census/`: the census CSVs for the five held DEDs (Clogher, Tullynaught, Donegal, Laghy, Tawnawully), the manifest-covered originals as supplied by NAI (`data/source/manifest.csv`). Every tool reads them from here. `python tools/refresh_census.py --year <1901|1911|1926> --all [--apply]`, or the manual workflow "Refresh census from NAI", replaces the originals for the chosen years with NAI's current data, all or none, saved as supplied. See [`docs/CENSUS_REFRESH.md`](docs/CENSUS_REFRESH.md).
- `data/source/nli_parish/<register>/`: our own transcription of an NLI parish register, in two stages (raw strings with two readings and adjudication, then a normalised file), specified in that folder's `SCHEMA.md` (DECISIONS.md, 2026-11-17). Tawnawilly baptisms and marriages are the first. The raw files are in `data/source/manifest.csv` like the census files, but they change by reviewed adjudication, so rebuild the normalised files (`python data/source/nli_parish/tawnawilly/normalised/build_normalised.py`) and run `python tools/source_manifest.py register-update` in the same commit as a review. Never edit a normalised file by hand.
- `data/source/nli_parish/tawnawilly/images/` and `shared_media/`: the register cover as supplied (with a manifest) and its one shared web image, shown on every register beat with the `nli` credit (`docs/MEDIA_SPEC.md` section 3.5, DECISIONS.md, 2026-11-27).
- `data/source/census_images/`: census form PDFs as supplied by the National Archives (`manifest.csv` holds SHA-256, archive reference and licence note; see `SCHEMA.md`). `python tools/census_form_images.py add|build|check` keeps them and makes the web images in `townlands/<name>/media/` (scope `census`, `docs/MEDIA_SPEC.md` section 3.4). Credit wording is in `tools/credits.py`. The story page shows it under "Credits and licences" (DECISIONS.md, 2026-11-26).
- `data/source/griffiths/`: askaboutireland Griffith's index CSVs as retrieved (parish master plus one individuals file per townland). `tools/attach_griffiths.py` turns each into `records/griffiths_index.json` for its case. The story's Griffith's beat uses the index when there is no authored transcription.
- `data/reference/surname_variants.csv`: the surname dictionary, checked by `tools/variants_reference.py` and `tools/validate.py` (DECISIONS.md, 2026-11-05).
- `tools/build.py` rewrites the map index `docs/index.html` and holds the helpers the story builder shares (media, case state, card summaries). It takes no case name. `tools/build_story.py <name>` or `--all` builds the story pages. To rebuild everything run `python tools/build_story.py --all`, then `python tools/build.py`. `tools/validate.py` checks before commit. `tools/extract_census.py` was removed on 2026-11-11 (superseded by `tools/attach_census.py`).
- `tests/`: every test module (moved from `tools/` on 2026-11-11). Run `python -m pytest -q tests`. The "Tests" workflow runs them and `tools/validate.py` on every pull request and push to main.
- `tools/create_townland_cases.py` makes a case for every Logainm townland. `tools/attach_census.py` attaches census returns to every case in each DED that is in the place layer (all five held DEDs since 2026-11-09), including Clogher and Cullionboy, by identical name or an accepted spelling, applies `records/corrections.json`, writes `records/census.json` and `records/census_match.json`, and lists other spellings in `data/processed/places/census_spelling_review.csv` for the user's review.
- `tools/census_links.py` proposes links between the 1901, 1911 and 1926 returns (`propose`), compares them with the tree (`check`), records the user's decisions (`accept`) and reports how often each band and flag was accepted (`calibrate`, read-only) in `data/research/associations/census_links.csv`. `tools/census_review.py <townland>` builds the review page. `tools/census_gedcom_export.py` writes a GEDCOM test file for a townland, family or DED from accepted links to `data/processed/census_gedcom/` (not committed). Specified in `docs/CENSUS_GEDCOM_SPEC.md`. The manual workflow "Census to GEDCOM" (`.github/workflows/census-gedcom.yml`) builds the same files as downloadable artifacts, the tentative one only when ticked, and never commits or publishes (`docs/CENSUS_GEDCOM_WORKFLOW.md`).
- `tools/family_facts.py <townland> <family>` writes the family fact sheet (`townlands/<name>/records/facts/<family>.json`, committed) with a tier and `usable` flag on every fact. `tools/check_story.py <townland> <family>` fails any name, place, date, age, number or relationship in the family story that is not in a usable fact (WP21). Run it before a story is accepted.
- `tools/build_story.py <name>` writes `townlands/<name>/records/story.json` (generated, never edited by hand) and `docs/<name>/story.html` from `engine/story.html`, the story player (`docs/TOWNLAND_STORY_SPEC.md`, `docs/TOWNLAND_STORY_ROLLOUT_SPEC.md`). Where the user has accepted family beats (a `_family_beats.csv` and its crosswalk) those are the families and carry the user's captions; otherwise every surname that appears in the records is a family, grouped only through verified rows of the variants dictionary (DECISIONS.md, 2026-11-27). `--all` writes only cases that have a story and also writes the survey report. `tools/story_report.py` is the read only survey (`data/processed/story_report.csv`, not committed). `tools/validate.py` checks every committed `story.json`. Baptisms in stories use the normalised register (DECISIONS.md, 2026-11-22). The event feed the story reads is `tools/events.py` (renamed from `tools/build_timeline.py`, 2026-11-26).
- `engine/index.html`: the template for the map index (`docs/index.html`): a Leaflet map and one card per case, in name order, tagged Townland Study, Census Returns or Townland Record by the case's state. Placeholders: `__MARK__`, `__COUNT__`, `__FOOTER__`, `__GEOJSON__`, `__CARDS__`. Where `data/processed/places/townland_boundaries.geojson` has an outline for a case, the map draws it (dotted, lightly filled) and the dot only where there is none. The map opens on the five DED shapes in `data/processed/places/ded_boundaries.geojson` and reveals the townlands when zoomed in (DECISIONS.md, 2026-11-22). A tap on a townland opens its card (the list card, cloned) and does not leave the page; each card shows a summary of the records held, from `build.case_summary` (DECISIONS.md, 2026-11-23). Change the layout there, never in `docs/index.html`. Only cases appear, so a place with no case folder has no card (DECISIONS.md, 2026-11-08).
- `tools/fetch_townland_boundaries.py` fetches Tailte Eireann townland outlines for every townland in `data/processed/places/places.csv`, joined on LOGAINM_ID, and writes `data/processed/places/townland_boundaries.geojson` plus `townland_boundaries_review.csv` (standard library only; `--input` takes a downloaded WGS84 GeoJSON if the service is down). The manual workflow "Townland boundaries" (`.github/workflows/townland-boundaries.yml`) runs it and pushes a review branch. Check every review row that is not `ok` before merging. The index map and the story pages draw the outlines and show the attribution; rebuild with `tools/build_story.py --all` and `tools/build.py` after the file changes (DECISIONS.md, 2026-11-22).
- `tools/build_ded_boundaries.py` merges the townland outlines into one shape per DED (`data/processed/places/ded_boundaries.geojson`, standard library only, no download). The "Townland boundaries" workflow runs it after the fetch. Run it, then `tools/build.py`, whenever `townland_boundaries.geojson` changes.
- `docs/<name>/story.html`: built output, served by GitHub Pages from /docs. Never edit by hand; run the build. `docs/index.html` lists every case, is regenerated by `tools/build.py` and is never edited by hand.

## Current state of the engine

Authored family stories and the Griffith's transcription live in `townlands/<name>/content.json`, so a new townland needs no engine edits. Every Logainm townland already has a case: add authored `townland.json` and `content.json` to enrich it, run `python tools/attach_census.py` for census returns, then `python tools/build_story.py <name>`. A story is generated honestly from what the case holds and grows as records are added. Researcher corrections to census rows go in `records/corrections.json` with a reason, never in code.

## Standing rules for images

Specified in [`docs/MEDIA_SPEC.md`](docs/MEDIA_SPEC.md) (draft, decided 2026-11-03). Images are committed as supplied, not resized, in `townlands/<name>/media/`, with a row for each in that folder's `media.csv`. Required per image: file, scope, caption, source. Date, reference, people shown and original link are optional. Photographs are shown whole in a frame, never cropped. The user checks each photograph for privacy himself before adding it; the validator applies no 100/75/50 test to media.

