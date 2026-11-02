"""Renders real built pages in a browser. Run from the repo root:

    python -m unittest tools.test_walk_render -v

Needs Playwright with Chromium; the tests are skipped if it is not installed.
Every test works in a temporary directory. The real repository is only read.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
