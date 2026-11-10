# 1926 census refresh 20261110T082907Z

- Acquired (UTC): 2026-11-10T08:29:07Z
- Source: https://c26-api.nationalarchives.ie/api/census/query_c26a/census-records.csv
- Files replaced in the repository: yes
- Source: National Archives of Ireland 1926 Census, CC BY 4.0. The CSVs are saved as supplied by NAI.
- This report is an audit aid. It does not modify any data.

## Summary

| DED | Logainm ID | Previous records | New records | Added | Removed | Changed | of which serialisation only | Unchanged | Bytes identical | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Clogher | 1372439 | 3627 | 3622 | 0 | 5 | 3622 | 51 | 0 | no | passed |
| Donegal | 1372456 | 2352 | 2366 | 15 | 1 | 2351 | 0 | 0 | no | passed |
| Laghy | 1372507 | 994 | 994 | 0 | 0 | 994 | 29 | 0 | no | passed |
| Tawnawully | 1372542 | 512 | 512 | 0 | 0 | 512 | 26 | 0 | no | passed |
| Tullynaught | 111482 | 894 | 901 | 17 | 10 | 884 | 22 | 0 | no | passed |

Rows are matched on `a_id`. The previous snapshots were written by GRA through pandas, which used CRLF line endings, wrote the text `nan` for blanks and wrote whole numbers as floats (`70.0`). NAI's own file has none of these. A difference that is only that is labelled serialisation only and is not a correction by NAI. Hashes change on a first refresh regardless. Substantive differences are the ones to review.

## Clogher

DEDs in the file: Clogher (665), Magheraclogher (2957)

Added 0, removed 5, changed 3622 (51 serialisation only). First substantive changes (full list in changes.csv, column kind):

- a_id 2645136 Mary McCafferty (Ardnagappery): relationship_to_head was 'Head', now 'Wife'
- a_id 2645136 Mary McCafferty (Ardnagappery): updated_relationship_to_head was 'Head', now 'Wife'
- a_id 2645137 Johnie McCafferty (Ardnagappery): relationship_to_head was 'nan', now 'Son'
- a_id 2645137 Johnie McCafferty (Ardnagappery): updated_relationship_to_head was 'nan', now 'Son'
- a_id 2645138 Teague McFadden (Ardnagappery): relationship_to_head was 'Head', now 'Son'
- a_id 2645138 Teague McFadden (Ardnagappery): updated_relationship_to_head was 'Head', now 'Son'
- a_id 2645139 Katherine McFadden (Ardnagappery): relationship_to_head was 'nan', now 'Head'
- a_id 2645139 Katherine McFadden (Ardnagappery): updated_relationship_to_head was 'nan', now 'Head'
- a_id 2645140 Mary Margaret McFadden (Ardnagappery): relationship_to_head was 'nan', now 'Mother Head'
- a_id 2645140 Mary Margaret McFadden (Ardnagappery): updated_relationship_to_head was 'nan', now 'Head'
- a_id 2645140 Mary Margaret McFadden (Ardnagappery): updated_marriage was 'nan', now 'Both Parents Alive'
- a_id 2645141 Bella McFadden (Ardnagappery): relationship_to_head was 'nan', now 'Daughter'
- a_id 2645141 Bella McFadden (Ardnagappery): updated_relationship_to_head was 'nan', now 'Daughter'
- a_id 2645141 Bella McFadden (Ardnagappery): updated_marriage was 'nan', now 'Both Parents Alive'
- a_id 2645142 Bridget Gallagher (Ardnagappery): relationship_to_head was 'nan', now 'Son'
- a_id 2645142 Bridget Gallagher (Ardnagappery): updated_relationship_to_head was 'nan', now 'Son'
- a_id 2645143 Peggie Doogan (Ardnagappery): birthplace_county was 'nan', now 'Down'
- a_id 2645143 Peggie Doogan (Ardnagappery): updated_age was '7.0', now '67'
- a_id 2645144 Anthony Doogan (Ardnagappery): relationship_to_head was 'nan', now 'Head'
- a_id 2645144 Anthony Doogan (Ardnagappery): updated_relationship_to_head was 'nan', now 'Head'

### New NAI rows against the working copy 1926_Clogher.csv

The working copy is never modified. It holds researcher-filled values, so differences are expected and are listed here for review only.

- Working copy records: 665. NAI records for this DED: 665.
- In NAI only: 0. In the working copy only: 0. Rows that differ: 665 (0 serialisation only). Identical rows: 0.

Substantively differing fields (count of rows):

- updated_relationship_to_head: 519
- years_married: 338
- relationship_to_head: 153
- children_born_alive: 150
- updated_marriage: 145
- updated_religion: 138
- children_living: 118
- updated_age: 56
- updated_sex: 20
- surname: 18
- first_name: 14
- birthplace_county: 12
- updated_irish_language: 1

