# Donegal Townlands: Media Specification

Status: Draft 1, open for review
Date: 2026-11-03
Parent documents: `CLAUDE.md`, `docs/REQUIREMENTS.md` (PRV-01), `docs/DATA_ARCHITECTURE.md`
Companion: `docs/WORK_PACKAGES.md` (separate numbering; media packages here are MP1 to MP8)

Priority: **M** must, **S** should, **L** later.
Size: **S** under a day of assistant work, **M** one to three days, **L** more.
Every requirement has an acceptance test. A package is finished when the tests for its requirements pass and a handover is left in the relevant `STATUS.md` and `DECISIONS.md`.

## 1. Purpose and scope

Add photographs and other images to townland pages so a page can show the place and its families, not only records.

In scope:
- Up to 3 header images per townland, shown on the title plate.
- Household photos, attached to a family plate and shown on a new Photos tab.
- A media folder per townland and a mapping file that ties each image to its townland or family, with a caption record.

Out of scope for this feature:
- Griffith's sheet scans and links to original records (covered by the 2026-11-02 decision on linking to original sources).
- Images on the 1850s, 1901, 1911 or 1926 tabs. Those tabs keep showing the households.
- Video or audio.
- Resizing, cropping, EXIF reading or any other image processing.
- Automatic privacy checks on photographs.
- Upload tooling for a CDN.

## 2. Decisions this specification assumes

| ID | Decision | Status |
|---|---|---|
| M1 | Townland header images (1 to 3) hang on top of the painted title scene. They do not replace it. With none, the title plate is unchanged. | Agreed 2026-11-03 |
| M2 | Household media attaches at family plate level, by the family name in `content.json`. A photo may name several families. No per-year household number. | Agreed 2026-11-03 |
| M3 | A family plate gets a Photos tab, first and shown by default, only when that family has at least one photo. Photos appear only on that tab. The existing year tabs are unchanged. | Agreed 2026-11-03 |
| M4 | The Photos tab shows the painted landscape and the framed photos only. No cottages are shown under the photos. | Agreed 2026-11-03 |
| M5 | Each photo is shown whole, never cropped, in a light frame with a mat, whatever its shape or resolution. Frame colours are light, never brown. | Agreed 2026-11-03 |
| M6 | Originals are not resized by the project. Files are committed as supplied. Typical scans are a few hundred KB. | Agreed 2026-11-03 |
| M7 | Each townland has `townlands/<name>/media/` holding the image files and `media.csv`. An optional `townlands/media_config.json` holds a CDN base address so images can later be served from a CDN without editing any CSV. | Agreed 2026-11-03 (CDN route optional) |
| M8 | No automated privacy check on photographs. Mike checks each photograph himself before adding it. The validator does not apply the 100/75/50 rule to media. | Agreed 2026-11-03 |
| M9 | `date` and `people_shown` are optional. When `people_shown` is filled it names only people already in the project datasets. The validator does not check this. | Agreed 2026-11-03 |
| M10 | Work is on branch `feature/media` and reviewed before merging to main. | Agreed 2026-11-03 |
| M11 | Header photographs should be landscape (wider than tall). This is guidance, checked with a warning, not a failure. Household photos can be any shape. | Agreed 2026-11-03 |

M6 and M9 change the standing image rule in `CLAUDE.md` (web-sized copies about 1600 px, caption record with source, reference, date, people shown, family). `CLAUDE.md` is updated to match in MP1.

## 3. Data model

### 3.1 Files

```
townlands/media_config.json              optional, repo wide
townlands/<name>/media/media.csv         one row per image
townlands/<name>/media/<image files>     as supplied
docs/<name>/media/<image files>          build output, never edited by hand
```

### 3.2 media.csv columns

| Column | Required | Meaning |
|---|---|---|
| `file` | M | File name inside the townland's `media/` folder. |
| `scope` | M | `townland` (header image) or `family` (household photo). |
| `slot` | for `townland` | 1, 2 or 3. Order across the header. Unique within the townland. Header images should be landscape (M11). |
| `family` | for `family` | One or more family names exactly as in `content.json` `families[].name`, separated by semicolons. |
| `caption` | M | Text shown with the image. |
| `source` | M | Where the image came from, for example "Family collection". |
| `alt` | no | Alternative text. If blank, the caption is used. |
| `reference` | no | Archive or collection reference. |
| `date` | no | Free text, for example "c. 1930s" or "unknown". |
| `people_shown` | no | Names, free text. |
| `link` | no | URL of the original (for example a shared album or archive page). Shown as "View original". |

Row order in the file is display order within a family's Photos tab.

