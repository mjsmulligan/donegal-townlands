# Census GEDCOM spec

Status: agreed in principle by Mike on 2026-11-07 (see the settled list at the end). Nothing here is built. Read with `docs/DATA_ARCHITECTURE.md` (sections 3, 5, 6.2, 7), `docs/RESEARCH_PRINCIPLES.md` and `docs/STORY_SPEC.md`.

## 1. Purpose

The 1901, 1911 and 1926 returns are close enough to follow the same person from one to the next. A census-only family can then be told as a sequence ("Ellen was twelve in 1901, twenty-two in 1911 and still at home in 1926") without a tree. The method is an automated pass that proposes links with a confidence, then Mike's review. Only accepted links are used.

This is a supporting layer for stories. Identity matching is not the purpose of the project (`docs/RESEARCH_PRINCIPLES.md`), so every link stays a reviewed proposal about the evidence, never a conclusion that replaces it.

## 2. Where it sits

- A census row is an observation with a deterministic ID such as `census1901:clogher:6040537`. Rows are never edited.
- A link between two rows is an association (DATA_ARCHITECTURE 6.2), with a new type, `same-person-across-returns`. It carries method, signals, confidence, status, reviewer and date, and it keys on the two observation IDs, so it survives reprocessing.
- A chain is the set of rows joined by accepted links. Its working ID is `chain:` plus the earliest observation ID. It is not a research entity and gets no UUID until it is promoted, for example when it joins a person in Mike's tree.
- The census GEDCOM is generated from accepted chains. It is a source-like input to the project GEDCOM, in the way Mike's own GEDCOM is (DECISIONS 2026-11-05). It is not a townland-specific master, so "one master GEDCOM" (DATA_ARCHITECTURE 7) stands. Merging the two into the project GEDCOM belongs to the incorporation work that WP16 and WP17 began, and is out of scope here.

## 3. Inputs

The three census files for a DED, as held in `data/census/` and `data/source/census/`.

| Year | Row ID | Household key | Useful columns |
|---|---|---|---|
| 1901, 1911 | `id` | townland plus `house_number` | surname, firstname, age, sex, relation_to_head, marriage_status, marriage_years, children_born, children_living, birthplace, language, occupation |
| 1926 | `a_id` | `aform_name` (the form) | first_name, surname, updated_age, updated_sex, updated_relationship_to_head, updated_marriage, years_married, children_born_alive, children_living, birthplace_county |

Scope is within one DED. A person who moves between townlands inside the DED can still be linked. Links across DEDs come later.

## 4. Matching

1. **Candidates.** Pair rows in consecutive returns (1901 to 1911, 1911 to 1926) and 1901 to 1926 for people the 1911 return does not show. Candidates must share a DED and sex, and a surname that is identical or a verified spelling family in `data/reference/surname_variants.csv`. Unverified spellings are never combined.
2. **Signals.**
   - Given name: identical, or a verified equivalent from a new reference, `data/reference/given_name_variants.csv`, kept like the surname dictionary (Bella and Isabella, Maggie and Margaret, Minnie, Packie). Only Mike verifies a row.
   - Age: the gap should equal the years between the returns. Allow 3 years of drift, widening to 6 where the implied birth is before 1864, since those ages were estimates (DECISIONS 2026-11-06).
   - Household: same townland and house, same head, and the share of other household members who also have candidates.
   - Relationship: whether the change is plausible (Son to Head, Single to Married, Daughter to Wife).
   - Marriage and children: `marriage_years` should fit the gap. Children counts should not fall.
   - Birthplace and language, where recorded.
3. **Women who marry.** A daughter in 1901 is usually a wife under another surname by 1911 or 1926, and the returns do not give the maiden name. These links rest on given name, age, townland and the husband's household, so they cap at low confidence unless Mike's tree supplies the maiden name.
4. **Assignment.** Each row links to at most one row in each other return. Where two rows compete for one candidate, the better pair wins only if it is clearly better. Otherwise both stay ambiguous.
5. **Confidence.** Config values, not code, tuned against the test below.
   - High: one clear candidate, identical or verified name, age within 3, same household continuity.
   - Medium: one clear candidate but one signal weaker, such as an age gap of 4 to 6, a nickname, or a move of townland inside the DED.
   - Low: ambiguous, name and age only, or a surname change.
