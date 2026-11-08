# Donegal Townlands: Work Packages

Status: Draft 1, open for review
Date: 2026-11-01
Parent documents: `docs/REQUIREMENTS.md`, `docs/DATA_ARCHITECTURE.md`, `docs/GAZETTEER_SPEC.md`

Size: **S** under a day of assistant work, **M** one to three days, **L** more.
Each package ends with a handover and a `DECISIONS.md` update (GOV-05).

## 1. Approach

Build the system around two connected paths. First, every recognised townland in the derived place table must be capable of becoming an independently identifiable research case, whether or not historical sources are available. Second, historical sources progressively enrich those cases through preservation, ETL, observation IDs, association, review and the evidence build.

Validate the complete path first against the current place table and the Clogher DED pilot. Then widen to other years, DEDs and source types. The existing Cullionboy and Clogher pages keep working throughout and are switched over only when the new path reproduces them.

GRA's source ingest and its already fetched census files are the starting point. Its person-linking pipelines are not used.

## 2. What GRA gives us

| GRA item | Used in | How |
|---|---|---|
| `data/*.csv`: 15 census files (Clogher, Magheraclogher, Donegal, Laghy, Tawnawully, Tullynaught; 1901, 1911, 1926), first committed to GRA on 2026-07-10 | WP1 | Copied unchanged into the source layer with a manifest entry |
| `src/ingest/fetch_census.py` | WP11 | Adapted into a database-free fetcher that saves the response unchanged |
| `src/ingest/fetch_places.py` | WP3 | Adapted to fetch and snapshot Logainm places, hierarchy and coordinates. GRA's flat place table shape is reused. |
| `src/evidence/census.py` helpers (`images` field, ages, roles) | WP4 | Small functions adapted with tests |
| `src/evidence/place_resolution.py` normalisation | WP6 | Ideas only: doubled consonants, "X or Y" names, suffix stripping |
| `docs/repositories.md` source catalogue | WP7, WP13 | Link templates and licence notes |
| Not used | | `conclusion/`, `evidence/similarity`, Splink features, `review/`, `dal/`, `db/`, `web/` |

## 3. Findings that shape the plan

- GRA's Clogher files hold two DEDs. The Clogher DED rows (948, 829 and 665) are identical in locator and content to the local files apart from the points below. Magheraclogher is about three times larger and is not yet used here.
- After normalising number formats, the local 1901 and 1911 files differ from GRA's only in `townland_clean` and `ded_clean` (GRA lowercases, the local files are proper case and curated) and in 18 `language_updated` values for 1901.
- GRA's raw files keep Keadew Lower and Keadew Upper distinct, including in the lowercased `townland_clean`. The curated `townland_clean` in the local 1901 and 1911 files folds Keadew Lower into Keadew Upper (65 and 63 rows). That change came from a later process and is exactly why matching uses the original `townland` value.
- The local 1926 file differs from GRA's in 519 `updated_relationship_to_head` values. These are researcher-filled values. They belong in an overlay, not in the source file.
- Townland strings are noisy outside the Clogher DED. For example 28 of 45 strings in Tullynaught and all 51 in Laghy do not match the project dictionary exactly. The Donegal DED includes street entries such as "Donegal Town: Bridge Street (part of)", and some strings hold two names, such as "Tullyleague or Tullybrook". The project dictionary cannot be the gazetteer. Logainm is the better seed.
- In the NAI data the DED is spelled Tawnawully. Tawnawilly in the microfilm filename is a variant.

## 4. Package list

