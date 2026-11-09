"""Tests for tools/census_gedcom.py (WP20). All rows are invented except the smoke test, which reads
the census files held in the repository."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import census_gedcom as cg  # noqa: E402
import census_links as cl  # noqa: E402
import gedcom_census  # noqa: E402

NAMES = cl.Names()
_n = [0]


def row(year, first, surname, age, sex="M", rel="Head", town="Alpha", house="1", marr=None, born=None, ded="Test"):
    _n[0] += 1
    r = {"year": year, "ded": ded, "townland": town, "first": first, "surname": surname, "age": age, "sex": sex,
         "house": house, "form": "", "rel": rel, "relc": cl.rel_class(rel), "marital": "", "marital_raw": "",
         "marr_years": marr, "born": born, "occ": "", "birth": "", "loc": "%06d" % _n[0], "ref": "", "url": ""}
    r["obs"] = "census%d:test:%d" % (year, _n[0])
    r["tkey"] = gedcom_census.place_key(town)
    r["hh"] = (year, r["tkey"], house)
    return r


def build(rows, pairs=(), anchors=None, kind="townland", value="Alpha", **kw):
    return cg.build_gedcom(rows, list(pairs), anchors or {}, kind, value, NAMES, **kw)


def indis(text):
    return [n for n in gedcom_census.parse_gedcom(text) if n.tag == "INDI"]


class ChainTests(unittest.TestCase):
    def test_accepted_link_makes_one_person_with_two_events_and_both_spellings(self):
        a, b = row(1901, "Ellen", "Doherty", 12, "F", "Daughter"), row(1911, "Nellie", "Dohertie", 22, "F", "Daughter")
        text, report, counts = build([a, b], [(a["obs"], b["obs"])])
        self.assertEqual(len(indis(text)), 1)
        self.assertEqual(text.count("\n1 CENS\n"), 2)
        self.assertIn("1 NAME Ellen /Doherty/", text)
        self.assertIn("1 NAME Nellie /Dohertie/\n2 TYPE aka", text)
        self.assertIn("2 DATE ABT 1889", text)   # earliest return: 1901 minus 12
        self.assertIn("Not a recorded date", text)

    def test_unlinked_rows_stay_separate_people(self):
        a, b = row(1901, "Ellen", "Doherty", 12, "F", "Daughter"), row(1911, "Ellen", "Doherty", 22, "F", "Daughter")
        text, _, counts = build([a, b])
        self.assertEqual(len(indis(text)), 2)

    def test_tree_anchor_joins_rows_and_is_recorded(self):
        a, b = row(1901, "Joe", "Kelly", 30), row(1911, "Joe", "Kelly", 40)
        text, _, _ = build([a, b], anchors={a["obs"]: "I1", b["obs"]: "I1"})
        self.assertEqual(len(indis(text)), 1)
        self.assertIn("1 REFN I1", text)

    def test_accepted_link_between_two_different_tree_people_is_refused_and_reported(self):
        a, b = row(1901, "Joe", "Kelly", 30), row(1911, "Joe", "Kelly", 40)
        text, report, _ = build([a, b], [(a["obs"], b["obs"])], anchors={a["obs"]: "I1", b["obs"]: "I2"})
        self.assertEqual(len(indis(text)), 2)
        self.assertTrue(any("different people" in r for r in report))

    def test_link_that_would_put_two_rows_of_one_return_in_a_person_is_refused(self):
        a = row(1901, "Joe", "Kelly", 30)
        b1, b2 = row(1911, "Joe", "Kelly", 40, house="1"), row(1911, "Joe", "Kelly", 40, house="2")
        text, report, _ = build([a, b1, b2], [(a["obs"], b1["obs"]), (a["obs"], b2["obs"])])
        self.assertEqual(len(indis(text)), 2)
        self.assertTrue(any("already have a row" in r or "both already" in r for r in report))


class CarriedYearsTests(unittest.TestCase):
    """The 1901 and 1926 returns do not state years married, so a wife's figure from 1911 is carried along her chain."""

    def setUp(self):
        self.h01 = row(1901, "Pat", "McCadden", 46, house="14")
        self.w01 = row(1901, "Bridget", "McCadden", 45, "F", "Wife", house="14")
        self.k01 = row(1901, "John", "McCadden", 18, "M", "Son", house="14")
        self.h11 = row(1911, "Pat", "McCadden", 59, house="12")
        self.w11 = row(1911, "Bridget", "McCadden", 60, "F", "Wife", house="12", marr=32, born=6)
        self.rows = [self.h01, self.w01, self.k01, self.h11, self.w11]
        self.pairs = [(self.h01["obs"], self.h11["obs"]), (self.w01["obs"], self.w11["obs"])]

    def fams(self, text):
        return [n for n in gedcom_census.parse_gedcom(text) if n.tag == "FAM"]

    def test_child_in_1901_joins_the_wife_through_her_1911_years_married(self):
        text, report, _ = build(self.rows, self.pairs)
        fams = self.fams(text)
        self.assertEqual(len(fams), 1)
        self.assertEqual(sum(1 for f in text.split("\n") if f.startswith("1 WIFE")), 1)
        self.assertEqual(text.count("1 CHIL"), 1)
        self.assertTrue(any("years married for the wife taken from her 1911 return" in r for r in report))

    def test_without_the_link_there_is_no_carried_figure_and_the_child_stays_with_the_head(self):
        text, _, _ = build(self.rows)
        self.assertNotIn("years married for the wife taken from", " ".join(build(self.rows)[1]))
        self.assertGreaterEqual(len(self.fams(text)), 2)

    def test_child_born_before_the_marriage_stays_with_the_head_only(self):
        old = row(1901, "Mick", "McCadden", 30, "M", "Son", house="14")   # 30 is older than 22 years married
        self.rows.append(old)
        text, _, _ = build(self.rows, self.pairs)
        wife_fams = [f for f in text.split("\n0 ") if " FAM" in f.split("\n")[0] and "1 WIFE" in f]
        self.assertEqual(len(wife_fams), 1)
        self.assertEqual(wife_fams[0].count("1 CHIL"), 1)    # John only, not Mick
        self.assertGreaterEqual(len(self.fams(text)), 2)     # Mick has a head-only family

    def test_born_alive_from_a_later_return_caps_the_children_attached(self):
        for i in range(7):
            self.rows.append(row(1901, "Kid%d" % i, "McCadden", 5, "M", "Son", house="14"))
        text, report, _ = build(self.rows, self.pairs)
        self.assertTrue(any("born alive" in r for r in report))


