# Research principles

## The townland is the primary unit of research

The purpose of Donegal Townlands is to tell the history of individual townlands through the surviving historical evidence relating to those places.

The townland, rather than the individual or family, is the organising framework for research. Its geography, land, holdings, population, households and development over time provide the historical context.

Griffith's Valuation is a foundational source because it records land and occupation within townland boundaries. Census records, maps, church and civil records, and other historical sources add further dimensions to the history of the same place.

## Family histories provide the human narrative

The townland is the organising framework, but the richness and human interest of the narrative will come largely through the histories of the families who lived there.

Family histories should explore continuity and change across generations, household composition, occupations, landholding, migration and other aspects of family life, where the evidence permits.

Identifying the same individuals across different records is a useful analytical technique, but it is not the primary purpose of the project. Do not allow the Grá approach or data model to dictate the structure of Donegal Townlands.

## Evidence before interpretation

Maintain a clear distinction between:

1. Direct evidence: what historical records actually state.
2. Analysis and interpretation: what the evidence suggests when records are compared and considered together.
3. Conclusions: what can reasonably be established about the townland and its families.

Preserve original recorded details. Do not silently replace them with normalised or inferred values. Identify the evidence supporting significant interpretations. Distinguish established facts from probable identifications and hypotheses. Retain uncertainties and contradictory evidence.

The presentation should make the direct evidence accessible before presenting interpretations or conclusions.

## Relationship with Grá and the role of ingestion

Grá (GRA) and Donegal Townlands have different organising purposes. Grá is a person-centred research engine: its pipelines ingest records and apply genealogical rules and probabilistic methods to link records into persons. Donegal Townlands is townland-centred and independent of that approach. It does not adopt person matching as its organising method and does not depend on Grá's matching engine, record identifiers or pipelines.

Donegal Townlands may acquire and process sources directly where that is the simplest and most reliable approach. It owns its data and its identifiers. There is no export contract between the projects. The historical source record, with its provenance and the information needed to trace it to the original source, is the fundamental unit of evidence. Donegal Townlands organises, compares and interprets records in the context of a townland. Decisions that records relate to the same person, household or family are primarily matters for human research and review. Any proposed relationship must remain distinguishable from what the source itself records.

Elements of Grá's design may be reused where they help. Its source catalogue, provenance architecture, source definitions, record structures and URL patterns (including those for Catholic parish registers and the Dúchas Schools Collection) are an existing design resource, and Grá may help with ETL for particular source data files. Reuse is chosen case by case. It is not an obligation and not a gateway that every source must pass through. A source being described in a catalogue does not mean its ingestion has been implemented or tested. Assistants must distinguish clearly between specified capability, implemented capability and data actually ingested.

The data architecture that follows from this is set out in `docs/DATA_ARCHITECTURE.md`.

In short: **Grá tells us what the sources contain. Donegal Townlands investigates what those records tell us about the history of a place.**

## Link readers to original sources

Wherever possible, significant factual claims in a townland history should link to the original historical or archival source, not only to a project transcription, dataset or summary.

Readers should be able to inspect the primary source for themselves and draw their own conclusions. Links should lead as directly as possible to the relevant original record, page, register entry or image, rather than merely to a general archive or collection landing page.

Project transcriptions and datasets remain valuable as searchable indexes and as a means of presenting structured research. They supplement the original sources; they do not replace them. Where an original source is unavailable online, provide a clear source reference so that readers can identify and, where possible, consult it.

The narrative is the project's considered interpretation of the evidence. Editorial review determines which interpretations are included and how they are expressed. Making the original sources accessible allows readers to examine the basis for that narrative independently.

## Implementation

1. Inspect the existing repository documentation before making changes.
2. Incorporate these principles into the appropriate research methodology document.
3. Ensure the assistant protocol explicitly requires assistants to follow these principles.
4. Update the workflow documentation where appropriate.
5. Avoid unnecessary duplication: use a clear foundational statement and refer to it from other documents.
6. Preserve existing useful material and terminology.
7. Report exactly which files were changed and summarise the changes.

Do not undertake an unrelated redesign or alter existing research findings as part of this task.

