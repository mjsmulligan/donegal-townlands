# Shared Assistant Collaboration Protocol

**Sections 1 to 8 and 10 are the shared core.** Each repository keeps its own copy at `docs/SHARED_ASSISTANT_PROTOCOL.md`. The copies need not be byte-for-byte identical (see section 9), but neither may weaken the core.

This protocol governs collaboration between AI assistants working with Mike across the Donegal Townlands and Grá repositories. It supplements, and never overrides, each repository's `AGENTS.md`, project documentation, source licences, privacy rules, or Mike's explicit instructions.

## 1. Shared source of truth

- Git repositories are the durable shared workspace. Chat histories, assistant memories, and private notes are not shared project state.
- Before work, read the current repository's `AGENTS.md` and this protocol.
- Then read relevant status and decision documents. In Grá, check `ROADMAP.md` before starting. In Donegal Townlands, check the relevant townland `STATUS.md` and `DECISIONS.md`.
- For any work in Donegal Townlands, read and follow [`docs/RESEARCH_PRINCIPLES.md`](RESEARCH_PRINCIPLES.md) before research, analysis, data design, writing, or presentation work.
- Follow deeper documentation only where the task requires it. Do not assume a previous assistant's summary is current.
- If repository state is unavailable or stale, say so. Never imply that a snapshot is the live repository.

## 2. Project boundaries and relationship

- **Grá is a person-centred research and ingestion engine.** It owns its own source acquisition, ingestion, source definitions, record structures, URL patterns, evidence processing, and its person-centred record-linkage capabilities and Irish genealogical rules. Grá was originally designed around identifying records that may relate to the same person, using rules and probabilistic methods.
- **Donegal Townlands is an independent, townland-centred historical research and publishing project.** It owns its data, identifiers, source acquisition and processing, and may acquire and process sources directly. It does not adopt Grá's person-matching engine, record identifiers or pipelines as a dependency or organising method. Its organising framework is the townland, not the individual or family.
- In Donegal Townlands the fundamental unit of evidence is the source record, with its provenance and the information needed to trace it to the original source. It is not a person identity inferred by any pipeline.
- In Donegal Townlands, relationships between records and people, households or families are primarily established through human research and review. A proposed relationship must remain distinguishable from what a source directly records. Probabilistic matches from Grá may be useful as leads where available, but are not authoritative conclusions for Townlands.
- Grá's source catalogue, provenance architecture and specifications are a design resource that may be reused where useful, and Grá may help with ETL for particular source data files. They describe additional sources, repositories, record structures and URL patterns, including Catholic parish registers and the Dúchas Schools Collection. Reuse is chosen case by case and is not an obligation. Do not describe a source as implemented or ingested merely because it is specified in a catalogue. Distinguish specified, implemented and actually ingested capability.
- For Donegal Townlands, Griffith's Valuation is foundational because it records land and occupation within townland boundaries. Census records, maps, church and civil records, and other historical sources add further dimensions to the history of the place.
- For Donegal Townlands, present direct documentary evidence distinctly from analysis and interpretation, and distinguish both from conclusions. Preserve original recorded details, source provenance, uncertainty, and contradictory evidence. Identity matching can support family histories but must not become the primary purpose or organising structure of the project.
- Donegal Townlands may inform Grá's research priorities and expose gaps. Neither repository depends on the other, and nothing here authorises automatic schema, scoring, or architecture changes in Grá.
- There is no export contract between the repositories and no required data flow. Any code, data or design taken from one repository into the other is copied or referenced explicitly, with provenance and licence checked. Any future interface between the two needs design discussion and Mike's approval before implementation.
- Preserve the evidence/conclusion boundary and all project-specific architecture rules. A presentation need must not weaken research integrity.

## 3. Start every task deliberately

Before editing:
1. Identify the requested outcome and the repository in which the change belongs.
2. Read applicable instructions, status, decisions, and (for Grá) the roadmap.
3. Search for existing implementations, open work, and prior decisions.
4. State the proposed scope, files likely to change, and validation approach.
5. If the task touches a protected boundary, schema, scoring, matching behaviour, a data interface between repositories, privacy, licensing, or a material architectural decision, stop for design agreement rather than quietly implementing it.

