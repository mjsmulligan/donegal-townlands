# Census refresh 20261110T202721Z (1901, 1911)

- Acquired (UTC): 2026-11-10T20:27:21Z
- Source: https://api-census.nationalarchives.ie/census/query/census-records.csv
- Files replaced in the repository: yes
- Source: National Archives of Ireland census, CC BY 4.0. The CSVs are saved as supplied by NAI.
- This report is an audit aid. It does not modify any data.

## Summary

| Year | DED | Logainm ID | Previous records | New records | Added | Removed | Changed | of which serialisation only | Unchanged | Bytes identical | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1901 | Clogher | 1372439 | 4114 | 4114 | 0 | 0 | 4114 | 4114 | 0 | no | passed |
| 1901 | Donegal | 1372456 | 2785 | 2785 | 0 | 0 | 2785 | 2781 | 0 | no | passed |
| 1901 | Laghy | 1372507 | 1343 | 1343 | 0 | 0 | 1343 | 1343 | 0 | no | passed |
| 1901 | Tawnawully | 1372542 | 709 | 709 | 0 | 0 | 709 | 709 | 0 | no | passed |
| 1901 | Tullynaught | 111482 | 1193 | 1193 | 0 | 0 | 1193 | 1187 | 0 | no | passed |
| 1911 | Clogher | 1372439 | 4080 | 4080 | 0 | 0 | 4080 | 4080 | 0 | no | passed |
| 1911 | Donegal | 1372456 | 2641 | 2641 | 0 | 0 | 2641 | 2641 | 0 | no | passed |
| 1911 | Laghy | 1372507 | 1225 | 1225 | 0 | 0 | 1225 | 1225 | 0 | no | passed |
| 1911 | Tawnawully | 1372542 | 670 | 670 | 0 | 0 | 670 | 670 | 0 | no | passed |
| 1911 | Tullynaught | 111482 | 1080 | 1080 | 0 | 0 | 1080 | 1080 | 0 | no | passed |

Rows are matched on the record ID (`a_id` for 1926, `id` for 1901 and 1911) and compared on the columns both files have. The previous snapshots were written through pandas, which wrote the text `nan` for blanks and wrote whole numbers as floats (`70.0`). NAI's own file has neither. A difference that is only that is labelled serialisation only. Every other difference is labelled substantive and is a difference between the two NAI releases (or, for a column GRA changed, between GRA's version and NAI's), which is what to review.

## Clogher 1901

DEDs in the file: Clogher (948), Magheraclogher (3166)
NAI's response also held 4080 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 4114 (4114 serialisation only). First substantive changes (full list in changes.csv, column kind):


## Donegal 1901

DEDs in the file: Donegal (2785)
NAI's response also held 2641 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 2785 (2781 serialisation only). First substantive changes (full list in changes.csv, column kind):

- id 6387593 Nora Matilda O'Neill (Diamond): language was 'nan', now 'None'
- id 6387676 Thomas McGinty (Main Street): language was 'nan', now 'None'
- id 6387855 Eliza McCarberry (Main Street): education was 'nan', now 'None'
- id 6388059 Catherine McCay (Quay Street): occupation was 'nan', now 'None'

## Laghy 1901

DEDs in the file: Laghy (1343)
NAI's response also held 1225 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 1343 (1343 serialisation only). First substantive changes (full list in changes.csv, column kind):


## Tawnawully 1901

DEDs in the file: Tawnawully (709)
NAI's response also held 670 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 709 (709 serialisation only). First substantive changes (full list in changes.csv, column kind):


## Tullynaught 1901

DEDs in the file: Tullynaught (1193)
NAI's response also held 1080 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 1193 (1187 serialisation only). First substantive changes (full list in changes.csv, column kind):

- id 6041362 Freddie Scott (Moyne): occupation was 'nan', now 'None'
- id 6041414 William Kee (Moyne): deafdumb was 'nan', now 'None'
- id 6041415 Susan Kee (Moyne): deafdumb was 'nan', now 'None'
- id 6041416 Samuel Kee (Moyne): deafdumb was 'nan', now 'None'
- id 6041417 Robert Wm Kee (Moyne): deafdumb was 'nan', now 'None'
- id 6041418 Mary J Kee (Moyne): deafdumb was 'nan', now 'None'

## Clogher 1911

DEDs in the file: Clogher (829), Magheraclogher (3251)
NAI's response also held 4114 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 4080 (4080 serialisation only). First substantive changes (full list in changes.csv, column kind):


## Donegal 1911

DEDs in the file: Donegal (2641)
NAI's response also held 2785 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 2641 (2641 serialisation only). First substantive changes (full list in changes.csv, column kind):


## Laghy 1911

DEDs in the file: Laghy (1225)
NAI's response also held 1343 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 1225 (1225 serialisation only). First substantive changes (full list in changes.csv, column kind):


## Tawnawully 1911

DEDs in the file: Tawnawully (670)
NAI's response also held 709 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 670 (670 serialisation only). First substantive changes (full list in changes.csv, column kind):


## Tullynaught 1911

DEDs in the file: Tullynaught (1080)
NAI's response also held 1193 rows of the other census year, which are not in this file.
Columns in the previous file that NAI's file does not have: townland_clean, ded_clean. Columns in NAI's file that the previous file did not have: none.

Added 0, removed 0, changed 1080 (1080 serialisation only). First substantive changes (full list in changes.csv, column kind):


