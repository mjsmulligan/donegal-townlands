# Cullionboy status (Clogher DED, Donegal)

Page: `docs/cullionboy/index.html`, built from `engine/walk.html` and `records/census.json`.

## Sources in
- Griffith's Valuation (mid 1850s), transcribed from page images, in `engine/walk.html` (`GR`)
- Census 1901, 1911, 1926 (`data/source/census/`, extracted to `records/census.json`; 1926 spells it Collinboy)
- townlands.ie for area and neighbours (Clogher is to the south)

## Media
- `media/media.csv` lists two photographs, both from Mike's personal photos: the header panorama (caption "Cullionboy") and a family photograph on The Kellys plate (caption "Bella, Rose & Mary Kate Kelly").
- The header shows under the title. The family photograph shows on the Photos tab of The Kellys plate, which is the first tab (docs/MEDIA_SPEC.md).
- Caption spelling is Mike's. The 1926 census records the daughters as Mary Katie (13) and Rose Anne (12) in Bella Kelly's household (form 0002). Kept as captioned, noted here and not resolved.
- Which woman is which is not recorded, so `people_shown` is left blank.

## Griffith's index check (2026-11-04)
- The askaboutireland index (`data/source/griffiths/cullionboy_griffiths_individuals.csv`, 27 entries) agrees with the transcription: 25 of 25 occupiers match by page order and name. Entries 52 (Earl of Arran) and 53 (blank name) are not tenants. They are labelled title_entry and blank_entry, proposed readings only. Record: `records/griffiths_index.json` and `records/griffiths_match.json`, written by `tools/attach_griffiths.py`.
- The index supports the readings Dimon, Hallaghy, Mulrenin and Phideas, but it is itself a transcription, so this is corroboration and not proof.

## Story voice pilot (2026-11-07, branch story-voice-kelly)
- The Kellys plate is the pilot for the plain, lay-person voice (DECISIONS.md, 2026-11-07). Its text is one account drawn from the census, Griffith's and the family tree, with no citations, IDs, speculation or open questions. Other families still carry the earlier census-report text and are to be rewritten once Mike approves the register.

## Timeline (2026-11-18)
- `docs/cullionboy/timeline.html`, built by `tools/build_timeline.py cullionboy` from `records/timeline_events.json`: Griffith's (1850s), the 1901, 1911 and 1926 returns, and the register baptisms that name Cullionboy with an agreed or resolved reading and an exact date. Baptisms whose readings are still disputed are left out and listed by the build.
- A baptism whose place is noted as blotted on the page is shown with that doubt marked.
- Register baptisms from p19 on have no townland written, so they are not placed. The register marriages never give one.

## Missing
- Tithe Applotment, valuation revision books, civil BMD from 1864, parish records

## Open
- Griffith's lot areas sum one acre over the printed total
- Some Griffith's name readings uncertain
- Dimon to Dunnion link is a hypothesis
- 1926 return, Michael Dunnion (71, Collinboy form 0352_0011_0004): years married is recorded as "0906", which is not a plausible number of years. Kept as recorded. Found 2026-11-08 in the census link review page.
- Further open items are kept in `questions` in content.json. The page no longer shows them (the "What is still open" plate was removed 2026-11-04).

## Doc
Claude Doc 845ed338-9fd0-41b6-9388-c94ad29267d4 still says "six children" for Bella Cassidy in one place. Correct is five.

## Kelly fact sheet conflicts (2026-11-09, WP21)
- Joseph Kelly: a tree note gives age 47 at death, but the birth (8 Jun 1875) and death (27 Dec 1925) dates give 50. Held open. The Kellys story does not state his age at death.
- Thomas Kelly: aged 60 in 1901 and 74 in 1911, a drift of 4 years against the 10 between returns. Held open. The story says "about sixty" in 1901.

## Documentary (2026-11-20, DP2)
`python tools/build_documentary.py cullionboy` writes `records/documentary.json` (10 beats: title, Griffith's, two baptism beats, three censuses, two change beats, closing). Generated, never edited by hand. Two baptism rows (TAW-B-p010-r115, TAW-B-p011-r123) are left out because their readings are disputed. The 1875 baptism beat says "possibly" for Joseph Kelly because the page place is blotted. Captions wait for Mike to read them aloud and sign off. Spec: `docs/DOCUMENTARY_SPEC.md`.
