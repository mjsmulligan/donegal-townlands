# Donegal Townlands: Place Layer Specification (Logainm)

Status: Draft 4, open for review
Date: 2026-11-01
Location in repository: `docs/GAZETTEER_SPEC.md` (file name kept so existing links still work)
Parent document: `docs/DATA_ARCHITECTURE.md` (section 6.1)

Draft 4 replaces the earlier plan for a full project gazetteer. Logainm is the place authority. This layer adds only what Logainm does not provide. Draft history: draft 3 proposed a Logainm seed, draft 2 added the 1926 matching test, draft 1 proposed a full gazetteer.

## 1. Purpose and principle

Every place association in the project points to a stable place key, never to a name string.

Logainm (logainm.ie) is a recognised place authority with stable IDs for townlands, civil parishes, DEDs, baronies and counties. The project uses it rather than building its own. The Logainm ID is the place key.

GRA reached the same conclusion when it built its place authority, and kept a flat table with the hierarchy held as columns on each place. The same shape is used here.

## 2. Scope

- In scope: every place named in the census files held in the source layer. That is the Clogher, Magheraclogher, Donegal, Laghy, Tawnawully and Tullynaught DEDs for 1901, 1911 and 1926, and the places that contain them.
- The project townland dictionary (about 70 names) is a cross-check, not the scope.
- Out of scope: sub-townland units (holdings, fields, houses), which belong to the property model, and places outside Donegal.

## 3. Components

### 3.1 Logainm snapshot (source layer)

- Raw Logainm API responses are saved unchanged, with a manifest entry for each: query, Logainm ID, retrieval date and licence note.
- The fetcher is adapted from GRA's `fetch_places.py`, with no database. It needs a Logainm API key, read from the environment and never committed.
- The snapshot keeps results reproducible if Logainm later changes, merges or retires an ID.

### 3.2 Place table (derived)

Built from the snapshot by script, so it can be regenerated at any time. One flat row per place.

| Field | Description |
|---|---|
| logainm_id | The place key |
| name_en | Logainm English name, used for display |
| name_ga | Irish name, where Logainm provides it |
| place_type | As Logainm gives it (townland, civil parish, DED, barony, county, town and so on) |
| ded_id, civil_parish_id, barony_id, county_id | Parent Logainm IDs, flat columns |
| latitude, longitude | Where Logainm provides them |
| snapshot_date | Retrieval date of the response it came from |

### 3.3 Manual places

For places Logainm does not hold. Likely examples are town parts (a street or "part of" subdivision, as in the Donegal DED files), church parishes, and possibly Keadew Lower.

| Field | Description |
|---|---|
| place_key | `dt-place:<uuid>`, recorded in the identifier registry |
| name, place_type | As found, with a type such as town_part or catholic_parish |
| parent_logainm_id | The enclosing Logainm place, where there is one |
| source and reason | Why this place is needed and what shows it exists |

A place that has a Logainm ID never gets a project ID. If Logainm later adds a place that was entered manually, the manual entry is retired in the registry with the Logainm ID as its successor.

### 3.4 Name variants

The main work of this layer. Each census spelling maps to one place key.

| Field | Description |
|---|---|
| variant | The spelling exactly as found |
| normalised_key | Lower case, punctuation and spacing stripped, for matching only |
| place_key | A Logainm ID or a `dt-place` key |
| source | Where the spelling occurs (for example census 1926) |
| variant_type | official, historical, phonetic, transcription_error, abbreviation, irish_form |
| status | proposed, accepted, rejected |
| reviewer and date | For accepted or rejected |

Rules:

- The original spelling is always retained. The normalised key is a matching aid and is never shown as the source value.
- A variant is accepted by a human. Automated matching may propose variants only.
- A name that could refer to two places (a townland and a DED of the same name, for example) is stored against both and flagged ambiguous.
- A compound string such as "Tullyleague or Tullybrook" is stored as aliases of one place and flagged.

### 3.5 Associations

As specified in `DATA_ARCHITECTURE.md` section 6.2, pointing to place keys. Methods are exact, variant, phonetic, fuzzy and manual.

## 4. Matching procedure for source records

For each observation carrying a place string:

1. Normalise the string to a key.
2. Look for an exact match on an accepted variant or a Logainm name, restricted where possible by the DED recorded in the same row.
3. If exactly one place matches, create a proposed association with method `variant_match`.
4. If several places match, create no association. Flag for review with the candidates.
5. If none match, try phonetic matching and create a proposed association with method `phonetic_match`, but only when the phonetic key points to exactly one place. Confidence is medium. Never auto-accept.
6. If none match phonetically, try fuzzy matching and create a proposed association with method `fuzzy_match` and low confidence. If the best two candidates score within 0.05 of each other, treat it as ambiguous and create no association. Never auto-accept.
7. If still none, record as unresolved and surface the string for review. An unresolved string is a candidate for a place missing from Logainm, not necessarily a bad spelling.
8. A reviewer accepts or rejects. Accepted new spellings become accepted variants with the source recorded.

The phonetic key used in the 1926 test lower-cases the string, treats c and k alike, y and i alike, ue and ew alike, and ou and ow alike, collapses doubled letters, and drops interior vowels. GRA's place resolution also collapses doubled consonants, strips words such as "townland" and handles "X or Y" names; those ideas are reused.

Matching always runs on the original `townland` value, which is preserved. The cleaned columns in the 1901 and 1911 files are a cross-check only. GRA's raw files keep Keadew Lower and Keadew Upper distinct, but the curated `townland_clean` in the local files folds them together.

## 5. Seeding and maintenance

