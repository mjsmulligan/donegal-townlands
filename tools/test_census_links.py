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
import given_names_reference  # noqa: E402
import variants_reference  # noqa: E402

CFG = cl.load_config()
NAMES = cl.Names()
# The real verified reference files, for tests that depend on them (Joseph and Joe).
REAL = cl.Names(given_names_reference.load(), variants_reference.load())
_n = [0]


def row(year, first, surname, age, sex="M", town="Alpha", house="1", rel="Head", marital="Married"):
    _n[0] += 1
    r = {"year": year, "ded": "Test", "townland": town, "first": first, "surname": surname,
         "age": age, "sex": sex, "house": house, "form": "", "rel": rel,
         "marital": cl.marital_class(marital), "marr_years": None, "born": None, "loc": str(_n[0])}
    r["obs"] = "census%d:test:%d" % (year, _n[0])
    r["tkey"] = cl.townland_key(town)
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


# ------------------------------------------------------------------ person matching (2026-11-11)

def gallagher_1901(house="1", town="Alpha"):
    return [row(1901, "John", "Gallagher", 25, rel="Head", house=house, town=town),
            row(1901, "Mary", "Gallagher", 24, "F", rel="Wife", house=house, town=town),
            row(1901, "Joseph", "Gallagher", 3, rel="Son", marital="Single", house=house, town=town)]


def gallagher_1911(house="1", town="Alpha"):
    return [row(1911, "John", "Gallagher", 35, rel="Head", house=house, town=town),
            row(1911, "Mary", "Gallagher", 34, "F", rel="Wife", house=house, town=town),
            row(1911, "Joe", "Gallagher", 13, rel="Son", marital="Single", house=house, town=town)]


def by_names(links):
    return {(c["a"]["first"], c["b"]["first"]): c for c in links}


class PersonMatchingTests(unittest.TestCase):
    def test_john_mary_and_joseph_joe_link_across_1901_and_1911(self):
        links = by_names(run(gallagher_1901() + gallagher_1911(), REAL))
        self.assertEqual(set(links), {("John", "John"), ("Mary", "Mary"), ("Joseph", "Joe")})
        self.assertEqual(links[("John", "John")]["confidence"], "high")
        self.assertEqual(links[("Mary", "Mary")]["confidence"], "high")
        joe = links[("Joseph", "Joe")]
        self.assertEqual(joe["given"], "verified")
        self.assertEqual(joe["confidence"], "medium")      # one weaker signal: a name variant
        self.assertEqual(joe["flags"], ["given name variant"])
        self.assertEqual(joe["support"], 2)                  # assessed with John and Mary

    def test_joseph_and_joe_need_the_reference_and_nothing_wider(self):
        self.assertEqual(NAMES.given("Joseph", "Joe"), "")                  # no reference loaded
        self.assertEqual(REAL.given("Joseph", "Joe"), "verified")
        self.assertEqual(REAL.given("Joe", "Joseph"), "verified")
        for other in ("Josephine", "Josie", "Joan", "Jo"):
            self.assertEqual(REAL.given("Joseph", other), "", other)

    def test_a_joe_with_no_household_to_corroborate_is_still_only_a_variant(self):
        links = run([row(1901, "Joseph", "Gallagher", 3, rel="Son", marital="Single"),
                     row(1911, "Joe", "Gallagher", 13, rel="Son", marital="Single")], REAL)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["support"], 0)
        self.assertNotEqual(links[0]["confidence"], "high")

    def test_age_progression_and_reasonable_variation(self):
        def link(age_a, age_b):
            return run([row(1901, "Hugh", "Boyle", age_a, marital="Single"),
                        row(1911, "Hugh", "Boyle", age_b, marital="Single")], REAL)
        self.assertEqual(len(link(25, 35)), 1)      # exactly ten years on
        self.assertEqual(len(link(25, 38)), 1)      # three years of drift is allowed
        self.assertEqual(link(25, 39), [])          # four is not, for someone born after 1864
        wide = link(40, 54)                         # born before 1864, so ages were estimates: six allowed
        self.assertEqual(len(wide), 1)
        self.assertIn("age drift 4", wide[0]["flags"])
        self.assertEqual(len(link(40, 56)), 1)
        self.assertEqual(link(40, 57), [])          # seven is too far (the larger drift for over 60s is a separate rule)

    def test_similar_names_and_ages_stay_ambiguous_without_household_evidence(self):
        a = [row(1901, "John", "Gallagher", 25, house="1"), row(1901, "John", "Gallagher", 26, house="2")]
        b = [row(1911, "John", "Gallagher", 36, house="3")]
        links = run(a + b, REAL)
        self.assertTrue(links)
        for c in links:
            self.assertIn("ambiguous", c["flags"])
            self.assertEqual(c["confidence"], "low")

    def test_plausible_individual_match_contradicted_by_household_evidence(self):
        # John fits another John Gallagher aged 36 in house 7 on name and age alone. But his wife and son
        # continue together, as head and son, in house 1, so house 7 is contradicted.
        a = gallagher_1901()
        b = [row(1911, "Mary", "Gallagher", 34, "F", rel="Head", marital="Widow", house="1"),
             row(1911, "Joe", "Gallagher", 13, rel="Son", marital="Single", house="1"),
             row(1911, "John", "Gallagher", 36, rel="Head", house="7")]
        john = by_names(run(a + b, REAL))[("John", "John")]
        self.assertEqual(john["confidence"], "low")
        self.assertTrue(any(f.startswith("household contradiction:") for f in john["flags"]))
        self.assertIn("continue together in house 1", " ".join(john["flags"]))
        # The same John with nothing contradicting him is not low.
        clean = by_names(run([row(1901, "John", "Gallagher", 25, rel="Head"), row(1911, "John", "Gallagher", 36, house="7", rel="Head")], REAL))
        self.assertNotEqual(clean[("John", "John")]["confidence"], "low")


