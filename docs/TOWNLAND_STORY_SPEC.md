# Donegal Townlands: Story Specification

Status: Draft 1, open for review
Date: 2026-11-20
Parent documents: `CLAUDE.md`, `docs/RESEARCH_PRINCIPLES.md`, `docs/STORY_SPEC.md`, `docs/MEDIA_SPEC.md`, `docs/DATA_ARCHITECTURE.md`
Concept paper: Claude Doc "Townland Story: Design Concept" (2026-11-20)

Priority: **M** must, **S** should, **L** later.
Size: **S** under a day of assistant work, **M** one to three days, **L** more.
Every requirement has an acceptance test. A package is finished when the tests for its requirements pass and a handover is left in the relevant `STATUS.md` and `DECISIONS.md`.

## 1. Purpose and scope

Bring the map, the townland walk, the townland timeline and the family timeline together as one experience that can be watched. A viewer presses play and the story of a townland unfolds in time order: the camera moves on the map, the right card opens, a caption tells it in plain words, and photographs appear when their date comes. Pausing, or touching anything, hands control back so the viewer can explore the same pages freely and then resume.

In scope:
- A **beat** format: one small record per moment in the story, generated from data the repo already holds.
- A generator that writes a townland's beats from its records, with no hand authoring.
- A player with two modes, Play and Explore, sharing one clock, one stage and one script.
- Captions as the first form of narration, written in the story voice of `docs/STORY_SPEC.md`.
- A "follow this family" thread inside a townland chapter.
- Phone first, with a desktop layout of the same stage.
- A Cullionboy pilot, then a rollout to every case.
- Replacing the townland walk as the main page of every townland (D9). Nothing the walk shows today may be lost in the move (DOC-25).

Out of scope for the first release:
- Recorded or synthetic audio narration, and background music. The schema reserves room for both (section 3.4).
- Hand-authored beats and hand-authored media placement. Reserved as an optional later layer (section 3.5).
- Video export.
- Changes to the source data, the census links, the surname dictionary or the privacy rule.

## 2. Decisions this specification assumes

| ID | Decision | Status |
|---|---|---|
| D1 | The townland is the primary unit. A family appears as a "follow this family" thread inside a townland chapter, not as the main frame. | Agreed 2026-11-20 |
| D2 | Beats are generated automatically from records so the feature scales over 100+ townlands. No beat needs hand authoring. Hand additions, mainly media, may be allowed later as an optional layer on top. | Agreed 2026-11-20 |
| D3 | Phones are the main audience, desktop is also supported. One player and one script, drawn in two layouts of the same stage, not two templates. Provisional until Cullionboy is tried on a phone. | Agreed in principle 2026-11-20, to confirm after DP5 |
| D4 | Play and Explore are two modes of one player built from the same pages. Pause or any tap moves to Explore. Resume returns to the beat that was playing. | Proposed |
| D5 | Captions follow `docs/STORY_SPEC.md` (third person, past tense, plain words, evidence only, silence over guessing) with one softening. Where a link between records is possible but not certain, the caption may say "possibly", once, at the point of the link. Nothing else is hedged. "Probably", "seems", "it is tempting to think" and similar stay out. | Agreed 2026-11-20 for the story. See note below. |
| D6 | The generator never invents a story for a gap in the record. Absence from a return is not told as a departure (STORY_SPEC, "Absence and departure"). | Proposed |
| D7 | Sound is off by default. Captions are always available. Audio is never the only carrier of any fact. | Proposed |
| D8 | Work is on branch `feature/story` and reviewed before merging to main. | Proposed |
| D9 | The story replaces the townland walk as the main page of every townland. The walk's plates, painted scenes, Griffith's, census and Photos content stay reachable inside the story in Explore mode. The walk is retired only at a cutover that the user approves, after parity is shown (DP9). Nothing is deleted without being asked (`CLAUDE.md`). | Agreed 2026-11-20 |

Note on D5. The standing story rule allows no hedges on the page. The user agreed on 2026-11-20 that this was too rigid for the story, and that "possibly" suits better than "probably". The rule is:

- **Certain.** A fact stated by a source, or a link the user has accepted, is told plainly with no hedge.
- **Possible.** A link that is not accepted, or where only names match, may be told with the single word "possibly" at the link, for example "A household of the same name in 1911 possibly followed." The caption states only what the names say, as the family timeline already does (DECISIONS.md, 2026-11-19).
- **Not told.** Where two households fit equally, the case stays in `held_open` and no beat is built.
- Every beat records its `certainty` (`stated`, `accepted` or `possible`) so a caption's wording can be checked against it.

This applies to the story only. `docs/STORY_SPEC.md` and the family stories are unchanged until the user says otherwise (O5).

## 3. Data model

### 3.1 Files

```
townlands/<name>/records/story.json     generated, never edited by hand
tools/build_story.py                    the generator
engine/story.html                       the player template
docs/<name>/story.html                  build output, never edited by hand
townlands/story_config.json             optional, repo wide (music, audio base address)
townlands/<name>/story_extras.csv       reserved, optional later (section 3.5)
```

The feed is derived and regenerated on every run, in the same way as `records/timeline_events.json`.

### 3.2 Inputs the generator reads

| Input | Gives |
|---|---|
| `townlands/<name>/place.json` | Name, Logainm id, latitude and longitude, DED, parish, barony |
| `townlands/<name>/records/timeline_events.json` | Griffith's, census and baptism events, each with date, source and attached media |
| `townlands/<name>/records/census.json` | Household and person counts by return, for arrival and change beats |
| `townlands/<name>/content.json` and `records/facts/<family>.json` | Authored family stories and their fact sheets. A family story is used only where `tools/check_story.py` passes. |
| `data/processed/family_timelines/<slug>.json` | Cross-townland family events and accepted links, for the family thread |
| `townlands/<name>/media/media.csv` | Header photographs and event-attached photographs |
| `data/reference/surname_variants.csv` | Verified surname families only |

The generator reads these and writes nothing back to them.

### 3.3 story.json

```json
{
  "schema": 1,
  "townland": "cullionboy",
  "generated_by": "donegal-townlands.build_story",
  "title": "Cullionboy",
  "span": { "from": "1850s", "to": "1926" },
  "chapters": [
    {
      "id": "cullionboy:ch:1850s",
      "title": "The land",
      "beats": [ "...beat records..." ]
    }
  ]
}
```

A chapter is a run of beats under one title. Chapters follow the evidence: the valuation period, each census, and the register years. A chapter with no beats is not written.

### 3.4 Beat record

