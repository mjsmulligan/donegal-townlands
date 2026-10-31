# Decisions

- 2026-10-31 Deliverable is a website (gallery walk), not a Claude Doc. The Cullionboy Claude Doc is kept for now.
- 2026-10-31 Host on GitHub (Pages from /docs) for simplicity. Cloudflare later, perhaps.
- 2026-10-31 Public is fine. No living people. 100/75/50 rule, not a calendar cutoff.
- 2026-10-31 Scope is Donegal only. Template may later be cloned for other counties.
- 2026-10-31 Clogher is the second townland, then Drumholm and Drumhome townlands.
- Dimon is treated as Dunnion as a working hypothesis (Cullionboy).
- Griffith's map is not part of the standard townland process (no high resolution images online).
- Tithe Applotment Books to be added as a source when available (sits before Griffith's).
- 2026-10-31 Two repos: GRA (research engine) and this one (publishing layer). One-way export contract in docs/EXPORT_CONTRACT.md. Local 1926 census copy kept as source because GRA's lacks about 500 researcher-filled relationship values.
- 2026-10-31 Engine holds no townland content. Each townland carries `townland.json`, `content.json` and `records/corrections.json`; `tools/extract_census.py <name>` and `tools/build.py <name>` are parameterised. Cullionboy was moved over and its rebuilt page checked as identical in rendered text, tables and interactions (23 of 23 plates). The 1926 Bradley form 0016 to 0017 household fix is now an explicit, reasoned correction rather than code.
- 2026-10-31 The shared assistant protocol copies in the two repos no longer have to be byte-identical. The shared core (sections 1 to 8 and 10) should stay consistent in substance, each repo may add supplementary wording, and core changes are carried across in a follow-up PR.