### 3.3 media_config.json

```json
{ "base_url": "" }
```

Empty or absent: images are copied from the townland `media/` folder into `docs/<name>/media/` and referenced by relative path. A non-empty `base_url` (for example a CDN address ending in a slash) is prefixed to each `file` and no copy is made.

## 4. Presentation

- **Title plate.** 1 to 3 framed photos sit over the painted scene, below the townland name and above the scroll hint, side by side at a common height. The plate stacks these in page order, so the photos never overlap the name on a short screen. Widths follow each photo's shape. When the row is wider than the screen it scrolls sideways inside itself, so the page never scrolls sideways.
- **Family plate.** The Photos tab shows the painted landscape (midday sky, no cottages) with the family's photos hung over it in a wrapping arrangement.
- **Frame.** Light mat and thin border with a soft shadow. Whole image visible, original proportions kept.
- **Enlarge.** Tapping or pressing Enter on a photo opens it large with caption, source, date, people and the "View original" link where present. Escape or a close button returns. The enlarged view is keyboard operable.
- **Accessibility.** Every image has alt text (the caption if `alt` is blank). Motion respects `prefers-reduced-motion`.
- **Loading.** Images load lazily, except header images. The build records each image's pixel width and height so the page reserves space and does not shift.

## 5. Requirements

### 5.1 Data and validation

| ID | Requirement | Pri | Test |
|---|---|---|---|
| MED-01 | `media.csv` is read per townland with the columns in section 3.2. Unknown columns are ignored. | M | A sample file with an extra column loads. |
| MED-02 | `file`, `scope`, `caption` and `source` are required on every row. `slot` is required for `townland` rows and `family` for `family` rows. | M | A row missing any one fails validation and the message names the row. |
| MED-03 | `slot` is 1 to 3 and unique within a townland. A fourth header image fails. | M | Duplicate and out of range slots fail. |
| MED-04 | Every `family` value matches a family name in the townland's `content.json`. Several names are separated by semicolons. | M | An unknown name fails and the message lists the valid names. |
| MED-05 | Every `file` exists in the townland's `media/` folder when no `base_url` is set. | M | A missing file fails. |
| MED-06 | An image file in `media/` that no row refers to is reported as a warning. | S | An unreferenced file is listed and the run still passes. |
| MED-07 | A file over 8 MB is reported as a warning. The total size of all media is reported on every run, with a warning above 500 MB. | S | A large test file produces the warning. |
| MED-08 | Media files and `media.csv` are checked for em dashes by the existing validator. | M | A caption with an em dash fails. |
| MED-09 | The validator applies no 100/75/50 test to media (decision M8). | M | A row with `people_shown` and a recent `date` passes. |
| MED-10 | Only `.jpg`, `.jpeg`, `.png` and `.webp` files are accepted. | M | Another extension fails. |
| MED-25 | A header image (`scope=townland`) that is not landscape, that is square or taller than wide as a browser shows it, gives a warning and still builds. Household photos are not checked for shape. | S | A portrait header warns. A landscape header and a portrait household photo do not. |

### 5.2 Build

| ID | Requirement | Pri | Test |
|---|---|---|---|
| MED-11 | `tools/build.py` reads `media.csv` and adds the rows to the page data, with pixel width and height read from the file header using the standard library only. An unreadable header gives a warning and the page falls back to natural sizing. | M | Test builds show width and height in the page data for a JPEG and a PNG. |
| MED-12 | With no `base_url`, build copies the referenced files unchanged to `docs/<name>/media/`. With a `base_url`, nothing is copied and the page data holds full addresses. | M | Byte-identical copy check. A `base_url` test shows no copy. |
| MED-13 | A townland with no `media.csv` builds exactly as it does today. | M | The existing build tests pass and a rebuild of Cullionboy without media gives the same page text. |
| MED-14 | Build output is deterministic: rebuilding without changes gives identical files. | M | Two builds compare equal. |

### 5.3 Page

| ID | Requirement | Pri | Test |
|---|---|---|---|
| MED-15 | The title plate shows header photos per M1 and M5, and is unchanged when there are none. | M | Render test with 0, 1, 2 and 3 header images. |
| MED-16 | A family plate gets the Photos tab per M3 and M4, only when it has photos, and it is the tab shown first. | M | Render test with and without photos for one family. |
| MED-17 | No image is cropped. Portrait, landscape and square test images keep their proportions inside the frame. | M | Render test checks the displayed shape against the data width and height. |
| MED-18 | Photos do not appear on the 1850s or census year tabs. | M | Render test over each tab. |
| MED-19 | Enlarge view opens, closes and is keyboard operable. | M | Render test with Enter and Escape. |
| MED-20 | Alt text is present on every image and falls back to the caption. | M | Render test finds no `img` without alt text. |
| MED-21 | On a 375 px wide viewport the header strip swipes horizontally and the page has no horizontal scroll. | M | Render test at 375 px. |
| MED-22 | A photo naming several families appears on each of those families' Photos tabs. | M | Render test with a two-family row. |

