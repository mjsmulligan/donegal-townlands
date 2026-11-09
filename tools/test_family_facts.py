"""Tests for the family fact sheet and the story check (WP21)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_story as cs  # noqa: E402
import family_facts as ff  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def fact(i, kind, tier, text, **kw):
    f = {"id": "F%03d" % i, "kind": kind, "tier": tier, "usable": tier in ff.USABLE, "text": text}
    f.update(kw)
    return f


def sheet(*facts):
    return {"townland": "x", "family": "Kelly", "tiers": {}, "accepted_census_links": 0,
            "proposed_census_links": 0, "conflicts": [], "facts": list(facts)}


BASE = sheet(
    fact(1, "person", "tree", "Joseph Kelly; born 8 Jun 1875 at Cullionboy; died 27 Dec 1925", who="Joseph Kelly",
         born="8 Jun 1875", died="27 Dec 1925", cleared=True),
    fact(2, "person", "tree", "Isabella McGettigan; born 6 Feb 1879 at Druminnin", who="Isabella McGettigan",
         born="6 Feb 1879", cleared=True),
    fact(3, "marriage", "tree", "Joseph Kelly married Isabella McGettigan on 6 Feb 1910 at Donegal Town",
         who=["Joseph Kelly", "Isabella McGettigan"], date="6 Feb 1910"),
    fact(4, "age", "derived", "Joseph Kelly was 34 at the marriage on 6 Feb 1910", who="Joseph Kelly", age=34, year=1910),
    fact(5, "relation", "tree", "Hugh Kelly is son of Joseph Kelly", relation="son", who="Hugh Kelly", of="Joseph Kelly"),
    fact(6, "census", "census", "Hugh Kelly, 7, in the 1926 return", who="Hugh Kelly", year=1926, age=7),
    fact(7, "link", "proposed", "Proposed, not accepted: Tom Kelly (20, 1901) may be Thomas Kelly (30, 1911)",
         obs=["a", "b"], confidence="medium"),
)


def run(text, s=BASE):
    return cs.check_text(text, s)[0]


def fails(text, s=BASE):
    return [f for f in run(text, s) if f.level == "FAIL"]


class StoryCheckTests(unittest.TestCase):
    def test_true_sentence_passes(self):
        self.assertEqual(fails("Joseph was thirty-four when he married Isabella McGettigan on 6 February 1910."), [])

    def test_invented_date_fails(self):
        r = fails("Joseph married Isabella McGettigan on 7 February 1910.")
        self.assertTrue(any(f.rule == "date" for f in r))

    def test_invented_year_fails(self):
        self.assertTrue(any(f.rule == "year" for f in fails("Joseph was farming in 1931.")))

    def test_decade_needs_a_year_in_it(self):
        self.assertEqual(fails("The family was there in the 1920s."), [])
        self.assertTrue(fails("The family was there in the 1940s."))

    def test_invented_name_and_place_fail(self):
        self.assertTrue(any(f.rule == "name" for f in fails("Joseph went to Glasgow.")))
        self.assertTrue(any(f.rule == "name" for f in fails("Joseph's friend Gerald came.")))

    def test_wrong_age_for_a_person_fails(self):
        r = fails("Joseph was thirty-six when he married Isabella.")
        self.assertTrue(any(f.rule in ("age", "number") for f in r))
        self.assertTrue(any(f.rule == "age" for f in fails("Hugh, nine, was at home.", sheet(
            *BASE["facts"], fact(8, "census", "census", "Dan Kelly, 9", who="Dan Kelly", year=1926, age=9)))))

    def test_age_for_a_person_passes(self):
        self.assertEqual(fails("Hugh, seven, was at home."), [])

    def test_invented_count_fails(self):
        self.assertTrue(any(f.rule == "number" for f in fails("There were eleven children at home.")))

    def test_relationship_must_be_held(self):
        self.assertEqual(fails("Joseph's son Hugh was at home."), [])
        self.assertTrue(any(f.rule == "relationship" for f in fails("Joseph's brother Hugh was at home.")))
        self.assertTrue(any(f.rule == "relationship" for f in fails("Joseph married Margaret McGettigan.")))

    def test_proposed_link_is_not_usable(self):
        # Tom is named only in a proposed link, so the story cannot use him
        self.assertTrue(any(f.rule == "name" for f in run("Tom was twenty in 1901.")))
        self.assertTrue(any(f.rule == "name" and f.level == "FAIL" for f in fails("The house had Tom in 1901.")))

    def test_unknown_word_at_sentence_start_warns(self):
        r = run("Gerald was at home.")
        self.assertTrue(any(f.rule == "name" and f.level == "WARN" for f in r))
        self.assertEqual([f for f in r if f.level == "FAIL"], [])

    def test_uncleared_person_is_flagged(self):
        s = sheet(*BASE["facts"], fact(9, "person", "tree", "Mary Kelly; born 1990", who="Mary Kelly", cleared=False))
        self.assertTrue(any(f.rule == "privacy" for f in fails("Mary Kelly was at home.", s)))

    def test_cause_of_death_words_must_be_held(self):
        s = sheet(*BASE["facts"], fact(9, "note", "tree", "Died of Pulmonary Tuberculosis", who="Joseph Kelly"))
        self.assertEqual(fails("Joseph died of tuberculosis on 27 December 1925.", s), [])
        self.assertTrue(any(f.rule == "cause" for f in fails("Joseph died of pneumonia on 27 December 1925.", s)))

    def test_plural_surname_is_not_a_new_name(self):
        self.assertEqual(fails("The Kellys were at home."), [])


class FactSheetTests(unittest.TestCase):
    def test_parse_date_and_age(self):
        self.assertEqual(ff.parse_date("6 Feb 1879"), (6, 2, 1879, True))
        self.assertEqual(ff.parse_date("about 1840"), (None, None, 1840, False))
        self.assertEqual(ff.age_between(ff.parse_date("6 Feb 1879"), ff.parse_date("6 Feb 1910")), (31, True))
        self.assertEqual(ff.age_between(ff.parse_date("6 Feb 1879"), ff.parse_date("5 Feb 1910")), (30, True))

    def test_cleared_rule(self):
        p = {"name": "A", "birth": {"date": "1 Jan 1950"}, "death": {}}
        self.assertFalse(ff.cleared(p, 2026, {})[0])
        self.assertTrue(ff.cleared(p, 2026, {"A": "allow"})[0])
        self.assertTrue(ff.cleared({"name": "B", "birth": {"date": "1 Jan 1900"}}, 2026, {})[0])

    @unittest.skipUnless((ROOT / "townlands" / "cullionboy" / "records" / "people.json").is_file(), "no case data")
    def test_kelly_sheet_and_story(self):
        sh = ff.build("cullionboy", "Kelly", with_proposals=False)
        self.assertEqual(sh["tiers"].get("proposed", 0), 0)
        self.assertTrue(any("Joseph" in c and "47" in c for c in sh["conflicts"]))
        text = cs.story_text(ROOT / "townlands" / "cullionboy", "Kelly")
        found, _ = cs.check_text(text, sh)
        self.assertEqual([str(f) for f in found if f.level == "FAIL"], [])
        # and a changed date in the real story fails
        bad = text.replace("6 February 1910", "7 February 1910")
        self.assertTrue(any(f.rule == "date" for f in cs.check_text(bad, sh)[0]))

    @unittest.skipUnless((ROOT / "townlands" / "cullionboy" / "records" / "people.json").is_file(), "no case data")
    def test_two_runs_are_identical(self):
        a = ff.build("cullionboy", "Kelly", with_proposals=False)
        b = ff.build("cullionboy", "Kelly", with_proposals=False)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