6. **No inference from absence.** A row with no link is unlinked, and nothing is concluded about death or emigration. Rejected pairs are never proposed again.

## 5. Review

- The tool writes a review report, not decisions, to `data/processed/` (not committed, like the WP16 reports).
- The report is grouped by household and sorted by confidence, so Mike can accept a whole household chain in one step when every link in it is high.
- Mike edits the status column, and an `accept` command writes only accepted and rejected rows to `data/research/associations/census_links.csv`, with reviewer and date, as WP16 does.
- Review policy (agreed 2026-11-07): Mike reviews medium and low links and audits a random sample of high links. The tool can also list everything if he wants it.
- Review is done in pieces. First a townland, with every household in it, then one family at a time inside that townland. The report can be cut by townland or by family surname group, and the first full run is Cullionboy.

## 6. The census GEDCOM

Generated from accepted chains, one file per DED, never edited by hand.

- One `INDI` per chain. Every spelling recorded across the returns is kept as a separate `NAME`, and the first return gives the primary name. Sex as recorded.
- A `BIRT` with an `ABT` year from the age in the earliest return, tagged as derived, with a note naming the return it came from (agreed 2026-11-07). The ages as recorded stay on the census events.
- One census event per return, with the place (townland, DED, county), the age as recorded and a source citation to the observation ID. Nothing else is stated as an event. No marriages or deaths are inferred.
- Families only where the return states the relationship in one household: a Head and Wife make a `FAM`, and a Son or Daughter of the Head is a child of the head. A child joins the wife in the `FAM` only if `years_married` and the children counts allow it, which covers a head who had married before. Sons-in-law, servants and visitors get no family.
- Mike's tree anchors the result. The 75 accepted GEDCOM-to-census links are fixed. A row used by an anchor is never reassigned. If the matcher disagrees with an anchor it is shown as a conflict for review and the anchor stands until Mike says otherwise.
- Persons in both files appear once, tied by the person pointer.

## 7. Using it in stories

Each family gets a fact sheet. Each fact in it is marked as coming from an accepted census chain, the tree, or Griffith's. The census chain tier in `docs/STORY_SPEC.md` uses only accepted chains. An unaccepted link is not mentioned.

## 8. Privacy

- Census files up to 1926 are custodian-published and are not withheld a second time (CLAUDE.md, decided 2026-11-02). The validator still refuses census files after 1926.
- The generated GEDCOM adds no event the returns do not state. Anyone with later data comes from Mike's tree under his own privacy check.
- A person aged under one in 1926 turns 100 in 2026, so no one in the returns is under the limit this year.
- The generated GEDCOM is regenerated when needed and is not committed (agreed 2026-11-07). The decisions file and the tools are.

## 9. Test plan

The only independent check is Mike's tree. It is small: of the 56 tree people with accepted census rows, 12 have rows in more than one return, giving 19 consecutive pairs (18 within one DED).

1. **Recovery.** Run the matcher on the Clogher and Tullynaught DEDs. Report how many of the 19 pairs it finds, at what confidence, and any it links wrongly.
2. **Distribution.** For Cullionboy and Clogher, count proposed links by confidence, and count ambiguous rows.
3. **Known hard cases.** The two John Cassidys in Cullionboy must not reach high confidence.
4. **Audit.** A sample is too small to prove precision, so Mike audits 50 random high links per DED before any high-confidence bulk accept is trusted.

## 10. Proposed work packages

Not yet added to `docs/WORK_PACKAGES.md`.

- **WP18** given-name reference and the matcher, with the review report.
- **WP19** `accept` command and `census_links.csv`, with validator checks.
- **WP20** census GEDCOM writer, with tree anchoring and conflict report.
- **WP21** fact sheet per family and the story check from `docs/STORY_SPEC.md`.

## 11. Settled 2026-11-07

1. Review medium and low links and audit a sample of high ones, in pieces: a townland first, then one family at a time.
2. The GEDCOM carries a derived `BIRT` with `ABT`, because it suits the stories.
3. The generated GEDCOM is regenerated, not committed.
4. The census GEDCOM is a generated input layer and not a townland-specific master, for now.
5. Mike verifies the given-name reference.
6. Linking across DEDs is a second phase. Mike expects something larger then, including hyperlinking between people in the presentation, so the chain IDs and links should be designed to support it.