### 5.4 Governance

| ID | Requirement | Pri | Test |
|---|---|---|---|
| MED-23 | `DECISIONS.md` records decisions M1 to M10. `CLAUDE.md` image rules and layout line match them. | M | Review. |
| MED-24 | Each package leaves a handover in the relevant `STATUS.md` (protocol section 7). | M | Review. |

## 6. Work packages

### MP1 Specification and decisions
- **Goal:** this document agreed, decisions logged, `CLAUDE.md` image rule updated.
- **Requirements:** MED-23.
- **Size:** S.
- **Acceptance:** Mike approves the specification. `python tools/validate.py` passes.

### MP2 Media loader and validation
- **Goal:** a standalone module that reads `media.csv` and `media_config.json` and reports problems, called by `tools/validate.py` and `tools/build.py`.
- **Outputs:** `tools/media.py` and `tools/test_media.py`. Hook in `tools/validate.py`.
- **Requirements:** MED-01 to MED-10.
- **Size:** S.
- **Acceptance:** all MED-01 to MED-10 tests pass.

### MP3 Build integration
- **Goal:** build reads media, records dimensions, copies files or uses the CDN base, and passes the data to the page.
- **Outputs:** changes in `tools/build.py` and tests in `tools/test_build.py`.
- **Requirements:** MED-11 to MED-14.
- **Size:** S.
- **Acceptance:** tests pass and townlands without media rebuild unchanged.

### MP4 Header photos on the title plate
- **Goal:** the framed header strip with enlarge view.
- **Outputs:** changes in `engine/walk.html` and render tests in `tools/test_walk_render.py`.
- **Requirements:** MED-15, MED-17, MED-19, MED-20, MED-21.
- **Size:** M.
- **Acceptance:** render tests pass. Mike views one page on his phone.

### MP5 Family Photos tab
- **Goal:** the Photos tab on family plates with the painted landscape and framed photos.
- **Outputs:** changes in `engine/walk.html` and render tests.
- **Requirements:** MED-16, MED-17 to MED-20, MED-22.
- **Size:** M.
- **Acceptance:** render tests pass. Mike views one family plate on his phone.

### MP6 Cullionboy pilot
- **Goal:** real use. Add the sample photo and any others with a filled `media.csv`, rebuild Cullionboy, and record what needs adjusting.
- **Needs from Mike:** the family, caption and source for each photo.
- **Requirements:** MED-13, MED-15, MED-16.
- **Size:** S.
- **Acceptance:** the Cullionboy page shows the photos as intended and Mike accepts it.

### MP7 Rollout
- **Goal:** rebuild all pages with the new engine and update the status notes.
- **Outputs:** `python tools/build.py --all`, committed separately from the code so the diff is reviewable.
- **Requirements:** MED-13, MED-14, MED-24.
- **Size:** S.
- **Acceptance:** every page without media is unchanged in rendered text and tables.

### MP8 CDN route (optional)
- **Goal:** a tested `base_url` path and a short note on adding images to a CDN by hand.
- **Requirements:** MED-12.
- **Size:** S.
- **Acceptance:** build with `base_url` references the CDN and copies nothing. Not started until Mike chooses a provider.

Order: MP1, MP2, MP3, then MP4 and MP5, then MP6, MP7. MP8 any time after MP3.

## 7. Open items

| ID | Item | Default until decided |
|---|---|---|
| O1 | CDN provider (ImageKit and Cloudinary resize through the URL, Cloudflare R2 does not). | Repo files. MP8 deferred. |
| O2 | Sky phase for the Photos tab. | Midday. |
| O3 | Size warning threshold (8 MB per file, 500 MB total). | As in MED-07. |
| O4 | Whether townlands with no authored families, and so no family plates, can show household photos anywhere. | Not shown. Header photos still work. |
| O5 | Caption wording standard (for example how to word an unknown date). | Free text. |

## 8. Progress and handovers

