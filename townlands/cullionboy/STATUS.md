# Cullionboy status (Clogher DED, Donegal)

Page: `docs/cullionboy/index.html`, built from `engine/walk.html` and `records/census.json`.

## Sources in
- Griffith's Valuation (mid 1850s), transcribed from page images, in `engine/walk.html` (`GR`)
- Census 1901, 1911, 1926 (`data/census/`, extracted to `records/census.json`; 1926 spells it Collinboy)
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
- The Kellys plate is the pilot for the family-gathering voice (DECISIONS.md, 2026-11-07). Its text is one account drawn from the census, Griffith's and the family tree, with no citations, IDs or "the records show". Other families still carry the earlier census-report text and are to be rewritten once Mike approves the register.
- The tree's Margaret Kelly (b. about 1912) is left out of the story because she may be Mary Katie recorded twice. Joseph's age at death is left out because the tree gives 47 and his birth date gives 50. Both are in `questions` in content.json.
- The tree link between Mary Kelly of Griffith's lot 5 and Thomas's mother Mary (b. about 1820) is stated in the story as a possibility only.

## Missing
- Tithe Applotment, valuation revision books, civil BMD from 1864, parish records

## Open
- Griffith's lot areas sum one acre over the printed total
- Some Griffith's name readings uncertain
- Dimon to Dunnion link is a hypothesis
- Further open items are kept in `questions` in content.json. The page no longer shows them (the "What is still open" plate was removed 2026-11-04).

## Doc
Claude Doc 845ed338-9fd0-41b6-9388-c94ad29267d4 still says "six children" for Bella Cassidy in one place. Correct is five.
