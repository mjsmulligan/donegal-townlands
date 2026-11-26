# Druminnin status

Logainm ID: 13969

## Place record

This case was created from the Logainm place register.

The place identity and current place-register details are held in
`place.json`. The case exists independently of the availability of
historical records.

## Research status

Census returns and the Griffith's index are attached to this case.

Estate records before Griffith's (added 2026-11-23, branch `data/druminnin-estate-sources`):
the Lough 1825 map reference sheet (NLI MS L 441, 17 holdings and 109 plots) and the
1831 Arran rental (22 lines), with the Griffith's map holdings (50) from the user's own
transcription. They are in `data/source/estate_records/arran_donegal/`, and the proposed
links across the three are in `data/research/associations/druminnin_holdings_crosswalk.csv`.
The household identifier for these sources is the holding number. See that folder's
`SCHEMA.md`. Nothing from these sources is used by the build or the story yet.

## Open questions

- John in the 1831 dated rental page reads McNamee, the undated pages read McArea at the same line and rent. Held open.
- The 1825 plots have no holding id yet.
- Harraghy (the user's label) is read Kirraghy in 1825 and Hanaghey in 1831. No Harraghy appears later. Corrigan holds three plots in the Griffith's map holdings. Whether Corrigan took over that ground is not tested.
- Gethins in the Griffith's map holdings is a McGettigan variant (the user). Verified by the user on 2026-11-23.
- Confirm historical spellings and any relevant variations.
- Establish historical place relationships where the evidence permits.
- Add historical records with references to their original sources.

## Townland story (2026-11-24)
`python tools/build_story.py druminnin` now opens with two estate beats, the Lough 1825 map (seventeen holdings, 22 tenants) and the 1831 Arran rental (22 tenants), before Griffith's. Counts only, taken from `data/source/estate_records/arran_donegal/normalised/druminnin_holdings_observations.csv`.
Open: the Griffith's beat says 36 occupiers (askaboutireland index), while the user's own transcription of the Griffith's map has 50 plots. The two are different counts (index entries against map plots) and are held open, not reconciled.
Open: the story does not yet follow families across 1825, 1831 and Griffith's; the crosswalk (`data/research/associations/druminnin_holdings_crosswalk.csv`) is still `proposed`.

## Griffith's printed page (2026-11-24)
The printed Griffith's page for Druminnin numbers 51 plots (1 to 51), plot 51 with no occupier. The user's sheet has 50, leaving 51 out for want of a name. The left column of the page is now held in `data/source/estate_records/arran_donegal/raw/griffiths_valuation_druminnin_page94_scan_left_column.csv`. Differences from the sheet are held open in `data/research/associations/druminnin_griffiths_sheet_vs_printed_page.csv`: plots 20 and 21 (Hugh McGinty on the sheet, Hugh Cassidy on the page), plot 1 spelling, and the layout of plots 3, 18 and 43. The 36 occupiers in the askaboutireland index remain a different count (index entries, not plots). Lessor, description and valuation columns to be added later.

## Family beats (2026-11-24)
The user accepted the holdings crosswalk as good enough for the story. Eleven of its thirteen rows are now `accepted`. Harraghy and Gillespie stay `proposed` (Open: Harraghy absent from Griffith's and every census, the Corrigan link is a hypothesis; Gillespie has no earlier record) and are not in the story. The story has eight family beats, authored in plain voice in `data/research/associations/druminnin_family_beats.csv` and used only while every crosswalk row they draw on is `accepted`.
Held out of the captions on purpose: the 1831 John line (McNamee on the dated page, McArea on the undated ones), plot counts for Cassidy and McGinty in Griffith's (plots 20 and 21 are Hugh McGinty on the user's sheet and Hugh Cassidy on the printed page), and the cause of the Gethins form.

## Authored study (2026-11-24)
Druminnin now has `townland.json` and `content.json`, so it builds as a ready study. Griffith's is the printed page: 38 occupier lines covering 51 plots, plots and occupiers only (lessor, description, area and valuation are blank and the walk leaves those columns out until they are filled). Plot 51 is printed with no occupier and is kept as a blank row. The Earl of Arran row carries `nofamily` so it makes no family plate. A new "Before the valuation" plate shows the 1825 and 1831 tenants as written. No authored family stories yet, so family plates are still generated from the census and Griffith's names.
Open: plots 20 and 21 (Cassidy on the printed page, McGinty on the user's sheet).

## Story review (2026-11-25)
The footnotes now name third-party sources only, and the Explore button opens a hub of the eight families and the record sources (DECISIONS.md, 2026-11-25; spec section 10). Not yet built: the two-part spine, the opening caption with its fact and family count, and highlight families. Open: the eight family beats still sit together at 1855 on the ribbon, which is the timeline problem the user named.


## Story families (2026-11-25)
The story now rewinds the clock for each family (DECISIONS.md, 2026-11-25). Highlights by rule: McGinty and Cassidy.

Open, not resolved: authored captions in `data/research/associations/druminnin_family_beats.csv` disagree with the census in two places. Thomas says "four Thomas households in 1901 and three in 1911"; the census has four and three Thomas people in two households each year. McNamee says "one in 1911"; the 1911 McNamee is a boarder (household 2), not a household head. The captions are kept as authored, and no generated census beat is made for those years.

The story's Griffith's caption now says 51 plots (the printed page), not 36 (index entries). The 36 and the 51 are different counts and stay open (2026-11-25).

## Census form image (2026-11-26)
The story's census milestone shows the 1926 Form B (house and building return, two pages, stamped STAT/1/8/36/DRUMININ/B/1 and B/2), kept as supplied in `data/source/census_images/1926/druminnin/`. The 1901 and 1911 forms are not added yet; they need NAI credit wording first. NAI credit wording is in the "Credits and licences" panel. Awaiting the user's phone check of the pager, the zoom and the panel.
