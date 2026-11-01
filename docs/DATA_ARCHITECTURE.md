# Donegal Townlands: Data Architecture

Status: Working specification, draft 2
Date: 2026-11-01
Location in repository: `docs/DATA_ARCHITECTURE.md`

This is the central working specification for the Donegal Townlands data architecture. It records agreed principles, states open decisions explicitly, and is updated as the architecture is tested against real sources.

## 1. Purpose and guiding principle

> GRA tells us what the sources contain. Donegal Townlands investigates what those records tell us about the history of a place.

- The townland is the primary unit of research and presentation.
- Family histories provide the human narrative within that place-based framework.
- Donegal Townlands is not a downstream publishing layer for GRA. It can acquire, process and research sources independently where that is simplest and most reliable.

## 2. Layers

| Layer | Role |
|---|---|
| 1. Source | Original datasets, documents and images exactly as obtained. Never altered. |
| 2. Processing | Source-specific extraction, transcription, ETL, normalisation and place association. |
| 3. Research | Structured models of people, families, properties, places, events and conclusions. |
| 4. Presentation | Townland-centred website drawing on the research models. |

Processing a source must never be confused with the conclusions drawn from it.

## 3. Five kinds of thing

Every piece of data belongs to exactly one of these. They are stored and identified separately.

1. **Source record**: the original document, image, row or entry.
2. **Observation**: information extracted or transcribed from a source record, plus any normalised values (original value always retained alongside).
3. **Association**: a link between an observation and a place (see section 6).
4. **Research entity**: an established person, family, property or place, with its own Donegal Townlands identifier.
5. **Assertion**: a research conclusion that cites observations and carries its own uncertainty (see section 9).

## 4. Source acquisition and processing

1. Download the original dataset into the project data area.
2. Preserve it unchanged, with a checksum and acquisition record (date, URL or repository, version).
3. Apply source-specific ETL to produce a research-ready form.
4. Retain traceability from every processed row back to the original record.
5. Associate observations with places during processing and research, not during acquisition.

Consequences:

- Acquisition is not limited to townlands under investigation. Original datasets stay complete.
- ETL is as simple as possible and specific to the source. A census CSV, a parish register image, a valuation book and a Duchas entry are not forced through one universal importer.
- A shared framework sets common principles. Each source type has its own import specification (section 12).

## 5. Identifiers

A Donegal Townlands identifier is generated when a research entity is formally established, not when a source record is imported.

### 5.1 Four kinds of identifier

| Kind | Example | Format |
|---|---|---|
| Original source locator | Archive reference, NLI image number, census row | As given by the source |
| Observation ID | `census1926:clogher:<a_id>` | Deterministic (see 5.2) |
| Research entity ID | Person, property, place | UUID (proposed) |
| GEDCOM pointer | `@I123@` | Internal to one GEDCOM file only. Never a permanent identifier. |

### 5.2 Deterministic observation IDs (agreed)

Observation IDs are built from source, locator and row so that reprocessing reproduces the same ID.

- Pattern: `<source>:<scope>:<locator>`
- The locator rule matters because sources differ. The 1901 and 1911 files carry an `id` column. The 1926 file carries only `a_id`. Each import specification states which field forms the locator and how uniqueness is verified.
- Where the source has no stable identifier, the specification defines a derived locator (for example image number plus line number) and records how it was derived.
- Reprocessing must either reproduce the same ID or fail loudly. It must never silently renumber.

### 5.3 Identifier registry (agreed in form, details open)

One append-only table, not a service.

| Field | Purpose |
|---|---|
| id | The identifier |
| type | person, family, property, place, source-record, assertion |
| status | active, merged, split, retired |
| successor | Identifier(s) that replace it, where applicable |
| date | When the status was set |
| reason | Why, with a pointer to the decision record |

Rules:

- Identifiers are never reused.
- Retired identifiers stay in the registry and resolve to their successors or status.
- Merge and split decisions are documented as decision records.
- Observation IDs are deterministic and are not registered individually. Research entities and assertions are.

## 6. Places and associations

### 6.1 Place authority (gazetteer): new, proposed as first decision

"Townland" cannot be treated as a plain string. The current files already show why:

- Clogher is both a townland and a district electoral division (DED).
- Spelling varies between sources and over time (for example Drumenny and Drummenny, Tawnawully and Tawnawilly).
- Different sources use different administrative units (townland, DED, parish, barony, civil parish).

The gazetteer provides:

- A stable place ID for every place.
- Alternate names, each with source and date range.
- A parent hierarchy (townland, DED, civil parish, barony, county) with time validity where boundaries or names changed.
- A place type, so that a townland and a DED of the same name are distinct places.

Place associations point to place IDs, never to name strings.

### 6.2 Associations are entities, not fields

A source record may relate to several townlands, or to none yet identified. For example, a marriage record may place the bride in Clogher and the groom in Cullionboy. It remains one record with two associations.

Each association records:

| Field | Examples |
|---|---|
| observation ID | Stable, deterministic |
| place ID | From the gazetteer |
| association type | residence, birthplace, event location, property location |
| method | exact name match, variant match, phonetic match, fuzzy match, manual |
| confidence | high, medium, low, with a note |
| status | proposed, accepted, rejected |
| reviewer and date | For accepted or rejected |

Because associations key to deterministic observation IDs, they survive reprocessing.

## 7. Genealogical research model: one master GEDCOM

- One master GEDCOM for the whole project. No townland-specific GEDCOM files.
- Contains people, families and relationships, genealogical events, and citations attached to individual facts and events.
- GEDCOM is the genealogical backbone, not the complete historical research database.
- GEDCOM pointers are not Donegal Townlands identifiers.
- Citations support individual facts, not a general bibliography.
- A source observation does not establish identity. Person matching is subject to human review.