class HouseholdContinuityTests(unittest.TestCase):
    def test_several_compatible_members_reinforce_one_another(self):
        links = run(gallagher_1901() + gallagher_1911(), REAL)
        for c in links:
            self.assertEqual(c["support"], 2, c["a"]["first"])
            self.assertNotIn("no household continuity", c["flags"])
            self.assertIn("Household: 2 other members continue into the same household", cl.method_text(c))

    def test_the_rationale_keeps_individual_and_household_evidence_apart(self):
        john = by_names(run(gallagher_1901() + gallagher_1911(), REAL))[("John", "John")]
        text = cl.method_text(john)
        individual, household = text.split(" Household: ")
        self.assertTrue(individual.startswith("Individual: given exact; surname exact; age drift 0"))
        self.assertNotIn("continue", individual)
        self.assertIn("Mary Gallagher 24 to 34", household)
        self.assertIn("Joseph Gallagher 3 to 13", household)

    def test_one_sound_link_alone_is_not_household_continuity(self):
        a = [row(1901, "John", "Gallagher", 25, rel="Head"), row(1901, "Mary", "Gallagher", 24, "F", rel="Wife")]
        b = [row(1911, "John", "Gallagher", 35, rel="Head"), row(1911, "Ellen", "Gallagher", 30, "F", rel="Wife")]
        john = run(a + b, REAL)[0]
        self.assertEqual(john["support"], 0)
        self.assertEqual(john["confidence"], "medium")
        self.assertIn("no household continuity", john["flags"])

    def test_weak_links_do_not_reinforce_one_another_or_the_head(self):
        # Minnie to Mary is a name variant and her children count falls: two weak signals, so low, and a low
        # link is never allowed to support anyone. John alone is not household continuity.
        wife_1901 = row(1901, "Minnie", "Gallagher", 24, "F", rel="Wife")
        wife_1901["born"] = 3
        wife_1911 = row(1911, "Mary", "Gallagher", 34, "F", rel="Wife")
        wife_1911["born"] = 1
        links = by_names(run([row(1901, "John", "Gallagher", 25, rel="Head"), wife_1901,
                              row(1911, "John", "Gallagher", 35, rel="Head"), wife_1911], REAL))
        minnie, john = links[("Minnie", "Mary")], links[("John", "John")]
        self.assertEqual(minnie["confidence"], "low")
        self.assertIn("children count fell", minnie["flags"])
        self.assertEqual(minnie["support"], 0)
        self.assertEqual(john["support"], 0)
        self.assertEqual(john["confidence"], "medium")
        self.assertIn("no household continuity", john["flags"])

    def test_one_later_person_cannot_corroborate_two_earlier_ones(self):
        # Two daughters called Mary in 1901 but one Mary in 1911. Both Mary links are ambiguous with each
        # other, and together they give John one supporter, not two.
        a = [row(1901, "John", "Gallagher", 40, rel="Head"),
             row(1901, "Mary", "Gallagher", 14, "F", rel="Daughter", marital="Single"),
             row(1901, "Mary", "Gallagher", 15, "F", rel="Daughter", marital="Single")]
        b = [row(1911, "John", "Gallagher", 50, rel="Head"),
             row(1911, "Mary", "Gallagher", 24, "F", rel="Daughter", marital="Single")]
        links = run(a + b, REAL)
        marys = [c for c in links if c["a"]["first"] == "Mary"]
        self.assertEqual(len(marys), 2)
        for c in marys:
            self.assertIn("ambiguous", c["flags"])
            self.assertEqual(c["confidence"], "low")
        john = next(c for c in links if c["a"]["first"] == "John")
        self.assertEqual(john["support"], 1)

    def test_household_evidence_separates_cousins_with_the_same_names(self):
        # Two Hugh Gallaghers aged 16 in 1926 would be ambiguous on name and age alone. His brother Owen and
        # his mother continue into one of those households, so the household separates them.
        a = [row(1911, "Hugh", "Gallagher", 1, rel="Son", marital="Single", house="1"),
             row(1911, "Owen", "Gallagher", 3, rel="Son", marital="Single", house="1"),
             row(1911, "Mary", "Gallagher", 40, "F", rel="Wife", house="1")]
        b = [row(1926, "Hugh", "Gallagher", 16, rel="Son", marital="Single", house="5"),
             row(1926, "Owen", "Gallagher", 18, rel="Son", marital="Single", house="5"),
             row(1926, "Mary", "Gallagher", 55, "F", rel="Wife", house="5"),
             row(1926, "Hugh", "Gallagher", 16, rel="Son", marital="Single", house="9")]
        hughs = [c for c in run(a + b, REAL) if c["a"]["first"] == "Hugh"]
        self.assertEqual(len(hughs), 1)                       # the cousin in house 9 is clearly beaten and not proposed
        self.assertEqual(hughs[0]["b"]["house"], "5")
        self.assertEqual(hughs[0]["support"], 2)
        self.assertNotIn("ambiguous", hughs[0]["flags"])

    def test_a_link_with_a_contradiction_never_gives_support_and_stays_low(self):
        # John is head in 1901 and a single son in 1911 (unlikely). Mary and Joe are sound and agree, so the
        # household continues and John's link receives its support, but it is flagged and low, and gives none.
        a = gallagher_1901()
        b = [row(1911, "John", "Gallagher", 35, rel="Son", marital="Single"),
             row(1911, "Mary", "Gallagher", 34, "F", rel="Wife"),
             row(1911, "Joe", "Gallagher", 13, rel="Son", marital="Single")]
        links = by_names(run(a + b, REAL))
        john = links[("John", "John")]
        self.assertEqual(john["confidence"], "low")
        self.assertIn("relationship unlikely", john["flags"])
        self.assertEqual(john["support"], 2)
        self.assertEqual(links[("Mary", "Mary")]["support"], 1)       # only Joe supports Mary: John's link never does
        self.assertEqual(links[("Joseph", "Joe")]["support"], 1)

    def test_a_real_household_merge_is_proposed_for_review_not_dropped(self):
        # A head in 1911 appears as a son in 1926, in his father's household, with his wife. Another John of the
        # same age who was a son in 1911 fits the individual evidence better, but the household keeps the
        # head's link in the proposals, so a reviewer sees both.
        a = [row(1911, "John", "McCadden", 30, rel="Head", house="13"),
             row(1911, "Mary", "McCadden", 28, "F", rel="Wife", house="13"),
             row(1911, "Hugh", "McCadden", 4, rel="Son", marital="Single", house="13"),
             row(1911, "John", "McCadden", 30, rel="Son", house="9")]
        b = [row(1926, "Patrick", "McCadden", 70, rel="Head", house="5"),
             row(1926, "John", "McCadden", 44, rel="Son", house="5"),
             row(1926, "Mary", "McCadden", 43, "F", rel="Daughter in Law", house="5"),
             row(1926, "Hugh", "McCadden", 19, rel="Grandson", marital="Single", house="5")]
        johns = [c for c in run(a + b, REAL) if c["a"]["first"] == "John" and c["b"]["first"] == "John"]
        self.assertEqual(len(johns), 2)
        head = next(c for c in johns if c["a"]["rel"] == "Head")
        self.assertEqual(head["confidence"], "low")
        self.assertIn("relationship unlikely", head["flags"])

    def test_household_changes_do_not_invalidate_a_credible_household(self):
        a = gallagher_1901() + [row(1901, "Anne", "Gallagher", 15, "F", rel="Sister", marital="Single")]   # leaves
        b = gallagher_1911() + [row(1911, "Peter", "Gallagher", 5, rel="Son", marital="Single"),          # born since
                                row(1911, "Ellen", "Boyle", 17, "F", rel="Servant", marital="Single")]    # arrived
        links = by_names(run(a + b, REAL))
        self.assertEqual(set(links), {("John", "John"), ("Mary", "Mary"), ("Joseph", "Joe")})
        self.assertEqual(links[("John", "John")]["confidence"], "high")
        self.assertEqual(links[("Mary", "Mary")]["confidence"], "high")
        self.assertEqual(links[("John", "John")]["conflicts"], [])

    def test_a_death_between_returns_does_not_invalidate_the_rest(self):
        a = gallagher_1901() + [row(1901, "Hugh", "Gallagher", 70, rel="Father", marital="Widow")]
        links = by_names(run(a + gallagher_1911(), REAL))
        self.assertEqual(links[("John", "John")]["confidence"], "high")
        self.assertNotIn(("Hugh", "Hugh"), links)

    def test_contradictory_relationships_count_against_the_other_members(self):
        # Mary and Joe continue into house 2, so that household is credible, but John is head in 1901 and
        # a single son in 1911, which does not fit.
        a = gallagher_1901()
        b = [row(1911, "John", "Gallagher", 35, rel="Son", marital="Single", house="2"),
             row(1911, "Mary", "Gallagher", 34, "F", rel="Wife", house="2"),
             row(1911, "Joe", "Gallagher", 13, rel="Son", marital="Single", house="2"),
             row(1911, "Peter", "Gallagher", 60, rel="Head", house="2")]
        links = by_names(run(a + b, REAL))
        john, mary = links[("John", "John")], links[("Mary", "Mary")]
        self.assertEqual(john["confidence"], "low")
        self.assertIn("relationship unlikely", john["flags"])
        self.assertTrue(any("John Gallagher is Head in 1901 but Son in 1911" in f for f in mary["flags"]))
        self.assertNotEqual(mary["confidence"], "high")
        self.assertIn("contradiction: John Gallagher is Head in 1901 but Son in 1911", cl.method_text(mary))

    def test_a_stray_risky_candidate_that_is_not_the_persons_best_link_is_ignored(self):
        # The only reversed candidate for John is not his best: he has a sound link to house 3. It says
        # nothing about the household that Mary and Joe continue into.
        a = gallagher_1901()
        b = [row(1911, "John", "Gallagher", 35, rel="Head", house="3"),
             row(1911, "John", "Gallagher", 35, rel="Son", marital="Single", house="1"),
             row(1911, "Mary", "Gallagher", 34, "F", rel="Wife", house="1"),
             row(1911, "Joe", "Gallagher", 13, rel="Son", marital="Single", house="1")]
        mary = by_names(run(a + b, REAL))[("Mary", "Mary")]
        self.assertEqual(mary["conflicts"], [])

    def test_result_does_not_depend_on_row_order(self):
        rows = gallagher_1901() + gallagher_1911()
        key = lambda links: sorted((c["a"]["first"], c["confidence"], c["support"], tuple(c["flags"])) for c in links)  # noqa: E731
        self.assertEqual(key(run(rows, REAL)), key(run(list(reversed(rows)), REAL)))