1. Fetch the six DEDs and their child townlands from Logainm into the snapshot.
2. Build the place table.
3. Cross-check against the project townland dictionary and townlands.ie. List places missing from either side.
4. Add manual places for gaps, each with a source and reason.
5. Load variants from each census source as it is processed, always as `proposed` first.
6. Keep a change log: what changed, when, why, who accepted it.

## 6. Validation

- Every association references a place key that exists in the place table or the manual places.
- Every manual place has a registry entry, a source and a reason.
- No place with a Logainm ID also has a `dt-place` key.
- Every accepted variant cites a source.
- Every snapshot file has a manifest entry and a matching checksum.
- Report: unresolved strings, ambiguous strings and fuzzy matches awaiting review, per source.

## 7. Open decisions

| Item | Notes |
|---|---|
| Logainm API key | Needed before anything can be fetched. |
| Logainm licence and attribution | Check the terms before committing raw responses. |
| Logainm coverage | Unknown until fetched: historical spellings, town parts, and places such as Keadew Lower. Gaps become manual places. |
| Retired or merged Logainm IDs | Proposed: record the change in the registry and migrate associations by a documented decision. |
| Time validity | Not modelled. Add only if a boundary or name change affects a place in the study period. |
| Catholic parish units | Needed for parish registers. Defer until that source is specified. They will be manual places. |
| Preferred spelling | Proposed: Logainm English name for display, census spellings kept as variants. |

## Appendix A. First test: 1926 Clogher, 2026-11-01

The test used the townland dictionary as the seed, with no place keys yet. Nothing was auto-accepted.

| Census | Rows | Exact | Phonetic | Fuzzy | Unresolved |
|---|---|---|---|---|---|
| 1926 | 665 | 263 | 392 | 0 | 10 |
| 1911 | 829 | 815 | 0 | 0 | 14 |
| 1901 | 948 | 733 | 140 | 58 | 17 |

- Every unresolved row is Keadew Lower (Keadue Lower in 1926). The dictionary lacks it.
- In 1926 there are 20 distinct townland strings. Twelve differ from the dictionary spelling. Eleven resolve to a single phonetic candidate and one (Keadue Lower) is unresolved.
- Weakest matches to review first: Collinboy (0.84), Tennycahill (0.86), Finny Cahill in 1901 (0.86).
- Every row has DED = Clogher in all three files, so DED disambiguation was not exercised.
- This is a small test set. It does not show the method is safe against all Drumholm townlands, where Tawnagh, Tawnaghgorm and similar names sit close together.

### Variants seen in the Clogher files (proposals, not accepted)

| Observed | Relation | Action |
|---|---|---|
| Keadew Lower (1901, 1911), Keadue Lower (1926) | Not in the dictionary. A separate townland from Keadew Upper. | Confirm in Logainm, otherwise a manual place. Never merge into Keadew Upper. |
| Collinboy (1926), Cullionboy (1901, 1911) | Spelling variant of one townland | Lowest-confidence phonetic match. Review first. |
| Tinnycahil, Tennycahill (1926), Finny Cahill (1901) | Spelling variants of one townland | Review. |
| Spierstown, Spearstown (1926), Shierstown (1901) | Spelling variants of one townland | Propose as variants. |
| Finnabanes, Finabanes (1926), Finnabunes (1901) | Spelling variants of one townland | Propose as variants. |
| Druminnin, Druminin (1926) | Spelling variant of one townland | Propose as a variant. |
| Clardrumbarren, Clardrimbarren (1926), Clardrumbarron (1901) | Spelling variants of one townland | Propose as variants. |
| Clardrumnagahan, Clardrimnagahan (1926), Clardumnagahan (1901) | Spelling variants of one townland | Propose as variants. |
| Clarlougheask, Clarlougheske (1926) | Spelling variant of one townland | Propose as a variant. |
| Mullanalamphry, Mullinalamphery (1926) | Spelling variant of one townland | Propose as a variant. |
| Birchhill, Birchill (1901) | Spelling variant of one townland | Propose as a variant. |
| Drumbarren, Drumbarron (1901) | Spelling variant of one townland | Drumbar is a different townland. |
| Carnbeagh North, Carnbeigh North (1926) | Spelling variant of one townland | Propose as a variant. |
| Clogher | A townland and a DED | Two places with different Logainm IDs. |
| Tawnawully (NAI DED name), Tawnawilly (microfilm filename) | Tawnawilly is a variant of the DED name | Record as a variant. Check the townland in Logainm. |
| Tawnagh, Tawnaghgorm, Tawnaghlahan, Tawnalary | Similar names, distinct places | Keep separate. Fuzzy-match risk. |
| Clarcam, Clarcarricknagun, Clardrumbarren, Clardrumnagahan, Clarlougheask | Shared prefix, distinct places | Keep separate. Prefer exact match. |
| Drumbar, Drumbarren | Near-identical, distinct places | Fuzzy-match risk. |
| Drumenny Upper, Drummenny Lower, Drummenny Middle (dictionary) | Inconsistent spelling in the dictionary | Logainm decides the preferred spelling. Others become variants. |

## Appendix B. What the wider GRA census files show

- 28 of 45 distinct townland strings in the Tullynaught files, and all 51 in the Laghy files, do not match the dictionary exactly. The dictionary cannot be the seed.
- The Donegal DED includes street entries such as "Donegal Town: Bridge Street (part of)", which are manual town parts unless Logainm holds them.
- Some strings hold two names, such as "Tullyleague or Tullybrook".
- A search for "Clogher" in the NAI API also returned the Magheraclogher DED, about three times as many rows. The DED selection happens in processing. Both DEDs are separate Logainm places.
