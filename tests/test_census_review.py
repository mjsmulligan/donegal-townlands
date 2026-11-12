"""Tests for the review queues in tools/census_review.py (WP23). Run from the repo root:

    python -m pytest -q tests/test_census_review.py

All rows are invented. The real census files are never read.
"""

import csv
import tempfile
import unittest
from pathlib import Path

import census_review as cr  # noqa: E402

HIDE = ["moved townland", "no household continuity"]


class QueueTests(unittest.TestCase):
    def test_clean_high_link(self):
        self.assertEqual(cr.queue_of("high", []), "clean")

    def test_medium_is_review(self):
        self.assertEqual(cr.queue_of("medium", ["given name variant"]), "review")

    def test_low_across_townland_without_household_support_is_hidden(self):
        self.assertEqual(cr.queue_of("low", HIDE + ["age drift 4"]), "hidden")
        self.assertEqual(cr.queue_of("low", ["ambiguous"] + HIDE), "hidden")

    def test_surname_change_is_never_hidden(self):
        self.assertEqual(cr.queue_of("low", ["surname change", "no household continuity"]), "review")
        self.assertEqual(cr.queue_of("low", ["surname change"] + HIDE), "review")

    def test_low_in_same_townland_or_with_household_support_stays_in_review(self):
        self.assertEqual(cr.queue_of("low", ["ambiguous", "no household continuity"]), "review")
        self.assertEqual(cr.queue_of("low", ["ambiguous", "moved townland"]), "review")
        self.assertEqual(cr.queue_of("low", ["relationship unlikely"]), "review")

    def test_show_all_turns_hiding_off(self):
        self.assertEqual(cr.queue_of("low", HIDE, hide=False), "review")
        self.assertEqual(cr.queue_of("high", [], hide=False), "clean")


class BuildRowsTests(unittest.TestCase):
    FIELDS = ["status", "confidence", "group", "from_obs", "from_name", "from_age", "from_relation",
              "from_townland", "to_obs", "to_name", "to_age", "to_relation", "to_townland", "years",
              "method", "flags", "ambiguous_with", "chain", "reviewer", "date", "note"]

    def make(self, tmp, rows):
        path = Path(tmp) / "x_links.csv"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=self.FIELDS)
            w.writeheader()
            for i, (conf, flags) in enumerate(rows):
                w.writerow({k: "" for k in self.FIELDS} | {
                    "confidence": conf, "flags": "; ".join(flags), "group": "g",
                    "from_obs": "census1901:t:%d" % i, "to_obs": "census1911:t:%d" % i, "years": "1901-1911",
                    "from_townland": "A", "to_townland": "B"})
        return [path]

    def test_every_row_has_a_queue_and_hidden_rows_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = self.make(tmp, [("high", []), ("medium", ["given name variant"]), ("low", HIDE)])
            rows = cr.build_rows(files)
            self.assertEqual([r["queue"] for r in rows], ["clean", "review", "hidden"])
            self.assertEqual(len(rows), 3)
            rows = cr.build_rows(files, hide=False)
            self.assertEqual([r["queue"] for r in rows], ["clean", "review", "review"])

    def test_audit_sample_is_drawn_from_high_links_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = cr.build_rows(self.make(tmp, [("high", [])] * 3 + [("low", HIDE)] * 3))
            self.assertTrue(all(r["conf"] == "high" for r in rows if r["audit"]))


if __name__ == "__main__":
    unittest.main()