class HouseholdShapeTests(unittest.TestCase):
    def fams(self, text):
        return [n for n in gedcom_census.parse_gedcom(text) if n.tag == "FAM"]

    def test_wife_row_is_not_paired_with_a_widowed_head(self):
        head = row(1911, "Hugh", "White", 85)
        head["marital_raw"] = "Widower"
        son = row(1911, "William", "White", 38, "M", "Son")
        wife = row(1911, "Rebeca", "White", 36, "F", "Wife", marr=12, born=7)
        text, report, _ = build([head, son, wife])
        self.assertFalse(any("1 WIFE" in l for l in text.split("\n")))
        self.assertTrue(any(r.startswith("household:") and "widower" in r.lower() for r in report))

    def test_two_heads_pair_with_the_wife_of_the_opposite_sex_and_give_no_children_to_anyone(self):
        anne = row(1911, "Anne", "McCadden", 80, "F", "Head of Family")
        anne["marital_raw"] = "Widow"
        adam = row(1911, "Adam", "McClay", 66, "M", "Head of Family")
        adam["marital_raw"] = "Married"
        euphema = row(1911, "Euphema", "McClay", 44, "F", "Wife", marr=10, born=2)
        edith = row(1911, "Edith", "McClay", 9, "F", "Daughter")
        text, report, _ = build([anne, adam, euphema, edith])
        self.assertNotIn("1 CHIL", text)
        self.assertEqual(len(self.fams(text)), 1)
        fam = [b for b in text.split("\n0 ") if " FAM" in b.split("\n")[0]][0]
        self.assertIn("1 HUSB", fam)
        self.assertIn("1 WIFE", fam)
        self.assertTrue(any(r.startswith("household:") and "2 heads" in r for r in report))

    def test_a_normal_head_and_wife_are_unaffected(self):
        head = row(1911, "Tom", "Kelly", 50)
        head["marital_raw"] = "Married"
        wife = row(1911, "Mary", "Kelly", 45, "F", "Wife", marr=20, born=3)
        kid = row(1911, "Joe", "Kelly", 10, "M", "Son")
        text, report, _ = build([head, wife, kid])
        self.assertIn("1 WIFE", text)
        self.assertEqual(text.count("1 CHIL"), 1)
        self.assertFalse(any(r.startswith("household:") for r in report))


