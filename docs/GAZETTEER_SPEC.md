# Donegal Townlands: Place Gazetteer Specification

Status: Draft 2, open for review (draft 2 adds the 1926 test result, the phonetic matching method and Keadew Lower)
Date: 2026-11-01
Location in repository: `docs/GAZETTEER_SPEC.md`
Parent document: `docs/DATA_ARCHITECTURE.md` (section 6.1)

## 1. Purpose

Every place association in the project points to a stable place ID from this gazetteer, never to a name string. The gazetteer is the authority for what places exist, what they have been called, and how they nest.

## 2. Scope

- In scope: Donegal places at townland level and above (townland, DED, civil parish, Catholic parish where needed, barony, county).
- Included from the start: Clogher, Cullionboy, and the other townlands in the project townland dictionary (about 70 names).
- Out of scope for now: sub-townland units (holdings, fields, houses). These belong to the property model.
- Out of scope: places outside Donegal. The template may later be cloned, with its own gazetteer.

## 3. Place record

| Field | Description |
|---|---|
| place_id | Stable UUID, never reused. Registered in the identifier registry (type: place). |
| place_type | townland, ded, civil_parish, catholic_parish, barony, county, other |
| preferred_name | Display name used on the site |
| irish_name | Where established, with source |
| external_refs | townlands.ie identifier, OSM relation, Logainm ID, with retrieval date |
| area | Statute acres, with source |
| valid_from / valid_to | Date range the unit existed in this form. Open-ended if unknown. |
| status | draft, reviewed, accepted |
| notes | Free text |

A townland and a DED of the same name are two places with different IDs and types. Clogher the townland and Clogher the DED must never share a record.

## 4. Name variants

Names live in their own table, many per place.

