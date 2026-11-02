"""Tests for tools/attach_census.py. Run from the repo root:

    python -m unittest tools.test_attach_census -v

Every test works in a temporary directory. The real repository is never touched.
"""

import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import attach_census as ac

PLACE_FIELDS = ["logainm_id", "name_en", "place_type", "ded_id"]


def place(i, name, kind="townland", ded="900"):
    return {"logainm_id": i, "name_en": name, "place_type": kind,
            "ded_id": ded if kind == "townland" else ""}


C_FIELDS = ["townland", "surname", "firstname", "house_number", "age", "sex",
            "relation_to_head_updated", "marriage_status", "occupation_updated",
            "language_updated", "images"]
C26_FIELDS = ["aform_name", "townland", "surname", "first_name", "updated_age",
              "updated_sex", "updated_relationship_to_head", "updated_marriage",
              "updated_irish_language"]


class AttachCensusTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.saved = (ac.ROOT, ac.PLACES_CSV, ac.CASES_CSV, ac.REVIEW_CSV, ac.CENSUS_DIR)
        ac.ROOT = self.root
        ac.PLACES_CSV = self.root / "places.csv"
        ac.CASES_CSV = self.root / "cases.csv"
        ac.REVIEW_CSV = self.root / "review.csv"
        ac.CENSUS_DIR = self.root / "census"
        ac.CENSUS_DIR.mkdir()
        self.addCleanup(self.restore)
        self.places([place("1", "Alpha"), place("2", "Beta"), place("900", "Clogher", "ded"),
                     place("3", "Other", ded="901")])
        for y in (1901, 1911):
            self.census(y, [])
        self.census(1926, [])

    def restore(self):
        (ac.ROOT, ac.PLACES_CSV, ac.CASES_CSV, ac.REVIEW_CSV, ac.CENSUS_DIR) = self.saved

    def places(self, rows):
        with ac.PLACES_CSV.open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=PLACE_FIELDS)
            w.writeheader()
            w.writerows(rows)
        with ac.CASES_CSV.open("w", encoding="utf-8", newline="") as h:
            w = csv.writer(h)
            w.writerow(["logainm_id", "case_path"])
            for r in rows:
                if r["place_type"] == "townland":
                    w.writerow([r["logainm_id"], "townlands/" + r["name_en"].lower()])
                    (self.root / "townlands" / r["name_en"].lower()).mkdir(parents=True, exist_ok=True)

    def census(self, year, rows):
        fields = C26_FIELDS if year == 1926 else C_FIELDS
        with (ac.CENSUS_DIR / f"{year}_Clogher.csv").open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    def p(self, townland, sur="Smith", age="40", year=1901):
        if year == 1926:
            return {"aform_name": f"{townland}_0001_0002_0003_0_00004.pdf", "townland": townland,
                    "surname": sur, "first_name": "Ann", "updated_age": age,
                    "updated_sex": "F", "updated_relationship_to_head": "Head"}
        return {"townland": townland, "surname": sur, "firstname": "Ann", "house_number": "1.0",
                "age": age, "sex": "F", "relation_to_head_updated": "Head",
                "images": "[{'id': 'nai000111', 'url': 'x'}]"}

    def run_attach(self):
        with contextlib.redirect_stdout(io.StringIO()):
            ac.main()

    def case_file(self, case, name):
        return self.root / "townlands" / case / "records" / name

    def review(self):
        with ac.REVIEW_CSV.open(encoding="utf-8", newline="") as h:
            return list(csv.DictReader(h))

    def test_exact_name_attaches_as_proposed_with_reference(self):
        self.census(1901, [self.p("Alpha"), self.p("alpha", "Jones")])
        self.run_attach()
        data = json.loads(self.case_file("alpha", "census.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["1901"]), 2)
        self.assertEqual(data["1901"][0]["ref"], "nai000111")
        match = json.loads(self.case_file("alpha", "census_match.json").read_text(encoding="utf-8"))
        self.assertEqual(match["status"], "proposed")
        self.assertEqual(match["years"]["1901"]["spellings"][0]["method"], "exact_name")

    def test_variant_spelling_is_not_attached_but_listed_for_review(self):
        self.census(1926, [self.p("Alpa", year=1926)])
        self.run_attach()
        self.assertFalse(self.case_file("alpha", "census.json").exists())
        rows = self.review()
        self.assertEqual([(r["census_spelling"], r["status"]) for r in rows], [("Alpa", "unreviewed")])
        self.assertIn("Alpha", rows[0]["similar_places_not_confirmed"])

    def test_places_in_other_deds_get_nothing(self):
        self.census(1901, [self.p("Other")])
        self.run_attach()
        self.assertFalse(self.case_file("other", "census.json").exists())

    def test_authored_census_is_never_touched(self):
        path = self.case_file("alpha", "census.json")
        path.parent.mkdir(parents=True)
        path.write_text('{"1901":["authored"]}', encoding="utf-8")
        self.census(1901, [self.p("Alpha")])
        self.run_attach()
        self.assertEqual(path.read_text(encoding="utf-8"), '{"1901":["authored"]}')
        self.assertFalse(self.case_file("alpha", "census_match.json").exists())

    def test_spelling_accepted_in_an_existing_case_is_not_listed_as_unreviewed(self):
        (self.root / "townlands" / "beta" / "townland.json").write_text(
            json.dumps({"census_spelling": {"1926": "Betta"}}), encoding="utf-8")
        self.census(1926, [self.p("Betta", year=1926)])
        self.run_attach()
        self.assertEqual(self.review()[0]["status"], "accepted_in_case")

    def test_second_run_changes_nothing(self):
        self.census(1901, [self.p("Alpha")])
        self.census(1926, [self.p("Alfa", year=1926)])
        self.run_attach()
        first = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.run_attach()
        second = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(first, second)

    def test_review_decision_is_applied_and_preserved(self):
        self.census(1926, [self.p("Alfa", year=1926)])
        self.run_attach()
        rows = self.review()
        rows[0]["status"], rows[0]["accepted_logainm_id"] = "accepted", "1"
        with ac.REVIEW_CSV.open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=ac.REVIEW_FIELDS)
            w.writeheader()
            w.writerows(rows)
        self.run_attach()
        match = json.loads(self.case_file("alpha", "census_match.json").read_text(encoding="utf-8"))
        self.assertEqual(match["years"]["1926"]["spellings"][0]["method"], "reviewed_variant")
        self.assertEqual(match["status"], "reviewed")
        again = self.review()[0]
        self.assertEqual((again["status"], again["accepted_logainm_id"]), ("accepted", "1"))

    def test_reviewer_note_survives_a_rerun(self):
        self.census(1926, [self.p("Alfa", year=1926)])
        self.run_attach()
        rows = self.review()
        rows[0].update(status="accepted", accepted_logainm_id="1", reviewer_note="checked by elimination")
        with ac.REVIEW_CSV.open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=ac.REVIEW_FIELDS)
            w.writeheader()
            w.writerows(rows)
        self.run_attach()
        self.run_attach()
        self.assertEqual(self.review()[0]["reviewer_note"], "checked by elimination")

    def test_mixed_exact_and_reviewed_matches_are_labelled_honestly(self):
        self.census(1901, [self.p("Alpha")])
        self.census(1926, [self.p("Alfa", year=1926)])
        self.run_attach()
        rows = self.review()
        rows[0].update(status="accepted", accepted_logainm_id="1")
        with ac.REVIEW_CSV.open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=ac.REVIEW_FIELDS)
            w.writeheader()
            w.writerows(rows)
        self.run_attach()
        match = json.loads(self.case_file("alpha", "census_match.json").read_text(encoding="utf-8"))
        self.assertEqual(match["status"], "proposed")
        self.assertIn("accepted on review", match["note"])

    def test_rejected_decision_is_preserved_and_attaches_nothing(self):
        self.census(1926, [self.p("Alfa", year=1926)])
        self.run_attach()
        rows = self.review()
        rows[0]["status"] = "rejected"
        with ac.REVIEW_CSV.open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=ac.REVIEW_FIELDS)
            w.writeheader()
            w.writerows(rows)
        self.run_attach()
        self.assertEqual(self.review()[0]["status"], "rejected")
        self.assertFalse(self.case_file("alpha", "census.json").exists())

    def test_published_census_rows_are_all_kept_including_missing_ages(self):
        self.census(1926, [self.p("Alpha", age="0", year=1926),
                           self.p("Alpha", sur="Unknown", age="", year=1926)])
        self.run_attach()
        data = json.loads(self.case_file("alpha", "census.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["1926"]), 2)
        match = json.loads(self.case_file("alpha", "census_match.json").read_text(encoding="utf-8"))
        self.assertEqual(match["years"]["1926"]["people"], 2)
        self.assertNotIn("withheld", match["years"]["1926"])

    def form(self, row, number):
        row["aform_name"] = f"Alpha_0001_0002_{number}_0_00004.pdf"
        return row

    def test_1926_rows_carry_form_numbers_and_are_sorted_by_form(self):
        self.census(1926, [self.form(self.p("Alpha", sur="Late", year=1926), "0009"),
                           self.form(self.p("Alpha", sur="Early", year=1926), "0002")])
        self.run_attach()
        rows = json.loads(self.case_file("alpha", "census.json").read_text(encoding="utf-8"))["1926"]
        self.assertEqual([(r["s"], r["fo"], r["h"]) for r in rows], [("Early", "0002", "0002"), ("Late", "0009", "0009")])

    def test_researcher_corrections_are_applied_and_recorded(self):
        self.census(1926, [self.form(self.p("Alpha", sur="Bradley", year=1926), "0016")])
        self.case_file("alpha", "corrections.json").parent.mkdir(parents=True, exist_ok=True)
        self.case_file("alpha", "corrections.json").write_text(json.dumps(
            {"1926": [{"match": {"fo": "0016"}, "set": {"h": "0017"}, "reason": "Named as a child in form 0017"}]}),
            encoding="utf-8")
        self.run_attach()
        rows = json.loads(self.case_file("alpha", "census.json").read_text(encoding="utf-8"))["1926"]
        self.assertEqual((rows[0]["fo"], rows[0]["h"]), ("0016", "0017"))
        match = json.loads(self.case_file("alpha", "census_match.json").read_text(encoding="utf-8"))
        self.assertEqual(match["corrections"][0]["rows"], 1)
        self.assertEqual(match["corrections"][0]["reason"], "Named as a child in form 0017")

    def test_a_spelling_accepted_in_a_case_is_attached(self):
        (self.root / "townlands" / "beta" / "townland.json").write_text(
            json.dumps({"census_spelling": {"1926": "Betta"}}), encoding="utf-8")
        self.census(1926, [self.p("Betta", year=1926)])
        self.run_attach()
        match = json.loads(self.case_file("beta", "census_match.json").read_text(encoding="utf-8"))
        self.assertEqual(match["years"]["1926"]["spellings"][0]["method"], "case_spelling")
        self.assertEqual(len(json.loads(self.case_file("beta", "census.json").read_text(encoding="utf-8"))["1926"]), 1)
        self.assertEqual(self.review()[0]["status"], "accepted_in_case")

    def test_an_identical_hand_extracted_census_is_adopted(self):
        self.census(1901, [self.p("Alpha")])
        path = self.case_file("alpha", "census.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        expected = ac.build_row(1901, self.p("Alpha"))
        expected.pop("ref")
        path.write_text(json.dumps({"1901": [expected]}), encoding="utf-8")
        self.run_attach()
        rows = json.loads(path.read_text(encoding="utf-8"))["1901"]
        self.assertEqual(rows[0]["ref"], "nai000111")
        self.assertTrue(self.case_file("alpha", "census_match.json").is_file())

    def test_a_townland_with_no_return_is_recorded_as_checked(self):
        self.census(1901, [self.p("Alpha")])
        self.run_attach()
        match = json.loads(self.case_file("beta", "census_match.json").read_text(encoding="utf-8"))
        self.assertEqual((match["status"], match["years"]), ("checked", {}))
        self.assertIn("1901, 1911, 1926", match["note"])
        self.assertFalse(self.case_file("beta", "census.json").exists())

    def test_checked_note_admits_spellings_still_awaiting_review(self):
        self.census(1901, [self.p("Alpha"), self.p("Alfa")])
        self.run_attach()
        match = json.loads(self.case_file("beta", "census_match.json").read_text(encoding="utf-8"))
        self.assertIn("awaiting review", match["note"])

    def test_a_census_year_after_1926_is_refused(self):
        saved = ac.YEARS
        ac.YEARS = (1901, 1911, 1926, 1936)
        self.addCleanup(setattr, ac, "YEARS", saved)
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            self.run_attach()
        self.assertIn("1936", err.getvalue())

    def test_source_csv_files_are_not_modified(self):
        self.census(1901, [self.p("Alpha")])
        before = {p.name: p.read_bytes() for p in ac.CENSUS_DIR.iterdir()}
        self.run_attach()
        self.assertEqual({p.name: p.read_bytes() for p in ac.CENSUS_DIR.iterdir()}, before)

    def test_missing_case_stops_with_instruction(self):
        self.census(1901, [self.p("Alpha")])
        ac.CASES_CSV.write_text("logainm_id,case_path\n1,townlands/alpha\n", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            self.run_attach()
        self.assertIn("create_townland_cases", err.getvalue())


if __name__ == "__main__":
    unittest.main()