class ConflictTests(unittest.TestCase):
    def test_a_mother_too_old_for_her_child_is_listed_and_the_family_is_kept(self):
        head = row(1911, "John", "McCadden", 55)
        wife = row(1911, "Catherine", "McCadden", 58, "F", "Wife", marr=20, born=10)
        kid = row(1911, "Anthony", "McCadden", 1, "M", "Son")
        text, report, _ = build([head, wife, kid])
        self.assertEqual(text.count("1 CHIL"), 1)
        self.assertTrue(any(r.startswith("conflict:") and "mother" in r for r in report))

    def test_two_wives_with_one_first_name_are_listed_not_merged(self):
        h1, w1 = row(1901, "Patrick", "Hone", 60), row(1901, "Maggie", "Hone", 40, "F", "Wife")
        h2, w2 = row(1911, "Patrick", "Hone", 69), row(1911, "Maggie", "Hone", 64, "F", "Wife")
        text, report, _ = build([h1, w1, h2, w2], [(h1["obs"], h2["obs"])])
        self.assertEqual(len(indis(text)), 3)
        self.assertTrue(any(r.startswith("conflict:") and "2 wives with the same first name" in r for r in report))


class TentativeTests(unittest.TestCase):
    def link(self, a, b, conf="high", flags=()):
        return {"fo": a["obs"], "to": b["obs"], "confidence": conf, "flags": list(flags)}

    def test_tentative_link_joins_rows_and_is_labelled_in_header_person_and_report(self):
        a, b = row(1901, "Ellen", "Doherty", 12, "F", "Daughter"), row(1911, "Ellen", "Doherty", 22, "F", "Daughter")
        text, report, counts = build([a, b], tentative=[self.link(a, b, "medium", ["age drift 4"])])
        self.assertEqual(len(indis(text)), 1)
        self.assertIn("TENTATIVE LINKS: this file also joins", text)
        self.assertIn("TENTATIVE LINK, not accepted by the researcher", text)
        self.assertIn("Matcher confidence medium; age drift 4", text)
        self.assertEqual(counts["tentative links used"], 1)
        self.assertEqual(counts["tentative medium"], 1)
        self.assertTrue(any(r.startswith("tentative link, matcher confidence medium") for r in report))

    def test_no_tentative_links_means_no_tentative_wording(self):
        a, b = row(1901, "Ellen", "Doherty", 12, "F", "Daughter"), row(1911, "Ellen", "Doherty", 22, "F", "Daughter")
        text, _, counts = build([a, b], [(a["obs"], b["obs"])])
        self.assertNotIn("TENTATIVE", text)
        self.assertNotIn("tentative links used", counts)

    def test_link_already_implied_by_the_tree_is_not_labelled_tentative(self):
        a, b = row(1901, "Joe", "Kelly", 30), row(1911, "Joe", "Kelly", 40)
        text, report, counts = build([a, b], anchors={a["obs"]: "I1", b["obs"]: "I1"}, tentative=[self.link(a, b)])
        self.assertEqual(counts["tentative links used"], 0)
        self.assertNotIn("TENTATIVE LINK, not accepted", text)

    def test_tree_anchor_beats_a_tentative_link(self):
        a, b = row(1901, "Joe", "Kelly", 30), row(1911, "Joe", "Kelly", 40)
        text, report, counts = build([a, b], anchors={a["obs"]: "I1", b["obs"]: "I2"}, tentative=[self.link(a, b)])
        self.assertEqual(len(indis(text)), 2)
        self.assertEqual(counts["tentative links used"], 0)
        self.assertTrue(any("different people" in r for r in report))

    def test_accepted_link_beats_a_competing_tentative_link(self):
        a = row(1901, "Joe", "Kelly", 30)
        b1, b2 = row(1911, "Joe", "Kelly", 40, house="1"), row(1911, "Joe", "Kelly", 40, house="2")
        text, report, counts = build([a, b1, b2], [(a["obs"], b2["obs"])], tentative=[self.link(a, b1)])
        self.assertEqual(counts["tentative links used"], 0)
        self.assertEqual(len(indis(text)), 2)

    def test_tentative_output_passes_structure_check_and_is_repeatable(self):
        a, b = row(1901, "Ellen", "Doherty", 12, "F", "Daughter"), row(1911, "Ellen", "Doherty", 22, "F", "Daughter")
        t = [self.link(a, b)]
        t1, t2 = build([a, b], tentative=t)[0], build([a, b], tentative=t)[0]
        self.assertEqual(t1, t2)
        self.assertEqual(cg.check_gedcom(t1), [])

    def test_run_names_the_file_tentative_and_leaves_the_decisions_file_alone(self):
        import io
        import tempfile
        if not cl.CENSUS_DIR.is_dir():
            self.skipTest("census files not present")
        before = cl.DECISIONS.read_bytes() if cl.DECISIONS.is_file() else None
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            rc = cg.run("family", "Kelly", cl.CENSUS_DIR, Path(d), cl.DECISIONS, cl.TREE, "evidence", buf, tentative=True)
            self.assertEqual(rc, 0)
            self.assertTrue((Path(d) / "family_kelly_tentative.ged").is_file())
            self.assertTrue((Path(d) / "family_kelly_tentative_report.txt").is_file())
        after = cl.DECISIONS.read_bytes() if cl.DECISIONS.is_file() else None
        self.assertEqual(before, after)


