"""Tests for the Tawnawilly normalised build (data/source/nli_parish/tawnawilly/normalised)."""
import csv
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
NORM = ROOT / "data/source/nli_parish/tawnawilly/normalised"
RAW = ROOT / "data/source/nli_parish/tawnawilly/raw"
spec = importlib.util.spec_from_file_location("build_normalised", NORM / "build_normalised.py")
bn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bn)


def rows(path):
    with open(path, encoding="utf-8", newline="") as s:
        return list(csv.DictReader(s))


class Helpers(unittest.TestCase):
    def test_split_name(self):
        self.assertEqual(bn.split_name("Patt. Mullin"), ("Patt.", "Mullin"))
        self.assertEqual(bn.split_name("Mary Anne McGinty"), ("Mary Anne", "McGinty"))
        self.assertEqual(bn.split_name("Chas. Johnston (alias Tullybrock)"), ("Chas.", "Johnston (alias Tullybrock)"))
        self.assertEqual(bn.split_name("Brigid"), ("Brigid", ""))
        self.assertEqual(bn.split_name(""), ("", ""))

    def test_parse_date(self):
        self.assertEqual(bn.parse_date("9 Jan 1873"), "1873-01-09")
        self.assertEqual(bn.parse_date("Dec 1872"), "1872-12")
        self.assertEqual(bn.parse_date(""), "")
        with self.assertRaises(ValueError):
            bn.parse_date("the ninth")

    def test_rules(self):
        rules = bn.Rules([
            {"kind": "forename", "as_written": "Patt.", "normalised": "Patrick", "status": "", "basis": ""},
            {"kind": "surname", "as_written": "Trower", "normalised": "Travers", "status": "", "basis": ""},
            {"kind": "townland", "as_written": "Town", "normalised": "Donegal Town", "status": "verified", "basis": ""},
        ])
        used = []
        self.assertEqual(bn.full_name(rules, "Patt. Trower", used, "sponsor1"), "Patrick Travers")
        self.assertEqual(len(used), 2)
        self.assertEqual(rules.townland("Town", []), ("Donegal Town", "verified"))
        self.assertEqual(rules.townland("Nowhere", []), ("Nowhere", "unmapped"))
        self.assertEqual(rules.townland("", []), ("", ""))


class Outputs(unittest.TestCase):
    def test_committed_outputs_match_a_rebuild(self):
        for kind in ("baptisms", "marriages"):
            committed = (NORM / f"tawnawilly_{kind}_normalised.csv").read_text(encoding="utf-8")
            self.assertEqual(committed, bn.build(kind), f"{kind} out of date: run build_normalised.py")

    def test_one_row_per_raw_row_in_order(self):
        for kind in ("baptisms", "marriages"):
            raw = rows(RAW / f"tawnawilly_{kind}_raw.csv")
            norm = rows(NORM / f"tawnawilly_{kind}_normalised.csv")
            self.assertEqual([r["row_id"] for r in raw], [r["row_id"] for r in norm])

    def test_resolved_rows_use_the_resolved_reading(self):
        raw = {r["row_id"]: r for r in rows(RAW / "tawnawilly_baptisms_raw.csv")}
        norm = {r["row_id"]: r for r in rows(NORM / "tawnawilly_baptisms_normalised.csv")}
        self.assertEqual(norm["TAW-B-p008-r76"]["date_iso"], "1873-10-05")
        self.assertEqual(norm["TAW-B-p008-r76"]["sponsor1"], "Bernard McGoldrick")
        self.assertEqual(norm["TAW-B-p008-r76"]["raw_status"], "resolved")
        self.assertTrue(raw["TAW-B-p008-r76"]["resolved_reading"])

    def test_every_override_points_at_a_real_row_and_field(self):
        ids = {}
        for kind in ("baptisms", "marriages"):
            for r in rows(NORM / f"tawnawilly_{kind}_normalised.csv"):
                ids[r["row_id"]] = r
        for o in rows(NORM / "overrides.csv"):
            self.assertIn(o["row_id"], ids)
            self.assertIn(o["field"], ids[o["row_id"]])
            self.assertTrue(o["basis"].strip(), o["row_id"])

    def test_dates_are_iso(self):
        import re
        for kind in ("baptisms", "marriages"):
            for r in rows(NORM / f"tawnawilly_{kind}_normalised.csv"):
                self.assertRegex(r["date_iso"], r"^\d{4}-\d{2}(-\d{2})?$", r["row_id"])


if __name__ == "__main__":
    unittest.main()