| WP | Name | Depends on | Size | Phase |
|---|---|---|---|---|
| 1 | Foundations and source preservation | none | M | A |
| 2 | Identifier registry | 1 | S | A |
| 3 | Place layer from Logainm | 1, 2 | S | A |
| 4 | 1926 census ETL and observation IDs | 1 | M | A |
| 5 | Corrections overlays | 4 | S | A |
| 6 | Association and review workflow | 3, 4 | M | A |
| 7 | Evidence build v1 | 5, 6 | M | A |
| 8 | Cutover of the Clogher and Cullionboy pages | 7 | M | A |
| 9 | 1901 and 1911 ETL, and all held DEDs | 6 | M | B |
| 10 | GEDCOM generation and GEDCOM 7 test | 6 | M | B |
| 11 | Census fetcher (re-acquisition) | 1 | S | B |
| 12 | Citations and assertions store | 7 | M | B |
| 13 | Parish registers and Tithe import specifications | 6 | L | C |
| 14 | Property and land model (Griffith's, revision books) | design first | L | C |
| 15 | Shared protocol follow-up in the GRA repository | none | S | any |
| 16 | GEDCOM to census associations | 6 | S | B |
| 17 | Family tree research on the pages | 16 | S | B |

Phase A completes the thin path. WP1 and WP2 can start now. WP3 needs a Logainm API key. WP10 needs the genealogy software to be named.

## 5. Packages in detail

### WP1 Foundations and source preservation
- **Goal:** a source layer that can be verified, holding the 15 GRA census files.
- **Outputs:** source folder layout; manifest CSV (file, origin, checksum, retrieval method, date first seen, licence note); `tools/` script to write and verify the manifest; `validate.py` checks for checksums.
- **Requirements:** SRC-01, SRC-02, SRC-03, SRC-04, SRC-06, GOV-01, GOV-07.
- **Acceptance:** verification passes on the 15 files. A changed byte fails. The manifest says the download time is unknown and gives the GRA commit and first-seen date.
- **Decision to make:** folder layout. Existing `data/census/` stays until WP8.

### WP2 Identifier registry
- **Goal:** the append-only registry and the script that generates UUIDs.
- **Outputs:** registry CSV; generator script; validator checks.
- **Requirements:** ID-01 to ID-04.
- **Acceptance:** the tests in the requirements pass, including rejection of a rewritten line.

### WP3 Place layer from Logainm

- **Goal:** a Logainm snapshot and derived place table for every DED held, together with the ability to create an independently identifiable research case for every recognised townland. A case must not depend on historical source availability.
- **Inputs:** an adapted `fetch_places.py`, the Logainm IDs for the six DEDs, an API key, the project dictionary as a cross-check.
- **Outputs:** the snapshot in the source layer with manifest entries; the derived place table; a list of dictionary townlands missing from Logainm and the reverse; an empty manual places table with its registry hook; the name variants table, loaded from the 15 census files as proposed; a repeatable townland case generator; a derived index mapping Logainm townland IDs to case locations.
- **Requirements:** PLC-01 to PLC-15.
- **Acceptance:** every townland row in `places.csv` is eligible for a case, including townlands with no historical records. Only rows with `place_type=townland` generate cases. Case identity is based on the Logainm ID. Repeated generation creates no duplicates and preserves researcher-authored content. A townland missing from a later snapshot is not silently deleted. The case index correctly identifies every generated case. Existing census townland strings are either matched, proposed or listed as unresolved. Keadew Lower remains a separate place, either from Logainm or as a manual place.
- **Risk:** Logainm may not cover historical spellings, town parts or every townland. Gaps become manual places and unresolved strings feed WP6.

### WP4 1926 census ETL and observation IDs
- **Goal:** the first import specification and a deterministic ETL for the 1926 files.
- **Outputs:** `docs/imports/census_1926.md`; ETL module; processed observation file for the Clogher DED; helper tests.
- **Requirements:** ETL-01 to ETL-06, OBS-01 to OBS-03.
- **Acceptance:** two runs are byte identical. The locator is `a_id` and is verified unique. Shuffling the rows does not change IDs.

### WP5 Corrections overlays
- **Goal:** move researcher-filled values out of the source files and into overlays.
- **Inputs:** the local 1926 Clogher file, the curated `townland_clean` columns, existing `corrections.json` files.
- **Outputs:** one overlay CSV per source, keyed by locator, with a reason column; a tool that applies overlays in processing.
- **Requirements:** SRC-02, EVD-02.
- **Acceptance:** source plus overlay reproduces the current local 1926 file. The 519 relationship values and the Bradley form 0016 to 0017 correction appear as overlay rows.

### WP6 Association and review workflow
- **Goal:** proposed associations, a review CSV and a script that applies decisions.
- **Outputs:** matcher (exact, variant, phonetic, fuzzy, with ambiguity rule); association file; review list; apply script; audit log; report.
- **Requirements:** ASC-01 to ASC-06, ASC-03.
- **Acceptance:** the Clogher 1926 test from the gazetteer spec, now against real Logainm IDs. Nothing is accepted without a reviewer.

### WP7 Evidence build v1
- **Goal:** generate the per-townland evidence bundle for Clogher DED 1926.
- **Outputs:** bundle JSON; link builder for the 1926 template (`aform_name`); reference checker; privacy filter.
- **Requirements:** EVD-01 to EVD-04, PRV-01, PRV-02.
- **Acceptance:** a bundle contains only accepted associations. A sample of links opens the right household. A broken reference fails the build. The build also handles a valid townland case with no historical evidence without treating the absence of evidence as an invalid case. The Phase A end-to-end acceptance milestone is completed before Phase A is declared finished.

### WP8 Cutover of the Clogher and Cullionboy pages
- **Goal:** the live pages read from the new path.
- **Requirements:** EVD-05.
- **Acceptance:** rendered text, tables and interactions match the current pages. The old extraction path is retired only after Mike's approval.

### WP9 1901 and 1911 ETL, and all held DEDs
- **Goal:** the locator rule generalises. The 1901 and 1911 files use `id` and the `images` field.
- **Requirements:** ETL-04, ETL-05, PLC-03.
- **Acceptance:** all 15 files load. Review lists exist for all DEDs.
- **Status:** partly done (2026-11-07). `tools/attach_census.py` now handles every DED it finds, with both file name patterns (`1901_Clogher.csv`, `Tullynaught_1901.csv`), each DED against its own townlands only. Clogher (21 cases) and Tullynaught (30 of 33 townlands) are attached. Donegal, Laghy and Tawnawully are skipped with a notice because their townlands are not in the place layer yet (WP3). One review file, with a `ded` column, lists the spellings not matched by identical name.

### WP10 GEDCOM generation and GEDCOM 7 test
- **Goal:** a script that generates the master GEDCOM from accepted decision files, and a tested identifier carrier.
- **Requirements:** GED-01 to GED-05, PRV-01.
- **Acceptance:** regeneration is identical. The test file imports into the named software with identifiers and citations intact.
- **Needs:** the genealogy software and the edit-or-read-only decision.

### WP11 Census fetcher (re-acquisition)
- **Goal:** an adapted fetcher to refresh or extend the source layer.
- **Requirements:** SRC-05.
- **Acceptance:** fetching Clogher 1926 reproduces the stored file or reports every difference.

### WP12 Citations and assertions store
- **Goal:** citations on facts and events, and the assertions store.
- **Requirements:** GED-03, AST-01, AST-02, EVD-06.

### WP13 Parish registers and Tithe import specifications
- **Goal:** import specifications for NLI parish register images, Dúchas and the Tithe Applotment Books, reusing GRA's catalogue entries where they exist.
- **Note:** distinguish specified, implemented and ingested capability.

### WP14 Property and land model
- **Goal:** the model for Griffith's Valuation and revision books. Design before any code.
- **Acceptance of the design:** agreed by Mike, then tested against Clogher.

### WP15 Shared protocol follow-up in the GRA repository
- **Goal:** apply the section 2 and 3 changes made here to GRA's copy of `docs/SHARED_ASSISTANT_PROTOCOL.md`, in its own pull request.

### WP16 GEDCOM to census associations
- **Goal:** link people in Mike's GEDCOM to the census rows their citations refer to, as reviewed associations, and audit the tree against the census.
- **Status:** first version built (2026-11-06) on branch `feature/gedcom-census-associations`.
- **Outputs:** `tools/gedcom_census.py` (`propose`, `accept`, `check`); `tools/test_gedcom_census.py`; `data/research/associations/gedcom_census.csv` (reviewed decisions); generated reports in `data/processed/gedcom/` (not committed).
- **Method:** each census citation on a GEDCOM person is parsed (year, townland, house, head of household, relationship, age, 1926 schedule file) and matched to a census row. A schedule file name or a house number plus name and age gives high confidence. A married woman under her husband's surname, or a nickname without a locator, is capped at medium or low. Every link is proposed until Mike accepts it. Observation IDs follow DATA_ARCHITECTURE 5.2 (`census1901:tullynaught:<id>`).
- **Audit:** tree birth years are compared with census-implied birth years. Births before 1864 were not registered, so census ages are estimates and drift is reported as expected drift for information. A conflict (an exact birth date from 1864 or later whose ages disagree by more than 3 years, or any tree year more than 10 years from every census-implied year) goes to Mike for review.
- **Privacy:** links are dropped for anyone born within the last 100 years. The GEDCOM is read from outside the repository and is never copied into it.
- **Person IDs:** Ancestry person pointers (`@I...@`) were stable across two downloads and across an edit and a deletion of three people (2026-11-06). Family pointers (`@F...@`) were renumbered by the deletion. The decisions file therefore keys on the person pointer and stores the name and birth as a guard, and never uses a family pointer.
- **Acceptance:** the 75 links proposed for the 69 person tree equal the 75 Mike reviewed and accepted. Two runs give identical files. A person pointer that now names someone else fails `check`.
- **Open:** permanent person IDs wait on the GEDCOM UID test (WP10). `check --gedcom` needs the private GEDCOM, so the ID guard is not part of `validate.py`.

## 6. First steps

1. Mike decides the open items in the requirements (public repository, GEDCOM editing, genealogy software, Logainm key).
2. Start WP1 and WP2, which have no dependencies.
3. Start WP4 in parallel with WP3 once the key is available.

### Phase A end-to-end acceptance milestone

Phase A is not complete merely because the source files have been ingested or the evidence build works for Clogher. It must demonstrate that the place-first, evidence-incremental system works as a whole.

The milestone passes when:

1. Every row with `place_type=townland` in the current `places.csv` has a valid, independently identifiable research case, including cases with no historical evidence.
2. DED and other non-townland rows do not generate townland cases.
3. Case generation is repeatable and does not create duplicates, overwrite researcher-authored work or silently delete cases when a place is absent from a later snapshot.
4. Clogher and Cullionboy retain their existing research content and can be represented in the case system without loss.
5. Druminnin can begin as a census-only case, with its spelling variants and identity questions kept open for research rather than assumed to be resolved.
6. Historical evidence can be added to a case incrementally, with source references and the distinction between source content and research conclusions retained.
7. The evidence build produces valid output for a case with evidence, while an empty case remains valid even when it has nothing to publish as historical narrative.

Record the test results and any unresolved issues in the Phase A handover. The milestone is a validation of the whole system, not a requirement to complete the historical research for every townland.

### WP17 Family tree research on the pages
- **Goal:** show dates, relationships and Mike's notes from the GEDCOM on the townland pages, for the people who appear in that townland's census returns, and keep them apart from the evidence.
- **Status:** first version built (2026-11-06) on branch `feature/gedcom-people-on-pages`.
- **Outputs:** `tools/gedcom_people.py` (`export`, `check`); `tools/test_gedcom_people.py`; `townlands/<name>/records/people.json` (committed, privacy filtered); `payload_for` in `tools/build.py` passes it through; `engine/walk.html` shows a "From the family tree" section in each family plate, labelled as research and placed above the census evidence.
- **Rules:** only people with an accepted link in `data/research/associations/gedcom_census.csv` are used. The 100/75/50 rule applies per person and per event. A relative is named only if that relative also passes. A note naming a year inside the last 50 years is withheld and listed for review. The tree's own numbering (Ahnentafel, Ahn. N) is removed. A family note shared by several people is shown once. `tools/validate.py` re-checks every `people.json`.
- **Not done:** 11 links in "Townagh" wait for Mike to decide whether that spelling is Tawnagh (see `census_spelling_review.csv`). A person is shown in the family plate of the household their census row sits in, so a wife appears under her husband's household.

### WP18 Census linker and review report
- **Goal:** propose links between a person's rows in consecutive census returns, with confidence, and produce a review report Mike can work through by townland and then by family.
- **Status:** built, awaiting Mike's review (2026-11-08). `python tools/census_links.py propose` writes one review CSV per DED to `data/processed/census_links/` (git-ignored); `check` compares the matcher with the tree's 19 pairs. The 24 given-name families are all `proposed` and none changes a link until Mike verifies them (`--include-proposed-given-names` previews the effect). Tree recovery of 18 within-DED pairs: verified names only, found 15 (high 5, medium 3, low 4, ambiguous 3), not found 3; with proposed given names, found 18 (high 6, medium 6, low 4, ambiguous 2). The two John Cassidys in Cullionboy are both low and ambiguous. Run time under one second for all five DEDs.
- **Outputs:** `data/reference/given_name_variants.csv` (verified by Mike only, checked by `tools/validate.py` like the surname dictionary); `tools/census_links.py` (`propose`); tests; confidence thresholds in a config file; reports in `data/processed/` (not committed).
- **Review page (added 2026-11-08):** `python tools/census_review.py <townland>` writes a single-file page (`data/processed/census_links/review_<townland>.html`, not committed) with one card per household pair and one row per person across 1901, 1911 and 1926, a rationale column, accept and reject buttons, and links to the National Archives originals. Mike copies his decisions from the page and sends them back. First run: Cullionboy, published as a private artifact.
- **Handover 2026-11-08:** Outcome: matcher, config, given-name seed (24 families, all `proposed`), tests and review page built. Files: `tools/census_links.py`, `tools/census_review.py`, `tools/census_review_template.html`, `tools/test_census_links.py`, `data/reference/census_link_config.json`, `data/reference/given_name_variants.csv`. Decisions needed from Mike: verify the given-name rows; given-name rows verified and the married-name and old-age drift choices confirmed on 2026-11-08 (see DECISIONS.md). Closed 2026-11-08: the earlier uncommitted WP18 start was an earlier Claude session working for Mike, so no one else holds a copy. Its versions of `tools/census_links.py` and the given-name CSV were replaced and cannot be recovered; the current files meet the spec and are tested. Validation: `python tools/validate.py` ok, `python -m pytest -q tools` 251 passed. Review: none independent. Git: branch `story-voice-kelly`, all committed and pushed, no pull request. Next step: Mike reviews Cullionboy on the page and sends decisions, then WP19 records them.
- **Acceptance:** on the Clogher and Tullynaught DEDs the matcher is run against the 19 consecutive pairs from Mike's accepted tree links, and recovery, confidence and any wrong links are reported. The two John Cassidys in Cullionboy do not reach high confidence. Two runs give identical output. Women whose surname changed are capped at low.

### WP19 Accepting census links
- **Status:** built 2026-11-08. `python tools/census_links.py accept <file>` (or `-` for standard input) records the decisions copied from the review page; `--dry-run` shows what would change. Decisions are checked on every `tools/validate.py` run. Regenerating the review page shows recorded decisions as already made. Tests: `ReviewTests` and `AcceptTests` in `tools/test_census_links.py`.
- **Goal:** record Mike's decisions as reviewed associations.
- **Depends on:** WP18.
- **Input (added 2026-11-08):** the decisions text copied from the review page (status, confidence, from_obs, to_obs, names, reviewer, date), so `accept` can read a pasted file as well as an edited CSV.
- **Outputs:** `tools/census_links.py accept`; `data/research/associations/census_links.csv` (accepted and rejected rows only, with reviewer and date); validator checks that every row points at real observation IDs, that no row links twice in one direction, and that a rejected pair is never proposed again. A household can be accepted in one step when every link in it is high.
- **Acceptance:** accepting then regenerating changes nothing. A reprocessed census file either reproduces the same observation IDs or fails loudly.

### WP20 Census GEDCOM writer
- **Status:** built 2026-11-08. `python tools/census_gedcom.py --townland cullionboy`, `--family Kelly` or `--ded Clogher` writes `data/processed/census_gedcom/<scope>.ged` and a `_report.txt` of items to review (not committed). `--wife-parent assume` attaches children to the wife unless the return contradicts it; the default needs marriage evidence, as the spec says. Tests: `tools/test_census_gedcom.py`. Not yet tried in Ancestry.
- **Goal:** generate a GEDCOM from accepted chains, tied to Mike's tree. Scopes (added 2026-11-08): one file per DED, one per townland, or one per family (a surname group from the verified dictionary), so that a single townland or family can be loaded as a test tree in Ancestry or other software.
- **Depends on:** WP19, WP16.
- **Outputs:** `tools/census_gedcom.py`; generated files in `data/processed/` (not committed). Content as set out in section 6 of the spec: every recorded spelling as a `NAME`, one census event per return with the age as recorded, a derived `BIRT ABT` tagged as derived, families only where a return states the relationship, and no inferred marriage, death or emigration.
- **Rules:** the 75 accepted GEDCOM-to-census links are anchors and no row they use is reassigned. A disagreement between an anchor and the matcher is listed as a conflict for Mike.
- **Scope options:** `--townland <name>` takes every accepted chain with a row in that townland. `--family <surname>` takes every accepted chain with a recorded name in that verified family. Whole households are included for each return the chain touches, so families and relationships read correctly, and people with no accepted link appear as single-return persons. Files are named for their scope and carry a header note that they are a derived test file. Not committed.
- **Acceptance:** a person in both Mike's tree and the census appears once. Output reads cleanly in the genealogy software Mike names, and two runs give identical files.

### WP21 Family fact sheet and story check
- **Goal:** give every family a fact sheet and check each story against it.
- **Depends on:** WP19, and WP20 for census-only families.
- **Outputs:** `townlands/<name>/records/facts/<family>.json` (committed), each fact marked as accepted census chain, tree or Griffith's; `tools/check_story.py`, which fails any name, date, age, place or relationship in a story that is not in the fact sheet, and flags anyone not cleared for privacy; STORY_SPEC checklist items automated where possible.
- **Acceptance:** the Kellys story passes with no edits. A sentence with an invented date fails.

