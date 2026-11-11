"""Tests for the Logainm snapshot and place table tools.

The responses below are SYNTHETIC. They follow the field names that GRA's
fetch_places.py reads (nameEN, categories, includedIn, geography, placenames)
but are not real Logainm data and invented IDs are used. The real response
shape must be confirmed against a live snapshot (see GAZETTEER_SPEC.md).
"""
import csv
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import logainm  # noqa: E402

DATE = "2026-01-01"

DED = {
    "id": 900001, "nameEN": "Testded",
    "categories": [{"id": "ED", "nameEN": "Electoral Division"}],
    "includedIn": [{"id": 900100, "nameEN": "Test County", "category": {"id": "CON", "nameEN": "County"}}],
}
TOWNLAND = {
    "id": 900002, "nameEN": "Testland Upper",
    "placenames": [{"language": "ga", "wording": "An Tulach Uachtarach"}],
    "categories": [{"id": "BF", "nameEN": "Townland"}],
    "geography": {"coordinates": [{"latitude": "54.7", "longitude": "-8.1"}]},
    "includedIn": [
        {"id": 900100, "nameEN": "Test County", "category": {"id": "CON", "nameEN": "County"}},
        {"id": 900200, "nameEN": "Test Barony", "category": {"id": "BAR", "nameEN": "Barony"}},
        {"id": 900300, "nameEN": "Test Parish", "category": {"id": "PAR", "nameEN": "Civil Parish"}},
    ],
}
CHILDREN = {"count": 1, "results": [{"id": 900002}]}


def make_snapshot(base: pathlib.Path, townland=TOWNLAND):
    raw = base / DATE / "raw"
    raw.mkdir(parents=True)
    rows = []
    for name, kind, lid, data in [
        ("place_900001.json", "place", 900001, DED),
        ("children_900001_p1.json", "children", 900001, CHILDREN),
        ("place_900002.json", "place", 900002, townland),
    ]:
        content = json.dumps(data).encode()
        (raw / name).write_bytes(content)
        rows.append({"file": f"raw/{name}", "kind": kind, "logainm_id": lid, "query": "test",
                     "retrieved_at": "2026-01-01T00:00:00Z", "sha256": logainm.sha256_bytes(content),
                     "licence_note": logainm.LICENCE_NOTE})
    logainm.write_manifest(DATE, rows)


class LogainmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original = logainm.SNAPSHOT_ROOT
        logainm.SNAPSHOT_ROOT = pathlib.Path(self.tmp.name)
        self.addCleanup(setattr, logainm, "SNAPSHOT_ROOT", self.original)

    def test_parse_townland(self):
        row = logainm.place_row(TOWNLAND, 900002, DATE)
        self.assertEqual(row["name_en"], "Testland Upper")
        self.assertEqual(row["name_ga"], "An Tulach Uachtarach")
        self.assertEqual(row["place_type"], "townland")
        self.assertEqual((row["county_id"], row["barony_id"], row["civil_parish_id"]), (900100, 900200, 900300))
        self.assertEqual((row["latitude"], row["longitude"]), (54.7, -8.1))

    def test_ded_taken_from_fetch_root(self):
        make_snapshot(logainm.SNAPSHOT_ROOT)
        rows = {r["logainm_id"]: r for r in logainm.build_rows(DATE)}
        self.assertEqual(rows[900002]["ded_id"], 900001)
        self.assertEqual(rows[900001]["place_type"], "ded")

    def test_build_is_deterministic(self):
        make_snapshot(logainm.SNAPSHOT_ROOT)
        out = pathlib.Path(self.tmp.name) / "places.csv"
        logainm.write_places(logainm.build_rows(DATE), out)
        first = out.read_bytes()
        logainm.write_places(logainm.build_rows(DATE), out)
        self.assertEqual(first, out.read_bytes())
        with out.open(encoding="utf-8", newline="") as stream:
            self.assertEqual(csv.DictReader(stream).fieldnames, logainm.PLACE_FIELDS)

    def test_changed_raw_file_fails_verification(self):
        make_snapshot(logainm.SNAPSHOT_ROOT)
        self.assertEqual(logainm.verify_snapshot(DATE), [])
        path = logainm.SNAPSHOT_ROOT / DATE / "raw" / "place_900002.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.assertEqual(len(logainm.verify_snapshot(DATE)), 1)

    def test_notes_and_citations_are_flagged(self):
        flagged = dict(TOWNLAND, notes="Explanatory text", placenames=[
            {"language": "ga", "wording": "X", "citations": [{"text": "from a source"}]}])
        paths = logainm.suspect_paths(flagged)
        self.assertTrue(any(p == "notes" for p in paths))
        self.assertTrue(any("citations" in p for p in paths))
        self.assertEqual(logainm.suspect_paths(TOWNLAND), [])


if __name__ == "__main__":
    unittest.main()
