"""Tests for tools/gedcom_people.py (WP17). Run: python -m pytest tests/test_gedcom_people.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import gedcom_people as gp  # noqa: E402

GED = """0 HEAD
0 @I1@ INDI
1 NAME Patrick /Kelly/
2 GIVN Patrick
2 SURN Kelly
2 NICK Packie
1 SEX M
1 BIRT
2 DATE ABT 1880
2 PLAC Cullionboy, County Donegal, Ireland
1 DEAT
2 DATE 3 Mar 1950
1 OCCU Farmer
1 NOTE Ahnentafel 4. Known as Packie (Ahn. 7). Born at home.
2 CONT
2 CONT Family Note: Shared note about the Kellys.
1 FAMS @F1@
0 @I2@ INDI
1 NAME Mary /Logue/
2 GIVN Mary
2 SURN Logue
1 SEX F
1 BIRT
2 DATE 1885
1 FAMS @F1@
0 @I3@ INDI
1 NAME Anne /Kelly/
2 GIVN Anne
2 SURN Kelly
1 SEX F
1 BIRT
2 DATE 4 May 1951
1 FAMC @F1@
0 @I4@ INDI
1 NAME Old /Kelly/
2 GIVN Old
2 SURN Kelly
1 SEX M
1 BIRT
2 DATE 1901
1 NOTE Moved away in 1990.
1 FAMC @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
1 CHIL @I4@
1 MARR
2 DATE 1 Jan 1910
0 TRLR
"""


def tree(tmp):
    p = Path(tmp) / "t.ged"
    p.write_text(GED, encoding="utf-8")
    return gp.read_tree(p)


def test_privacy_per_person(tmp_path):
    t = tree(tmp_path)["people"]
    assert gp.passes(t["@I1@"], 2026)        # born 1880
    assert gp.passes(t["@I4@"], 2026)        # born 1901
    assert not gp.passes(t["@I3@"], 2026)    # born 1951, no death: presumed living
    assert gp.passes(t["@I3@"], 2060)        # a later year lets the rule pass


def test_event_dates_follow_their_own_years(tmp_path):
    t = tree(tmp_path)["people"]
    assert gp._shown(t["@I1@"]["death"], gp.DEATH_YEARS, 2026)["date"] == "3 Mar 1950"
    assert gp._shown(t["@I1@"]["death"], gp.DEATH_YEARS, 1990) is None   # only 40 years
    assert gp._shown({"raw": "", "date": "", "year": None, "place": "x"}, 50, 2026) is None


def test_display_wording_keeps_raw(tmp_path):
    t = tree(tmp_path)["people"]["@I1@"]
    assert t["birth"]["date"] == "about 1880" and t["birth"]["raw"] == "ABT 1880"


def test_note_cleaning_strips_tree_numbers(tmp_path):
    p = tree(tmp_path)["people"]["@I1@"]
    joined = " ".join(p["notes"])
    assert "Ahnentafel" not in joined and "Ahn." not in joined
    assert "Known as Packie" in joined


def test_recent_years_in_notes():
    assert gp.recent_year_in("Moved away in 1990.", 2026) == 1990
    assert gp.recent_year_in("Died in 1954.", 2026) is None


def _root(tmp, rows_h="1"):
    root = Path(tmp)
    rec = root / "townlands" / "cullionboy" / "records"
    rec.mkdir(parents=True)
    (rec / "census.json").write_text(json.dumps(
        {"1911": [{"h": 1, "s": "Kelly", "f": "Patrick", "a": 30, "r": "Head", "i": 0}]}))
    (rec / "census_match.json").write_text(json.dumps(
        {"years": {"1911": {"spellings": [{"spelling": "Cullionboy", "method": "exact_name", "rows": 1}]}}}))
    return root


def test_build_names_only_people_who_pass(tmp_path):
    t = tree(tmp_path)
    root = _root(tmp_path / "r")
    rows = [{"year": 1911, "obs": "census1911:clogher:9", "townland": "Cullionboy", "house": "1",
             "surname": "Kelly", "first": "Patrick", "age": 30, "form": ""}]
    dec = [{"person_ptr": "@I1@", "person_name": "Patrick Kelly", "obs_id": "census1911:clogher:9", "status": "accepted"}]
    out, rep = gp.build(t, dec, rows, root, 2026)
    p = out["cullionboy"]["people"][0]
    assert p["name"] == "Patrick Kelly" and p["census"][0]["h"] == 1
    names = {r["name"] for r in out["cullionboy"]["refs"].values()}
    assert "Mary Logue" in names and "Old Kelly" in names
    assert "Anne Kelly" not in names                      # born 1951: not named as a child
    assert out["cullionboy"]["family_notes"] == ["Shared note about the Kellys."]
    assert all("Family Note" not in n for n in p["notes"])


def test_rejected_and_unmapped_links_are_not_exported(tmp_path):
    t = tree(tmp_path)
    root = _root(tmp_path / "r")
    rows = [{"year": 1911, "obs": "census1911:clogher:9", "townland": "Cullionboy", "house": "1",
             "surname": "Kelly", "first": "Patrick", "age": 30, "form": ""}]
    dec = [{"person_ptr": "@I1@", "person_name": "P", "obs_id": "census1911:clogher:9", "status": "rejected"},
           {"person_ptr": "@I1@", "person_name": "P", "obs_id": "census1911:clogher:404", "status": "accepted"}]
    out, rep = gp.build(t, dec, rows, root, 2026)
    assert out == {} and rep["unmapped"] == ["census1911:clogher:404"]


def test_living_person_is_withheld(tmp_path):
    t = tree(tmp_path)
    root = _root(tmp_path / "r")
    rows = [{"year": 1911, "obs": "census1911:clogher:9", "townland": "Cullionboy", "house": "1",
             "surname": "Kelly", "first": "Patrick", "age": 30, "form": ""}]
    dec = [{"person_ptr": "@I3@", "person_name": "Anne", "obs_id": "census1911:clogher:9", "status": "accepted"}]
    out, rep = gp.build(t, dec, rows, root, 2026)
    assert out == {} and rep["withheld_people"] == ["Anne Kelly"]


def test_check_file_catches_recent_data(tmp_path):
    bad = {"people": [{"name": "X", "birth": {"raw": "1990", "date": "1990"}, "death": None,
                       "marriages": [], "notes": ["Seen in 2015."]}], "refs": {}}
    f = Path(tmp_path) / "people.json"
    f.write_text(json.dumps(bad))
    errs = gp.check_file(f, 2026)
    assert len(errs) == 2
    good = {"people": [{"name": "Y", "birth": {"raw": "1880", "date": "1880"}, "death": None,
                        "marriages": [], "notes": ["Died 1950."]}], "refs": {}}
    f.write_text(json.dumps(good))
    assert gp.check_file(f, 2026) == []
