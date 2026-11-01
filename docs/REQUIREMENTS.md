# Donegal Townlands: Requirements

Status: Draft 1, open for review
Date: 2026-11-01
Parent documents: `docs/DATA_ARCHITECTURE.md`, `docs/GAZETTEER_SPEC.md`
Companion: `docs/WORK_PACKAGES.md`

Priority: **M** must, **S** should, **L** later.
Every requirement has an acceptance test. A work package is finished when the tests for its requirements pass.

## 1. Implementation decisions these requirements assume

| ID | Decision | Status |
|---|---|---|
| D1 | The build pipeline is Python. The browser only displays static JSON produced by the build. No matching, filtering or identifier work happens in the page. | Agreed 2026-11-01 |
| D2 | Logic from GRA is reused by copy and adapt, with a provenance header, not by import. GRA's person-linking pipelines are not reused. | Agreed in principle 2026-11-01 |
| D3 | GRA's source ingest and its already fetched census files are the starting point for the source layer. | Agreed 2026-11-01 |
| D4 | Logainm is the place authority and the Logainm ID is the place key. The project builds no full gazetteer. It keeps a Logainm snapshot, name variants, manual places and associations. The dictionary is a cross-check. | Agreed 2026-11-01 (replaces the earlier gazetteer plan). The `dt-place:<uuid>` key for manual places is proposed. |
| D5 | Researcher-filled values are kept as overlay files, so source files stay unchanged. | Proposed |
| D6 | Processed layers are CSV and JSON files in git. The single master GEDCOM is the exception for people and relationships. | Agreed 2026-11-01 |
| D7 | Accept and reject decisions are made in a review CSV edited in a spreadsheet and applied by script. | Agreed 2026-11-01 |

## 2. Source layer

| ID | Requirement | Pri | Test |
|---|---|---|---|
| SRC-01 | Every acquired source file is stored unchanged with a SHA-256 checksum and a manifest entry: origin, URL or repository path, retrieval method, date acquired or first seen, licence note. | M | The manifest lists every file under the source folder. Verification passes. Changing one byte makes validation fail. |
| SRC-02 | Source files are never edited in place. Corrections live in separate overlay files keyed by the source locator, each with a reason. | M | No source file differs from its manifest checksum. Each overlay row has a reason. |
| SRC-03 | Acquisition is complete for the DED and year requested, not filtered to the townlands under study. | M | Row counts of a stored file equal the counts returned by the source. |
| SRC-04 | The census files already fetched by GRA (Clogher, Magheraclogher, Donegal, Laghy, Tawnawully and Tullynaught, for 1901, 1911 and 1926, GRA commit `1dab647`) are adopted as source inputs. The manifest records the GRA path and checksum and says the exact download time is unknown. The date they were first committed to GRA (2026-07-10) is recorded as first seen. | M | Fifteen files are in the manifest with origin recorded. Their checksums match the GRA copies. |
| SRC-05 | A census fetcher adapted from GRA can re-acquire any DED and year from the NAI APIs and save the response unchanged, with no database. | S | Fetching Clogher 1926 reproduces the stored file or reports the differences. |
| SRC-06 | The licence of each source is recorded before anything from it is committed. Historic Graves data is never committed. | M | Every manifest entry has a licence note. |

## 3. Processing and observations

| ID | Requirement | Pri | Test |
|---|---|---|---|
| ETL-01 | Each source type has an import specification, using the headings in `DATA_ARCHITECTURE.md` section 12, before its ETL is written. | M | The specification file exists and is linked from the ETL module. |
| ETL-02 | ETL is source specific, deterministic and re-runnable. | M | Running it twice gives byte-identical output. |
| ETL-03 | Original values are kept alongside any normalised value. Every processed row carries its observation ID and a reference to its source file. | M | A check finds no processed row without an original value, an ID and a file reference. |
| ETL-04 | Census ETL handles 1926 first, then 1901 and 1911, using the documented locator rule. | M | All three years load for Clogher. |
| ETL-05 | Locator uniqueness is verified per file. A duplicate or missing locator fails the run. | M | A test file with a duplicate locator fails. |
| ETL-06 | Parsing helpers (the `images` field, age values, role mapping) are adapted from GRA with unit tests. | S | The tests pass on the Clogher files. |
| OBS-01 | Observation IDs follow `<source>:<scope>:<locator>` and are deterministic. | M | Two runs produce identical IDs. |
| OBS-02 | Reprocessing reproduces the same IDs or fails. It never renumbers silently. | M | Changing the row order in a test file does not change any ID. |
| OBS-03 | An observation ID is a plain string usable in associations, assertions and evidence links. | M | The IDs resolve in the evidence build. |

## 4. Places and associations