```json
{
  "id": "cullionboy:beat:census:1911",
  "kind": "census",
  "chapter": "cullionboy:ch:1911",
  "time": { "label": "1911", "iso": "1911-04-02", "sort": "1911-04-02", "approximate": false },
  "place": { "townland": "cullionboy", "logainm_id": "13967", "lat": 54.6855, "lon": -7.9759, "camera": "townland" },
  "scene": { "stage": "map", "open_card": "cullionboy:census:1911" },
  "caption": "In 1911 seventy-two people lived in sixteen households in Cullionboy.",
  "people": [],
  "media": [],
  "evidence": { "events": ["cullionboy:census:1911"], "basis": "return_for_townland" },
  "duration_ms": 6200,
  "audio": null
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | M | Stable and unique across the repo. Built from townland, kind and the source event id. |
| `kind` | M | One of the kinds in section 3.6. |
| `chapter` | M | The chapter id. |
| `time` | M | Same shape as the timeline `date` plus `sort`. The clock is driven by `sort`. A range such as the 1850s sets `approximate`. |
| `place` | M | The townland, its Logainm id and coordinates, and the camera level: `parish`, `townland` or `household`. |
| `scene` | M | `stage` is `map`, `walk` or `timeline`. `open_card` is the id of the event or plate to open. The stage and card are existing pages, not new ones. |
| `caption` | M | Plain text, one to three short sentences, written for the ear. No em dashes. |
| `people` | no | Person or household references for a family thread. Names only as recorded. |
| `media` | no | File names from the townland's `media/` folder, shown whole in a frame (MEDIA_SPEC M5). |
| `evidence` | M | The source event ids behind the beat, the association basis and the `certainty` (`stated`, `accepted` or `possible`). This is what Explore mode opens on "The records behind this". |
| `duration_ms` | M | Derived from caption length (section 4.3). Never hand set. |
| `audio` | reserved | `null` in the first release. Later a file name or address for a pre-generated narration. |

### 3.5 Reserved: hand additions

`story_extras.csv` is reserved so hand additions, mainly photographs and the odd authored beat, can be merged after generation without changing the generator's output. It is not built in the first release. A hand-added beat must carry the same required fields and goes through the same validation.

### 3.6 Beat kinds

| Kind | Source | What it says |
|---|---|---|
| `title` | place record, span | The townland, its parish, and the years covered. One per townland. |
| `valuation` | Griffith's event | That the land and its occupiers were valued, and how many occupiers are named. |
| `census` | census events | How many people in how many households, by return, as recorded. |
| `change` | Retired 2026-11-22 | The user dropped it: it told each census year a second time and was confusing. The schema and checker still accept the kind, but the generator writes none. A comparison between returns may return later as part of the census beat or the records panel. |
| `baptism` | register baptism events | A single baptism, or a short run in one year, with the family names as recorded. 100 year rule applies. |
| `photo` | media with an `event`, or a header image | A photograph at its date. The caption is the media caption. Never a person tag beyond the caption (STORY_SPEC, Photographs). |
| `family` | authored family story that passes `check_story.py`, or accepted census links | A "follow this family" thread: one or two beats in the family's own words, with a jump to its plate or family timeline. |
| `closing` | last return held | The latest evidence, ending on a plain fact. |

Marriages are not a beat kind in the first release because the register records no townland for them (DECISIONS.md, 2026-11-18). They enter only through the family thread.

## 4. Behaviour

### 4.1 The player

- **One clock.** A playhead over `time.sort`. Pressing play advances beat by beat. Scrubbing moves the whole experience. The timeline strip is the control, so the existing timeline view becomes the paused view.
- **One stage.** The map is the stage. The camera moves parish, then townland, then household level, according to each beat's `place.camera`.
- **One script.** The beats in order. The player holds no townland content of its own (same rule as `engine/walk.html`).
- **Play mode.** Auto-advance, captions shown, the open card follows the beat, chapter list and skip at the edge.
- **Explore mode.** Entered by pause or by tapping anything. The viewer has the ordinary interactive page. Resume returns to the beat that was playing.
- **Deep links.** `#beat=<id>` opens paused on that beat. This is also how the timeline, walk and map link into the story.

### 4.2 Layouts (D3)

- **Phone, portrait.** Map above, card and caption below, controls at the bottom within thumb reach. No horizontal page scroll.
- **Desktop.** Map beside the cards, caption under the map.
- The layout is chosen in the browser from the viewport. The script is identical. Nothing in `story.json` mentions layout.

### 4.3 Timing

`duration_ms` is derived: words divided by 2.5 per second, with a floor of 4 seconds and a ceiling of 14 seconds, plus 1 second when the beat carries a photograph. The same rule is used for any later audio so captions and voice stay together. The viewer can slow or speed playback with a control. No beat is timed by hand.

### 4.4 Wording

- The caption generator is rule based and fully deterministic. Variety comes from a fixed set of sentence patterns per kind, chosen by a stable hash of the beat id, so a rebuild changes nothing.
- Numbers up to twenty are written in words inside sentences and figures are kept for dates (STORY_SPEC, Names, dates and numbers). This covers people as well as households ("six people in two households", "93 people in eighteen households").
- A closing beat that follows a later photograph says only that the story reaches that year. It does not repeat a census figure.
- Names and spellings are as recorded. Townland names are as the source spells them.
- A thin townland gets a short story, not padding (D2, and STORY_SPEC, Shape of a family story).

### 4.5 Privacy

The 100/75/50 rule applies to every beat built from information the project holds that is not taken unchanged from a published source. Census returns to 1926 are exempt, as in `CLAUDE.md`. Baptisms must be 100 or more years old. Photographs are checked by the user (MEDIA_SPEC M8). The generator refuses a beat that fails the rule and lists it, rather than dropping it silently.