class FamilyTests(unittest.TestCase):
    def household(self, yrs, wife_born=None, child_age=10):
        head = row(1911, "Tom", "Kelly", 50)
        wife = row(1911, "Mary", "Kelly", 45, "F", "Wife", marr=yrs, born=wife_born)
        kid = row(1911, "Joe", "Kelly", child_age, "M", "Son")
        return [head, wife, kid]

    def fam(self, text):
        return [n for n in gedcom_census.parse_gedcom(text) if n.tag == "FAM"]

    def test_head_and_wife_make_a_family_and_child_joins_when_years_married_allow(self):
        text, _, _ = build(self.household(yrs=15, wife_born=1))
        fams = self.fam(text)
        couple = [f for f in fams if any(k.tag == "WIFE" for k in f.kids)]
        self.assertEqual(len(couple), 1)
        self.assertEqual(sum(1 for k in couple[0].kids if k.tag == "CHIL"), 1)

    def test_child_older_than_the_marriage_is_attached_to_the_head_only(self):
        text, _, _ = build(self.household(yrs=5))
        couple = [f for f in self.fam(text) if any(k.tag == "WIFE" for k in f.kids)]
        self.assertEqual(sum(1 for k in couple[0].kids if k.tag == "CHIL"), 0)
        single = [f for f in self.fam(text) if not any(k.tag == "WIFE" for k in f.kids)]
        self.assertEqual(sum(1 for k in single[0].kids if k.tag == "CHIL"), 1)

    def test_no_marriage_data_means_no_attachment_to_the_wife_unless_assumed(self):
        rows = self.household(yrs=None)
        evidence = [f for f in self.fam(build(rows)[0]) if any(k.tag == "WIFE" for k in f.kids)]
        assume = [f for f in self.fam(build(rows, wife_parent="assume")[0]) if any(k.tag == "WIFE" for k in f.kids)]
        self.assertEqual(sum(1 for k in evidence[0].kids if k.tag == "CHIL"), 0)
        self.assertEqual(sum(1 for k in assume[0].kids if k.tag == "CHIL"), 1)

    def test_more_children_than_the_wife_recorded_born_are_not_attached_and_reported(self):
        rows = self.household(yrs=15, wife_born=0)
        text, report, _ = build(rows)
        couple = [f for f in self.fam(text) if any(k.tag == "WIFE" for k in f.kids)]
        self.assertEqual(sum(1 for k in couple[0].kids if k.tag == "CHIL"), 0)
        self.assertTrue(any("born alive" in r for r in report))

    def test_a_married_years_value_that_cannot_be_right_is_ignored(self):
        text, _, _ = build(self.household(yrs=906))
        couple = [f for f in self.fam(text) if any(k.tag == "WIFE" for k in f.kids)]
        self.assertEqual(sum(1 for k in couple[0].kids if k.tag == "CHIL"), 0)

    def test_daughter_in_law_and_servant_get_no_family(self):
        head = row(1911, "Tom", "Kelly", 70)
        dil = row(1911, "Bella", "Kelly", 30, "F", "Daughter in Law")
        sv = row(1911, "Jim", "Roe", 20, "M", "Servant")
        text, _, _ = build([head, dil, sv])
        self.assertEqual([f for f in self.fam(text) if any(k.tag == "WIFE" for k in f.kids)], [])


