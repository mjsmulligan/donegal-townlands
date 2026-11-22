# Documentary rollout and satellite index (draft)

Status: draft written 2026-11-21, for a new working session. This extends `docs/DOCUMENTARY_SPEC.md` (DP7, rollout) and adds the index page restyle. Read that file first, then `docs/MEDIA_SPEC.md`, `docs/DATA_ARCHITECTURE.md` and `CLAUDE.md`.

## 1. Where things stand

Cullionboy has a working documentary page at `docs/cullionboy/documentary.html`, built from `townlands/cullionboy/records/documentary.json` by `tools/build_documentary.py` and the template `engine/documentary.html`. The user has tried it on a phone and approved the direction. What exists:

- **Generator.** Rule based, deterministic, self checking. Beat kinds: title, valuation, baptism, census, change, photo, family (not built), closing. Dated photographs are placed by year. Census and change beats carry counts. Baptisms under 100 years are refused and listed.
- **Player.** One page, one script. A satellite opening that falls from far above Ireland to the townland and then stays as the full bleed backdrop under a pale wash. Cards travel along a track, a year ribbon runs between moments, people dots on census and change beats, dissolves between moments, a Play button, Replay opening, deep links (`#beat=`), reduced motion, keyboard and swipe.
- **Media.** `media.csv` scopes `townland`, `family`, `parish` (shown beside baptism moments) and `griffiths` (the original valuation page, shown on the valuation moment). Optional `lat` and `lon`. No captions are shown under photographs.
- **Imagery.** Esri World Imagery tiles, credited in the page footer. The tile source is a single line in `engine/documentary.html` and in `engine/index.html` once restyled.

Everything else is Cullionboy only. No other townland has a documentary file. The index page (`engine/index.html`, built to `docs/index.html`) is still the old street map with a brown palette and does not link to any documentary.

## 2. Purpose of this package

1. Generate documentaries for a deliberately mixed set of townlands, so the differences in data richness show up on screen and in the generator, before any wider rollout.
2. Restyle the index page to match the documentary: satellite map, light palette, cards that link to the documentary.
3. Record what the comparison teaches, and decide what is needed before `--all` (DP7).

This package does not retire the walk (DP9), add sound (DP8), or build the family thread (DP6).

## 3. The sample set

The data richness varies a lot. The survey of the repository on 2026-11-21 found 143 townland cases: 136 with census returns, 4 with a Griffith's index file, 2 with authored content (Cullionboy, Clogher), 2 with media, 8 with `people.json`, and 7 with no census at all. The Tawnawilly baptism register resolves only 191 rows to 39 places, and one place, Donegal Town, holds 56 of them. Most townlands will therefore have census and nothing else. Choose these six first (the new session confirms each against the data before generating):

| Tier | Townland | Why it is in the set | What to expect |
|---|---|---|---|
| A, full | Cullionboy | The reference. Census 1901, 1911, 1926, baptisms, Griffith's index and page image, parish photograph, dated photograph. | The existing documentary, unchanged. |
| B, authored study | Clogher | Authored `content.json`, media, 7 baptisms, three census years, a timeline events file. | Compare authored content against generated beats. Does the documentary use anything the authored study holds? |
| C, valuation and census | Mullanalamphry | Griffith's index file, three census years, 3 baptisms, `people.json`. | A valuation beat from a names only index, and a short baptism beat. |
| D, census and baptisms | Aghlem | Three census years, 4 baptisms, no Griffith's. | No valuation beat. The story starts with baptisms. |
| E, census only | Straness | Three census years, no baptisms, no Griffith's. | The common case. Title, three census beats, two change beats, closing. |
| F, thin | Meenabrock | Logainm place record only, no census. | Title beat and the note (DOC-10). Checks the honest empty case. |

Add one townland with exactly one or two census years if the report in WP-R1 finds one, and one with a very large census population (to stress the people dots and the card text).

### 3.1 Sample confirmed by the survey (WP-R1, 2026-11-21)

`python tools/documentary_report.py` surveyed all 143 cases with no errors. Census years held: three in 127 cases, two in 6, one in 3, none in 7. Tiers by what the generator can use today: 2 full (Cullionboy, Clogher), 3 valuation and census, 21 census and baptisms, 110 census only (3 of them have a single return and so get a title beat and the note), 7 thin. No coordinate is outside Donegal or far from the others, so RO-08 has nothing to flag yet.

One finding changes the set. The generator reads the raw register and matches the townland by the clerk's exact spelling (`tools/build_timeline.py`, `baptism_events`). The normalised file resolves variants (Aughlin and Aughlim to Aghlem, Mullinalamphrey to Mullanalamphry), which is where the counts of 4 and 3 in the table above came from. Today Aghlem shows no baptisms and Mullanalamphry shows none (its one exact match is disputed and left out). Whether documentaries should use the normalised file is Q3, and it also changes the timeline pages, so it is left for the user to decide.

