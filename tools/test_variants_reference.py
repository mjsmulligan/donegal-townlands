"""Tests for tools/variants_reference.py. Run from the repo root:

    python -m unittest tools.test_variants_reference -v

Every test works in a temporary directory except the last, which checks the real file.
"""

import csv
import tempfile
import unittest
from pathlib import Path

from tools import variants_reference as vr


def row(**kw):
    r = dict(family_id="a-b", label="Ab", spellings="Ab|Ba", status="proposed", authority="", basis="",
             observed_in="", added="2026-11-05", notes="")
    r.update(kw)
    return r


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "v.csv"

    def write(self, rows, header=None):
        with self.path.open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, header or vr.FIELDS)
            w.writeheader()
            w.writerows(rows)

    def test_a_good_file_has_no_problems_and_an_absent_file_is_empty(self):
        self.write([row(), row(family_id="c-d", label="Cd", spellings="Cd|Dc", status="verified", authority="Mike",
                              basis="x", observed_in="y")])
        self.assertEqual(vr.check(self.path), [])
        self.assertEqual(vr.check(self.path.with_name("none.csv")), [])
        self.assertEqual(vr.load(self.path.with_name("none.csv")), [])

    def test_wrong_header_is_reported(self):
        self.write([{"family_id": "a"}], header=["family_id"])
        self.assertEqual(len(vr.check(self.path)), 1)

    def test_each_rule_is_enforced(self):
        cases = {
            "slug": row(family_id="Bad Id"),
            "status": row(status="maybe"),
            "two different spellings": row(spellings="Ab|ab"),
            "label": row(label="Zz"),
            "needs authority": row(status="verified", basis="x", observed_in="y"),
            "needs basis": row(status="verified", authority="Mike", observed_in="y"),
            "needs observed_in": row(status="verified", authority="Mike", basis="x"),
        }
        for words, bad in cases.items():
            self.write([bad])
            msgs = vr.check(self.path)
            self.assertTrue(any(words in m for m in msgs), (words, msgs))

    def test_repeated_family_id_is_reported(self):
        self.write([row(), row()])
        self.assertTrue(any("repeats" in m for m in vr.check(self.path)))

    def test_lookup_ignores_case_and_punctuation_and_skips_rejected(self):
        self.write([row(), row(family_id="c-d", label="Cd", spellings="Cd|Mc Ab", status="rejected")])
        rows = vr.load(self.path)
        self.assertEqual([r["family_id"] for r in vr.lookup("AB", rows)], ["a-b"])
        self.assertEqual(vr.lookup("mcab", rows), [])
        self.assertEqual(vr.lookup("unknown", rows), [])

    def test_overlap_with_a_verified_row_fails_and_between_proposed_rows_only_warns(self):
        ver = dict(status="verified", authority="Mike", basis="x", observed_in="y")
        self.write([row(), row(family_id="c-d", label="Cd", spellings="Cd|Ba")])
        self.assertEqual(vr.check(self.path), [])
        self.assertEqual(len(vr.warnings(self.path)), 1)
        self.write([row(**ver), row(family_id="c-d", label="Cd", spellings="Cd|Ba")])
        self.assertTrue(any("more than one family" in m for m in vr.check(self.path)))
        self.assertEqual(vr.warnings(self.path), [])

    def test_a_page_gets_only_verified_families_with_a_spelling_it_holds(self):
        ver = dict(status="verified", authority="Mike", basis="x", observed_in="y")
        self.write([row(**ver), row(family_id="c-d", label="Cd", spellings="Cd|Dc"),
                    row(family_id="e-f", label="Ef", spellings="Ef|Fe", **ver)])
        rows = vr.load(self.path)
        self.assertEqual(vr.page_families(["AB"], rows), [{"label": "Ab", "recorded_as": ["Ab", "Ba"]}])
        self.assertEqual(vr.page_families(["Dc"], rows), [])
        self.assertEqual(vr.page_families(["Zz"], rows), [])

    def test_the_real_reference_is_valid_and_every_row_is_verified(self):
        self.assertEqual(vr.check(), [])
        self.assertEqual(vr.warnings(), [])
        verified = [r["family_id"] for r in vr.load() if r["status"] == "verified"]
        self.assertEqual(verified, [r["family_id"] for r in vr.load()])
        self.assertEqual(len(verified), 10)
        self.assertEqual([r["family_id"] for r in vr.lookup("McKenna")], ["mcanaw"])


if __name__ == "__main__":
    unittest.main()