## Donegal

DEDs in the file: Donegal (2366)

Added 15, removed 1, changed 2351 (0 serialisation only). First substantive changes (full list in changes.csv, column kind):

- a_id 2943157 Charles McKelvey (Ballydevitt): relationship_to_head was 'Head', now ''
- a_id 2943158 Maggie McKelvey (Ballydevitt): relationship_to_head was 'Sister', now ''
- a_id 2943158 Maggie McKelvey (Ballydevitt): updated_marriage was 'nan', now 'Single'
- a_id 2943159 Patrick Campbell (Altidoo): relationship_to_head was 'Head', now ''
- a_id 2943160 Oonah Campbell (Altidoo): relationship_to_head was 'Sister', now ''
- a_id 2943160 Oonah Campbell (Altidoo): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2943161 John O'Donnell (Altidoo): relationship_to_head was 'Head', now ''
- a_id 2943161 John O'Donnell (Altidoo): birthplace_county was 'nan', now 'Scotland'
- a_id 2943161 John O'Donnell (Altidoo): updated_age was 'nan', now '43'
- a_id 2943162 Brigid O'Donnell (Altidoo): relationship_to_head was 'Daughter', now ''
- a_id 2943162 Brigid O'Donnell (Altidoo): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2943163 Daniel O'Donnell (Altidoo): relationship_to_head was 'Son', now ''
- a_id 2943163 Daniel O'Donnell (Altidoo): updated_marriage was 'nan', now 'Mother is Dead'
- a_id 2943163 Daniel O'Donnell (Altidoo): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2943164 Brigid Lavin (Altidoo): relationship_to_head was 'Head', now ''
- a_id 2943164 Brigid Lavin (Altidoo): updated_age was 'nan', now '29'
- a_id 2943165 Mary E Lavin (Altidoo): relationship_to_head was 'Daughter', now ''
- a_id 2943165 Mary E Lavin (Altidoo): updated_marriage was 'nan', now 'Both Parents Alive'
- a_id 2943165 Mary E Lavin (Altidoo): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2943165 Mary E Lavin (Altidoo): birthplace_county was 'nan', now 'United States'

## Laghy

DEDs in the file: Laghy (994)

Added 0, removed 0, changed 994 (29 serialisation only). First substantive changes (full list in changes.csv, column kind):

- a_id 2605700 Hugh McGrath (Ballykillowen): relationship_to_head was 'Head', now 'Servant'
- a_id 2605700 Hugh McGrath (Ballykillowen): updated_relationship_to_head was 'Head', now 'Servant'
- a_id 2605701 John J Doherty (Ballykillowen): birthplace_county was 'nan', now 'Scotland'
- a_id 2605702 Farney Doherty (Ballykillowen): relationship_to_head was 'nan', now 'Wife'
- a_id 2605702 Farney Doherty (Ballykillowen): updated_relationship_to_head was 'nan', now 'Wife'
- a_id 2605702 Farney Doherty (Ballykillowen): birthplace_county was 'nan', now 'Scotland'
- a_id 2605703 Mary Doherty (Ballykillowen): relationship_to_head was 'nan', now 'Visitor'
- a_id 2605703 Mary Doherty (Ballykillowen): updated_relationship_to_head was 'nan', now 'Visitor'
- a_id 2605703 Mary Doherty (Ballykillowen): birthplace_county was 'nan', now 'Scotland'
- a_id 2605704 Patrick Cassidy (Ballykillowen): relationship_to_head was 'Head', now 'Visitor'
- a_id 2605704 Patrick Cassidy (Ballykillowen): updated_relationship_to_head was 'Head', now 'Visitor'
- a_id 2605705 James Cassidy (Ballykillowen): relationship_to_head was 'Head', now 'Son'
- a_id 2605705 James Cassidy (Ballykillowen): updated_relationship_to_head was 'Head', now 'Son'
- a_id 2605706 John Cassidy (Ballykillowen): relationship_to_head was 'nan', now 'Son'
- a_id 2605706 John Cassidy (Ballykillowen): updated_relationship_to_head was 'nan', now 'Son'
- a_id 2605707 Maggie E Cassidy (Ballykillowen): relationship_to_head was 'nan', now 'Servant'
- a_id 2605707 Maggie E Cassidy (Ballykillowen): updated_relationship_to_head was 'nan', now 'Servant'
- a_id 2605708 Mary Anne Cassidy (Ballykillowen): relationship_to_head was 'nan', now 'Employee'
- a_id 2605708 Mary Anne Cassidy (Ballykillowen): updated_relationship_to_head was 'nan', now 'Employee'
- a_id 2605709 James Cassidy (Ballykillowen): relationship_to_head was 'nan', now 'Head'

