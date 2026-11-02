"""Tests for tools/create_townland_cases.py. Run from the repo root:

    python -m unittest tools.test_create_townland_cases -v

Every test works in a temporary directory. The real repository is never touched.
"""

import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import create_townland_cases as gen

HEADER = [
    "logainm_id", "name_en", "name_ga", "place_type", "ded_id",
    "civil_parish_id", "barony_id", "county_id",
    "latitude", "longitude", "snapshot_date",
]


def row(logainm_id, name, kind="townland", ded="900", snap="2026-11-01"):
    return {
        "logainm_id": logainm_id, "name_en": name, "name_ga": "",
        "place_type": kind, "ded_id": ded if kind == "townland" else "",
        "civil_parish_id": "1", "barony_id": "2", "county_id": "3",
        "latitude": "54.1", "longitude": "-8.1", "snapshot_date": snap,
    }


class CaseGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.saved = (gen.ROOT, gen.PLACES_CSV, gen.TOWNLANDS_DIR, gen.INDEX_CSV)
        gen.ROOT = self.root
        gen.PLACES_CSV = self.root / "data/processed/places/places.csv"
        gen.TOWNLANDS_DIR = self.root / "townlands"
        gen.INDEX_CSV = self.root / "data/processed/places/townland_cases.csv"
        self.addCleanup(self.restore)

    def restore(self):
        gen.ROOT, gen.PLACES_CSV, gen.TOWNLANDS_DIR, gen.INDEX_CSV = self.saved

    def write_places(self, rows):
        gen.PLACES_CSV.parent.mkdir(parents=True, exist_ok=True)
        with gen.PLACES_CSV.open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=HEADER)
            w.writeheader()
            w.writerows(rows)

    def run_gen(self):
        with contextlib.redirect_stdout(io.StringIO()):
            gen.main()

    def index(self):
        with gen.INDEX_CSV.open(encoding="utf-8", newline="") as h:
            return list(csv.DictReader(h))

    def legacy_case(self, folder, name, ded="Clogher"):
        d = gen.TOWNLANDS_DIR / folder
        d.mkdir(parents=True)
        (d / "townland.json").write_text(
            json.dumps({"name": name, "ded": ded}), encoding="utf-8")
        (d / "content.json").write_text('{"story": "authored"}', encoding="utf-8")
        (d / "STATUS.md").write_text("My research notes\n", encoding="utf-8")
        return d

    def dirs(self):
        return sorted(p.name for p in gen.TOWNLANDS_DIR.iterdir() if p.is_dir())

    def test_only_townlands_get_cases(self):
        self.write_places([row("1", "Alpha"), row("2", "Beta"),
                           row("50", "Clogher", kind="ded")])
        self.run_gen()
        self.assertEqual(self.dirs(), ["alpha", "beta"])
        self.assertEqual(len(self.index()), 2)

    def test_new_case_is_valid_and_empty(self):
        self.write_places([row("13969", "Druminnin")])
        self.run_gen()
        d = gen.TOWNLANDS_DIR / "druminnin"
        place = json.loads((d / "place.json").read_text(encoding="utf-8"))
        self.assertEqual(place["logainm_id"], "13969")
        self.assertTrue((d / "STATUS.md").is_file())
        self.assertEqual(sorted(p.name for p in d.iterdir()),
                         ["STATUS.md", "place.json"])

    def test_legacy_case_adopted_and_untouched(self):
        d = self.legacy_case("cullionboy", "Cullionboy")
        before = {p.name: p.read_bytes() for p in d.iterdir()}
        self.write_places([row("13967", "Cullionboy", ded="900"),
                           row("900", "Clogher", kind="ded")])
        self.run_gen()
        self.assertEqual(self.dirs(), ["cullionboy"])
        for name, data in before.items():
            self.assertEqual((d / name).read_bytes(), data, name)
        self.assertTrue((d / "place.json").is_file())

    def test_second_run_is_identical_and_makes_no_duplicates(self):
        self.legacy_case("clogher", "Clogher")
        self.write_places([row("13964", "Clogher"), row("900", "Clogher", kind="ded"),
                           row("1", "Alpha")])
        self.run_gen()
        snap = {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}
        self.run_gen()
        again = {str(p.relative_to(self.root)): p.read_bytes()
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(snap, again)
        self.assertEqual(self.dirs(), ["alpha", "clogher"])

    def test_identity_survives_a_name_change(self):
        self.write_places([row("7", "Oldname")])
        self.run_gen()
        self.write_places([row("7", "Newname")])
        self.run_gen()
        self.assertEqual(self.dirs(), ["oldname"])
        place = json.loads((gen.TOWNLANDS_DIR / "oldname/place.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(place["name_en"], "Newname")

    def test_same_name_different_ded_get_separate_cases(self):
        self.write_places([row("10", "Tully", ded="901"), row("11", "Tully", ded="902")])
        self.run_gen()
        self.assertEqual(self.dirs(), ["tully", "tully-11"])
        self.run_gen()
        self.assertEqual(self.dirs(), ["tully", "tully-11"])
        ids = {r["logainm_id"]: r["case_path"] for r in self.index()}
        self.assertEqual(ids, {"10": "townlands/tully", "11": "townlands/tully-11"})

    def test_ambiguous_name_is_not_adopted_by_name(self):
        d = self.legacy_case("tully", "Tully", ded="Other")
        before = (d / "townland.json").read_bytes()
        self.write_places([row("10", "Tully", ded="901"), row("11", "Tully", ded="902")])
        self.run_gen()
        self.assertFalse((d / "place.json").exists())
        self.assertEqual((d / "townland.json").read_bytes(), before)
        self.assertEqual(self.dirs(), ["tully", "tully-10", "tully-11"])

    def test_ded_mismatch_blocks_adoption(self):
        d = self.legacy_case("tully", "Tully", ded="Clogher")
        self.write_places([row("10", "Tully", ded="901"),
                           row("901", "Elsewhere", kind="ded")])
        self.run_gen()
        self.assertFalse((d / "place.json").exists())
        self.assertIn("tully-10", self.dirs())

    def test_unmarked_place_json_is_never_overwritten(self):
        d = gen.TOWNLANDS_DIR / "alpha"
        d.mkdir(parents=True)
        (d / "townland.json").write_text(
            json.dumps({"name": "Alpha", "logainm_id": "1"}), encoding="utf-8")
        (d / "place.json").write_text('{"logainm_id": "1", "mine": true}',
                                      encoding="utf-8")
        self.write_places([row("1", "Alpha")])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_gen()
        self.assertEqual((d / "place.json").read_text(encoding="utf-8"),
                         '{"logainm_id": "1", "mine": true}')

    def test_existing_status_is_never_replaced(self):
        d = self.legacy_case("alpha", "Alpha")
        self.write_places([row("1", "Alpha", ded="900")])
        self.run_gen()
        self.assertEqual((d / "STATUS.md").read_text(encoding="utf-8"),
                         "My research notes\n")

    def test_case_absent_from_later_snapshot_is_kept_and_indexed(self):
        self.write_places([row("1", "Alpha"), row("2", "Beta")])
        self.run_gen()
        self.write_places([row("1", "Alpha")])
        self.run_gen()
        self.assertEqual(self.dirs(), ["alpha", "beta"])
        flags = {r["logainm_id"]: r["in_latest_snapshot"] for r in self.index()}
        self.assertEqual(flags, {"1": "yes", "2": "no"})

    def test_duplicate_logainm_id_in_places_stops_the_run(self):
        self.write_places([row("1", "Alpha"), row("1", "Beta")])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_gen()
        self.assertFalse(gen.TOWNLANDS_DIR.exists() and self.dirs())

    def test_two_cases_claiming_one_id_stops_the_run(self):
        for folder in ("a", "b"):
            d = gen.TOWNLANDS_DIR / folder
            d.mkdir(parents=True)
            (d / "townland.json").write_text(
                json.dumps({"name": "X", "logainm_id": "1"}), encoding="utf-8")
        self.write_places([row("1", "Alpha")])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_gen()

    def test_no_em_dashes_in_generated_files(self):
        self.write_places([row("1", "Alpha")])
        self.run_gen()
        for p in self.root.rglob("*"):
            if p.is_file():
                self.assertNotIn(chr(0x2014), p.read_text(encoding="utf-8"), p.name)


if __name__ == "__main__":
    unittest.main()