class TownlandIdentityTests(unittest.TestCase):
    def test_keadew_lower_and_upper_stay_distinct(self):
        self.assertNotEqual(cl.townland_key("Keadew Lower"), cl.townland_key("Keadew Upper"))
        self.assertNotEqual(cl.townland_key("Keadew"), cl.townland_key("Keadew Upper"))

    def test_the_verified_spelling_keadue_is_the_same_place_with_the_same_suffix(self):
        self.assertEqual(cl.townland_key("Keadew Upper"), cl.townland_key("Keadue Upper"))
        self.assertEqual(cl.townland_key("Keadew Lower"), cl.townland_key("KEADUE LOWER"))
        self.assertNotEqual(cl.townland_key("Keadew Lower"), cl.townland_key("Keadue Upper"))
        self.assertNotEqual(cl.townland_key("Keadue Lower"), cl.townland_key("Keadew Upper"))

    def test_no_suffix_is_ever_folded_away_or_swapped(self):
        for base in ("Keadew", "Carrick", "Drumroosk"):
            keys = {cl.townland_key("%s %s" % (base, s)) for s in ("Upper", "Lower", "Middle", "East", "West", "North", "South")}
            self.assertEqual(len(keys), 7, base)
            self.assertNotIn(cl.townland_key(base), keys)

    def test_other_verified_spellings_still_group_and_keep_their_suffix(self):
        self.assertEqual(cl.townland_key("Collinboy"), cl.townland_key("Cullionboy"))
        self.assertEqual(cl.townland_key("Spearstown East"), cl.townland_key("Spierstown East"))
        self.assertNotEqual(cl.townland_key("Spearstown East"), cl.townland_key("Spierstown West"))

    def write(self, directory, rows):
        with open(Path(directory) / "1901_Test.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=H1, lineterminator="\n")
            w.writeheader()
            for i, (town, clean) in enumerate(rows):
                w.writerow({"census_year": 1901, "ded": "Test", "townland": town, "townland_clean": clean, "firstname": "John",
                            "surname": "Gallagher", "age": 30, "sex": "Male", "house_number": str(i + 1), "relation_to_head": "Head",
                            "relation_to_head_updated": "Head", "marriage_status": "Married", "marriage_years": "",
                            "children_born": "", "id": str(900 + i), "images": "[]", "occupation": "", "occupation_updated": "",
                            "birthplace": "Co Donegal"})

    def test_load_census_uses_the_original_townland_never_townland_clean(self):
        with tempfile.TemporaryDirectory() as d:
            # A curated townland_clean that folds Keadew Lower into Keadew Upper, as the old local files did.
            self.write(d, [("Keadew Lower", "Keadew Upper"), ("Keadew Upper", "Keadew Upper")])
            rows = cl.load_census(Path(d))
        self.assertEqual([r["townland"] for r in rows], ["Keadew Lower", "Keadew Upper"])
        self.assertNotEqual(rows[0]["tkey"], rows[1]["tkey"])
        self.assertNotEqual(rows[0]["hh"], rows[1]["hh"])

    def test_matching_treats_a_move_from_lower_to_upper_as_a_move(self):
        a = [row(1901, "John", "Gallagher", 25, rel="Head", town="Keadew Lower")]
        same = run(a + [row(1911, "John", "Gallagher", 35, rel="Head", town="Keadew Lower")], REAL)[0]
        moved = run(a + [row(1911, "John", "Gallagher", 35, rel="Head", town="Keadew Upper")], REAL)[0]
        self.assertTrue(same["same_townland"])
        self.assertFalse(moved["same_townland"])
        self.assertIn("moved townland", moved["flags"])
        self.assertNotIn("moved townland", same["flags"])

    def test_the_1926_spelling_matches_the_1901_spelling_only_for_the_same_suffix(self):
        a = [row(1901, "John", "Gallagher", 25, rel="Head", town="Keadew Upper")]
        self.assertTrue(run(a + [row(1911, "John", "Gallagher", 35, rel="Head", town="Keadue Upper")], REAL)[0]["same_townland"])
        self.assertFalse(run(a + [row(1911, "John", "Gallagher", 35, rel="Head", town="Keadue Lower")], REAL)[0]["same_townland"])

    def test_proposals_for_one_townland_do_not_leak_into_its_sister(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, [("Keadew Lower", ""), ("Keadew Upper", "")])
            out = Path(d) / "out"
            cl.run_propose(Path(d), out, CFG, townland="Keadew Lower", names=REAL, decisions=None)
            self.assertEqual(list(out.glob("*_links.csv"))[0].read_text(encoding="utf-8").count("Keadew Upper"), 0)


if __name__ == "__main__":
    unittest.main()
