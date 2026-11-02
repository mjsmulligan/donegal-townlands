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
        return self.case(name, {"place.json": '{"logainm_id": "13969"}',
                                "STATUS.md": "starter\n"})

    def full_case(self, name="alpha"):
        return self.case(name, {
            "townland.json": json.dumps({"name": "Alpha", "page_title": "Alpha Study"}),
            "content.json": '{"story": "x"}',
            "records/census.json": '{"1901": []}',
        })

    def test_empty_case_is_valid_and_publishes_nothing(self):
        base = self.empty_case()
        before = sorted(p.name for p in base.rglob("*"))
        state, text = self.run_build("druminnin")
        self.assertEqual(state, "empty")
        self.assertIn("Nothing to publish", text)
        self.assertFalse((self.root / "docs").exists())
        self.assertEqual(sorted(p.name for p in base.rglob("*")), before)

    def test_partial_case_is_reported_not_built(self):
        self.case("beta", {"place.json": "{}",
                           "records/census.json": "{}"})
        state, text = self.run_build("beta")
        self.assertEqual(state, "partial")
        self.assertIn("content.json", text)
        self.assertFalse((self.root / "docs").exists())

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

    def test_empty_case_never_removes_an_existing_page(self):
        self.empty_case()
        page = self.root / "docs" / "druminnin" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text("published", encoding="utf-8")
        self.run_build("druminnin")
        self.assertEqual(page.read_text(encoding="utf-8"), "published")

    def test_unknown_case_is_an_error(self):
        with self.assertRaises(SystemExit):
            self.run_build("nosuchplace")

    def test_all_counts_each_state(self):
        self.full_case("alpha")
        self.empty_case("one")
        self.empty_case("two")
        self.case("beta", {"records/census.json": "{}"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            build.main(["--all"])
        self.assertIn("1 built or buildable, 1 partial, 2 empty", out.getvalue())

    def test_no_em_dashes_in_output(self):
        self.empty_case()
        self.assertNotIn(chr(0x2014), self.run_build("druminnin")[1])


if __name__ == "__main__":
    unittest.main()
