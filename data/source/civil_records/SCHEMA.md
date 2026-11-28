# Civil records: data schema (DRAFT for review, 2026-11-28)

Source: the civil registers of births, marriages and deaths (General Register Office), as seen on irishgenealogy.ie or on a register image. Civil registration of Catholic marriages began in 1864 and of all births and deaths in 1864.

Location in the repo: `data/source/civil_records/`.

```
data/source/civil_records/
  SCHEMA.md
  births.csv
  marriages.csv
  deaths.csv
  batches.csv
```

## 1. How this source differs from the parish registers

The Tawnawilly register was one fixed set of pages, transcribed as a single batch. Civil records are added a few at a time, from different places, as the user sources them. So these files are append-only working source files, and each addition is logged in `batches.csv`.

There is no hand-typed adjudication layer like the register's. The register form already has fixed columns, so each form column is a CSV column, kept as written.

## 2. Principles

1. **As written.** Values are kept as the register or site shows them. No spelling is corrected, no date is converted, no name is split or normalised. Reading doubts go in `comment`.
2. **Graduated provenance.** Every row says how far it has been checked (section 4). A row can move up. It is never deleted when it moves.
3. **Append only.** Rows are added. A change to a row is a correction with a reason in `comment`, and a row that gains an entry number is renamed with the old ID kept in `previous_row_id`.
4. **A search is not a conclusion.** `batches.csv` records what was searched. The absence of a record from these files says nothing about the register (CLAUDE.md, no inference from absence).
5. **Stage 2 is derived.** ISO dates, surname families, townlands resolved through Logainm and observation IDs belong to a later derived layer and are never written into these files.

## 3. Keys

- `row_id` is `CIV-<B|M|D>-<district>-<year>-<entry_no>`, where the district is in lower case with no spaces, the year is the year of registration and the entry number has three digits. Example: `CIV-M-mountcharles-1878-006`.
- The entry number is the number printed on the register entry. It restarts each year in each registrar's district, so district, year and entry number together identify a record. A second row with the same key is refused on load.
- A row sourced without an entry number (for example from an old note) gets a provisional ID `CIV-<B|M|D>-prov-<serial>` and the `comment` says so. When the entry is found the row is renamed and the old ID goes in `previous_row_id`. IDs are never reused.
- `image_id` is the identifier printed on the register image, where there is one. One image can hold several entries.

## 4. Provenance values

| Value | Meaning |
|---|---|
| `study_note` | The user's earlier transcription, not checked against the site or an image |
| `site_transcript` | Copied from the irishgenealogy.ie record page |
| `image_read` | Read from the register image by an assistant, not yet checked by the user |
| `image_checked` | The user has confirmed the row against the image |

## 5. Columns shared by all three files

| Column | Meaning |
|---|---|
| `row_id` | See section 3 |
| `record_type` | birth, marriage or death |
| `previous_row_id` | Earlier ID of a renamed row, otherwise blank |
| `image_id` | Identifier on the register image |
| `page_no` | Printed page number, where there is one |
| `entry_no` | Number printed on the entry |
| `source_url` | The record page or image link, where there is one |
| `provenance` | See section 4 |
| `batch_id` | The sourcing session that added the row (`batches.csv`) |
| `comment` | Reading doubts, marks, margin notes, anything odd |

## 6. Marriage columns (`marriages.csv`)

These follow the nine columns of the marriage register form. The groom's and bride's columns are paired.

| Column | Meaning |
|---|---|
| `church` | Where the marriage was solemnised, as written |
| `registrar_district`, `union`, `county` | As written |
| `date_married`, `date_registered` | As written, not converted |
| `registered_by` | The registrar, as read |
| `groom_name`, `bride_name` | Name and surname as written, one string |
| `groom_age`, `bride_age` | As written |
| `groom_condition`, `bride_condition` | Bachelor, spinster, widow and so on |
| `groom_rank`, `bride_rank` | Rank or profession |
| `groom_residence`, `bride_residence` | Residence at the time of marriage |
| `groom_father_name`, `bride_father_name` | Father's name and surname as written, including "dead" where written |
| `groom_father_rank`, `bride_father_rank` | Rank or profession of the father |
| `minister` | The officiating minister |
| `witness_1`, `witness_2` | The two witnesses |
| `signed_by_mark` | Which of groom, bride, witness_1 and witness_2 signed by mark |

## 7. Birth and death columns (draft)

These follow the registers' columns as I understand them, and are confirmed against the first birth and the first death image before any row is loaded.

`births.csv` adds: `registrar_district`, `union`, `county`, `date_born`, `place_born`, `child_name`, `sex`, `father_name`, `father_rank`, `mother_name` (as written, including maiden surname where given), `informant`, `date_registered`, `registered_by`, `baptismal_name_added`.

`deaths.csv` adds: `registrar_district`, `union`, `county`, `date_died`, `place_died`, `name`, `sex`, `condition`, `age`, `rank`, `cause`, `informant`, `informant_qualification` (the relationship or standing the informant states, for example Son), `date_registered`, `registered_by`.

## 8. Batches (`batches.csv`)

One row for each sourcing session: `batch_id`, `date`, `added_by`, `method`, `search_scope` (what was searched or which record was read), `rows_added`, `files` and `note`. Batch IDs have the form `B-YYYY-MM-DD-NN`.

## 9. Rules

- **Privacy** is applied by the source. The registers withhold births under 100 years, marriages under 75 and deaths under 50. The repo's own privacy validator still applies to anything built from these files.
- **Images** are not committed to the repo. `image_id` and `source_url` point at them. The user keeps the originals.
- **Source manifest.** These files are not entered in `data/source/manifest.csv`, because they change with every batch and a checksum would fail each time. `batches.csv` is their log.
- **Validation.** A later `tools/` check should confirm that every row has a unique key, a known provenance and a known batch, and that the columns match this schema. It is not built yet.
- **Surnames.** Variant spellings such as McAdden for McCadden go through `data/reference/surname_variants.csv` as proposed rows. The user verifies them.

## 10. Open items

1. Confirm the birth and death columns against a real image of each.
2. Confirm that the number printed on the image identifies it (marriage 6 of 1878, Mountcharles, shows 06058320).
3. Decide how irishgenealogy.ie page copies are loaded in bulk once the user has several.
4. Build the validation check and the stage 2 observation file.
