# Tawnawilly parish register: data schema (DRAFT for review, 2026-11-17)

Source: NLI Microfilm 04599/04, Tawnawilly (Raphoe). Images: https://registers.nli.ie/pages/vtls000631954_0NN (NN = page).
Coverage: baptisms pp 4-36, marriages pp 37-43. Pages 44-45 were never supplied.

Location in the repo: `data/source/nli_parish/tawnawilly/`.

```
data/source/nli_parish/tawnawilly/
  SCHEMA.md
  raw/
    tawnawilly_baptisms_raw.csv
    tawnawilly_marriages_raw.csv
  overrides_seed_from_interpreted_rows.csv     starting point for stage 2 overrides
  (later) normalised/ and overrides.csv
```

Shared reference data already exists in the repo and is used as is, not duplicated here:
- `data/reference/surname_variants.csv`: the single surname dictionary (DECISIONS.md, 2026-11-06). Family rows, not as-written pairs. Only Mike verifies a row. A new family or spelling from this register is added as `proposed`, which changes nothing until Mike verifies it.
- `data/reference/given_name_variants.csv`: the given-name equivalents (Sera = Sarah, Cath. = Catherine and so on, once verified).
- Place spellings go through the Logainm place layer (`data/processed/places/`, `census_spelling_review.csv`). A suffix such as Lower, Middle or Upper is part of the name and is never merged.

Source conventions that are specific to this register (for example the Do. rule) are documented here and are not reference data.

Relationship to the repo's source-data principles (CLAUDE.md): there is no custodian transcription of this register, so the raw files are our own transcription of the NLI images, not data supplied as is. They are the source layer for this register and are changed only by recorded adjudication (the `resolved_reading` and resolution columns) in reviewed commits, so git history is the audit trail. Downstream interpretation lives in separate files and never changes them.

## 1. Two stages

| | Stage 1: raw | Stage 2: normalised |
|---|---|---|
| Question answered | What does the page say? | What does it mean, in a form we can use? |
| Source of truth | Yes | No, always derived |
| Parsed into roles | No, strings only | Yes |
| Editable by hand | Yes, via adjudication fields | No, regenerate instead |
| Evidence allowed | The image, the clerk's hand, other entries in this register, local knowledge | Everything in stage 1, plus census, dictionaries, civil records, reference tables |

Rule of thumb: stage 1 is a reading task, stage 2 is an interpretation task. Checking how the clerk forms a letter, or how the same name is written elsewhere in the register, is a reading task.

## 2. Keys

- `row_id`: stable, human readable, e.g. `TAW-B-p004-r001` (B baptism, M marriage). Page + record_no is the natural key but record_no repeats across pages.
- Clerk's own numbering is followed. Extras use a letter suffix (`70b`) or a `U_` prefix for unnumbered entries, as in the current files.
- Raw and normalised files share `row_id`, so every normalised row points back to exactly one raw row.

## 3. Raw file columns (stage 1)

| Column | Meaning |
|---|---|
| `row_id` | See above |
| `record_type` | baptism or marriage |
| `page`, `record_no` | As on the register |
| `image_url` | Page image |
| `reading_1_source` | claude or manual |
| `reading_1` | First reading, one string |
| `reading_2_source` | gemini or manual (blank if no second reading) |
| `reading_2` | Second reading, one string |
| `status` | See section 5 |
| `resolved_reading` | The single adopted string. Blank until status is agreed or resolved |
| `resolution_basis` | See section 6 |
| `resolution_by` | Who adjudicated, e.g. mike |
| `resolution_date` | ISO date |
| `resolution_note` | Which part was decided and why, in a sentence |
| `comment` | Transcription notes: ink, damage, margin notes, binding, clerk slips, no priest signature |

Notes:
- No parsing and no role labels. No F:, M:, S: prefixes.
- DECIDED (A): one string per entry, with ` | ` between printed columns in page order. Keep it simple and atomic.
- For status `agreed`, `resolved_reading` is filled from `reading_1`. For `disputed` and `unresolved` it stays empty.
- Differences between the two readings are computed by diff at review time, not stored by hand.

