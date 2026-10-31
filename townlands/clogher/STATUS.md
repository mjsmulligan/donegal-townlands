# Clogher status (Clogher DED, Donegal)

Page: `docs/clogher/index.html`, built from `engine/walk.html`, `townland.json`, `content.json` and `records/census.json`. Draft for review. Not yet linked from `docs/index.html`.

## Sources in
- Griffith's Valuation (mid 1850s), Parish of Donegal, page 96, transcribed from an image into `content.json` (`griffiths.rows`). Areas (with the water entry) and total valuations add exactly to the printed totals.
- Census 1901, 1911, 1926 (`data/census/`, extracted to `records/census.json`). Clogher townland rows only: 125, 112 and 89 people in 27, 23 and 20 households.
- townlands.ie for area, Irish name and neighbours.
- Tawnawilly registers: page index only (`data/Microfilm_04599_04_Tawnawilly_index.csv`), no names, so no Clogher baptisms or marriages yet.

## Missing
- Tithe Applotment, valuation revision books, civil BMD from 1864, parish register entries.
- Land and buildings split of each Griffith's valuation (the transcription holds totals only). Those two columns are blank.
- Links to the original records: census page URLs and the Griffith's page. Research principles ask for these.

## Open
- Griffith's lots 3 and 20 areas are the least certain readings. Publication year and union still to confirm.
- 1926: four ages missing, three Hone women with no age, "English Only" for everyone, Kone, two Flanagan women both named Unity (82 and 62).
- 1911: house numbers 12 and 15 have no Clogher rows.
- Further open items are listed in the page's "What is still open" plate (`questions` in content.json).

## Notes
- Built from the earlier Clogher Claude Doc study (27 Oct 2026). Its Griffith's map plan, "Who held land beside whom" section and "On the map" paragraphs are left out, because the map is not part of the standard process.
- Family plates count everyone in a household headed by that surname. The study counted everyone carrying the surname, so people totals differ (for example Flanagan 1926: 1 here, 4 in the study). Household counts agree in every case.
- Two infants recorded as age 0 in 1926 (James Hone, form 2, and John Lynch, form 11) were born 1925 or 1926 and only just meet the 100 year rule this year.

## Handover
- Outcome: Clogher page built on the per-townland engine, with the Griffith's transcription, 11 family plates and a smaller-families plate.
- Validation: `python tools/validate.py` ok; page renders with 20 plates and no script errors.
- Review: no independent review yet.
- Next step: Mike to confirm publishing, then add the Griffith's land and buildings split and the original-record links.