| Package | Status | Where |
|---|---|---|
| MP1 Specification and decisions | Done 2026-11-03 | Commit `eddbaff` |
| MP2 Media loader and validation | Done 2026-11-03 | `tools/media.py`, `tools/test_media.py`, `tools/validate.py` |
| MP3 Build integration | Done 2026-11-03 | `tools/build.py`, `tools/test_build.py` |
| MP4 Header photos on the title plate | Done 2026-11-03, awaiting Mike's phone check | `engine/walk.html`, `tools/test_walk_render.py` |
| MP5 Family Photos tab | Not started | |
| MP6 Cullionboy pilot | Not started | Needs family, caption and source for each photo from Mike |
| MP7 Rollout | Not started | |
| MP8 CDN route | Deferred (O1) | The `base_url` path is built and tested in MP2 and MP3; only the provider choice and an upload note remain |

### Handover: MP2 and MP3 (2026-11-03)

- **Outcome:** `media.csv` and `media_config.json` are read and checked. The build adds a `media` entry to the page data (header images by slot, household photos by family, each with url, pixel size, caption and optional fields) and copies the images unchanged to `docs/<name>/media/`. The page does not show media yet, because `engine/walk.html` is unchanged until MP4 and MP5.
- **Files:** `tools/media.py` (new), `tools/test_media.py` (new), `tools/build.py`, `tools/test_build.py`, `tools/validate.py`.
- **Decisions and assumptions:** image size is read from the file header with the standard library, and a JPEG's EXIF orientation is applied so a rotated phone photo gets the shape a browser shows. A case with media errors is reported and not built, and the other cases still build. Old copies in `docs/<name>/media/` are never deleted. With a CDN `base_url`, the size is still read when the file also exists in the townland's media folder, otherwise the page uses natural size.
- **Validation:** `python -m unittest` over all `tools/test_*.py` modules, 115 tests, all pass. `python tools/build.py --all` rewrote all 55 pages with no change in `docs/`, so townlands without media build as before (MED-13). `python tools/validate.py` fails only on the missing `data/source/manifest.csv`, which also fails on main and is not part of this work.
- **Review:** no independent review yet.
- **Git state:** branch `feature/media`, see the latest commit.
- **Next step:** MP4, the header strip in `engine/walk.html`. Mike views one page on his phone before MP5.

### Handover: MP4 (2026-11-03)

- **Outcome:** header photographs show on the title plate. Each is framed whole (`object-fit: contain`, light mat, soft shadow) with a short caption under it. Tap or press Enter to enlarge: the enlarged view shows the whole photograph with caption, source, reference, date, people and a "View original" link when present. Arrow keys step between photographs, Escape closes, Tab stays inside, and focus returns to the photograph that was opened. A photograph that fails to load shows "Photograph not available". With no header photographs the title plate is unchanged.
- **Files:** `engine/walk.html` (styles, `photoFrame`, `hangRow`, enlarged view, title plate), `tools/test_walk_render.py` (new `MediaRenderTests`).
- **Decisions and assumptions:** a frame's width is calculated from the photograph's shape (width over height from the build, corrected from the loaded file), because a browser cannot turn a percentage height into a width. A photograph wider than the screen is scaled down inside its frame, not cropped. The title plate becomes a stacked layout only when it has photographs. The enlarged view keeps its photographs in the order of their slots.
- **Not done:** the family Photos tab (MP5). The built pages in `docs/` have not been rebuilt, so they do not carry the new engine until MP7.
- **Validation:** all `tools/test_*.py` modules pass. Render tests cover 0, 1 and 3 photographs, shape at 375 px and 1440 px, no overlap at 1280 x 720, alt text, keyboard operation including Tab, and a failed image. I also looked at screenshots at 360 px to 1920 px wide.
- **Found while testing:** the focus trap first listed buttons out of page order and let Tab escape the enlarged view. Fixed and covered by a test.
- **Review:** no independent review yet. Mike to view one page on his phone.
- **Next step:** MP5, the family Photos tab.

### Update: landscape guidance and frame fit (2026-11-03)

- **Landscape:** header photographs should be landscape (decision M11, requirement MED-25). A portrait or square header gives a warning from `validate.py` and `build.py` and still builds. A rotated phone photo is judged by the shape it shows. Household photographs are not checked for shape. Mike's Cullionboy panorama (2576 x 886, about 2.9 to 1) was tried as the header: it fills a desktop frame and fits a phone frame with an even mat.
- **Frame fit:** the first MP4 layout left extra white mat above and below a wide photograph on a phone, where the frame width is capped by the screen. The frame now takes its height from the picture, so the mat is even at any width.
- **Found while testing:** the page already had a `.frame` class (4:5, dashed) for the "Not yet hung" plate, and the photograph frame was inheriting its shape. Photographs now use `.pframe`, and a test checks the mat is even and the border solid.
- **Validation:** all `tools/test_*.py` modules pass, 126 tests.