| ID | Requirement | Pri | Test |
|---|---|---|---|
| PLC-01 | The place layer holds a Logainm snapshot, a derived place table, manual places, name variants and associations as specified in `GAZETTEER_SPEC.md`. | M | The validation rules in the spec pass. |
| PLC-02 | Logainm responses are fetched by a fetcher adapted from GRA and stored unchanged in the source layer, with a manifest entry (query, Logainm ID, retrieval date). The place table is derived from the snapshot by script and holds the Logainm ID, names, type, parent IDs and coordinates. The project dictionary is a cross-check. An API key is needed and is never committed. Raw responses are committed only if they contain no Logainm notes or collected citations (outside the CC BY 4.0 licence). | M | Every townland in the six held DEDs has a Logainm record in the snapshot or is listed as missing. Regenerating the place table gives identical output. |
| PLC-03 | The place layer covers every DED held in the source layer. | M | No census townland string falls in a DED with no place coverage. |
| PLC-04 | Place types include townland, DED, civil parish, barony, county, town and town part (a street or "part of" subdivision, as in the Donegal DED files). | M | The Donegal DED files resolve street strings to town parts. |
| PLC-05 | Compound names such as "Tullyleague or Tullybrook" are stored as aliases of one place and flagged. | S | Both parts match the same place. |
| PLC-06 | A place Logainm does not hold gets a `dt-place:<uuid>` key, recorded in the identifier registry with a source and reason. A place with a Logainm ID never gets a project ID. | M | The registry check passes. No place has both keys. |
| PLC-07 | If Logainm merges or retires an ID, the change is recorded in the registry and associations are migrated by a documented decision. | S | A test migration moves associations and keeps the audit trail. |
| PLC-08 | Published pages and the repository credit Logainm: "Irish-language placename data by Logainm, Government of Ireland, licensed under CC BY 4.0." | M | The attribution appears in the README and on every published townland page. |
| PLC-09 | Every row in `data/processed/places/places.csv` with `place_type=townland` is eligible for a townland research case, independently of historical source availability. | M | Every townland row in a test place table has a corresponding case, including rows with no historical records. |
| PLC-10 | A newly generated case has a stable identity based on its Logainm ID and contains the place identity and available place-register information. It does not require census, valuation, parish or other historical records. | M | A townland with no historical source data generates a valid case that passes validation. |
| PLC-11 | Case generation is deterministic and repeatable. The Logainm ID, not the current place name or directory name, determines whether a case already exists. | M | Running the generator twice creates no duplicate cases. Changing a townland's display name does not create a second case. |
| PLC-12 | Case generation preserves existing researcher-authored content and does not overwrite files that it does not own. | M | A test adds researcher-authored content, reruns generation and verifies that the content is unchanged. |
| PLC-13 | A townland absent from a later Logainm snapshot is not silently deleted from the research system. | M | A test removes a townland from the input place table and verifies that its existing case remains. |
| PLC-14 | A generated townland case index maps each current Logainm townland ID to its case location. It is derived output and does not replace the place table or source snapshot. | M | The index contains exactly one entry for each eligible townland in the input place table, with the correct case location. |
| PLC-15 | Only rows with `place_type=townland` generate townland cases. DEDs, civil parishes, baronies, counties and other place types do not. | M | A mixed place table generates cases for townland rows only. |
| ASC-01 | Associations are entities with observation ID, place ID, type, method, confidence, status, reviewer and date. | M | A schema check on the association file passes. |
| ASC-02 | Matching proposes only. Nothing is accepted automatically. | M | No accepted association lacks a reviewer and a date. |
| ASC-03 | Matching runs on the original place string. Cleaned columns are a cross-check only. | M | A test shows Keadew Lower is not matched to Keadew Upper. |
| ASC-04 | A review list is exported as CSV. A script applies the decisions and keeps an audit trail. | M | Applying a sample decisions file changes only the intended rows and logs each change. |
| ASC-05 | Accepted decisions survive reprocessing. | M | Reprocessing leaves accepted associations unchanged. |
| ASC-06 | A report lists unresolved, ambiguous and fuzzy matches per source. | M | The report matches the counts in the review list. |

## 5. Identifiers

| ID | Requirement | Pri | Test |
|---|---|---|---|
| ID-01 | The registry is one append-only CSV with id, type, status, successor, date and reason. | M | The validator rejects any edit that removes or rewrites an earlier line. |
| ID-02 | UUIDs are generated by one script, checked for uniqueness and never reused. | M | Generating 10,000 IDs gives no duplicates and none already in the registry. |
| ID-03 | Merges and splits record a successor and a decision record. | M | A retired ID without a successor or status fails validation. |
| ID-04 | The registry is validated by `tools/validate.py`. | M | The validator reports registry errors. |

## 6. GEDCOM and people