Open: GEDCOM 7 as target version, pending compatibility and round-trip testing in the intended genealogy software. GEDCOM 7 `UID`, `EXID` and `REFN` are candidate carriers for Donegal Townlands identifiers. The choice needs testing, including whether identifiers survive edit and regeneration.

## 8. Wider historical research model (property and land)

Griffith's Valuation and the Valuation Revision Books need a separate model. It should represent:

- Properties and land holdings.
- Occupiers and owners.
- Valuation entries and changes over time.
- Relationships between properties, people and places.
- Other historical information that does not belong in the genealogical model.

A person in the master GEDCOM may be linked to a recorded occupier where the evidence supports it. The detailed structure is an open decision to be settled using Valuation records as the test case.

## 9. Assertions store: new, proposed

Some conclusions belong in neither GEDCOM nor the property model. Example: "this holding was subdivided between 1856 and 1901."

An assertion has:

| Field | Purpose |
|---|---|
| assertion ID | Registered identifier |
| statement | The claim, in plain language |
| subject | Research entities and places it concerns |
| supporting observations | Observation IDs and entity IDs cited |
| conflicting evidence | Observation IDs that cut against it |
| confidence | With a note on why |
| status | draft, reviewed, accepted, withdrawn |
| author, reviewer, dates | Who proposed it and who reviewed it |

Narrative on the website may cite assertions. Assertions cite observations. Readers can follow the chain back to the original source.

## 10. Connecting the models

The GEDCOM, the property model and the assertions store refer to the same entities through Donegal Townlands identifiers, never through GEDCOM pointers. The presentation layer draws on all three, so a townland history can combine families, land and wider developments.

## 11. Evidence, provenance and conclusions

Keep these distinct throughout:

- Original documentary evidence.
- Transcriptions and extracted observations.
- Normalised or interpreted values.
- Research identities and relationships.
- Analytical conclusions and narrative.

Further principles:

- Narrative is not mechanically generated. Assistants may draft. The project owner reviews the evidence and can change or remove material where evidence is weak.
- Readers can follow links to the original primary sources (for example NLI images), not just to project datasets.
- Uncertainty and conflicting evidence are preserved, not resolved silently.
- Automated processing may suggest links. It must never silently turn a suggestion into an accepted identity or association.

## 12. Source-specific import specifications

Each source type gets its own specification covering:

1. Source and repository.
2. Acquisition method and original format.
3. Preservation arrangements.
4. Extraction or transcription process.
5. Field mapping and normalisation.
6. Observation ID construction (locator rule).
7. Provenance and links to original evidence.
8. Place association method.
9. Validation and error handling.
10. Reprocessing arrangements.

## 13. Research workflow

1. Acquire the source material.
2. Preserve the original unchanged.
3. Process with source-specific ETL or transcription.
4. Retain observations and provenance.
5. Associate observations with places (proposed associations).
6. Review association and identity suggestions.
7. Accept associations. Establish a research identity only where justified.
8. Generate a Donegal Townlands identifier and register it.
9. Update the master GEDCOM, property model and assertions store.
10. Attach citations and links to original evidence.
11. Validate and publish to the presentation layer.

## 14. Relationship with GRA

Donegal Townlands may reuse GRA's source catalogue, provenance architecture and ETL where useful. However:

- GRA is not a mandatory acquisition or processing gateway.
- The project owns its data and identifiers and does not require GRA record IDs.
- There is no assumed universal GRA-to-Townlands export contract.
- Sources are tracked in three states: specified in a catalogue, implemented, and actually ingested.

## 15. Implementation test cases

| Order | Source | What it tests |
|---|---|---|
| 1 | 1926 Census (existing Clogher file) | Acquisition, preservation, source-specific ETL, deterministic observation IDs from `a_id`, gazetteer-based place association, traceability |
| 2 | Parish registers | Image-based records, transcription, citations, links to NLI images |
| 3 | Valuation records | Property and land model, occupier and valuation changes over time |

1901 and 1911 follow the 1926 pattern but use an `id` locator, which makes them a useful check that the locator rule generalises.

Use these to test and refine the architecture before adding complexity.

## 16. Decision status

### Agreed

- Townland-centred research and presentation.
- Original source material preserved unchanged.
- Source-specific processing, no universal ETL.
- One master GEDCOM. No townland-specific GEDCOMs.
- Separate wider historical model, including property data.
- Citations on individual facts and events.
- Stable Donegal Townlands identifiers connect the models.
- Human review of identity conclusions.
- Observations distinguished from established research entities.
- One source record may associate with multiple townlands.
- Direct links to original primary sources.
- Associations are entities with type, method, confidence and status.
- Deterministic observation IDs built from source, locator and row. UUIDs reserved for established entities.
- Central registry is a single append-only table.

### Proposed, needs agreement or testing

| Item | Notes |
|---|---|
| Place gazetteer | Proposed as the first decision. Everything else depends on it. |
| Assertions store | Structure in section 9 is a first draft. |
| GEDCOM 7 as target | Needs compatibility and round-trip testing. |
| UUID format and version | Which UUID version, and how generated and checked. |
| GEDCOM `UID`, `EXID`, `REFN` use | Needs testing in the intended software. |
| Identifier retention on GEDCOM edit or regeneration | Needs a tested procedure. |
| Property research model structure | Settle using Valuation records. |
| Intermediate processing formats | Per source. |
| Folder structure and implementation | After the above. |

## 17. Repository follow-up

Reflect this specification consistently in `AGENTS.md` and the shared assistant protocol. Reconcile any existing guidance that describes Townlands as merely downstream of GRA, or assumes a universal export contract.