Do not broaden a task because adjacent improvements seem attractive. Record follow-on ideas separately.

## 4. Make changes small and reviewable

- Prefer small, coherent changes that can be reviewed independently.
- Preserve source provenance and uncertainty. Never silently turn a hypothesis into a fact or a candidate match into a confirmed identity.
- Do not overwrite another assistant's unreviewed work. Inspect current diffs and repository state before editing or committing.
- Do not delete files, history, published material, or source data unless Mike explicitly asks.
- Check provenance and redistribution rights before adding data, using the relevant repository's source register.
- Follow all privacy and living-person restrictions in the relevant repository.
- Never commit credentials, tokens, private configuration, or other secrets.

## 5. Independent review is separate

- A change is not accepted merely because an assistant implemented it, tests pass, or it has been pushed.
- Where practical, ask a different assistant to review independently. The reviewer should inspect the diff and relevant context, not simply endorse the implementer's summary.
- Review correctness, scope, evidence quality, licensing, privacy, architectural boundaries, regressions, and fit to the request.
- Report specific findings, with file and line references where possible. Distinguish blocking defects from suggestions.
- The implementer should respond to each substantive finding. If assistants disagree, preserve the disagreement and present alternatives and consequences to Mike.
- Mike decides unresolved questions and whether a change is accepted. Assistant approval is not a substitute for his approval where required.

## 6. Tests and validation

- Run checks required by the repository's `AGENTS.md` and project documentation.
- Report exactly what was run and whether it passed. Do not claim checks that were not performed.
- If a check could not be run, explain why and identify the remaining risk.
- For Grá, run its required test suite. Changes affecting linkage thresholds or scoring also require the timing report and a note of material match-rate shifts.
- For Donegal Townlands, run `python tools/validate.py` before a commit and rebuild affected pages using the documented build command. Never hand-edit generated pages.

## 7. Handover for substantive work

At the end of substantive work, leave a concise handover in the repository's established status, changelog, or roadmap location. Do not create a competing log if one already exists.

A handover should state:
- **Outcome:** what changed and why.
- **Files:** important files changed.
- **Evidence and decisions:** sources used, assumptions, decisions required, and unresolved uncertainties.
- **Validation:** commands/checks run and results.
- **Review:** whether independent review occurred and open findings.
- **Git state:** branch and commit reference, if known; whether changes are committed or pushed.
- **Next step:** the smallest useful next action.

Keep durable project facts in repository documentation, not only in chat or assistant memory.

## 8. Coordinate safely across assistants

- Before editing, check whether another assistant has changed relevant files or recorded in-progress work.
- Use branches or clearly separated commits where possible. Avoid concurrent edits to the same files.
- If assistants work in parallel, agree file ownership and interfaces first.
- If a conflict occurs, do not silently choose a version. Preserve both proposals, explain the trade-off, and ask Mike.
- A push is a transfer of work, not proof of review or acceptance. Include a handover with every push intended for another assistant.
- Never assume assistants can see one another's conversations, private workspaces, or unpushed changes.

## 9. Keep the shared core consistent

- Each repository keeps a copy at `docs/SHARED_ASSISTANT_PROTOCOL.md`. The copies do not have to be identical, and no hash comparison is required.
- A repository may add project-specific wording to its copy, provided it supplements the shared core and does not contradict or weaken it, or the order of authority in section 10.
- When the shared core itself changes, make the same change in the other repository as a follow-up, in its own pull request and in its own time. Say in the pull request that the other copy still needs updating.
- Update each `AGENTS.md` only to link to this protocol and explain that it supplements repository-specific rules. Do not paraphrase the protocol in either `AGENTS.md`.
- If the two copies differ in a way that matters to the task, follow the copy in the repository you are working in, and tell Mike about the difference.

## 10. Authority and escalation

The order of authority is:
1. Mike's explicit instructions and decisions.
2. The current repository's project-specific rules and recorded decisions.
3. This shared collaboration protocol.
4. An assistant's proposed approach or preference.

When instructions conflict, stop and explain the conflict. Do not invent permission, infer approval from silence, or conceal uncertainty.