| ID | Requirement | Pri | Test |
|---|---|---|---|
| GED-01 | One master GEDCOM serves the whole project. There are no townland-specific GEDCOM files. | M | One file exists. |
| GED-02 | The GEDCOM is generated from accepted decision files by script. Whether it is ever edited in genealogy software is open. | M | Regenerating from unchanged inputs gives an identical file. |
| GED-03 | Each fact and event has a citation that points to observation IDs and to a link to the original source. | M | A check finds no fact without a citation. |
| GED-04 | Donegal Townlands identifiers are carried in the GEDCOM using the structure chosen after testing (UID, EXID or REFN). | M | The identifiers survive an import into the intended software. |
| GED-05 | GEDCOM 7 is tested for import in the intended genealogy software. | S | The test file imports without loss of identifiers or citations. |

## 7. Evidence build and presentation

| ID | Requirement | Pri | Test |
|---|---|---|---|
| EVD-01 | A per-townland evidence bundle (JSON) is generated from accepted associations only. | M | A proposed association never appears in a bundle. |
| EVD-02 | Each evidence row shows the original value first, then any normalised value, then any correction with its reason. | M | The Cullionboy 1926 Bradley correction shows original, corrected value and reason. |
| EVD-03 | Each row links to the original record or image using the URL templates in the source catalogue. The 1901 and 1911 link uses the first image ID in the `images` field. The 1926 link uses `aform_name`. | M | A sample of links opens the right household. |
| EVD-04 | Authored narrative references evidence by ID. The build fails on a reference that does not resolve or that points at something not accepted. | M | A test with a broken reference fails the build. |
| EVD-05 | The existing Cullionboy and Clogher pages are reproduced from the new path before cutover. The `extract_census.py` path stays until then. | M | The rebuilt pages match the current pages in rendered text, tables and interactions. |
| EVD-06 | Family sections draw on GEDCOM people and accepted assertions and appear after the direct evidence they rest on. | S | A review of a sample page. |

## 8. Privacy

| ID | Requirement | Pri | Test |
|---|---|---|---|
| PRV-01 | The 100/75/50 rule and `privacy_overrides.csv` are applied when the evidence bundles and the published GEDCOM are built. | M | A person born less than 100 years ago with no death record is absent from the output. |
| PRV-02 | The validator fails the build if a presumed living person appears in published output. | M | A seeded test person is caught. |
| PRV-03 | The project decides what the public repository may hold, including the processed research layers and the GEDCOM. | M | The decision is recorded in `DECISIONS.md`. |

## 9. Assertions

| ID | Requirement | Pri | Test |
|---|---|---|---|
| AST-01 | An assertions store holds the fields in `DATA_ARCHITECTURE.md` section 9. | L | A schema check passes. |
| AST-02 | Each assertion cites observation IDs and entity IDs. Narrative may cite assertions. | L | Every cited ID resolves. |

## 10. Governance and quality

| ID | Requirement | Pri | Test |
|---|---|---|---|
| GOV-01 | `tools/validate.py` keeps the em dash check and adds checks for checksums, registry, ID uniqueness and reference resolution. | M | The validator runs in under a minute and fails on seeded errors. |
| GOV-02 | The pipeline is Python with minimal dependencies (`requests` and `rapidfuzz`, and `pandas` only if needed). It does not use `psycopg2` or `splink`. | M | `requirements.txt` lists only approved packages. |
| GOV-03 | Code adapted from GRA carries a header naming the source file and GRA commit. | M | A search finds a header in every adapted module. |
| GOV-04 | The licence of the Townlands repository is checked against GRA's PolyForm Noncommercial licence before adapted code is committed. | S | The check is recorded in `DECISIONS.md`. |
| GOV-05 | Each work package ends with a handover and a `DECISIONS.md` update, as the shared protocol requires. | M | The handover exists. |
| GOV-06 | Existing rules continue: metric units, no em dashes, light palettes with no brown, original spellings kept. | M | The validator and review pass. |
| GOV-07 | Every pipeline step runs from one documented command, written for a user with limited Python. | M | Mike can run each step from the README. |

## 11. Open items

| Item | Notes |
|---|---|
| Public repository and research data | Which processed layers and which GEDCOM can be public. Recommendation: keep the full research layer private and commit only filtered output. |
| GEDCOM edited in genealogy software or read-only output | Decides whether the GEDCOM 7 test is round trip or import only. |
| Genealogy software in use | Needed for GED-04 and GED-05. |
| Logainm API key | Needed for PLC-02. |
| Logainm licence and coverage | Licence found: CC BY 4.0 (Government of Ireland), except Logainm's explanatory notes and collected citations. Attribution is required. Coverage of town parts, historical spellings and places such as Keadew Lower is unknown until fetched. |
| Overlay format for researcher-filled values | Proposed: one CSV per source, keyed by the locator. Needs agreement. |
| Source folder layout | To be settled in work package 1. |