### 4.6 Accessibility and motion

- Captions are always shown or one tap away. Audio, when it exists, is off until the viewer turns it on (D7).
- `prefers-reduced-motion` replaces camera flights with cuts and replaces auto-advance with a Next control.
- Every control is keyboard operable. Space plays and pauses, arrow keys step, Escape leaves a photograph.
- Every image has alt text, falling back to the caption.

## 5. Requirements

### 5.1 Data and generation

| ID | Requirement | Pri | Test |
|---|---|---|---|
| DOC-01 | `tools/build_story.py <name>` writes `records/story.json` from the inputs in section 3.2 and writes nothing else. | M | Run on Cullionboy. Only that file and the page change. |
| DOC-02 | Every beat has the required fields in section 3.4 and a unique id. A beat that fails fails the build and the message names it. | M | A beat missing `caption` fails with its id. |
| DOC-03 | Output is deterministic. Rebuilding with no change gives identical files. | M | Two builds compare equal. |
| DOC-04 | Beats are in `time.sort` order, chapters follow beats, and an empty chapter is not written. | M | Order and emptiness checks on three cases. |
| DOC-05 | Every beat's `evidence.events` ids exist in the townland's `timeline_events.json` or in an accepted family link. | M | A beat citing a missing id fails. |
| DOC-06 | Captions contain no em dash, no source talk ("the records show", "is recorded as"), and no hedge word from the STORY_SPEC "What stays out" list except "possibly". | M | A caption with each fails validation. |
| DOC-06a | "Possibly" appears only in a beat whose `certainty` is `possible`, at most once per caption. A `possible` beat without it, or a `stated` or `accepted` beat with it, fails. | M | Fixtures for each of the four cases. |
| DOC-07 | Every name, number, place and date in a caption appears in the beat's evidence. A `family` beat also passes `tools/check_story.py`. | M | A number not in the source event fails. |
| DOC-08 | Retired 2026-11-22 with the `change` beat. No beat may name a cause or a departure: census captions state counts only. | M | The generator writes no `change` beat, and census captions hold counts only. |
| DOC-09 | The 100/75/50 rule is applied (section 4.5). A refused beat is listed in the build output. | M | A baptism under 100 years old is refused and listed. |
| DOC-10 | A case with fewer than two events gets a title beat and a short note, not a story. It builds without error. | M | A Logainm only case builds. |
| DOC-11 | A townland with no `media.csv` builds a story without photograph beats and is otherwise unchanged. | M | Build Cullionboy with and without media. |

### 5.2 Player

