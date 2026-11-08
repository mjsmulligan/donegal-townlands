"""Tests for tools/census_links.py (WP18). Run from the repo root:

    python -m pytest -q tools/test_census_links.py

All rows are invented. The real census files are never read.
"""

import sys
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


class GivenNameTests(unittest.TestCase):
    def test_reference_checks_clean(self):
        import given_names_reference as g
        self.assertEqual(g.check(), [])


if __name__ == "__main__":
    unittest.main()
