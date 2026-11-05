"""Tests for tools/attach_griffiths.py and the names-only Griffith's plate. Run from the repo root:

    python -m unittest tools.test_attach_griffiths -v

Every test works in a temporary directory. The real repository is never touched.
"""

import contextlib
import csv
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools import attach_griffiths as ag
from tools import build
from tools.test_build import BuildTests as _B

FIELDS = ["townland", "civil_parish", "county", "barony", "askaboutireland_place_id", "askaboutireland_record_id",
          "occupier_surname_as_indexed", "occupier_forename_as_indexed", "original_page_position_rs",
          "valuation_sheet_reference", "details_url", "original_page_url", "map_url",
          "website_transcription_status", "image_transcription_status", "notes"]
MASTER = ["logainm_id", "townland", "number_of_entries"]


def idx_row(rid, pos, sur, fore, **kw):
    r = {k: "" for k in FIELDS}
    r.update(townland="Testland", civil_parish="Donegal", county="Donegal", barony="Tirhugh",
             askaboutireland_place_id="1", askaboutireland_record_id=str(rid), original_page_position_rs=str(pos),
             valuation_sheet_reference="1,2", details_url="https://x/?mysession=999&ID=%s" % rid,
             website_transcription_status="not yet captured", image_transcription_status="not yet transcribed")
    r.update(occupier_surname_as_indexed=sur, occupier_forename_as_indexed=fore)
    r.update(kw)
    return r


ROWS = [idx_row(10, 5, "DOHERTY", "MARY"), idx_row(11, 6, "MCCOOL", "EDW."),
        idx_row(12, 7, "MCCOOL", "EDWARD"), idx_row(13, 8, "ARRAN", "EARL OF"), idx_row(14, 9, "", "")]


class AttachTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.src = self.root / "data" / "source" / "griffiths"
        self.src.mkdir(parents=True)
        (self.root / "townlands" / "testland").mkdir(parents=True)

    def write_index(self, rows=ROWS, master_entries=5):
        with (self.src / "testland_griffiths_individuals.csv").open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, FIELDS); w.writeheader(); w.writerows(rows)
        with (self.src / "donegal_griffiths_parish_master_complete.csv").open("w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, MASTER); w.writeheader()
            w.writerow({"logainm_id": "1", "townland": "Testland", "number_of_entries": master_entries})

    def run_it(self):
        out = []
        n = ag.run(self.src, self.root, out.append)
        return n, out

    def index(self):
        return json.loads((self.root / "townlands" / "testland" / "records" / "griffiths_index.json").read_text())

    def test_index_is_written_without_session_ids_and_roles_are_proposed(self):
        self.write_index()
        n, out = self.run_it()
        self.assertEqual(n, 0)
        d = self.index()
        self.assertEqual([r["role"] for r in d["rows"]], ["occupier"] * 3 + ["title_entry", "blank_entry"])
        self.assertTrue(all(r["tier"] == 1 for r in d["rows"]))
        self.assertNotIn("mysession", json.dumps(d))
        self.assertEqual(d["rows"][0]["listing_url"], ag.listing_url(1, 5, 0))
        self.assertNotIn("image_url", d["rows"][0])
        self.assertNotIn("details_url", d["rows"][0])
        self.assertEqual(d["parish_master_entries"], 5)

    def test_rows_follow_record_id_not_page_position(self):
        rows = [idx_row(20, 35, "A", "ONE"), idx_row(21, 1, "B", "TWO"), idx_row(22, 2, "C", "THREE")]
        self.write_index(rows, 3)
        self.run_it()
        self.assertEqual([r["record_id"] for r in self.index()["rows"]], [20, 21, 22])

    def test_listing_link_has_no_session_and_pages_run_in_twenties(self):
        rows = [idx_row(100 + i, i + 1, "S%d" % i, "F") for i in range(45)]
        self.write_index(rows, 45)
        self.run_it()
        d = self.index()["rows"]
        self.assertEqual([d[i]["listing_page"] for i in (0, 19, 20, 39, 40, 44)], [1, 1, 2, 2, 3, 3])
        self.assertIn("offset=20&", d[20]["listing_url"])
        self.assertIn("totalrows=45&PlaceID=1&", d[20]["listing_url"])
        self.assertNotIn("mysession", json.dumps(d))

    def test_status_columns_set_the_tier(self):
        rows = [idx_row(1, 1, "A", "B", website_transcription_status="captured"),
                idx_row(2, 2, "C", "D", website_transcription_status="captured", image_transcription_status="transcribed")]
        self.write_index(rows, 2)
        self.run_it()
        self.assertEqual([r["tier"] for r in self.index()["rows"]], [2, 3])

    def test_master_count_disagreement_is_reported(self):
        self.write_index(master_entries=9)
        n, out = self.run_it()
        self.assertEqual(n, 1)
        self.assertTrue(any("parish master says 9" in l for l in out))

    def test_missing_case_folder_is_reported_not_created(self):
        self.write_index()
        (self.root / "townlands" / "testland").rmdir()
        n, out = self.run_it()
        self.assertEqual(n, 1)
        self.assertFalse((self.root / "townlands" / "testland").exists())

    def test_match_pairs_by_order_and_ignores_nicknames(self):
        self.write_index()
        authored = {"griffiths": {"rows": [{"lot": "1", "occ": "Mary Doherty"}, {"lot": "2", "occ": "Edw. McCool (Wee)"},
                                           {"lot": "3", "occ": "Edwd. McCool (Long)"}]}}
        (self.root / "townlands" / "testland" / "content.json").write_text(json.dumps(authored))
        before = (self.root / "townlands" / "testland" / "content.json").read_text()
        n, _ = self.run_it()
        m = json.loads((self.root / "townlands" / "testland" / "records" / "griffiths_match.json").read_text())
        self.assertEqual(n, 1)                      # Edward vs Edw. is a real difference, reported
        self.assertEqual([p["names_agree"] for p in m["pairs"]], [True, True, False])
        self.assertEqual((self.root / "townlands" / "testland" / "content.json").read_text(), before)

    def test_extra_rows_on_either_side_are_problems(self):
        self.write_index()
        authored = {"griffiths": {"rows": [{"occ": "Mary Doherty"}]}}
        (self.root / "townlands" / "testland" / "content.json").write_text(json.dumps(authored))
        n, out = self.run_it()
        self.assertEqual(n, 2)


class NamesOnlyPlateTests(_B):
    """Build a case that holds only the index, and one that also has a transcription."""

    def index_payload(self):
        return {"townland": "Druminnin", "rows": [
            {"record_id": 1, "position": 3, "surname": "GILDEA", "forename": "PATRICK", "role": "occupier", "tier": 1,
             "listing_url": "https://x/l", "listing_page": 1},
            {"record_id": 2, "position": 4, "surname": "", "forename": "", "role": "blank_entry", "tier": 1,
             "listing_url": "https://x/l", "listing_page": 1}]}

    def test_index_only_case_carries_names_and_says_so(self):
        self.case("druminnin", {"place.json": {**__import__("tools.test_build", fromlist=["PLACE"]).PLACE},
                                "records/griffiths_index.json": self.index_payload()})
        self.run_build("druminnin")
        d = self.data_of("druminnin")
        self.assertEqual(d["griffiths_index"]["rows"][0]["surname"], "GILDEA")
        frames = {f[0]: f for f in d["content"]["plates"]["not_yet_hung"]["frames"]}
        self.assertEqual(frames["Griffith's Valuation"][2:], ["Names only.", True])
        self.assertTrue(any("only the askaboutireland index" in q for q in d["content"]["questions"]))
        self.assertIn("Griffith's, the names", self.page("druminnin"))

    def test_a_transcription_wins_over_the_index(self):
        P = __import__("tools.test_build", fromlist=["PLACE"]).PLACE
        self.case("druminnin", {"place.json": {**P}, "records/griffiths_index.json": self.index_payload(),
                                "townland.json": {"name": "Druminnin"},
                                "content.json": {"griffiths": {"rows": [{"lot": "1", "hd": "1", "occ": "Patrick Gildea"}],
                                                                "sheet": {"heading": "X", "sub": "", "printed_total": [], "foot": ""}}}})
        self.run_build("druminnin")
        d = self.data_of("druminnin")
        self.assertNotIn("griffiths_index", d)
        frames = {f[0]: f for f in d["content"]["plates"]["not_yet_hung"]["frames"]}
        self.assertEqual(frames["Griffith's Valuation"][2], "Held.")


if __name__ == "__main__":
    unittest.main()


from tools import parse_griffiths_pages as pg


def page(rows, total, place=77, start=1):
    body = "".join(
        '<tr><td class="results">%s</td><td class="results">%s</td><td class="results">DONEGAL</td><td class="results">DONEGAL</td>'
        '<td><a href="https://x/details.xml?action=showDetails&amp;mysession=5&amp;ID=%d&amp;la=">d</a></td>'
        '<td><a href="https://x/details.xml?action=showImage&amp;mysession=5&amp;ID=%d&amp;rs=%d&amp;width=640&amp;height=480">p</a></td>'
        '<td><a href="https://x/details.xml?action=i8&amp;sheet=94&amp;mysession=5&amp;barony=TIRHUGH&amp;townland=TESTLAND">m</a></td></tr>'
        % (s, f, rid, rid, rs) for s, f, rid, rs in rows)
    return ('<!-- saved from url=(0100)https://x/index.xml?PlaceID=%d&totalrows=%d -->Results %d to %d of %d'
            '<table class="gv-results">%s</table>' % (place, total, start, start + len(rows) - 1, total, body))


class ParsePagesTests(unittest.TestCase):
    A = page([("CASSIDY", "PETER", 12, 35), ("MCGINTY", "MARY", 13, 1)], 4)
    B = page([("", "", 16, 2), ("ARRAN", "EARL OF", 15, 3)], 4, start=3)

    def test_two_pages_become_rows_in_record_id_order_with_gaps_reported(self):
        say = []
        name, rows = pg.build([self.A, self.B], {"77": "Testland"}, say.append)
        self.assertEqual(name, "Testland")
        self.assertEqual([r["askaboutireland_record_id"] for r in rows], [12, 13, 15, 16])
        self.assertEqual(rows[0]["original_page_position_rs"], 35)
        self.assertNotIn("width=", rows[0]["original_page_url"])
        self.assertEqual(rows[0]["barony"], "Tirhugh")
        self.assertEqual(rows[3]["notes"], "Blank occupier name in source index; retain as an entry")
        self.assertTrue(any("14 to 14" in s for s in say))

    def test_missing_page_stops_the_run(self):
        with self.assertRaises(ValueError):
            pg.build([self.A], {"77": "Testland"}, lambda s: None)

    def test_same_page_twice_stops_the_run(self):
        with self.assertRaises(ValueError):
            pg.build([self.A, self.A], {"77": "Testland"}, lambda s: None)

    def test_pages_for_two_places_stop_the_run(self):
        with self.assertRaises(ValueError):
            pg.build([self.A, page([("A", "B", 40, 1)], 4, place=78)], {}, lambda s: None)

    def test_not_a_results_page_stops_the_run(self):
        with self.assertRaises(ValueError):
            pg.parse_page("<html>nothing here</html>")


class RawPageTests(unittest.TestCase):
    """The raw page source: unquoted attributes, relative links, unclosed rows, no PlaceID."""
    RAW = ("Results 1 to 2 of 2 <table class='gv-results'><tr><th class=\"doprint\">Surname</th></tr>"
           "<tr><td class=results> THOMAS </td><td class=results> MICHAEL </td><td class=results> DONEGAL </td>"
           "<td class=results> DONEGAL </td><td><a href=\"details.xml?action=showDetails&mysession=5&ID=31&la=\">d</a></td>"
           "<td><a href=\"details.xml?action=showImage&mysession=5&ID=31&rs=17&width=640&height=480\">p</a>"
           "<a href=\"details.xml?action=showImage&mysession=5&ID=31&rs=17\">p</a></td>"
           "<td class=resultsmap><a href=\"details.xml?action=i8&sheet=94&mysession=5&placename=MULLANALAMPHRY&barony=TIRHUGH\">m</a></td>"
           "<tr><td class=results> LYNCH </td><td class=results> JAMES </td><td class=results> DONEGAL </td>"
           "<td class=results> DONEGAL </td><td><a href=\"details.xml?action=showDetails&mysession=5&ID=32&la=\">d</a></td>"
           "<td><a href=\"details.xml?action=showImage&mysession=5&ID=32&rs=18\">p</a></td>"
           "<td class=resultsmap><a href=\"details.xml?action=i8&sheet=94&mysession=5&placename=MULLANALAMPHRY&barony=TIRHUGH\">m</a></td>"
           "</table> footer details.xml?action=showDetails&ID=99")
    NAMES = {"MULLANALAMPHRY": [(1489546, "Mullanalamphry")]}

    def test_raw_page_rows_and_townland_from_the_placename(self):
        name, rows = pg.build([self.RAW], {}, lambda s: None, self.NAMES)
        self.assertEqual(name, "Mullanalamphry")
        self.assertEqual([r["askaboutireland_record_id"] for r in rows], [31, 32])
        self.assertEqual(rows[0]["askaboutireland_place_id"], 1489546)
        self.assertTrue(rows[0]["original_page_url"].startswith("https://www.askaboutireland.ie/griffith-valuation/details.xml"))
        self.assertNotIn("width=", rows[0]["original_page_url"])

    def test_unknown_placename_stops_the_run(self):
        with self.assertRaises(ValueError):
            pg.build([self.RAW], {}, lambda s: None, {})
