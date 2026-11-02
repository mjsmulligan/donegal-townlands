"""Tests for tools/build.py. Run from the repo root:

    python -m unittest tools.test_build -v

Every test works in a temporary directory. The real repository is never touched.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import build

TEMPLATE = "<title>__TITLE__</title><h1>__BRAND__</h1><script>var D=__DATA__;</script>"


PLACE = json.dumps({"logainm_id": "13969", "name_en": "Druminnin", "name_ga": "",
                    "ded_id": "", "latitude": "54.68", "longitude": "-8.02"})


class BuildStateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.saved = build.ROOT
        build.ROOT = self.root
        self.addCleanup(self.restore)
        (self.root / "engine").mkdir()
        (self.root / "engine" / "walk.html").write_text(TEMPLATE, encoding="utf-8")
        (self.root / "engine" / "place.html").write_text(
            (self.saved / "engine" / "place.html").read_text(encoding="utf-8"),
            encoding="utf-8")
        (self.root / "townlands").mkdir()

    def restore(self):
        build.ROOT = self.saved

    def case(self, name, files):
        base = self.root / "townlands" / name
        (base / "records").mkdir(parents=True)
        for rel, text in files.items():
            (base / rel).write_text(text, encoding="utf-8")
        return base

    def run_build(self, name):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            state = build.build(name)
        return state, out.getvalue()

    def empty_case(self, name="druminnin"):
        return self.case(name, {"place.json": PLACE.replace("Druminnin", name.title()),
                                "STATUS.md": "starter\n"})

    def full_case(self, name="alpha"):
        return self.case(name, {
            "townland.json": json.dumps({"name": "Alpha", "page_title": "Alpha Study"}),
            "content.json": '{"story": "x"}',
            "records/census.json": '{"1901": []}',
        })

    def page(self, name):
        return (self.root / "docs" / name / "index.html").read_text(encoding="utf-8")

    def test_empty_case_publishes_an_honest_place_page(self):
        base = self.empty_case()
        before = sorted(p.name for p in base.rglob("*"))
        state, _ = self.run_build("druminnin")
        self.assertEqual(state, "empty")
        page = self.page("druminnin")
        self.assertIn("<h1>Druminnin</h1>", page)
        self.assertIn("logainm.ie/en/13969", page)
        self.assertIn("No historical records have been added", page)
        self.assertIn("Logainm, Government of Ireland, licensed under CC BY 4.0", page)
        self.assertNotIn("__BODY__", page)
        self.assertEqual(sorted(p.name for p in base.rglob("*")), before)

    def test_partial_case_page_lists_records_held(self):
        self.case("beta", {"place.json": PLACE.replace("Druminnin", "Beta"),
                           "records/census.json": '{"1901": [{}, {}], "1926": [{}]}'})
        state, _ = self.run_build("beta")
        self.assertEqual(state, "partial")
        page = self.page("beta")
        self.assertIn("not yet enough for a full study", page)
        self.assertIn("Census 1901: 2 people recorded", page)
        self.assertIn("Census 1926: 1 people recorded", page)

    def test_case_without_place_json_cannot_get_a_place_page(self):
        self.case("gamma", {"records/census.json": "{}"})
        _, text = self.run_build("gamma")
        self.assertIn("create_townland_cases", text)
        self.assertFalse((self.root / "docs").exists())

    def test_place_page_is_replaced_when_the_case_is_enriched(self):
        base = self.case("alpha", {"place.json": PLACE.replace("Druminnin", "Alpha")})
        self.run_build("alpha")
        self.assertIn("Research status", self.page("alpha"))
        for rel, text in {"townland.json": json.dumps({"name": "Alpha", "page_title": "Alpha Study"}),
                          "content.json": "{}", "records/census.json": "{}"}.items():
            (base / rel).write_text(text, encoding="utf-8")
        self.run_build("alpha")
        self.assertIn("<title>Alpha Study</title>", self.page("alpha"))

    def test_a_page_not_generated_as_a_place_page_is_never_replaced(self):
        self.empty_case()
        page = self.root / "docs" / "druminnin" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text("hand written", encoding="utf-8")
        _, text = self.run_build("druminnin")
        self.assertEqual(page.read_text(encoding="utf-8"), "hand written")
        self.assertIn("Left untouched", text)

    def test_place_page_escapes_names(self):
        self.case("x", {"place.json": PLACE.replace("Druminnin", "<b>X</b>")})
        self.run_build("x")
        self.assertNotIn("<b>X</b>", self.page("x"))

    def test_ready_case_is_built_with_its_data(self):
        self.full_case()
        state, _ = self.run_build("alpha")
        self.assertEqual(state, "ready")
        page = (self.root / "docs" / "alpha" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Alpha Study</title>", page)
        self.assertIn('"story":"x"', page)

    def test_adding_place_json_does_not_change_ready_state(self):
        base = self.full_case()
        (base / "place.json").write_text('{"logainm_id": "1"}', encoding="utf-8")
        self.assertEqual(build.case_state(base)[0], "ready")

    def test_unknown_case_is_an_error(self):
        with self.assertRaises(SystemExit):
            self.run_build("nosuchplace")

    def test_all_counts_each_state(self):
        self.full_case("alpha")
        (self.root / "townlands" / "alpha" / "place.json").write_text(PLACE.replace("Druminnin", "Alpha"), encoding="utf-8")
        self.empty_case("one")
        self.empty_case("two")
        self.case("beta", {"records/census.json": "{}"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            build.main(["--all"])
        self.assertIn("1 studies, 1 partial, 2 empty", out.getvalue())
        index = (self.root / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="./alpha/"', index)
        self.assertIn('href="./one/"', index)
        self.assertNotIn('href="./beta/"', index)

    def test_building_one_case_still_regenerates_the_index(self):
        self.full_case("alpha")
        self.empty_case("one")
        with contextlib.redirect_stdout(io.StringIO()):
            build.main(["one"])
        index = (self.root / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="./one/"', index)
        self.assertIn('href="./alpha/"', index)  # a study stays listed when another case is built
        self.assertIn("generated: donegal-townlands index", index)

    def test_no_em_dashes_in_output(self):
        self.empty_case()
        self.assertNotIn(chr(0x2014), self.run_build("druminnin")[1])


if __name__ == "__main__":
    unittest.main()