| ID | Requirement | Pri | Test |
|---|---|---|---|
| DOC-12 | Play advances through all beats in order and stops at the last. Pause stops at the current beat. | M | Render test steps through a fixture. |
| DOC-13 | Tapping a card, the map or the timeline moves to Explore. Resume returns to the beat that was playing. | M | Render test checks the beat id before and after. |
| DOC-14 | `#beat=<id>` opens paused on that beat. An unknown id opens at the start. | M | Render test with a valid and an invalid hash. |
| DOC-15 | The camera follows `place.camera`. | M | Render test checks the map view for each level. |
| DOC-16 | The open card matches `scene.open_card`. | M | Render test compares card id to beat. |
| DOC-17 | Photographs are shown whole in a frame and never cropped. | M | Existing media render checks reused. |
| DOC-18 | At 375 px the page has no horizontal scroll and controls are reachable. At 1440 px the map sits beside the cards. | M | Render tests at both widths. |
| DOC-19 | With reduced motion the camera cuts and nothing auto-advances. | M | Render test with the media query forced. |
| DOC-20 | Space, arrows and Escape work. Every image has alt text. | M | Keyboard and alt text render tests. |
| DOC-21 | Before cutover, every existing walk page is unchanged by this work. | M | Rebuild shows no diff for walk pages. |
| DOC-25 | Parity. Every plate and tab the walk offers for a townland (title, Griffith's, census years, family plates with their year tabs and Photos tab, the media enlarge view, the records panel) is reachable in Explore mode with the same content. | M | A render test compares the walk's plate and tab list to the story's for Cullionboy, Clogher and a Logainm only case. |
| DOC-26 | After cutover `docs/<name>/index.html` is the story, and every old `#` link into a walk plate lands on the matching card. | M | Render test over a set of old fragment links. |

### 5.3 Governance

| ID | Requirement | Pri | Test |
|---|---|---|---|
| DOC-22 | `DECISIONS.md` records D1 to D8 as they are agreed. `CLAUDE.md` layout section names the new files. | M | Review. |
| DOC-23 | Each package leaves a handover in the relevant `STATUS.md` (protocol section 7). | M | Review. |
| DOC-24 | Page size stays reasonable on a mobile connection. The player and one townland's beats together stay under 1.5 MB before images. | S | A size check in the build output. |

## 6. Work packages

### DP1 Specification and decisions
- **Goal:** this document agreed, D1 to D8 logged, `CLAUDE.md` updated.
- **Requirements:** DOC-22.
- **Size:** S.
- **Acceptance:** the user approves. `python tools/validate.py` passes.

### DP2 Beat generator
- **Goal:** `build_story.py` produces `story.json` for Cullionboy.
- **Outputs:** `tools/build_story.py`, `tests/test_build_story.py`.
- **Requirements:** DOC-01 to DOC-11.
- **Size:** M.
- **Acceptance:** tests pass. The user reads the Cullionboy captions aloud and signs them off.

### DP3 Validation and privacy
- **Goal:** the caption checks and the 100/75/50 filter are enforced by `tools/validate.py`.
- **Requirements:** DOC-06, DOC-07, DOC-09.
- **Size:** S.
- **Acceptance:** each failing fixture is caught.

### DP4 Player core
- **Goal:** a player that plays, pauses and steps through beats using the existing map, timeline cards and walk plates, with captions and no sound.
- **Outputs:** `engine/story.html`, render tests.
- **Requirements:** DOC-12 to DOC-17, DOC-20.
- **Size:** L.
- **Acceptance:** render tests pass. The user plays Cullionboy on his phone.

### DP5 Layouts, accessibility and motion
- **Goal:** phone and desktop layouts of the same stage, reduced motion, keyboard.
- **Requirements:** DOC-18, DOC-19.
- **Size:** M.
- **Acceptance:** render tests pass. The user confirms or revises D3 after trying it on a phone.

### DP6 Family thread
- **Goal:** one family followed across a townland chapter, drawing on authored stories that pass `check_story.py` and on accepted census links.
- **Needs from the user:** the first family to follow (suggested: the Kellys in Cullionboy, since the fact sheet exists).
- **Requirements:** DOC-07, DOC-08.
- **Size:** M.
- **Acceptance:** the Kellys thread reads as one story and passes `check_story.py`.

### DP7 Rollout
- **Goal:** build a story for every case with enough records and update status notes.
- **Outputs:** `python tools/build_story.py --all`, committed separately from the code.
- **Requirements:** DOC-10, DOC-21, DOC-23, DOC-24. Stories are built beside the walk pages, not in place of them.
- **Size:** S.
- **Acceptance:** pages without a story are unchanged.

### DP8 Sound (later)
- **Goal:** pre-generated narration and an optional music track.
- **Needs from the user:** the voice choice and the music rights decision (O2, O3).
- **Size:** M.
- **Acceptance:** not started until the user chooses.

### DP9 Cutover
- **Goal:** make the story the main page and retire the walk from the build, once parity is shown.
- **Outputs:** `tools/build.py` writes the story to `docs/<name>/index.html`, `docs/index.html` map cards link to it, `CLAUDE.md` layout section updated, a short note in `DECISIONS.md`. Walk template and old pages are kept in git history. Nothing is deleted without the user's say so.
- **Requirements:** DOC-22, DOC-25, DOC-26.
- **Size:** M.
- **Acceptance:** DOC-25 passes for every case, the user has played Cullionboy and one thin case on his phone and approves the switch.

Order: DP1, DP2, DP3, then DP4 and DP5, then DP6, DP7, then DP9. DP8 any time after DP4. DP4 must be built to reuse the walk's scenes and plates so DP9 is a switch, not a rewrite.

## 7. Open items

| ID | Item | Default until decided |
|---|---|---|
| O1 | Closed 2026-11-20. The story replaces the walk (D9). The standalone townland timeline pages stay as they are. | Decided |
| O2 | Narration voice: synthetic, or recordings in the user's own voice for key chapters. | Captions only. |
| O3 | Music: own recordings, public domain traditional airs, or licensed tracks. | No music. |
| O4 | Whether the townland pages link to the family timelines now that the story is the shared home. This was held on 2026-11-19 until the big picture was settled. | Still held. Family thread only inside the story. |
| O5 | Whether the softening in D5 ("possibly" for possible links) should also apply to the family stories in `docs/STORY_SPEC.md`. | Story only. STORY_SPEC unchanged. |
| O6 | Default playback speed and whether chapters have a short title card. | 1.0 and no title cards. |
| O7 | Whether `story.html` is a new page per townland or a mode of the existing timeline page. | New page per townland, reusing timeline card code. |

## 8. Progress and handovers

| Package | Status | Where |
|---|---|---|
| DP1 Specification and decisions | Draft written 2026-11-20, awaiting the user's review | This file, branch `feature/story` |
| DP2 Beat generator | Built 2026-11-20, awaiting the user's sign-off of the Cullionboy captions | `tools/build_story.py`, `tests/test_build_story.py`, `townlands/cullionboy/records/story.json` |
| DP3 Validation and privacy | Done 2026-11-22: the generator checks every beat (DOC-02, 05, 06, 06a, 07, 08, 09) and stops on a failure, and `tools/validate.py` checks every committed `story.json` (`build_story.check_repo`) | `tools/build_story.py`, `tools/validate.py`, `tests/test_build_story.py` |
| DP4 Player core | Built and tried on a phone 2026-11-21 | engine/story.html, docs/cullionboy/story.html. Satellite opening and backdrop, travelling cards, year ribbon, people dots, dissolves, deep links, reduced motion. Further changes follow the rollout comparison. |
| DP5 Layouts, accessibility and motion | Not started | |
| DP6 Family thread | Not started | |
| DP7 Rollout | Specified 2026-11-21. WP-R1 to WP-R3 done 2026-11-22, review of the eight pages in section 9 | `docs/TOWNLAND_STORY_ROLLOUT_SPEC.md` (section 3.1), `tools/story_report.py`, `tests/test_story_report.py` |
| DP8 Sound | Deferred (O2, O3) | |
| DP9 Cutover | Not started, needs the user's approval after parity | |

## 9. Comparison review of the eight sample pages (WP-R4, 2026-11-22)

Written from the committed `story.json` files and from stepping each page through in a browser. The satellite opening and backdrop could not be seen without a network, so imagery is not reviewed here. Running times are the sum of the beat durations, before the opening.

### 9.1 What each tier looks like

| Tier | Townland | Beats | Runs | What the viewer gets |
|---|---|---|---|---|
| A full | Cullionboy | 11 | 70 s | Valuation, two baptism groups, three census years with two change beats, the 1954 photograph, a closing beat. The only page with a photograph and the richest. |
| A full | Clogher | 11 | 67 s | The same shape with three baptism groups and no photograph. The authored study is not used. |
| C valuation and census | Mullanalamphry | 9 | 48 s | A names only valuation, one baptism group, census. |
| D census and baptisms | Goladoo | 10 | 56 s | No valuation, three baptism groups, census. The title says the story runs from 1873. |
| D census and baptisms | Druminnin | 11 | 61 s | Valuation of 36 occupiers, three baptisms, the largest population (148 in 1911). |
| E census only | Straness | 7 | 34 s | Three returns and two changes. Nothing else. |
| E census, two years | Tawnalary | 5 | 23 s | Two returns and one change. |
| F thin | Meenabrock | 1 | 4 s | The title card and a note. The ribbon and controls are hidden. |

The shape is honest and consistent: a page grows as records are added, and no page invents anything. The weakest cases are the middle ones, where the census beats repeat what the change beats then say again.

### 9.2 What felt thin or repetitive

1. **Each census year is told twice.** A census beat gives the people and households, and the change beat that follows gives the same figures again as a comparison ("Cullionboy had 72 people in sixteen households in 1911." then "By 1911 Cullionboy had 72 people, down from 93 in 1901."). In a case with only census data this is 60 percent of the page. Option: let the change beat carry the comparison only ("72 people, down from 93") and drop the repeated count, or fold the change into the census beat from 1911 on.
2. **Equal counts read awkwardly.** "It had seven households, against seven." (Straness, twice, and Tawnalary). Option: when the count is unchanged, say "It had seven households again."
3. **People are figures, households are words.** "6 people in two households" but "sixteen households". STORY_SPEC writes numbers in words inside sentences. Option: write people as words up to twenty as well, or write both as figures when a sentence holds two counts.
4. **The census beat opens three different ways** ("In 1901, 93 people...", "Cullionboy had 72 people...", "In 1926, 89 people..."). The variety is deliberate, to avoid a drumbeat, but a viewer who reads two in a row may not see the pattern as intended.
5. **Thin pages end quickly.** Tawnalary runs 23 seconds. That is accurate for two returns, but the opening alone is nine seconds of satellite, so the opening may be longer than the story (see 9.4).
6. **Baptism groups are by year, not by family.** Goladoo and Druminnin each get three groups of unrelated names. The viewer cannot tell which are from one family. This is what the family thread (DP6) is for.

### 9.3 Wording and data points to change

- **"Edw. Gallagher"** (Clogher). The normalised given-name rules (`data/source/nli_parish/tawnawilly/normalised/rules.csv`) have `Ed.`, `Edwd` and `Edwd.` for Edward but no `Edw.`. Adding the rule is a change to the normalised file, so it is for the user to approve. Other abbreviations may be in the same state: worth running the rules over all given names and listing those with a trailing full stop.
- **Mullanalamphry's "Catherine Thomas"** is correct: the father is Charles Thomas. No change.
- **Cullionboy's closing beat** says "The story reaches 1954 here. In 1926, Cullionboy had fifteen households." The second sentence repeats a figure shown two beats earlier and sits oddly after a 1954 photograph. Option: drop it when the last event is not a census.
- **Title beat span.** "runs from the 1850s to 1954" and "runs from 1873 to 1926" are accurate. Straness, "runs from 1901 to 1926", is right but flat. No change proposed.

### 9.4 Timing, opening and imagery (for a phone trial)

- Running times are 23 to 70 seconds for pages with a story. That is a good length for a phone. The longest, Cullionboy at 70 seconds, would be shortened by item 9.2.1: its two change beats take 13.6 seconds, so dropping the repeated counts could bring it near 57 seconds.
- The nine second satellite opening is longer than the whole of Tawnalary. Options (Q6): play the full fall only on a first visit in a session, a shorter fall for the thinner pages, or an option to skip.
- Imagery cannot be judged from here. The trial should look at Druminnin, Straness and Tawnalary first, which are the most remote, and say whether the final zoom should stop earlier (RO-09).
- Data use on mobile (Q7) grows with the size of the opening, not the page. The eight pages are each under 60 KB without media.

### 9.5 What to change before wider rollout

In suggested order. Items 1 to 3 are small, change only the wording code and can go in one pull request. Item 4 changes source rules and so needs the user's approval.

1. Drop the repeated counts in change beats and fold them into the census beat or shorten them (9.2.1, 9.2.2).
2. Write counts as words consistently (9.2.3).
3. Drop the second sentence of the closing beat when the last event is not a census (9.3).
4. Add the `Edw.` rule, and check other abbreviations (9.3).
5. Decide Q5 for thin cases (Meenabrock's page is a title card with a note: it is honest but a viewer arriving from the index gets nothing to play, so the index may do better to link the walk for these ten).
6. Phone trial of the opening and backdrop, then decide RO-09 and Q6.

Nothing in this review has been changed in the code.

