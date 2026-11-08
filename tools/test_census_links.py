"""Tests for tools/census_links.py (WP18). Run from the repo root:

    python -m pytest -q tools/test_census_links.py

All rows are invented. The real census files are never read.
"""

import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import census_links as cl  # noqa: E402

CFG = cl.load_config()
NAMES = cl.Names()
_n = [0]


def row(year, first, surname, age, sex="M", town="Alpha", house="1", rel="Head", marital="Married"):
    _n[0] += 1
    r = {"year": year, "ded": "Test", "townland": town, "first": first, "surname": surname,
         "age": age, "sex": sex, "house": house, "form": "", "rel": rel,
         "marital": cl.marital_class(marital), "marr_years": None, "born": None, "loc": str(_n[0])}
    r["obs"] = "census%d:test:%d" % (year, _n[0])
    r["tkey"] = cl.gedcom_census.place_key(town)
    r["relc"] = cl.rel_class(rel)
    r["hh"] = (year, r["tkey"], house)
    return r


def run(rows, names=NAMES):
    return cl.propose_ded(rows, names, CFG)[0]


def pairs(links):
    return {(c["a"]["obs"], c["b"]["obs"]): c for c in links}


class LinkTests(unittest.TestCase):
    def test_clear_family_links_high(self):
        a = [row(1901, "Thomas", "Kelly", 60), row(1901, "Margaret", "Kelly", 58, "F", rel="Wife")]
        b = [row(1911, "Thomas", "Kelly", 70), row(1911, "Margaret", "Kelly", 68, "F", rel="Wife")]
        links = run(a + b)
        self.assertEqual(len(links), 2)
        self.assertEqual({c["confidence"] for c in links}, {"high"})

    def test_sex_must_match(self):
        links = run([row(1901, "Joe", "Kelly", 30), row(1911, "Joe", "Kelly", 40, "F")])
        self.assertEqual(links, [])

    def test_age_drift_beyond_limit_is_not_linked(self):
        links = run([row(1901, "Joe", "Kelly", 30), row(1911, "Joe", "Kelly", 52)])
        self.assertEqual(links, [])

    def test_unverified_surnames_not_combined(self):
        links = run([row(1901, "Joe", "Sweeny", 30), row(1911, "Joe", "Sweeney", 40)])
        self.assertEqual(links, [])

    def test_two_johns_never_high(self):
        a = [row(1901, "John", "Cassidy", 40, house="12"), row(1901, "John", "Cassidy", 36, house="14")]
        b = [row(1911, "John", "Cassidy", 49, house="9")]
        links = run(a + b)
        self.assertTrue(links)
        for c in links:
            self.assertEqual(c["confidence"], "low")
            self.assertIn("ambiguous", c["flags"])

    def test_married_name_found_in_other_townland_and_capped_low(self):
        a = [row(1901, "Bella", "McGettigan", 20, "F", town="Mull", rel="Daughter", marital="Single")]
        b = [row(1911, "Bella", "Kelly", 30, "F", town="Alpha", rel="Daughter in Law")]
        links = run(a + b)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["confidence"], "low")

    def test_older_age_allows_larger_drift_but_grades_low(self):
        links = run([row(1901, "Mary", "Doe", 60, "F", marital="Widow"),
                     row(1911, "Mary", "Doe", 80, "F", marital="Widow")])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["confidence"], "low")

    def test_deterministic(self):
        a = [row(1901, "Thomas", "Kelly", 60), row(1901, "Joe", "Kelly", 30, rel="Son")]
        b = [row(1911, "Thomas", "Kelly", 70), row(1911, "Joe", "Kelly", 40, rel="Son")]
        first = [(c["a"]["obs"], c["b"]["obs"], c["confidence"]) for c in run(a + b)]
        second = [(c["a"]["obs"], c["b"]["obs"], c["confidence"]) for c in run(list(reversed(a + b)))]
        self.assertEqual(sorted(first), sorted(second))

    def test_each_row_links_once_per_return(self):
        a = [row(1901, "Joe", "Kelly", 30)]
        b = [row(1911, "Joe", "Kelly", 40, house="1"), row(1911, "Joe", "Kelly", 40, house="2")]
        links = run(a + b)
        self.assertTrue(all("ambiguous" in c["flags"] for c in links))


H1 = ["census_year", "ded", "townland", "townland_clean", "firstname", "surname", "age", "sex", "house_number",
      "relation_to_head", "relation_to_head_updated", "marriage_status", "marriage_years", "children_born", "id",
      "images", "occupation", "occupation_updated", "birthplace"]


