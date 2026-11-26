# Census form images

Census form pages as supplied by the National Archives of Ireland (NAI), kept unchanged. Source data principles in `CLAUDE.md` apply: nothing here is edited, and acquisition facts live in `manifest.csv`.

Layout: `<census year>/<townland>/<original file name>.pdf`

`manifest.csv` columns:

| Column | Meaning |
|---|---|
| `file` | Path under this folder. |
| `townland`, `census_year`, `form`, `page` | What the page is. Pages are in the order the files were added. |
| `archive_ref` | The reference stamped on the form, for example `STAT/1/8/36/DRUMININ/B/1`. |
| `form_date` | The date the return was completed, as written on the form. |
| `origin`, `date_acquired`, `licence_note` | Where it came from, when, and the licence conditions. |
| `sha256` | Checked by `python tools/census_form_images.py check`. |

Web images are derived from these by `tools/census_form_images.py build` and live in `townlands/<name>/media/` with scope `census` in `media.csv`. They are converted and resized, never cropped. Specified in `docs/MEDIA_SPEC.md` section 3.4.