## Tawnawully

DEDs in the file: Tawnawully (512)

Added 0, removed 0, changed 512 (26 serialisation only). First substantive changes (full list in changes.csv, column kind):

- a_id 2748465 Bernard Martin (Ardatowel): relationship_to_head was 'Head', now 'Wife'
- a_id 2748465 Bernard Martin (Ardatowel): updated_relationship_to_head was 'Head', now 'Wife'
- a_id 2748466 Ann Martin (Ardatowel): relationship_to_head was 'Wife', now 'Sister'
- a_id 2748466 Ann Martin (Ardatowel): updated_relationship_to_head was 'Wife', now 'Sister'
- a_id 2748466 Ann Martin (Ardatowel): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2748467 Bridget Martin (Ardatowel): relationship_to_head was 'Daughter', now 'Head'
- a_id 2748467 Bridget Martin (Ardatowel): updated_relationship_to_head was 'Daughter', now 'Head'
- a_id 2748467 Bridget Martin (Ardatowel): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2748468 John Martin (Ardatowel): relationship_to_head was 'Son', now 'Wife'
- a_id 2748468 John Martin (Ardatowel): updated_relationship_to_head was 'Son', now 'Wife'
- a_id 2748468 John Martin (Ardatowel): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2748469 Francis Martin (Ardatowel): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2748470 James Martin (Ardatowel): relationship_to_head was 'Son', now 'Daughter'
- a_id 2748470 James Martin (Ardatowel): updated_relationship_to_head was 'Son', now 'Daughter'
- a_id 2748470 James Martin (Ardatowel): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2748471 Peter Cassidy (Ardatowel): relationship_to_head was 'Head', now 'Daughter'
- a_id 2748471 Peter Cassidy (Ardatowel): updated_relationship_to_head was 'Head', now 'Daughter'
- a_id 2748472 Ellen Cassidy (Ardatowel): relationship_to_head was 'Wife', now 'Grandson'
- a_id 2748472 Ellen Cassidy (Ardatowel): updated_relationship_to_head was 'Wife', now 'Grandson'
- a_id 2748473 John Cassidy (Ardatowel): relationship_to_head was 'Son', now 'Head'

## Tullynaught

DEDs in the file: Tullynaught (901)

Added 17, removed 10, changed 884 (22 serialisation only). First substantive changes (full list in changes.csv, column kind):

- a_id 2772510 William Gillespie (Aghlem): relationship_to_head was 'Head', now 'Wife'
- a_id 2772510 William Gillespie (Aghlem): updated_relationship_to_head was 'Head', now 'Wife'
- a_id 2772510 William Gillespie (Aghlem): updated_religion was 'nan', now 'Roman Catholic'
- a_id 2772511 John Gillespie (Aghlem): relationship_to_head was 'Brother', now 'Daughter'
- a_id 2772511 John Gillespie (Aghlem): updated_relationship_to_head was 'Brother', now 'Daughter'
- a_id 2772512 Catherine Gillespie (Aghlem): relationship_to_head was 'Sister', now 'Son'
- a_id 2772512 Catherine Gillespie (Aghlem): updated_relationship_to_head was 'Sister', now 'Son'
- a_id 2772513 Edward Gillespie (Aghlem): relationship_to_head was 'Head', now 'Daughter'
- a_id 2772513 Edward Gillespie (Aghlem): updated_relationship_to_head was 'Head', now 'Daughter'
- a_id 2772514 Margaret Gillespie (Aghlem): relationship_to_head was 'Wife', now 'Daughter'
- a_id 2772514 Margaret Gillespie (Aghlem): updated_relationship_to_head was 'Wife', now 'Daughter'
- a_id 2772515 Francey Gillespie (Aghlem): relationship_to_head was 'Son', now 'Head'
- a_id 2772515 Francey Gillespie (Aghlem): updated_relationship_to_head was 'Son', now 'Head'
- a_id 2772516 Agnes Gillespie (Aghlem): relationship_to_head was 'Daughter', now 'Wife'
- a_id 2772516 Agnes Gillespie (Aghlem): updated_relationship_to_head was 'Daughter', now 'Wife'
- a_id 2772517 Annie Gillespie (Aghlem): relationship_to_head was 'Daughter', now 'Servant'
- a_id 2772517 Annie Gillespie (Aghlem): updated_relationship_to_head was 'Daughter', now 'Servant'
- a_id 2772518 Lizzie Gillespie (Aghlem): relationship_to_head was 'Daughter', now 'Head'
- a_id 2772518 Lizzie Gillespie (Aghlem): updated_relationship_to_head was 'Daughter', now 'Head'
- a_id 2772518 Lizzie Gillespie (Aghlem): updated_marriage was 'nan', now 'Single'

