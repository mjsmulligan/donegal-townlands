"""Tests for tools/tree_census_links.py (WP16). Uses small invented fixtures only."""
import csv
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import tree_census_links as gc  # noqa: E402

CENSUS_1901_HEADER = ("id,census_year,county,surname,firstname,townland,townland_clean,ded,age,sex,house_number,"
                      "relation_to_head,relation_to_head_updated")
CENSUS_1926_HEADER = ("aform_name,county,townland,ded,first_name,surname,relationship_to_head,"
                      "updated_relationship_to_head,updated_age,a_id")

GEDCOM = """0 HEAD
0 @I1@ INDI
1 NAME Hugh /Example/
2 GIVN Hugh
2 SURN Example
1 BIRT
2 DATE ABT 1850
1 SOUR @S1@
2 PAGE 1901 Census, Ballyfake, house 4, head of household; farmer, age 51.
1 NOTE Death cert says 1911 Census showed age 60 so this is only a note.
0 @I2@ INDI
1 NAME Anne /Maiden/
2 GIVN Anne
2 SURN Maiden
1 BIRT
2 DATE ABT 1855
1 SOUR @S1@
2 PAGE 1901 Census, Ballyfake, house 4; wife, age 46, married.
0 @I3@ INDI
1 NAME Kate /Example/
2 GIVN Kate
2 SURN Example
1 BIRT
2 DATE 3 Mar 1900
1 SOUR @S2@
2 PAGE 1926 Census, Ballyfake, household of Hugh Example; form Ballyfake_0001_0002.pdf; Kate listed as daughter,
3 CONC  age 26.
0 @I4@ INDI
1 NAME Old /Example/
2 GIVN Old
2 SURN Example
1 BIRT
2 DATE ABT 1810
1 SOUR @S1@
2 PAGE 1901 Census, Ballyfake, house 9; age 55 - possible match.
0 @I5@ INDI
1 NAME Young /Example/
2 GIVN Young
2 SURN Example
1 BIRT
2 DATE 5 May 1950
1 SOUR @S1@
2 PAGE 1926 Census, Ballyfake, household of Hugh Example; Young listed as son, age 1.
0 TRLR
"""


def write(path, text):
    pathlib.Path(path).write_text(text, encoding="utf-8")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        write(self.dir / "t.ged", GEDCOM)
        (self.dir / "census").mkdir()
        write(self.dir / "census" / "X_1901.csv", "\n".join([
            CENSUS_1901_HEADER,
            "100,1901,Donegal,Example,Hugh,Ballyfake,ballyfake,Testded,51.0,M,4.0,Head of Family,Head of Family",
            "101,1901,Donegal,Example,Anne,Ballyfake,ballyfake,Testded,46.0,F,4.0,Wife,Wife",
            "102,1901,Donegal,Other,Mary,Ballyfake,ballyfake,Testded,30.0,F,5.0,Head of Family,Head of Family",
            ""]))
        write(self.dir / "census" / "X_1926.csv", "\n".join([
            CENSUS_1926_HEADER,
            "Ballyfake_0001_0002.pdf,Donegal,Ballyfake,Testded,Kate,Example,Daughter,Daughter,26.0,900",
            "Ballyfake_0001_0002.pdf,Donegal,Ballyfake,Testded,Hugh,Example,Head,Head,76.0,901",
            ""]))
        self.people = gc.load_people(self.dir / "t.ged")
        self.rows = gc.load_census(self.dir / "census")

    def tearDown(self):
        self.tmp.cleanup()


class CitationTests(Fixture):
    def test_parses_fields_and_joins_continuation(self):
        c = self.people["@I3@"]["cites"][0]
        self.assertEqual((c["year"], c["townland"], c["head"], c["rel"], c["age"]),
                         (1926, "Ballyfake", "Hugh Example", "daughter", 26))
        self.assertEqual(c["form"], "Ballyfake_0001_0002.pdf")

    def test_note_mentioning_a_census_is_not_a_citation(self):
        self.assertEqual(len(self.people["@I1@"]["cites"]), 1)

    def test_house_and_head_flag(self):
        c = self.people["@I1@"]["cites"][0]
        self.assertEqual(c["house"], "4")
        self.assertTrue(c["is_head"])


class CensusTests(Fixture):
    def test_observation_ids(self):
        ids = {r["obs"] for r in self.rows}
        self.assertIn("census1901:testded:100", ids)
        self.assertIn("census1926:testded:900", ids)
        self.assertTrue(all(gc.OBS_RE.match(i) for i in ids))