| Tier | Townland | Decision | Reason |
|---|---|---|---|
| A | Cullionboy | Kept | Full case, 11 beats. |
| B | Clogher | Kept | Authored study, 11 beats. It holds 7 baptisms and a landscape photograph. |
| C | Mullanalamphry | Kept | Valuation from a names only index (18 occupiers), three census years. It has no baptism beat under exact matching. |
| D | Goladoo | Swapped in for Aghlem | Seven baptisms match by exact name, the most of any case, so the baptism beat is tested. |
| E | Straness | Kept | Census only, three returns, 7 beats. |
| F | Meenabrock | Kept | Logainm record only, title beat and note. |
| extra | Tawnalary | Added | Two census years (1911 and 1926), the common short case, 5 beats. |
| extra | Druminnin | Added | Largest population (148 people in one return), with a valuation of 36 occupiers. Stresses the people dots and card text. |
| Q3 probe | Aghlem | Not generated | Kept in the report as the clearest case of the baptism spelling gap. Revisit after Q3. |

## 4. Requirements

Numbering continues the documentary spec's style. RO means rollout.

**Generation**

- RO-01. `python tools/build_documentary.py <name>` works for every case, including those with no census, no baptisms or no coordinates. It never throws. A case with no usable coordinates builds no page and says so in its output.
- RO-02. The generator never invents. A case with fewer than two story events gets the title beat and the note only. The player shows the opening, the title card and the note, and nothing else is offered as a story.
- RO-03. Output stays deterministic. Running the generator twice gives byte identical files. The same tests, `tools/validate.py` and `python -m pytest -q tests`, pass.
- RO-04. `tools/validate.py` checks every committed `documentary.json`: schema, unique ids, evidence ids exist, no dashes, no hedge words except the one allowed "possibly" on possible beats, numbers in captions found in evidence. This is the remainder of DP3.
- RO-05. `--all` writes documentary files only for cases that have a story. It does not run `tools/build.py --all`, which currently rewrites 134 built pages with unrelated "nan" changes. Fix that drift as its own commit, with the user's agreement, or avoid it. Do not mix the two.
- RO-06. The whole run produces a report: one row per case with its tier, number of beats by kind, total duration, files written and refusals (baptisms under 100 years, missing coordinates). Save it as `data/processed/documentary_report.csv` (not committed) and print the summary. This is the comparison tool.

**Page**

- RO-07. The documentary page for each case is `docs/<name>/documentary.html`, with its media copied beside it. It is generated, never edited by hand.
- RO-08. The opening and the backdrop depend only on the case's coordinates. Check coordinate quality in the sample: a townland's Logainm point may sit away from where people lived. Report any that look wrong rather than correcting them silently.
- RO-09. Imagery coverage varies. At the closest zoom some rural tiles may be soft or missing. The new session looks at all six and decides whether the final zoom should vary by townland size or stop at 15.
- RO-10. Phones first. Every sample page is checked at 360 and 375 px wide and at desktop width, with no horizontal scroll, readable cards and 48 px controls. Reduced motion and no network (no map library) must still leave a working story.

**Index**

- RO-11. `engine/index.html` becomes a satellite map in the same style as the documentary: the same imagery, a light palette and no brown (the current `--bg-color` and gold variables are brown and go), the Newsreader and Instrument Sans fonts, and the same pill and card look. The built `docs/index.html` is never edited by hand. Placeholders stay as documented in `CLAUDE.md`.
- RO-12. Each card shows its state (Townland Study, Census Returns or Townland Record) and, where a documentary page exists, a clear "Play the documentary" link. The walk link stays until DP9.
- RO-13. The index map shows all 143 cases, performs well on a phone, and the imagery credit is visible. Marker or polygon choice follows what the repository holds (GeoJSON already feeds the current map).
- RO-14. Opening a townland from the index leads to its documentary when one exists. A card for a case with no documentary shows the walk as today.

**Data and rights**

- RO-15. The 100/75/50 rule applies as before. Baptisms and photographs follow the rules in `docs/MEDIA_SPEC.md`. A parish photograph (`parish` scope) is stored per townland for now. A shared parish level home is open question Q2.
- RO-16. No personal names or family relationships of the user appear in any repo file or commit. Use "the user". Do not add Claude session links to commits, pull request text or files. No em dashes.

## 5. Work packages

| Package | What | Done when |
|---|---|---|
| WP-R1 Survey and report | Write `tools/documentary_report.py` (or extend the generator output) to list every case with its richness: census years, baptism count, Griffith's index, media, coordinates, expected beat count. Choose the sample set from it. | The report runs, the six townlands are confirmed or swapped with reasons. |
| WP-R2 Generator hardening | RO-01 to RO-04. Tests for the thin cases, no coordinates, one census year, and large populations. Add the `validate.py` check. | Tests and validator pass on all six. |
| WP-R3 Generate the sample | Run the generator for the six. Commit the six `documentary.json` files and the built pages. | Six pages build. Each is checked on a phone width screenshot. |
| WP-R4 Comparison review | A short note in the new session's pull request, and `docs/DOCUMENTARY_SPEC.md` updated: what each tier looks like, what is missing, what felt thin, what to change in captions, timing, opening length or imagery before wider rollout. | The user has read it and chosen what to change. |
| WP-R5 Index restyle | RO-11 to RO-14 in `engine/index.html` and `tools/build.py` (or the index builder), then rebuild `docs/index.html` only. | The index builds, shows satellite imagery, links to the six documentaries, and passes the phone checks. |
| WP-R6 Decisions for `--all` | Resolve Q1 to Q6 below with the user. | Decisions logged in `DECISIONS.md`. |

