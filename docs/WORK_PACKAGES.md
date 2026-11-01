# Donegal Townlands: Work Packages

Status: Draft 1, open for review
Date: 2026-11-01
Parent documents: `docs/REQUIREMENTS.md`, `docs/DATA_ARCHITECTURE.md`, `docs/GAZETTEER_SPEC.md`

Size: **S** under a day of assistant work, **M** one to three days, **L** more.
Each package ends with a handover and a `DECISIONS.md` update (GOV-05).

## 1. Approach

Build one thin path end to end first: the 1926 Clogher census through preservation, ETL, observation IDs, place layer, association, review and the evidence build. Then widen to other years and DEDs, then to other sources. The existing Cullionboy and Clogher pages keep working throughout and are switched over only when the new path reproduces them.

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
- **Goal:** a Logainm snapshot and a derived place table for every DED held, plus a home for manual places and name variants. Logainm is the authority, so there is no full gazetteer to build.
- **Inputs:** an adapted `fetch_places.py`, the Logainm IDs for the six DEDs, an API key, the project dictionary as a cross-check.
- **Outputs:** the snapshot in the source layer with manifest entries; the derived place table; a list of dictionary townlands missing from Logainm and the reverse; an empty manual places table with its registry hook; the name variants table, loaded from the 15 census files as proposed.
- **Requirements:** PLC-01 to PLC-07.
- **Acceptance:** every townland string in the 15 census files is either matched, proposed or listed as unresolved. Keadew Lower is a separate place, either from Logainm or as a manual place. Regenerating the place table gives identical output.
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
- **Acceptance:** a bundle contains only accepted associations. A sample of links opens the right household. A broken reference fails the build.

### WP8 Cutover of the Clogher and Cullionboy pages
- **Goal:** the live pages read from the new path.
- **Requirements:** EVD-05.
- **Acceptance:** rendered text, tables and interactions match the current pages. The old extraction path is retired only after Mike's approval.

### WP9 1901 and 1911 ETL, and all held DEDs
- **Goal:** the locator rule generalises. The 1901 and 1911 files use `id` and the `images` field.
- **Requirements:** ETL-04, ETL-05, PLC-03.
- **Acceptance:** all 15 files load. Review lists exist for all DEDs.

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

## 6. First steps

1. Mike decides the open items in the requirements (public repository, GEDCOM editing, genealogy software, Logainm key).
2. Start WP1 and WP2, which have no dependencies.
3. Start WP4 in parallel with WP3 once the key is available.