def write_census(directory: Path, people):
    """people: (year, id, house, first, surname, age, sex, relation, marital). 1901 and 1911 only."""
    for year in (1901, 1911):
        with open(directory / ("%d_Test.csv" % year), "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=H1, lineterminator="\n")
            w.writeheader()
            for y, i, house, first, sur, age, sex, rel, marital in people:
                if y == year:
                    w.writerow({"census_year": y, "ded": "Test", "townland": "Alpha", "townland_clean": "Alpha",
                                "firstname": first, "surname": sur, "age": age, "sex": "Male" if sex == "M" else "Female",
                                "house_number": house, "relation_to_head": rel, "relation_to_head_updated": rel,
                                "marriage_status": marital, "marriage_years": "", "children_born": "", "id": i,
                                "images": "[]", "occupation": "", "occupation_updated": "", "birthplace": "Co Donegal"})


PEOPLE = [
    (1901, "100", "1", "Thomas", "Kelly", 60, "M", "Head", "Married"),
    (1901, "101", "1", "Margaret", "Kelly", 58, "F", "Wife", "Married"),
    (1911, "200", "1", "Thomas", "Kelly", 70, "M", "Head", "Married"),
    (1911, "201", "1", "Margaret", "Kelly", 68, "F", "Wife", "Married"),
    (1901, "110", "2", "John", "Doe", 30, "M", "Head", "Single"),
    (1911, "210", "5", "John", "Doe", 40, "M", "Head", "Single"),
    (1911, "211", "6", "John", "Doe", 41, "M", "Head", "Single"),
]
K = {"a": "census1901:test:100>census1911:test:200", "b": "census1901:test:101>census1911:test:201"}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.census = self.dir / "census"
        self.census.mkdir()
        write_census(self.census, PEOPLE)
        self.records = self.dir / "census_links.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def accept(self, lines, **kw):
        text = "status,confidence,from_obs,to_obs,from_name,to_name,reviewer,date\n" + "\n".join(lines) + "\n"
        out = io.StringIO()
        code = cl.run_accept(text, self.records, self.census, out=out, **kw)
        return code, out.getvalue()

    def proposed(self):
        outdir = self.dir / "out"
        cl.run_propose(self.census, outdir, CFG, names=NAMES, decisions=self.records)
        with open(outdir / "test_links.csv", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def test_accepting_twice_changes_nothing(self):
        line = "accepted,high,census1901:test:100,census1911:test:200,Thomas Kelly,Thomas Kelly,Mike,2026-11-08"
        self.assertEqual(self.accept([line])[0], 0)
        first = self.records.read_bytes()
        code, msg = self.accept([line])
        self.assertEqual(code, 0)
        self.assertIn("1 already recorded", msg)
        self.assertEqual(self.records.read_bytes(), first)

    def test_accepted_link_is_kept_with_reviewer_and_date(self):
        self.accept(["accepted,high,census1901:test:100,census1911:test:200,Thomas Kelly,Thomas Kelly,Mike,2026-11-08"])
        rows = {(r["from_obs"], r["to_obs"]): r for r in self.proposed()}
        r = rows[("census1901:test:100", "census1911:test:200")]
        self.assertEqual((r["status"], r["reviewer"], r["date"]), ("accepted", "Mike", "2026-11-08"))

    def test_rejected_pair_is_never_proposed_again(self):
        self.assertIn(("census1901:test:100", "census1911:test:200"),
                      {(r["from_obs"], r["to_obs"]) for r in self.proposed()})
        self.accept(["rejected,low,census1901:test:100,census1911:test:200,Thomas Kelly,Thomas Kelly,Mike,2026-11-08"])
        after = {(r["from_obs"], r["to_obs"]) for r in self.proposed()}
        self.assertNotIn(("census1901:test:100", "census1911:test:200"), after)

    def test_accepted_row_does_not_compete(self):
        before = [r for r in self.proposed() if r["from_obs"] == "census1901:test:110"]
        self.assertEqual(len(before), 2)                       # two Johns, so both stay open
        self.accept(["accepted,low,census1901:test:110,census1911:test:211,John Doe,John Doe,Mike,2026-11-08"])
        after = [r for r in self.proposed() if r["from_obs"] == "census1901:test:110"]
        self.assertEqual([(r["to_obs"], r["status"]) for r in after], [("census1911:test:211", "accepted")])

    def test_unsound_decisions_write_nothing(self):
        bad = [
            "accepted,high,census1901:test:100,census1911:test:999,A,B,Mike,2026-11-08",
            "accepted,high,census1911:test:200,census1901:test:100,A,B,Mike,2026-11-08",
        ]
        for line in bad:
            code, msg = self.accept([line])
            self.assertEqual(code, 1)
            self.assertFalse(self.records.exists())
        code, msg = self.accept(["accepted,high,census1901:test:110,census1911:test:210,A,B,Mike,2026-11-08",
                                 "accepted,high,census1901:test:110,census1911:test:211,A,B,Mike,2026-11-08"])
        self.assertEqual(code, 1)
        self.assertIn("already linked", msg)
        self.assertFalse(self.records.exists())

    def test_changed_mind_replaces_earlier_decision(self):
        a = "census1901:test:100,census1911:test:200,Thomas Kelly,Thomas Kelly,Mike,2026-11-08"
        self.accept(["accepted,high," + a])
        code, msg = self.accept(["rejected,high," + a])
        self.assertIn("1 changed", msg)
        self.assertEqual(cl.load_decisions(self.records)[("census1901:test:100", "census1911:test:200")]["status"], "rejected")

    def test_validator_check_reports_a_stale_id(self):
        self.accept(["accepted,high,census1901:test:100,census1911:test:200,A,B,Mike,2026-11-08"])
        self.assertEqual(cl.check_decisions(self.records, self.census), [])
        (self.census / "1911_Test.csv").write_text(",".join(H1) + "\n", encoding="utf-8")
        self.assertTrue(cl.check_decisions(self.records, self.census))


class GivenNameTests(unittest.TestCase):
    def test_reference_checks_clean(self):
        import given_names_reference as g
        self.assertEqual(g.check(), [])


if __name__ == "__main__":
    unittest.main()


class AcceptTests(unittest.TestCase):
    """WP19: recording decisions pasted from the review page."""

    def setUp(self):
        import io
        import tempfile
        from unittest import mock
        self.io, self.tmp = io, tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "census_links.csv"
        self.a, self.b, self.c = row(1901, "Joe", "Kelly", 30), row(1911, "Joe", "Kelly", 40), row(1911, "Joe", "Kelly", 41, house="2")
        self.rows = [self.a, self.b, self.c]
        p = mock.patch.object(cl, "load_census", lambda d: self.rows)
        p.start()
        self.addCleanup(p.stop)

    def text(self, *decisions):
        out = ["status,confidence,from_obs,to_obs,from_name,to_name,reviewer,date"]
        for status, f, t in decisions:
            out.append("%s,high,%s,%s,A,B,Mike,2026-11-08" % (status, f["obs"], t["obs"]))
        return "\n".join(out) + "\n"

    def accept(self, *d, **kw):
        return cl.run_accept(self.text(*d), self.path, Path("."), out=self.io.StringIO(), **kw)

    def test_accepted_and_rejected_rows_are_recorded_with_reviewer_and_date(self):
        self.assertEqual(self.accept(("accepted", self.a, self.b), ("rejected", self.a, self.c)), 0)
        d = cl.load_decisions(self.path)
        self.assertEqual(d[(self.a["obs"], self.b["obs"])]["status"], "accepted")
        self.assertEqual(d[(self.a["obs"], self.c["obs"])]["status"], "rejected")
        self.assertEqual(d[(self.a["obs"], self.b["obs"])]["reviewer"], "Mike")
        self.assertEqual(d[(self.a["obs"], self.b["obs"])]["date"], "2026-11-08")

    def test_accepting_the_same_decisions_twice_changes_nothing(self):
        self.accept(("accepted", self.a, self.b))
        first = self.path.read_text()
        self.accept(("accepted", self.a, self.b))
        self.assertEqual(first, self.path.read_text())

    def test_a_later_decision_replaces_the_earlier_one(self):
        self.accept(("accepted", self.a, self.b))
        self.accept(("rejected", self.a, self.b))
        self.assertEqual(cl.load_decisions(self.path)[(self.a["obs"], self.b["obs"])]["status"], "rejected")

    def test_unknown_observation_id_records_nothing(self):
        ghost = dict(self.b, obs="census1911:test:999999")
        self.assertEqual(self.accept(("accepted", self.a, ghost)), 1)
        self.assertFalse(self.path.exists())

    def test_a_row_cannot_be_accepted_to_two_rows_of_the_same_return(self):
        self.assertEqual(self.accept(("accepted", self.a, self.b), ("accepted", self.a, self.c)), 1)
        self.assertFalse(self.path.exists())

    def test_a_link_must_run_forwards(self):
        self.assertEqual(self.accept(("accepted", self.b, self.a)), 1)

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.accept(("accepted", self.a, self.b), dry_run=True), 0)
        self.assertFalse(self.path.exists())

    def test_rows_without_a_decision_are_ignored(self):
        self.assertEqual(cl.run_accept("status,from_obs,to_obs\n,x,y\n", self.path, Path("."), out=self.io.StringIO()), 1)

    def test_a_rejected_pair_is_never_proposed_again_and_an_accepted_one_is_kept(self):
        a = row(1901, "Ellen", "Doherty", 12, "F", "Daughter")
        b = row(1911, "Ellen", "Doherty", 22, "F", "Daughter")
        d = {(a["obs"], b["obs"]): {"status": "rejected", "confidence": "", "from_obs": a["obs"], "to_obs": b["obs"]}}
        links, _ = cl.propose_ded([a, b], NAMES, CFG, d)
        self.assertEqual(links, [])
        d[(a["obs"], b["obs"])]["status"] = "accepted"
        links, _ = cl.propose_ded([a, b], NAMES, CFG, d)
        self.assertEqual(len(links), 1)