Order: WP-R1, WP-R2, WP-R3, WP-R4, WP-R5, WP-R6. WP-R5 can start once WP-R3 has produced at least two pages. The full rollout (`--all`, committed on its own) comes after WP-R6 and is a separate pull request.

## 6. Open questions

- Q1. Esri imagery terms. The imagery is used as a free, credited backdrop. Check whether the terms allow this use for a public site, and whether Tailte Eireann or another source is better. The tile URL is one line in each template.
- Q2. Parish photographs. St. Agatha's is stored in Cullionboy's media folder. A parish level home shared by every townland in the parish is needed before more townlands use it. Suggested: one folder and one sheet per parish, read by the generator for every case in that parish.
- Q3. Baptisms resolve to a place. The Tawnawilly register covers only some townlands, and many rows resolve to Donegal Town or to unresolved spellings. Confirm that a documentary baptism beat is shown only for rows resolved to the townland (verified or dictionary status), and decide whether `probable` and `possible` rows appear with the "possibly" wording.
- Q4. The Griffith's page image. The user plans to collect it for other townlands. Decide a naming convention and where the originals come from (the source line in `media.csv` should say).
- Q5. Thin cases. For a case with no story, should the documentary page exist at all, or should the index link to the walk? Preference to be decided after seeing the Meenabrock page.
- Q6. Opening length and repeat visits. Nine seconds of satellite fall on every visit may tire. Options: play once per browser session, a shorter fall for returning visitors, or an option to skip by default.
- Q7. Data use on mobile. The satellite opening loads many tiles. Decide whether to cap tile requests or add a small notice.

## 7. For the new session

- Branch from `main`. Use `feature/` names. Commit messages need no session line.
- The sandbox is a shallow clone. The stop hook wrongly says there are unpushed commits and no remote branch. Check with `git ls-remote origin <branch>`, which should print the same commit as `git rev-parse HEAD`.
- GitHub GraphQL is blocked here. Open pull requests with `gh api repos/mjsmulligan/donegal-townlands/pulls -f title=... -f head=... -f base=main -f body=...`.
- The sandbox cannot load Leaflet, tiles or Google Fonts. Test the player with a stub for the map library and screenshots with Playwright. The real look is only seen on the user's phone, so ask for a phone trial.
- Work in small pull requests: report, generator hardening, sample pages, index restyle. Do not run `tools/build.py --all` casually.
- Read these before starting: `docs/DOCUMENTARY_SPEC.md`, this file, `docs/MEDIA_SPEC.md`, `tools/build_documentary.py`, `tests/test_build_documentary.py`, `engine/documentary.html`, `engine/index.html`, `townlands/cullionboy/STATUS.md`.

## 8. Progress

| Package | Status |
|---|---|
| WP-R1 Survey and report | Done 2026-11-21 (pull request 108). Sample confirmed in section 3.1. |
| Q3 baptism spellings | Decided 2026-11-22 (pull request 109): documentaries and timelines use the normalised register. |
| WP-R2 Generator hardening | Done 2026-11-22. RO-01 never throws and builds no page without coordinates. RO-02 a case with no story is the opening, the title card and the note, and the player hides the ribbon and controls. RO-03 the page and the JSON are byte identical on a rebuild. RO-04 `tools/validate.py` checks every committed `documentary.json`. RO-05 `--all` writes only cases with a story and does not run `tools/build.py --all`. RO-06 `--all` writes the survey report with the files written. Tried once on the real repo and then discarded: 133 cases with a story, 10 without, all 133 pass the validator, 1.5 seconds. |
| WP-R3 Generate the sample | Done 2026-11-22. Eight pages built: Cullionboy, Clogher, Mullanalamphry, Goladoo, Straness, Meenabrock, Tawnalary, Druminnin. Each was stepped through at 360, 375 and 1440 px with the network blocked, and at 375 px with reduced motion: no horizontal scroll, controls at least 48 px, every caption as in the data, no page errors. Two faults found and fixed (a background photograph added 15 px of scrollable width, and reduced motion changed the Play label back to Play). Not checkable here: the satellite imagery and the opening, which need a phone trial (RO-09). |
| WP-R4 Comparison review | Next. |
| Caption changes after the review | Done 2026-11-22: change beats dropped, people in words, closing beat shortened, `Edw.` rule added (DECISIONS.md, 2026-11-22). Thin cases left as they are. |
