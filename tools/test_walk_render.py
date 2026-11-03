"""Renders real built pages in a browser. Run from the repo root:

    python -m unittest tools.test_walk_render -v

Needs Playwright with Chromium; the tests are skipped if it is not installed.
Every test works in a temporary directory. The real repository is only read.
"""

import contextlib
import io
import json
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from tools import build

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

REAL_ROOT = build.ROOT


def person(sur="Harvey", house=1, age=40, sex="M"):
    return {"h": house, "s": sur, "f": "Ann", "a": age, "x": sex, "r": "Head", "m": "", "o": "", "i": 0, "ref": "r1"}


@unittest.skipIf(sync_playwright is None, "Playwright is not installed")
class WalkRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.ROOT = cls.root
        (cls.root / "engine").mkdir()
        shutil.copy(REAL_ROOT / "engine" / "walk.html", cls.root / "engine" / "walk.html")
        shutil.copytree(REAL_ROOT / "data" / "processed" / "places", cls.root / "data" / "processed" / "places")
        (cls.root / "townlands").mkdir()
        place = {"logainm_id": "1", "name_en": "Sample", "name_ga": "", "ded_id": "1372439", "civil_parish_id": "784",
                 "barony_id": "52", "county_id": "100013", "latitude": "54.6", "longitude": "-8.0", "snapshot_date": "2026-11-01"}

        def case(name, census=None, match=None):
            base = cls.root / "townlands" / name
            (base / "records").mkdir(parents=True)
            (base / "place.json").write_text(json.dumps({**place, "name_en": name.title()}), encoding="utf-8")
            if census:
                (base / "records" / "census.json").write_text(json.dumps(census), encoding="utf-8")
                years = {y: {"spellings": [{"spelling": name.title(), "method": "exact_name", "rows": 1}], "people": len(r)} for y, r in census.items()}
                (base / "records" / "census_match.json").write_text(json.dumps({"status": "proposed", "years": years}), encoding="utf-8")
            if match:
                (base / "records" / "census_match.json").write_text(json.dumps(match), encoding="utf-8")

        case("empty")
        case("checked", match={"status": "checked", "years": {}})
        case("oneyear", {"1911": [person(), person("Gildea", 2)]})
        case("twoyears", {"1901": [person()], "1926": [person()]})
        case("threeyears", {"1901": [person()], "1911": [person()], "1926": [person()]})
        shutil.copytree(REAL_ROOT / "townlands" / "cullionboy", cls.root / "townlands" / "cullionboy")
        with contextlib.redirect_stdout(io.StringIO()):
            build.main(["--all"])
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        build.ROOT = REAL_ROOT
        cls.tmp.cleanup()

    def render(self, name):
        page = self.browser.new_page(viewport={"width": 390, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/fonts.*/**", lambda r: r.abort())
        page.goto((self.root / "docs" / name / "index.html").as_uri())
        page.wait_for_timeout(200)
        info = page.evaluate("""() => ({
            plates: [...document.querySelectorAll('section.plate h1, section.plate h2')].map(e => e.textContent),
            count: document.querySelectorAll('section.plate').length,
            text: document.body.innerText,
            wide: document.documentElement.scrollWidth > window.innerWidth + 2})""")
        page.close()
        self.assertEqual(errors, [], name)
        self.assertFalse(info["wide"], name + " scrolls sideways at phone width")
        self.assertIn("Logainm, Government of Ireland", info["text"], name)
        return info

    def test_empty_place_is_a_short_walk_with_no_empty_rooms(self):
        info = self.render("empty")
        self.assertEqual(info["count"], 4)
        self.assertNotIn("The households", info["text"])  # no households, so no Room II
        self.assertIn("Not yet hung", info["plates"])
        self.assertNotIn("It runs from", info["text"])

    def test_checked_place_says_no_return_was_found(self):
        self.assertIn("Checked. No return found.", self.render("checked")["text"])

    def test_one_census_year(self):
        info = self.render("oneyear")
        self.assertEqual(info["count"], 6)
        self.assertIn("The census of 1911", info["plates"])
        self.assertIn("It covers the census of 1911.", info["text"])
        self.assertNotIn("Pick a year", info["text"])
        self.assertIn("1911, census return: 2 households, 2 people.", info["text"])

    def test_two_census_years(self):
        info = self.render("twoyears")
        self.assertIn("Two censuses", info["plates"])
        self.assertIn("It runs from 1901 to 1926.", info["text"])

    def test_three_census_years(self):
        info = self.render("threeyears")
        self.assertIn("Three censuses", info["plates"])
        self.assertIn("Method, sources and numbers", info["plates"])

    def test_authored_study_still_renders_in_full(self):
        info = self.render("cullionboy")
        self.assertEqual(info["count"], 23)
        self.assertIn("Twenty-five names", info["plates"])
        self.assertIn("It runs from the 1850s to 1926.", info["text"])
        self.assertIn("Census 1926 (Collinboy)", info["text"])


def real_png(w, h, rgb=(180, 200, 195)):
    """A small PNG a browser can really decode (the test_media images are header-only)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


@unittest.skipIf(sync_playwright is None, "Playwright is not installed")
class MediaRenderTests(unittest.TestCase):
    """Header photographs on the title plate (docs/MEDIA_SPEC.md, MED-15 and MED-17 to MED-21)."""
    HEAD = "file,scope,slot,family,caption,alt,source,reference,date,people_shown,link\n"
    ROWS = [
        "tall.png,townland,1,,A tall photograph,Alt for the tall one,Family collection,,,,https://example.org/original",
        "square.png,townland,2,,A square photograph,,Family collection,,c. 1930s,,",
        "wide.png,townland,3,,A wide photograph,,Family collection,,,,",
    ]

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.ROOT = cls.root
        (cls.root / "engine").mkdir()
        shutil.copy(REAL_ROOT / "engine" / "walk.html", cls.root / "engine" / "walk.html")
        shutil.copytree(REAL_ROOT / "data" / "processed" / "places", cls.root / "data" / "processed" / "places")
        (cls.root / "townlands").mkdir()
        place = {"logainm_id": "1", "name_en": "Sample", "name_ga": "", "ded_id": "1372439", "civil_parish_id": "784",
                 "barony_id": "52", "county_id": "100013", "latitude": "54.6", "longitude": "-8.0", "snapshot_date": "2026-11-01"}
        images = {"tall.png": real_png(100, 200), "square.png": real_png(150, 150), "wide.png": real_png(300, 150)}

        def case(name, rows=None, files=None):
            base = cls.root / "townlands" / name
            base.mkdir()
            (base / "place.json").write_text(json.dumps({**place, "name_en": name.title()}), encoding="utf-8")
            if rows:
                (base / "media").mkdir()
                for fname, data in (files if files is not None else images).items():
                    (base / "media" / fname).write_bytes(data)
                (base / "media" / "media.csv").write_text(cls.HEAD + "\n".join(rows) + "\n", encoding="utf-8")

        case("plain")
        case("three", cls.ROWS)
        case("one", cls.ROWS[:1])
        case("broken", ["bad.png,townland,1,,Broken one,,Src,,,,"], {"bad.png": b"this is not an image"})
        with contextlib.redirect_stdout(io.StringIO()):
            for name in ("plain", "three", "one", "broken"):
                build.build(name)
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        build.ROOT = REAL_ROOT
        cls.tmp.cleanup()

    def open(self, name, width=375, height=667):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.errors = []
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.route("**/fonts.*/**", lambda r: r.abort())
        page.goto((self.root / "docs" / name / "index.html").as_uri())
        page.wait_for_timeout(300)
        self.addCleanup(page.close)
        return page

    def test_no_header_photographs_leaves_the_title_plate_as_it_was(self):
        page = self.open("plain")
        self.assertEqual(page.locator(".hang").count(), 0)
        self.assertEqual(page.locator(".art.has-hang").count(), 0)
        self.assertEqual(self.errors, [])

    def test_three_photographs_are_framed_whole_at_phone_and_desktop_widths(self):
        for width, height in ((375, 667), (1440, 900)):
            page = self.open("three", width, height)
            shapes = page.evaluate("""() => [...document.querySelectorAll('.pframe img')].map(i => {
                const b = i.getBoundingClientRect(); return {w: b.width, h: b.height, nw: i.naturalWidth, nh: i.naturalHeight}})""")
            self.assertEqual(len(shapes), 3)
            for s in shapes:    # the picture area has the photograph's own shape, so nothing is cropped
                self.assertAlmostEqual(s["w"] / s["h"], s["nw"] / s["nh"], delta=0.03, msg=str(width))
            self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('.pframe img')).objectFit"), "contain")
            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth + 2"), str(width))
        self.assertEqual(self.errors, [])

    def test_the_frame_hugs_the_picture_with_an_even_mat(self):
        # Regression: the page already has a .frame class (4:5, dashed) for the "Not yet hung" plate.
        # Photographs use .pframe so they cannot inherit its shape, border or extra height.
        for width in (375, 1440):
            page = self.open("three", width, 800)
            boxes = page.evaluate("""() => [...document.querySelectorAll('.pframe')].map(f => {
                const r = f.getBoundingClientRect(), i = f.querySelector('img').getBoundingClientRect();
                return {extraW: r.width - i.width, extraH: r.height - i.height, dashed: getComputedStyle(f).borderStyle}})""")
            for b in boxes:
                self.assertAlmostEqual(b["extraW"], b["extraH"], delta=1.5, msg=str(width))   # same mat all round
                self.assertLess(b["extraH"], 20, str(width))
                self.assertEqual(b["dashed"], "solid")

    def test_photographs_never_overlap_the_title_on_a_short_wide_screen(self):
        page = self.open("three", 1280, 720)
        gap = page.evaluate("""() => document.querySelector('.hang').getBoundingClientRect().top
                              - document.querySelector('.bigtitle h1').getBoundingClientRect().bottom""")
        self.assertGreaterEqual(gap, 20)

    def test_every_photograph_has_alt_text_falling_back_to_the_caption(self):
        alts = self.open("three").evaluate("[...document.querySelectorAll('.pframe img')].map(i => i.alt)")
        self.assertEqual(alts, ["Alt for the tall one", "A square photograph", "A wide photograph"])

    def test_enlarge_opens_and_closes_from_the_keyboard_and_returns_focus(self):
        page = self.open("three")
        page.focus(".pframe")
        page.keyboard.press("Enter")
        self.assertTrue(page.evaluate("!!document.querySelector('.lb.open')"))
        self.assertEqual(page.evaluate("document.activeElement.textContent"), "Close")
        self.assertIn("A tall photograph", page.inner_text(".lb-cap"))
        self.assertIn("Source: Family collection.", page.inner_text(".lb-meta"))
        self.assertTrue(page.is_visible(".lb-link"))                    # this one has an original link
        plate_before = page.inner_text("#count")
        page.keyboard.press("ArrowRight")                               # next photograph, not next plate
        self.assertEqual(page.inner_text(".lb-count"), "2 / 3")
        self.assertEqual(page.inner_text("#count"), plate_before)
        self.assertFalse(page.is_visible(".lb-link"))                   # this one has none
        for _ in range(8):                                              # Tab stays inside the enlarged view
            page.keyboard.press("Tab")
            self.assertTrue(page.evaluate("!!document.activeElement.closest('.lb')"))
        page.keyboard.press("Escape")
        self.assertFalse(page.evaluate("!!document.querySelector('.lb.open')"))
        self.assertEqual(page.evaluate("document.activeElement.className"), "pframe")
        self.assertEqual(self.errors, [])

    def test_a_single_photograph_has_no_next_or_previous(self):
        page = self.open("one")
        page.click(".pframe")
        self.assertFalse(page.is_visible(".lb button[aria-label='Next photograph']"))
        self.assertEqual(page.inner_text(".lb-count"), "")

    def test_an_image_that_will_not_load_says_so_instead_of_showing_a_broken_icon(self):
        page = self.open("broken")
        self.assertEqual(page.locator(".pframe.broken").count(), 1)
        self.assertIn("Photograph not available", page.inner_text(".pframe.broken"))
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
