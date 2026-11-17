"""Tests for the parish-register rows of data/source/manifest.csv (tools/source_manifest.py)."""
import csv
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import source_manifest as sm  # noqa: E402

BAP = "nli_parish/tawnawilly/raw/tawnawilly_baptisms_raw.csv"
MAR = "nli_parish/tawnawilly/raw/tawnawilly_marriages_raw.csv"


class RegisterManifest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.src = self.root / "data/source"
        (self.src / "census").mkdir(parents=True)
        (self.src / "nli_parish/tawnawilly/raw").mkdir(parents=True)
        (self.src / "census/Alpha_1926.csv").write_bytes(b"census_year\r\n1926\r\n")
        (self.src / BAP).write_text("row_id\nTAW-B-p004-r1\n", encoding="utf-8")
        (self.src / MAR).write_text("row_id\nTAW-M-p037-r1\n", encoding="utf-8")
        self.manifest = self.src / "manifest.csv"
        rows = [sm.source_metadata(self.src / "census/Alpha_1926.csv")]
        with self.manifest.open("w", encoding="utf-8", newline="") as s:
            w = csv.DictWriter(s, fieldnames=sm.FIELDS)
            w.writeheader()
            w.writerows(rows)
        self.patches = [
            mock.patch.object(sm, "SOURCE_DIR", self.src / "census"),
            mock.patch.object(sm, "MANIFEST", self.manifest),
            mock.patch.object(sm, "EXPECTED_FILES", 1),
            mock.patch.object(sm, "ROOT", self.root),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self._tmp.cleanup()

    def verify(self):
        with mock.patch("sys.stderr"), mock.patch("builtins.print"):
            return sm.verify_manifest()

    def test_unlisted_register_file_fails(self):
        self.assertEqual(self.verify(), 1)

    def test_add_then_verify(self):
        self.assertEqual(sm.register_add(), 0)
        self.assertEqual(self.verify(), 0)
        files = [r["file"] for r in sm.read_manifest()]
        self.assertIn(BAP, files)
        self.assertIn(MAR, files)

    def test_add_does_not_change_existing_rows(self):
        before = [r for r in sm.read_manifest()]
        sm.register_add()
        self.assertEqual(sm.read_manifest()[:1], before)

    def test_edit_fails_until_register_update(self):
        sm.register_add()
        (self.src / BAP).write_text("row_id\nTAW-B-p004-r1\nTAW-B-p004-r2\n", encoding="utf-8")
        self.assertEqual(self.verify(), 1)
        self.assertEqual(sm.register_update(), 0)
        self.assertEqual(self.verify(), 0)

    def test_update_never_touches_census_rows(self):
        sm.register_add()
        (self.src / "census/Alpha_1926.csv").write_bytes(b"census_year\r\n1926\r\nchanged\r\n")
        census_before = sm.read_manifest()[0]["sha256"]
        sm.register_update()
        self.assertEqual(sm.read_manifest()[0]["sha256"], census_before)
        self.assertEqual(self.verify(), 1)

    def test_missing_register_file_fails(self):
        sm.register_add()
        (self.src / MAR).unlink()
        self.assertEqual(self.verify(), 1)

    def test_blank_field_fails(self):
        sm.register_add()
        rows = sm.read_manifest()
        for r in rows:
            if r["file"] == BAP:
                r["licence_note"] = ""
        sm.write_manifest(rows)
        self.assertEqual(self.verify(), 1)


if __name__ == "__main__":
    unittest.main()