### Verbatim conventions for readings

- Keep exactly what is written: abbreviations (Wm., Patk., Margt.), spelling, capitalisation, the clerk's date form (`7th`, `Feb. 6th`), `Do.` and ditto marks, `Widow`, `Mrs.`.
- Do not expand Do., do not complete dates, do not convert Latin names.
- Notation inside a string:
  - `[?]` after a doubtful word or letter group
  - `[illegible]` for lost text
  - `[struck: text]` for struck-out text
  - `[margin: text]` for marginal notes
  - `[cut]` where binding or page edge removes text
- Anything longer than a short mark goes in `comment`.

## 4. Normalised file columns (stage 2)

Built by `normalised/build_normalised.py`. One row per raw row, same order, same `row_id`.

Baptisms: `row_id, page, record_no, date_iso, child_forename, father_forename, father_surname, mother_forename, mother_surname, townland, townland_status, sponsor1..sponsor4, priest, raw_status, confidence, rules_applied`.

Marriages: `row_id, page, record_no, date_iso, groom_forename, groom_surname, bride_forename, bride_surname, witness1, witness2, priest, raw_status, confidence, rules_applied`.

| Column | Meaning |
|---|---|
| `date_iso` | `YYYY-MM-DD`, or `YYYY-MM` where the day is not known |
| `townland_status` | From `rules.csv`: verified, dictionary, probable, possible, ambiguous, unresolved, unmapped, institution. Blank when no place is written |
| `raw_status` | The raw row's status. A row that is not `agreed` or `resolved` is built from `reading_1` as a working value and is not settled |
| `confidence` | certain, probable, possible. Blank when only rules were applied. Comes from `overrides.csv` (lowest on the row) |
| `rules_applied` | Every change made to the written form, e.g. `father_surname: Trower > Travers; override sponsor1: Patt. Mall > Patrick Moss` |

The text used is `resolved_reading` where it exists, otherwise `reading_1`. Derived in stage 2 only: parsing into roles, date to ISO, forename expansion, surname variants, townland spelling. Priest is carried as written (empty if no signature). `comment` and the two reading columns stay in raw.

## 5. Status values (raw)

| Status | Meaning | `resolved_reading` |
|---|---|---|
| `agreed` | Both readings match | filled automatically |
| `single_reader` | Only one reading exists | filled from `reading_1`, flagged for second reading |
| `disputed` | Readings differ, not yet reviewed | empty |
| `resolved` | Reviewed and decided | filled by adjudication |
| `unresolved` | Reviewed, image or evidence cannot settle it | empty, or both candidates in `resolution_note` |

Migration from the current `row_status`: agreed to agreed, single_reader to single_reader, disputed to disputed, adjudicated to resolved. Current `interpreted` rows move to `overrides.csv` and the raw row keeps the page reading.

## 6. Resolution basis tags (raw)

Combine with `;` where needed.

- `image`: re-read the page image
- `hand`: compared with the clerk's letterforms elsewhere on the page or register
- `register`: same name or entry written elsewhere in this register
- `local`: local knowledge (Mike)
- `ditto_rule`: Do. resolved under the standing rule

Not allowed as a basis in stage 1: census, surname dictionary, civil records, GRO indexes, family trees. Those go in stage 2 (`overrides.csv`).

DECIDED (B): civil records are stage 2 only. They need their own stage 1 capture first, because the current transcriptions do not record all of their data. So each external source (civil BMD lookups, and later others) gets its own raw file in the same pattern (verbatim strings, readings, status, resolution), and `overrides.csv` cites those rows by id in `interpretation_basis` rather than pasting values.

## 7. Rules and override files (stage 2)

In `normalised/`, next to the build script, and read by it.

