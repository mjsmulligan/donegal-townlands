# Arran estate records, Manor of Donegal: data schema (DRAFT for review, 2026-11-23)

Sources, all for the Earl of Arran's Donegal estate:
- Maps of part of the Manor of Donegal by James Lough, made in summer 1825. National Library of Ireland, MS L 441 (Manuscripts Reading Room). One volume of 32 hand drawn, hand coloured maps, each with a facing reference page naming the land and its tenants. Map 15 (Raforker) is missing, cut out. Reproduction rights are owned by the NLI and the volume exists only as a physical copy. The date is taken from the title page, so it is an inferred date for the maps and reference pages.
- Rental of the Earl of Arran's Donegal estate for the year ending November 1831. The date is written on the page heading. The other rental pages supplied show no year of their own and are not used in these files.

Location in the repo: `data/source/estate_records/arran_donegal/`. The first townland is Druminnin.

```
raw/
  lough_1825_druminnin_tenants_raw.csv
  lough_1825_druminnin_plots_user_sheet.csv
  arran_rental_1831_druminnin_raw.csv
  griffiths_map_druminnin_holdings_user_sheet.csv
normalised/
  druminnin_holdings_observations.csv
```

The images are not held in this repository. The photographs and the user's colouring of the 1825 map are derived from an NLI volume, and the Griffith's map screenshots come from askaboutireland. Confirm the terms of each before publishing any image.

## Household identifier

As with the census and Griffith's, each observation carries a household identifier. For these sources it is the holding number (user decision, 2026-11-23):

| Source | holding_id | id_type |
|---|---|---|
| Lough 1825 reference sheet | the Ref number in the user's sheet, 1 to 17. Tenants who share a holding share the id | `holding_ref (user sheet)` |
| Arran rental 1831 | the line number on the dated page. The rental has no holding number | `rental_line (dated page)` |
| Griffith's map holdings | the map plot number, 1 to 50 | `holding_no (map plot)` |

## Raw files

Source layer. Names and numbers are as written, with no expansion and no correction.

- `lough_1825_druminnin_tenants_raw.csv`: one row per tenant line on the reference sheet, read from a photograph. The areas (right-hand columns) are cropped in the photograph and are not transcribed, and the lot numbers are not transcribed because the photograph is slanted.
- `lough_1825_druminnin_plots_user_sheet.csv`: the user's own table of the 109 plots on the 1825 map, with the family for each plot. The `holding_id` column is blank because the user's sheet gives the family, not the holding.
- `arran_rental_1831_druminnin_raw.csv`: the 22 Druminnin lines on the dated 1831 page, with the yearly rent as written (pounds, shillings, pence). The line for John (McNamee on this page) is unresolved: the undated rental pages read John McArea at the same position and rent. Both readings are kept and neither is merged.
- `griffiths_map_druminnin_holdings_user_sheet.csv`: the user's transcription of the Griffith's map holdings, 50 rows, with the occupier string as in the user's sheet. It supplements the askaboutireland index in `data/source/griffiths/`, which is not changed.

## Normalised file

`normalised/druminnin_holdings_observations.csv`: one row per tenant or occupier line, all three sources together. Columns: `source, source_date, date_basis, holding_id, id_type, tenant_seq, forename_as_written, surname_as_written, yearly_rent, interpreted_surname, interpretation_basis, confidence, notes`. The as-written columns are never changed. The interpreted surname, its basis and its confidence carry the interpretation. It is derived, so it is regenerated and not edited by hand once a build script exists. There is no build script yet.

## Links across sources

`data/research/associations/druminnin_holdings_crosswalk.csv` holds proposed links by family: the holders in 1825, 1831 and the Griffith's map holdings, how far the forenames carry over, and a link strength. Every row is `proposed`. The user decides.

## Open items

1. Registration in `data/source/manifest.csv`: `tools/source_manifest.py` knows only the census files and the NLI parish registers, so these files are not in the manifest. Extending it needs the user's agreement.
2. The exact year of the Griffith's valuation for Druminnin is not yet filled in.
3. The 1825 plots need a holding id. A flat photograph of the right-hand half of the reference sheet, or a holding column in the user's sheet, would settle it.
4. John McNamee in the 1831 dated page against John McArea in the undated pages.
5. Surname spellings from these sources are listed as proposals in `data/research/associations/druminnin_surname_proposals.csv`, not in `data/reference/surname_variants.csv`, because the reference file holds verified rows only (a test enforces it). They change nothing until the user verifies them and they are moved into the reference file.
6. A map of Druminnin dated 1811, of unknown source, was used by the user only as a guide to reading names. It is not citable and is not in these files.