| Field | Description |
|---|---|
| variant_id | Stable ID |
| place_id | The place the name belongs to |
| name | The spelling exactly as found |
| normalised_key | Lower case, punctuation and spacing stripped, for matching only |
| source | Where the spelling occurs (for example census 1901, Griffith's, townlands.ie) |
| date_range | When used, if known |
| variant_type | official, historical, phonetic, transcription_error, abbreviation, irish_form |
| status | proposed, accepted, rejected |

Rules:

- The original spelling is always retained. The normalised key is a matching aid and is never shown as the source value.
- A variant is accepted by a human. Automated matching may propose variants only.
- A name that could refer to two places (such as a townland and a DED, or two townlands in different parishes) is stored against both, and flagged ambiguous.

### 4.1 Variants already visible in the current files

| Observed | Likely relation | Action |
|---|---|---|
| Drumenny Upper, Drummenny Lower, Drummenny Middle | Same family of names with inconsistent spelling in the dictionary | Decide one preferred spelling per place and record the other as a variant |
| Tawnawully Mountains (dictionary), Tawnawilly (microfilm index filename) | Spelling variant, possibly the same place | Verify against townlands.ie before accepting |
| Tawnagh, Tawnaghgorm, Tawnaghlahan, Tawnalary | Similar names, distinct places | Keep separate. Flag fuzzy-match risk. |
| Clogher | Townland and DED | Two place records |
| Clarcam, Clarcarricknagun, Clardrumbarren, Clardrumnagahan, Clarlougheask | Shared prefix, distinct places | Keep separate. Exact match preferred over fuzzy. |
| Drumbar, Drumbarren | Near-identical, distinct places | Flag fuzzy-match risk |
| Keadew Upper, Drumenny Upper (and Lower, Middle) | Upper, Middle and Lower qualifiers | Treat the qualifier as part of the name. Census rows may omit it. |
| Keadew Lower (1901, 1911), Keadue Lower (1926) | Not in the townland dictionary. A separate townland from Keadew Upper. | Add to the seed list. Never merge into Keadew Upper. |
| Collinboy (1926), Cullionboy (1901, 1911) | Spelling variant of one townland | Propose Collinboy as a variant of Cullionboy. Lowest-confidence phonetic match, review first. |
| Tinnycahil, Tennycahill (1926), Finny Cahill (1901) | Spelling variants of one townland | Propose both as variants of Tinnycahil. Review. |
| Spierstown, Spearstown (1926), Shierstown (1901) | Spelling variants of one townland | Propose as variants of Spierstown. |
| Finnabanes, Finabanes (1926), Finnabunes (1901) | Spelling variants of one townland | Propose as variants of Finnabanes. |
| Druminnin, Druminin (1926) | Spelling variant of one townland | Propose Druminin as a variant of Druminnin. |
| Clardrumbarren, Clardrimbarren (1926), Clardrumbarron (1901) | Spelling variants of one townland | Propose as variants. |
| Clardrumnagahan, Clardrimnagahan (1926), Clardumnagahan (1901) | Spelling variants of one townland | Propose as variants. |
| Clarlougheask, Clarlougheske (1926) | Spelling variant of one townland | Propose as a variant. |
| Mullanalamphry, Mullinalamphery (1926) | Spelling variant of one townland | Propose as a variant. |
| Birchhill, Birchill (1901) | Spelling variant of one townland | Propose as a variant. |
| Drumbarren, Drumbarron (1901) | Spelling variant of one townland | Propose as a variant. Note Drumbar is a different townland. |
| Carnbeagh North, Carnbeigh North (1926) | Spelling variant of one townland | Propose as a variant. |

The rows from Keadew Lower onwards come from the 1926 matching test (section 10). They are proposals from automated matching, not accepted variants. Entries marked "likely" are hypotheses, not facts. All still need confirmation from townlands.ie and the source images.

## 5. Hierarchy

A parent link table, with time validity.

| Field | Description |
|---|---|
| child_place_id | For example a townland |
| parent_place_id | For example a DED, civil parish or barony |
| relationship | within_ded, within_civil_parish, within_barony, within_county |
| valid_from / valid_to | When the link held |
| source | Authority for the link |

A townland normally has one DED, one civil parish and one barony at a given date. Different hierarchies (civil, Catholic, electoral) are separate relationship types, not one tree. Census sources record DED, so DED links are needed first.

## 6. Matching procedure for source records

For each observation carrying a place string:

1. Normalise the string to a key.
2. Look for an exact match on a variant, restricted where possible by the DED recorded in the same row.
3. If exactly one place matches, create a proposed association with method `variant_match`.
4. If several places match, create no association. Flag for review with the candidates.
5. If none match, try phonetic matching and create a proposed association with method `phonetic_match`, but only when the phonetic key points to exactly one place. Confidence is medium. Never auto-accept.
6. If none match phonetically, try fuzzy matching and create a proposed association with method `fuzzy_match` and low confidence. If the best two candidates score within 0.05 of each other, treat it as ambiguous and create no association. Never auto-accept.
7. If still none, record as unresolved and surface the string for review. An unresolved string is a candidate for a place missing from the gazetteer, not necessarily a bad spelling (see Keadew Lower in section 4.1).
8. A reviewer accepts or rejects. Accepted new spellings become accepted variants with the source recorded.

The phonetic key used in the 1926 test lower-cases the string, treats c and k alike, y and i alike, ue and ew alike, and ou and ow alike, collapses doubled letters, and drops interior vowels. It is a matching aid only and is never shown as the source value.

Using the DED column to disambiguate is important, but it only helps once more than one DED is loaded. The census files carry both `townland` and `ded` fields (and the 1901 and 1911 files carry `townland_clean` and `ded_clean`). Matching always runs on the original `townland` value, which is preserved. The cleaned value is a proposed normalisation by an earlier process. It is used only as a cross-check and never as the gazetteer match, because it can merge distinct places: in 1901 and 1911 `townland_clean` folds Keadew Lower into Keadew Upper.

## 7. Seeding and maintenance

1. Seed from the project townland dictionary and townlands.ie. Keep both as preserved source files. The dictionary is known to lack Keadew Lower, so reconcile it against townlands.ie and add any other missing townlands before census association begins.
2. Assign place IDs and register them.
3. Add variants from each source as it is processed, always as `proposed` first.
4. Keep a change log: what changed, when, why, who accepted it.
5. Retired or merged places follow the registry rules (never reuse, link to successor).

## 8. Validation

- Every place has exactly one place_type and a unique place_id.
- No two places share the same preferred_name and place_type within the same parent.
- Every accepted variant cites a source.
- Every association references a place_id that exists.
- Every townland has at least one DED parent link before census association begins.
- Report: unresolved strings, ambiguous strings, and fuzzy matches awaiting review, per source.

## 9. Open decisions

| Item | Notes |
|---|---|
| Preferred spelling policy | Official (townlands.ie or OSI) versus the spelling found in Griffith's. Proposed: official for display, historical forms as variants. |
| Granularity of time validity | Needed only if boundary or name changes affect Donegal townlands in the study period. Start simple. |
| Catholic parish units | Needed for parish registers. Defer until that source is specified. |
| Source for Irish names | Logainm is the candidate. Check licence and attribution. |
| Whether Drumhome parish townlands load at the start | Likely yes, to avoid reworking later. |
| Verification of every variant in section 4.1 | The census CSVs have now been used. townlands.ie and the source images still need checking. |
| Missing townlands in the dictionary | Keadew Lower found. Others may exist outside the Clogher DED. |
| Tawnawully versus Tawnawilly | Still unverified. Not exercised by the Clogher census files. |

## 10. First test

Process the 1926 Clogher file. Success means every row resolves to a place ID or lands in a reviewable unresolved list, with no silent matches.

### 10.1 Result, 2026-11-01

The test was run against the townland dictionary as the seed list, with no gazetteer IDs yet. Nothing was auto-accepted.

| Census | Rows | Exact | Phonetic | Fuzzy | Unresolved |
|---|---|---|---|---|---|
| 1926 | 665 | 263 | 392 | 0 | 10 |
| 1911 | 829 | 815 | 0 | 0 | 14 |
| 1901 | 948 | 733 | 140 | 58 | 17 |

- Every unresolved row is Keadew Lower (Keadue Lower in 1926). The dictionary lacks it.
- In 1926 there are 20 distinct townland strings. Twelve differ from the dictionary spelling. Eleven resolve to a single phonetic candidate and one (Keadue Lower) is unresolved.
- Weakest matches to review first: Collinboy (0.84), Tennycahill (0.86), Finny Cahill in 1901 (0.86).
- In all three files every row has DED = Clogher, so DED disambiguation was not exercised.
- Phonetic matching alone produced no ambiguous results on this data. This is a small test set and does not show the method is safe against the full set of Drumholm townlands, where Tawnagh, Tawnaghgorm and similar names sit close together.

The review list of every distinct place string, with proposed match and status, is the next input to human review.
