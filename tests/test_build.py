"""Tests for tools/build.py: the map index and the media copy the story pages share.

The townland pages themselves are the stories (tests/test_build_story.py). Every test works in a
temporary directory and never touches the real repository.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import build
from tests.test_media import jpeg, png

REAL_ROOT = build.ROOT
PLACE = {"logainm_id": "13969", "name_en": "Druminnin", "name_ga": "", "ded_id": "900",
         "civil_parish_id": "784", "barony_id": "52", "county_id": "100013",
         "latitude": "54.68", "longitude": "-8.02", "snapshot_date": "2026-11-01"}


def person(sur="Harvey", house=1, age=40, sex="M", rel="Head"):
    return {"h": house, "s": sur, "f": "Ann", "a": age, "x": sex, "r": rel, "m": "", "o": "", "i": 0, "ref": "r1"}


class BuildTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        build.ROOT = self.root
        self.addCleanup(setattr, build, "ROOT", REAL_ROOT)
        (self.root / "engine").mkdir()
        (self.root / "engine" / "index.html").write_bytes((REAL_ROOT / "engine" / "index.html").read_bytes())
        (self.root / "townlands").mkdir()
        names = self.root / "data" / "processed" / "places"
        names.mkdir(parents=True)
        (names / "places.csv").write_text(
            "logainm_id,name_en,name_ga,place_type,ded_id,civil_parish_id,barony_id,county_id,latitude,longitude,snapshot_date\n"
            "900,Clogher,,ded,,,,,,,\n", encoding="utf-8")
        (names / "place_names.csv").write_text(
            "logainm_id,name_en,place_type,source\n784,Donegal,civil_parish,x\n52,Tirhugh,barony,x\n100013,Donegal,county,x\n",
            encoding="utf-8")

    def case(self, name, files):
        base = self.root / "townlands" / name
        (base / "records").mkdir(parents=True, exist_ok=True)
        for rel, data in files.items():
            (base / rel).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return base

    def empty_case(self, name="druminnin", **place):
        return self.case(name, {"place.json": {**PLACE, **place}, "STATUS.md": "starter\n"})

    def census_case(self, name="druminnin", census=None, **place):
        census = census or {"1901": [person(), person("Harvey", 1, 38, "F", "Wife")], "1911": [person()]}
        return self.case(name, {"place.json": {**PLACE, **place}, "records/census.json": census})

    def authored(self):
        return self.case("alpha", {
            "place.json": {**PLACE, "name_en": "Alpha", "logainm_id": "1"},
            "townland.json": {"name": "Alpha", "page_title": "Alpha Study", "storage_key": "alpha-q",
                              "census_spelling": {"1901": "Alpha"}},
            "content.json": {"families": [{"name": "The Harveys"}]},
            "records/census.json": {"1901": [person()]}})

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            build.main(list(argv))
        return out.getvalue()

    def index(self):
        return (self.root / "docs" / "index.html").read_text(encoding="utf-8")

    # ---- the index

    def test_index_lists_every_case_in_name_order_with_its_state(self):
        self.authored()
        self.census_case("two")
        self.empty_case("one")
        self.run_main()
        index = self.index()
        pos = [index.index('data-slug="%s"' % s) for s in ("alpha", "one", "two")]
        self.assertEqual(pos, sorted(pos))
        for slug, tag in (("alpha", "Townland Study"), ("two", "Census Returns"), ("one", "Townland Record")):
            card = index[index.index('data-slug="%s"' % slug):]
            self.assertIn(tag, card[:card.index("</article>")])
        self.assertIn("3 Records", index)
        self.assertIn("generated: donegal-townlands index", index)
        self.assertIn("Logainm, Government of Ireland", index)

    def test_a_case_links_to_its_story_only_when_the_story_page_exists(self):
        self.authored()
        self.empty_case("one")
        story = self.root / "docs" / "alpha" / "story.html"
        story.parent.mkdir(parents=True)
        story.write_text("<html></html>", encoding="utf-8")
        out = self.run_main()
        index = self.index()
        self.assertIn('href="./alpha/story.html"', index)
        self.assertNotIn("./one/", index)
        self.assertIn("1 of 2 places have a story page", out)

    def test_build_takes_no_case_name_any_more(self):
        with self.assertRaises(SystemExit):
            self.run_main("alpha")

    def test_building_the_index_changes_no_case_folder(self):
        base = self.authored()
        before = sorted((p.name, p.stat().st_size) for p in base.rglob("*"))
        self.run_main()
        self.assertEqual(sorted((p.name, p.stat().st_size) for p in base.rglob("*")), before)

    # ---- media shared with the story pages (docs/MEDIA_SPEC.md)

    SHEET = ("file,scope,slot,family,caption,alt,source,reference,date,people_shown,link\n"
             "wide.jpg,townland,1,,A wide view,,Family collection,,,,\n"
             "tall photo.png,family,,The Harveys,A tall one,,Family collection,Ref 1,c. 1930s,,https://example.org/o\n")

    def media_case(self):
        base = self.authored()
        folder = base / "media"
        folder.mkdir()
        (folder / "wide.jpg").write_bytes(jpeg(1600, 900))
        (folder / "tall photo.png").write_bytes(png(500, 800))
        (folder / "media.csv").write_text(self.SHEET, encoding="utf-8")
        return base

    def test_images_are_copied_unchanged_and_nothing_is_copied_twice(self):
        base = self.media_case()
        found = build.media_for("alpha")
        self.assertEqual(found["errors"], [])
        self.assertEqual(build.copy_media("alpha", found), 2)
        for name in ("wide.jpg", "tall photo.png"):
            self.assertEqual((self.root / "docs" / "alpha" / "media" / name).read_bytes(), (base / "media" / name).read_bytes())
        self.assertEqual(build.copy_media("alpha", build.media_for("alpha")), 0)

    def test_a_cdn_base_address_means_nothing_is_copied(self):
        self.media_case()
        (self.root / "townlands" / "media_config.json").write_text('{"base_url": "https://cdn.example.org/m"}', encoding="utf-8")
        found = build.media_for("alpha")
        self.assertEqual(found["base_url"], "https://cdn.example.org/m/")
        self.assertEqual(build.copy_media("alpha", found), 0)
        self.assertFalse((self.root / "docs" / "alpha" / "media").exists())

    def test_old_media_copies_are_never_deleted(self):
        self.media_case()
        stale = self.root / "docs" / "alpha" / "media" / "old.jpg"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"old")
        build.copy_media("alpha", build.media_for("alpha"))
        self.assertEqual(stale.read_bytes(), b"old")

    def test_media_problems_are_reported_for_that_case(self):
        base = self.media_case()
        (base / "media" / "media.csv").write_text(
            "file,scope,slot,family,caption,source\nwide.jpg,family,,The Smiths,Cap,Src\n", encoding="utf-8")
        found = build.media_for("alpha")
        self.assertTrue(any("unknown family The Smiths" in e for e in found["errors"]))


if __name__ == "__main__":
    unittest.main()
