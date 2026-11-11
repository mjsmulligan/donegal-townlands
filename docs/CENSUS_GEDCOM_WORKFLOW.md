# Census to GEDCOM on GitHub Actions

Status: built 2026-11-11 (WP20). The workflow file is `.github/workflows/census-gedcom.yml`. It has been checked with a workflow linter and its steps have been rehearsed against the repository's census files, but it has not yet been run on GitHub, and the output has not yet been imported into Ancestry. Both are manual checks, set out below.

## What it does

It builds the census GEDCOM test file described in [`CENSUS_GEDCOM_SPEC.md`](CENSUS_GEDCOM_SPEC.md) without anyone running Python locally. It uses the census files already in `data/source/census/`, the accepted links in `data/research/associations/` and the tree anchors already in the repository. Nothing is uploaded by hand.

It produces up to two files, which are never mixed:

| File | What it holds | When |
| --- | --- | --- |
| NORMAL | Accepted census links and tree anchors only. No matcher proposals. | Always |
| TENTATIVE | The same, plus links the matcher proposes that nobody has reviewed. Each such person carries a `TENTATIVE LINK` note with the matcher's confidence and its rationale, and each family that includes such a person carries a `TENTATIVE` note. | Only when you tick the box |

The tentative file is a disposable experiment for private import into Ancestry. It never becomes an accepted decision, never enters the normal file and is never published.

## How to run it

1. Open the repository on GitHub, choose **Actions**, then **Census to GEDCOM** in the list on the left.
2. Choose **Run workflow**. Leave the branch as it is unless you want to test another one.
3. Fill in the boxes:
   - **scope**: `townland`, `family` or `ded`.
   - **value**: the townland name (for example `Cullionboy` or `Keadew Lower`), the family surname (its verified spellings are included) or the DED name (for example `Clogher`). Letters, digits, spaces, apostrophes, full stops and hyphens only. A suffix such as Upper or Lower is part of the name and is never dropped.
   - **tentative**: leave unticked for the normal file only. Tick it to also get the tentative file.
   - **min_confidence**: used only for the tentative file. `low` includes every unambiguous proposal, `medium` or `high` narrows it.
   - **wife_parent**: leave on `evidence`. `assume` attaches children to the head's wife when the returns do not say, which is a guess.
4. Choose **Run workflow** and wait for the green tick. It takes a few minutes, most of it the tests that run first.

## Getting the files

Open the finished run. At the bottom of the page, under **Artifacts**, download:

- `census-gedcom-normal-<scope>-<name>`, a zip holding `<scope>_<name>.ged` and `<scope>_<name>_report.txt`.
- `census-gedcom-TENTATIVE-<scope>-<name>`, only if you ticked the box, holding `<scope>_<name>_tentative.ged` and `<scope>_<name>_tentative_report.txt`.

The report lists the items to review: household shapes, age conflicts, and any accepted link refused because it would join two people the tree keeps apart. The run summary at the top of the page says which artifacts were made. Artifacts are kept for 14 days. Anyone who can see the repository can download them. The files hold census returns as published by the National Archives and tree reference numbers, nothing else.

## What it never does

- It never commits, pushes, opens a pull request or publishes anything. Its token is read-only.
- It never writes to `data/research/associations/census_links.csv` (the accepted decisions), the master GEDCOM or any other file in the repository. A guard step fails the run if anything in the repository changed.
- It never turns a tentative link into an accepted one. Accepting a link is still done only by Mike, through `tools/census_links.py accept`.

## Checking a file in Ancestry (manual, not yet done)

Structural checks pass for every file the tool writes, but that does not show that Ancestry reads the file the way we intend. Do this once for the normal file and once for the tentative file before relying on either, and record the result in WP20.

1. In Ancestry, import the file as a **new, separate tree**. Never import into a tree you want to keep.
2. Check the people count against the report, and that a few known people appear once each with a census event per return and the right townland (Keadew Lower and Keadew Upper must stay apart).
3. Open a household. Check that spouses and children are as the returns state, and that nobody has a parent the return does not support.
4. Check the notes: derived birth years are marked as not recorded, and each census event keeps its source and observation number.
5. For the tentative file only: check that every joined person shows a `TENTATIVE LINK` note and that a joined family shows the `TENTATIVE` note. Use Ancestry's hints to test the proposals, but record nothing from them as a decision.
6. Delete the test trees when finished.

## Running the same thing on your own computer

```
python tools/census_gedcom_export.py --townland "Keadew Lower"
python tools/census_gedcom_export.py --townland "Keadew Lower" --tentative --min-confidence low
```

Files go to `data/processed/census_gedcom/`, which is not committed. The command line is unchanged by the workflow.

## If a run fails

- **Tests failed**: the first step runs the census tests. Open the step and read the first failure. Do not work around it.
- **The value must be a plain name**: remove any character other than letters, digits, spaces, apostrophes, full stops and hyphens.
- **No people found**: the name matches no returns. Use the spelling as it appears in the census, or the Logainm name. Verified spelling variants such as Keadew and Keadue are matched for you.
- **Repository changed**: the guard found a changed file. This should never happen. Do not use the artifacts and ask for the workflow to be reviewed.