class MatchTests(Fixture):
    def setUp(self):
        super().setUp()
        self.assoc, self.pending, self.unresolved = gc.propose(self.people, self.rows)
        self.by = {a["person_ptr"]: a for a in self.assoc}

    def test_head_matches_with_high_confidence(self):
        a = self.by["@I1@"]
        self.assertEqual(a["obs_id"], "census1901:testded:100")
        self.assertEqual(a["confidence"], "high")

    def test_married_woman_found_under_husbands_surname_but_not_high(self):
        a = self.by["@I2@"]
        self.assertEqual(a["obs_id"], "census1901:testded:101")
        self.assertEqual(a["confidence"], "medium")
        self.assertIn("married name", a["method"])

    def test_schedule_id_links_1926_row(self):
        a = self.by["@I3@"]
        self.assertEqual(a["obs_id"], "census1926:testded:900")
        self.assertTrue(a["method"].startswith("schedule id"))

    def test_citation_with_no_matching_row_is_unresolved_not_guessed(self):
        self.assertNotIn("@I4@", self.by)
        self.assertIn("@I4@", [u["person_ptr"] for u in self.unresolved])

    def test_unloaded_townland_is_pending(self):
        people = {"@I9@": {**self.people["@I1@"], "ptr": "@I9@",
                           "cites": [gc.parse_citation("1901 Census, Elsewhere, house 1; age 30.")]}}
        _, pending, unresolved = gc.propose(people, self.rows)
        self.assertEqual(len(pending), 1)
        self.assertEqual(unresolved, [])


class PrivacyTests(Fixture):
    def test_person_born_within_100_years_is_withheld(self):
        assoc, _, _ = gc.propose(self.people, self.rows)
        kept, withheld = gc.privacy_filter(self.people, assoc, this_year=2026)
        self.assertNotIn("@I5@", {a["person_ptr"] for a in kept})
        self.assertIn("@I1@", {a["person_ptr"] for a in kept})

    def test_withholds_when_birth_unknown_and_implied_year_recent(self):
        p = {"ptr": "@I7@", "birth_year": None}
        links = [{"cite_year": 1926, "row_age": 3}]
        self.assertIsNone(gc.person_birth_floor({"birth_year": None}, []))
        self.assertEqual(gc.person_birth_floor(p, links), 1923)


class AuditTests(Fixture):
    def _assoc(self, ptr, pairs):
        return [{"person_ptr": ptr, "cite_year": y, "row_age": a} for y, a in pairs]

    def test_estimated_birth_with_drift_is_expected_drift(self):
        people = {"@A@": {"name": "A", "birth": "ABT 1854", "birth_year": 1854}}
        rows = gc.audit(people, self._assoc("@A@", [(1901, 47), (1911, 68), (1926, 79)]))
        self.assertEqual(rows[0]["tier"], "expected drift")

    def test_tree_year_far_from_every_census_year_is_conflict(self):
        people = {"@A@": {"name": "A", "birth": "ABT 1810", "birth_year": 1810}}
        rows = gc.audit(people, self._assoc("@A@", [(1901, 55)]))
        self.assertEqual(rows[0]["tier"], "conflict")

    def test_exact_birth_after_1864_needs_tight_agreement(self):
        people = {"@A@": {"name": "A", "birth": "3 Mar 1870", "birth_year": 1870}}
        rows = gc.audit(people, self._assoc("@A@", [(1901, 31), (1911, 36)]))
        self.assertEqual(rows[0]["tier"], "conflict")

    def test_consistent_person_is_not_listed(self):
        people = {"@A@": {"name": "A", "birth": "ABT 1850", "birth_year": 1850}}
        self.assertEqual(gc.audit(people, self._assoc("@A@", [(1901, 51), (1911, 61)])), [])


class DecisionTests(Fixture):
    def _write(self, rows):
        path = self.dir / "decisions.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, gc.DECISION_FIELDS)
            w.writeheader()
            w.writerows(rows)
        return path

    def row(self, **kw):
        base = {"person_ptr": "@I1@", "person_name": "Hugh Example", "person_birth": "ABT 1850",
                "obs_id": "census1901:testded:100", "status": "accepted", "reviewer": "Mike",
                "date": "2026-11-06", "method": "m", "proposed_confidence": "high", "note": ""}
        base.update(kw)
        return base

    def test_valid_decision_passes_with_id_guard(self):
        path = self._write([self.row()])
        self.assertEqual(gc.check_decisions(path, self.people, self.rows), [])

    def test_changed_person_behind_an_id_is_caught(self):
        path = self._write([self.row(person_name="Someone Else")])
        errs = gc.check_decisions(path, self.people, self.rows)
        self.assertTrue(any("decision was for" in e for e in errs))

    def test_duplicate_missing_reviewer_and_unknown_observation(self):
        path = self._write([self.row(), self.row(), self.row(obs_id="census1901:testded:999", reviewer="")])
        errs = " | ".join(gc.check_decisions(path, self.people, self.rows))
        self.assertIn("duplicate", errs)
        self.assertIn("reviewer is required", errs)
        self.assertIn("not in the census files", errs)

    def test_bad_status_and_date(self):
        path = self._write([self.row(status="maybe", date="6 Nov")])
        errs = " | ".join(gc.check_decisions(path))
        self.assertIn("accepted or rejected", errs)
        self.assertIn("YYYY-MM-DD", errs)


class RepeatabilityTests(Fixture):
    def test_two_runs_give_identical_files(self):
        out1, out2 = self.dir / "o1", self.dir / "o2"
        gc.run_propose(self.dir / "t.ged", self.dir / "census", out1)
        gc.run_propose(self.dir / "t.ged", self.dir / "census", out2)
        for name in ("proposed_associations.csv", "audit.csv", "unresolved_in_loaded_data.csv"):
            self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