class ScopeTests(unittest.TestCase):
    def test_townland_scope_takes_whole_households_including_unlinked_people(self):
        head = row(1911, "Tom", "Kelly", 50, town="Alpha")
        servant = row(1911, "Jim", "Roe", 20, "M", "Servant", town="Alpha")
        elsewhere = row(1911, "Pat", "Moore", 40, town="Beta", house="9")
        text, _, _ = build([head, servant, elsewhere], value="Alpha")
        self.assertEqual(len(indis(text)), 2)

    def test_family_scope_matches_the_surname_and_pulls_in_the_household(self):
        head = row(1911, "Tom", "Kelly", 50, town="Alpha")
        servant = row(1911, "Jim", "Roe", 20, "M", "Servant", town="Alpha")
        other = row(1911, "Pat", "Moore", 40, town="Beta", house="9")
        text, _, _ = build([head, servant, other], kind="family", value="Kelly")
        self.assertEqual(len(indis(text)), 2)

    def test_ded_scope_takes_everyone_in_the_ded(self):
        a, b = row(1911, "Tom", "Kelly", 50, ded="One"), row(1911, "Pat", "Moore", 40, ded="Two", house="9")
        text, _, _ = build([a, b], kind="ded", value="One")
        self.assertEqual(len(indis(text)), 1)


class OutputTests(unittest.TestCase):
    def test_two_runs_give_identical_text(self):
        rows = [row(1901, "Tom", "Kelly", 50), row(1901, "Mary", "Kelly", 45, "F", "Wife"), row(1901, "Joe", "Kelly", 10, "M", "Son")]
        self.assertEqual(build(rows)[0], build(list(reversed(rows)))[0])

    def test_output_passes_its_own_structure_check(self):
        rows = [row(1901, "Tom", "Kelly", 50), row(1901, "Mary", "Kelly", 45, "F", "Wife", marr=20), row(1901, "Joe", "Kelly", 10, "M", "Son")]
        self.assertEqual(cg.check_gedcom(build(rows)[0]), [])

    def test_check_catches_a_dangling_pointer(self):
        bad = "0 HEAD\n0 @I1@ INDI\n1 FAMC @F9@\n0 TRLR\n"
        self.assertTrue(cg.check_gedcom(bad))

    def test_no_dates_or_events_beyond_the_returns_are_written(self):
        rows = [row(1911, "Tom", "Kelly", 50), row(1911, "Mary", "Kelly", 45, "F", "Wife", marr=20)]
        text = build(rows)[0]
        for tag in ("\n1 MARR", "\n1 DEAT", "\n1 EMIG", "\n1 BURI"):
            self.assertNotIn(tag, text)

    def test_long_note_lines_are_split(self):
        r = row(1911, "Tom", "Kelly", 50)
        r["occ"] = "x" * 400
        text = build([r])[0]
        self.assertEqual(cg.check_gedcom(text), [])
        self.assertTrue(all(len(l) <= 255 for l in text.split("\n")))


class RealDataSmokeTest(unittest.TestCase):
    def test_cullionboy_builds_and_checks(self):
        if not cl.CENSUS_DIR.is_dir():
            self.skipTest("census files not present")
        rows = cl.load_census(cl.CENSUS_DIR)
        text, report, counts = cg.build_gedcom(rows, [], cg.load_anchors(), "townland", "Cullionboy", NAMES)
        self.assertEqual(cg.check_gedcom(text), [])
        self.assertGreater(counts["people"], 100)
        self.assertEqual([r for r in report if not r.startswith(("household:", "conflict:")) and "years married for the wife taken from" not in r], [])


if __name__ == "__main__":
    unittest.main()
