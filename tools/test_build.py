"""Tests for tools/build.py. Run from the repo root:

    python -m unittest tools.test_build -v

Every test works in a temporary directory. The real repository is never touched.
"""

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools import build
from tools.test_media import jpeg, png

REAL_ROOT = build.ROOT
PLACE = {"logainm_id": "13969", "name_en": "Druminnin", "name_ga": "", "ded_id": "900",
         "civil_parish_id": "784", "barony_id": "52", "county_id": "100013",
         "latitude": "54.68", "longitude": "-8.02", "snapshot_date": "2026-11-01"}


def person(sur="Harvey", house=1, age=40, sex="M", rel="Head"):
    return {"h": house, "s": sur, "f": "Ann", "a": age, "x": sex, "r": rel, "m": "", "o": "", "i": 0, "ref": "r1"}


class BuildTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        build.ROOT = self.root
        self.addCleanup(setattr, build, "ROOT", REAL_ROOT)
        (self.root / "engine").mkdir()
        for _n in ("walk.html", "index.html"):
            (self.root / "engine" / _n).write_bytes((REAL_ROOT / "engine" / _n).read_bytes())
        (self.root / "townlands").mkdir()
        names = self.root / "data" / "processed" / "places"
        names.mkdir(parents=True)
        (names / "places.csv").write_text(
            "logainm_id,name_en,name_ga,place_type,ded_id,civil_parish_id,barony_id,county_id,latitude,longitude,snapshot_date\n"
            "900,Clogher,,ded,,,,,,,\n", encoding="utf-8")
        (names / "place_names.csv").write_text(
            "logainm_id,name_en,place_type,source\n784,Donegal,civil_parish,x\n52,Tirhugh,barony,x\n100013,Donegal,county,x\n",
            encoding="utf-8")

    def case(self, name, files):
        base = self.root / "townlands" / name
        (base / "records").mkdir(parents=True, exist_ok=True)
        for rel, data in files.items():
            (base / rel).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return base

    def empty_case(self, name="druminnin", **place):
        return self.case(name, {"place.json": {**PLACE, **place}, "STATUS.md": "starter\n"})

    def census_case(self, name="druminnin", census=None, spellings=None, **place):
        census = census or {"1901": [person(), person("Harvey", 1, 38, "F", "Wife"), person("Gildea", 2)],
                            "1911": [person()]}
        spellings = spellings or {y: "Druminnin" for y in census}
        match = {"status": "proposed", "years": {y: {"spellings": [{"spelling": s, "method": "exact_name", "rows": 1}],
                                                     "people": len(census[y])} for y, s in spellings.items()}}
        return self.case(name, {"place.json": {**PLACE, **place}, "records/census.json": census,
                                "records/census_match.json": match})

    def run_build(self, name):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            state = build.build(name)
        return state, out.getvalue()

    def page(self, name):
        return (self.root / "docs" / name / "index.html").read_text(encoding="utf-8")

    def data_of(self, name):
        return json.loads(re.search(r"var DATA = (\{.*?\});\n", self.page(name)).group(1))

    # ---- every state builds a walk

    def test_empty_case_builds_a_walk_from_the_place_record(self):
        base = self.empty_case()
        before = sorted(p.name for p in base.rglob("*"))
        state, _ = self.run_build("druminnin")
        self.assertEqual(state, "empty")
        d = self.data_of("druminnin")
        t = d["content"]["plates"]["title"]
        self.assertEqual(t["heading"], "Druminnin")
        self.assertEqual(t["medium"], "A townland in Clogher electoral division, Donegal civil parish, Tirhugh barony")
        self.assertIn("No historical records have been added yet", t["story"][1])
        self.assertEqual(d["place"]["logainm_url"], "https://www.logainm.ie/en/13969")
        self.assertIn("Logainm, Government of Ireland", d["place"]["credit"])
        self.assertNotIn("griffiths", d["content"])
        self.assertEqual(d["census"], {})
        self.assertIn('id="walk"', self.page("druminnin"))
        self.assertEqual(sorted(p.name for p in base.rglob("*")), before)  # case folder untouched

    def test_names_are_looked_up_never_guessed(self):
        self.empty_case(civil_parish_id="999", barony_id="998")
        self.run_build("druminnin")
        medium = self.data_of("druminnin")["content"]["plates"]["title"]["medium"]
        self.assertEqual(medium, "A townland in Clogher electoral division")

    def test_irish_name_is_used_when_recorded(self):
        self.empty_case(name_ga="Dromainín")
        self.run_build("druminnin")
        t = self.data_of("druminnin")["content"]["plates"]["title"]
        self.assertEqual((t["irish"], t["title"]), ("Dromainín", "Dromainín"))
        self.assertIn("Its Irish name is Dromainín.", t["story"][0])

    def test_no_return_found_is_stated_only_when_checked(self):
        self.empty_case("a")
        self.case("b", {"place.json": PLACE, "records/census_match.json": {"status": "checked", "years": {}}})
        for n in ("a", "b"):
            self.run_build(n)
        a = self.data_of("a")["content"]
        b = self.data_of("b")["content"]
        self.assertEqual(a["plates"]["not_yet_hung"]["frames"][5][2], "Not yet added.")
        self.assertEqual(b["plates"]["not_yet_hung"]["frames"][5][2], "Checked. No return found.")
        self.assertIn("have not yet been attached", a["questions"][0])
        self.assertIn("No census return is linked", b["questions"][0])

    def test_census_case_states_what_it_holds_and_nothing_more(self):
        self.census_case()
        state, _ = self.run_build("druminnin")
        self.assertEqual(state, "partial")
        c = self.data_of("druminnin")["content"]
        self.assertIn("1901 and 1911 are held", c["plates"]["title"]["story"][1])
        self.assertEqual(c["plates"]["not_yet_hung"]["medium"], "Six frames for six kinds of record. One is filled")
        self.assertEqual(c["plates"]["method"]["numbers_intro"],
                         "The census files record {n1901} people in 1901 and {n1911} in 1911.")
        self.assertEqual(c["plates"]["records"]["placeholder"], "for example Harvey")
        self.assertTrue(any("1926" in q and "No census return" in q for q in c["questions"]))

    def test_census_links_are_offered_only_for_years_held(self):
        self.census_case()
        self.run_build("druminnin")
        urls = self.data_of("druminnin")["census_urls"]
        self.assertEqual(sorted(urls), ["1901", "1911"])
        self.assertTrue(all(u.startswith("https://nationalarchives.ie/collections/search-the-census/view-pdf/?doc={ref}")
                            for u in urls.values()))
        self.assertIn("view-1926-pdf", build.CENSUS_URLS["1926"])

    def test_empty_case_has_no_census_links(self):
        self.case("alpha", {"place.json": dict(PLACE, name_en="Alpha")})
        self.run_build("alpha")
        self.assertEqual(self.data_of("alpha")["census_urls"], {})

    def test_method_text_does_not_claim_the_census_is_a_plain_transcription(self):
        self.census_case()
        self.run_build("druminnin")
        paras = self.data_of("druminnin")["content"]["plates"]["method"]["paras"]
        text = " ".join(p if isinstance(p, str) else p["before"] + p["after"] for p in paras)
        self.assertIn("filled in or corrected by the researcher", text)
        self.assertNotIn("as transcribed", text)

    def test_spelling_variants_are_reported_in_the_page_data(self):
        self.census_case(census={"1901": [person()], "1926": [person()]},
                         spellings={"1901": "Druminnin", "1926": "Druminin"})
        self.run_build("druminnin")
        d = self.data_of("druminnin")
        self.assertEqual(d["townland"]["census_spelling"], {"1901": "Druminnin", "1926": "Druminin"})
        self.assertTrue(any("Druminnin in 1901 and Druminin in 1926" in q for q in d["content"]["questions"]))

    # ---- authored content always wins

    def authored(self):
        return self.case("alpha", {
            "place.json": {**PLACE, "name_en": "Alpha", "logainm_id": "1"},
            "townland.json": {"name": "Alpha", "page_title": "Alpha Study", "storage_key": "alpha-q",
                              "census_spelling": {"1901": "Alpha"}},
            "content.json": {"groups": {"colours": {"Harvey": "#123456", "Other": "#A9B7B3"}, "territory": ["Harvey", "Other"], "map": {"harvey": "Harvey"}},
                             "griffiths": {"rows": [{"lot": "1", "occ": "A B", "hd": "1"}]},
                             "families": [{"name": "The Harveys"}], "questions": ["Authored question"],
                             "plates": {"title": {"title": "T", "irish": "Irish", "heading": "Alpha", "medium": "Authored medium", "story": ["Authored story"]}}},
            "records/census.json": {"1901": [person()]}})

    def test_authored_content_overrides_generated_but_gaps_are_filled(self):
        self.authored()
        state, _ = self.run_build("alpha")
        self.assertEqual(state, "ready")
        d = self.data_of("alpha")
        c = d["content"]
        self.assertEqual(c["plates"]["title"]["medium"], "Authored medium")
        self.assertEqual(c["questions"], ["Authored question"])
        self.assertEqual(c["groups"]["colours"]["Harvey"], "#123456")
        self.assertEqual(c["families"], [{"name": "The Harveys"}])
        self.assertIn("not_yet_hung", c["plates"])                       # generated gap filled
        self.assertEqual(c["plates"]["not_yet_hung"]["frames"][1][2], "Held.")  # Griffith's is held
        self.assertEqual(d["townland"]["page_title"], "Alpha Study")
        self.assertEqual(d["place"]["logainm_id"], "1")                  # studies get the Logainm card too
        self.assertIn("<title>Alpha Study</title>", self.page("alpha"))

    def test_enriching_a_case_replaces_the_page_at_the_same_address(self):
        base = self.empty_case("alpha")
        self.run_build("alpha")
        self.assertNotIn("1901", json.dumps(self.data_of("alpha")["census"]))
        (base / "records" / "census.json").write_text(json.dumps({"1901": [person()]}), encoding="utf-8")
        self.run_build("alpha")
        self.assertIn("1901", self.data_of("alpha")["census"])

    # ---- safety

    def test_a_page_not_generated_by_the_tool_is_never_replaced(self):
        self.empty_case()
        page = self.root / "docs" / "druminnin" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text("hand written", encoding="utf-8")
        _, text = self.run_build("druminnin")
        self.assertEqual(page.read_text(encoding="utf-8"), "hand written")
        self.assertIn("Left untouched", text)

    def test_an_earlier_plain_place_page_is_replaced_by_the_walk(self):
        self.empty_case()
        page = self.root / "docs" / "druminnin" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(build.PLACE_MARK + "<p>old</p>", encoding="utf-8")
        self.run_build("druminnin")
        self.assertIn('id="walk"', page.read_text(encoding="utf-8"))

    def test_case_with_nothing_to_show_is_reported_not_built(self):
        self.case("gamma", {"records/census.json": {}})
        _, text = self.run_build("gamma")
        self.assertIn("create_townland_cases", text)
        self.assertFalse((self.root / "docs").exists())

    def test_unknown_case_is_an_error(self):
        with self.assertRaises(SystemExit):
            self.run_build("nosuchplace")

    def test_names_are_escaped_in_the_page(self):
        self.empty_case(name_en="<b>X</b>")
        self.run_build("druminnin")
        page = self.page("druminnin")
        self.assertNotIn("<b>X</b>", page)
        self.assertNotIn("</", self.data_of_raw(page))

    @staticmethod
    def data_of_raw(page):
        return re.search(r"var DATA = (\{.*?\});\n", page).group(1)

    def test_no_em_dashes_in_generated_pages(self):
        self.census_case()
        self.run_build("druminnin")
        self.assertNotIn(chr(0x2014), json.dumps(self.data_of("druminnin")["content"], ensure_ascii=False))

    # ---- media (docs/MEDIA_SPEC.md)

    SHEET = ("file,scope,slot,family,caption,alt,source,reference,date,people_shown,link\n"
             "wide.jpg,townland,1,,A wide view,,Family collection,,,,\n"
             "tall photo.png,family,,The Harveys,A tall one,,Family collection,Ref 1,c. 1930s,,https://example.org/o\n")

    def media_case(self, sheet=None):
        base = self.authored()
        folder = base / "media"
        folder.mkdir()
        (folder / "wide.jpg").write_bytes(jpeg(1600, 900))
        (folder / "tall photo.png").write_bytes(png(500, 800))
        (folder / "media.csv").write_text(self.SHEET if sheet is None else sheet, encoding="utf-8")
        return base

    def test_a_case_without_media_has_no_media_data_and_no_media_folder(self):
        self.authored()
        self.run_build("alpha")
        self.assertNotIn("media", self.data_of("alpha"))
        self.assertFalse((self.root / "docs" / "alpha" / "media").exists())

    def test_media_reaches_the_page_data_and_images_are_copied_unchanged(self):
        base = self.media_case()
        state, out = self.run_build("alpha")
        self.assertEqual(state, "ready")
        m = self.data_of("alpha")["media"]
        self.assertEqual([(h["url"], h["w"], h["h"], h["caption"]) for h in m["header"]],
                         [("media/wide.jpg", 1600, 900, "A wide view")])
        photo = m["families"]["The Harveys"][0]
        self.assertEqual((photo["url"], photo["w"], photo["h"], photo["date"]), ("media/tall%20photo.png", 500, 800, "c. 1930s"))
        for name in ("wide.jpg", "tall photo.png"):
            self.assertEqual((self.root / "docs" / "alpha" / "media" / name).read_bytes(), (base / "media" / name).read_bytes())
        self.assertIn("media 2 rows, 2 files copied", out)

    def test_rebuilding_media_is_deterministic_and_copies_nothing_twice(self):
        self.media_case()
        self.run_build("alpha")
        first = self.page("alpha")
        _, out = self.run_build("alpha")
        self.assertEqual(self.page("alpha"), first)
        self.assertIn("0 files copied", out)

    def test_a_cdn_base_address_means_nothing_is_copied(self):
        self.media_case()
        (self.root / "townlands" / "media_config.json").write_text('{"base_url": "https://cdn.example.org/m"}', encoding="utf-8")
        _, out = self.run_build("alpha")
        m = self.data_of("alpha")["media"]
        self.assertEqual(m["header"][0]["url"], "https://cdn.example.org/m/wide.jpg")
        self.assertEqual(m["header"][0]["w"], 1600)          # still sized from the local file when it exists
        self.assertFalse((self.root / "docs" / "alpha" / "media").exists())
        self.assertIn("served from https://cdn.example.org/m/", out)

    def test_media_problems_stop_that_case_only_and_say_why(self):
        self.media_case("file,scope,slot,family,caption,source\nwide.jpg,family,,The Smiths,Cap,Src\n")
        self.census_case("two")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            build.main(["--all"])
        text = out.getvalue()
        self.assertIn("alpha: media problems, not built", text)
        self.assertIn("unknown family The Smiths", text)
        self.assertFalse((self.root / "docs" / "alpha" / "index.html").exists())
        self.assertTrue((self.root / "docs" / "two" / "index.html").exists())

    def test_old_media_copies_are_never_deleted(self):
        self.media_case()
        stale = self.root / "docs" / "alpha" / "media" / "old.jpg"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"old")
        self.run_build("alpha")
        self.assertEqual(stale.read_bytes(), b"old")

    def test_media_text_is_escaped_in_the_page(self):
        self.media_case("file,scope,slot,family,caption,source\nwide.jpg,townland,1,,</script><b>x,Src\n")
        self.run_build("alpha")
        self.assertNotIn("</script><b>", self.page("alpha"))
        self.assertEqual(self.data_of("alpha")["media"]["header"][0]["caption"], "</script><b>x")

    # ---- the index

    def test_all_builds_everything_and_groups_the_index(self):
        self.authored()
        self.census_case("two")
        self.empty_case("one")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            build.main(["--all"])
        self.assertIn("1 studies, 1 partial, 1 empty", out.getvalue())
        index = (self.root / "docs" / "index.html").read_text(encoding="utf-8")
        pos = [index.index('href="./%s/"' % s) for s in ("alpha", "one", "two")]
        self.assertEqual(pos, sorted(pos))    # one list, in name order
        for slug, tag in (("alpha", "Townland Study"), ("two", "Census Returns"), ("one", "Townland Record")):
            card = index[index.index('data-slug="%s"' % slug):]
            self.assertIn(tag, card[:card.index("</a>")])
        self.assertIn("3 Records", index)
        self.assertIn("generated: donegal-townlands index", index)
        self.assertIn("Logainm, Government of Ireland", index)

    def test_building_one_case_still_regenerates_the_index(self):
        self.empty_case("one")
        with contextlib.redirect_stdout(io.StringIO()):
            build.main(["one"])
        self.assertIn('href="./one/"', (self.root / "docs" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