`rules.csv` (`kind, as_written, normalised, status, basis`) applies to every occurrence:
- `forename`: abbreviation or variant expansion (Patt. to Patrick), matched on the whole forename text, then word by word. Status `abbreviation`.
- `surname`: variant mapping on the whole surname text (Trower to Travers). Status `proposed`: they were marked verified in the earlier normalised file, but nothing here is in the shared dictionary until Mike verifies it in `data/reference/surname_variants.csv`. This file adds nothing there.
- `townland`: written place to Logainm spelling, with `status` becoming `townland_status` and `basis` saying why. A blank `normalised` means the place is unresolved or unmapped and is kept out of the output rather than guessed.

`overrides.csv` (`row_id, field, as_read, value, basis, confidence, decided_by`) is one row per evidence-based or adjudicated choice that is not a rule, for example Mall to Moss or a partial adjudication from the raw file. `field` is a normalised column. The basis says what the choice rested on. Overrides never change the raw layer.

Shared reference data (surname dictionary, given-name variants, Logainm place layer) is in `data/reference/` and `data/processed/places/`. Promoting a rule from here to there is Mike's decision.

## 8. Build and versioning

- Rebuild after any change to raw, `rules.csv` or `overrides.csv`: `python data/source/nli_parish/tawnawilly/normalised/build_normalised.py`. `--check` fails if the committed outputs differ from a rebuild. `tests/test_tawnawilly_normalised.py` runs that check, so a stale output fails the tests.
- Never edit a normalised file by hand.
- Review commit recipe: enter the adjudications in raw (`resolved_reading`, basis, by, date, note), rebuild, run `python tools/source_manifest.py register-update`, run `python tools/validate.py` and `python -m pytest -q tests`, commit.
- CSV hygiene for clean diffs: fixed column order, rows in page order, UTF-8, LF line endings, no newlines inside cells.
- One commit per review batch, message naming pages and row counts.
- Tag snapshots at the end of each phase.

## 9. Round trip (done 2026-11-17)

The first build was checked against the earlier normalised files (baptisms with the 2026-11-17 judgments applied, and marriages). Every field in all 677 rows matches, with one explained exception. `TAW-B-p012-r146` lists Rose Kelly twice in reading 1. The earlier file put the second one in `sponsor4` and left `sponsor3` blank, which was a fault in that pipeline. The build puts her in `sponsor3`. Reading 2 has her once, so the repeat in reading 1 is probably a slip, to check on the image.

## 10. Open decisions

Decided 2026-11-17:
- A: one string per entry, ` | ` between printed columns
- B: civil records are stage 2, each with its own stage 1 capture
- C: two files (baptisms, marriages) with the same raw schema; `record_type` stays as a column for safety
- D: the older as-written files are not needed. The current work is the base. They may be used later for comparisons if that adds value.

- E: existing raw strings are accepted as they are. `reading_1` is the Claude reading and `reading_2` is the Gemini reading, copied unchanged (so reading_2 keeps its F:/M:/S: labels, and reading_1 keeps its expanded Do. and completed dates). The Do. positions stay recoverable from reading_2. Four full passes (two each by Claude and Gemini) are judged enough, no further verbatim pass is planned.

Notes on the first build:
- 21 baptism rows are `resolved` from the 2026-11-17 judgments, 5 stay `disputed` with the settled and open parts in `resolution_note`, and 76 stay `disputed` awaiting review. `resolution_date` is the date the judgments were entered, not the date each page was checked.
- Three baptism entries share p21 rec 385 (clerk's number repeated). They are `TAW-B-p021-r385`, `.2` and `.3` in file order. record_no is left as written.
- The 13 rows previously marked `interpreted` had no reader disagreement. They are `agreed` (or `single_reader`) in raw, and their interpretations are in `overrides.csv` (seeded from `overrides_seed_from_interpreted_rows.csv`) for stage 2.
- Raw `comment` keeps only page notes and Gemini transcription notes. Variant mappings, reader-disagreement text and similar derived notes are left to stage 2.
