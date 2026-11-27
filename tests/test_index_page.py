"""The map index (RO-11 to RO-14): story links, no link without a story, no brown, credit."""
import unittest
from tools import build

E1 = {'slug': 'alpha', 'name': 'Alpha', 'state': 'ready', 'name_ga': 'Alfa', 'lat': '54.6', 'lng': '-8.0', 'doc': True}
E2 = {'slug': 'beta', 'name': 'Beta', 'state': 'empty', 'name_ga': '', 'lat': '', 'lng': '', 'doc': False}
TEMPLATE = (build.ROOT / 'engine' / 'index.html').read_text(encoding='utf-8')


class IndexTests(unittest.TestCase):
    def page(self):
        return build.index_page([E2, E1], TEMPLATE)

    def test_story_card_plays_the_story(self):
        p = self.page()
        self.assertIn('<a class="pill main" href="./story.html?t=alpha">Play the story</a>', p)
        self.assertIn('<a class="card-en" href="./story.html?t=alpha">Alpha</a>', p)
        self.assertNotIn('Gallery walk', p)

    def test_card_without_story_has_a_name_and_no_link(self):
        p = self.page()
        self.assertIn('<span class="card-en">Beta</span>', p)
        self.assertNotIn('./beta/', p)

    def test_case_without_coordinates_has_a_card_and_no_pin(self):
        p = self.page()
        self.assertIn('data-name="Beta"', p)
        self.assertEqual(p.count('"type": "Point"'), 1)

    def test_case_with_no_records_has_a_card_and_no_pin(self):
        empty = dict(E2, lat='54.7', lng='-8.1')
        p = build.index_page([E1, empty], TEMPLATE)
        self.assertIn('data-name="Beta"', p)
        self.assertEqual(p.count('"type": "Point"'), 1)

    def test_no_placeholder_left_and_credit_present(self):
        p = self.page()
        for ph in ('__MARK__', '__COUNT__', '__FOOTER__', '__GEOJSON__', '__CARDS__'):
            self.assertNotIn(ph, p)
        self.assertIn('Imagery: Esri, Maxar, Earthstar Geographics', p)

    def test_light_palette_no_brown(self):
        for old in ('#f4efe6', '#8c6d3b', '#b8a686', 'Cinzel', 'Baskerville'):
            self.assertNotIn(old, TEMPLATE)
        self.assertIn('Newsreader', TEMPLATE)
        self.assertIn('Instrument Sans', TEMPLATE)

    def test_map_is_primary_and_list_is_behind_a_button(self):
        self.assertIn('id="seelist"', TEMPLATE)
        self.assertIn('id="listpanel"', TEMPLATE)
        self.assertIn('class="off" role="dialog" aria-label="List of townlands" hidden', TEMPLATE)
        self.assertIn('#map-container{position:fixed;inset:0', TEMPLATE)

    def test_index_and_story_share_the_view_handoff(self):
        doc = (build.ROOT / 'engine' / 'story.html').read_text(encoding='utf-8')
        self.assertIn("var KEY='dt-view'", TEMPLATE)
        self.assertIn("sessionStorage.getItem('dt-view')", doc)
        self.assertNotIn('m.setView(ll0,3,', doc)           # no more fall from the globe

    OUTLINE = {'type': 'Polygon', 'coordinates': [[[-8.01, 54.68], [-7.97, 54.68], [-7.97, 54.70], [-8.01, 54.70], [-8.01, 54.68]]]}

    def test_outline_travels_with_its_credit_and_the_dot_is_the_fallback(self):
        p = build.index_page([E1, dict(E1, slug='gamma', name='Gamma', outline=self.OUTLINE)], TEMPLATE)
        self.assertEqual(p.count('"type": "Polygon"'), 1)       # only Gamma has an outline
        self.assertEqual(p.count('"type": "Point"'), 2)         # both keep a centre point
        self.assertIn(build.BOUNDARY_CREDIT, p)
        self.assertIn('Tailte \u00c9ireann, CC BY 4.0', p)
        self.assertIn('if(p.outline){', TEMPLATE)               # outline drawn, otherwise the circle marker
        self.assertIn('L.circleMarker', TEMPLATE)

    DED = {'type': 'Feature', 'properties': {'ded_id': '1', 'name': 'Alphaville', 'name_ga': '', 'townlands': 3},
           'geometry': {'type': 'Polygon', 'coordinates': [[[-8.1, 54.5], [-7.9, 54.5], [-7.9, 54.8], [-8.1, 54.5]]]}}

    def test_deds_open_the_map_and_townlands_come_in_on_zoom(self):
        p = build.index_page([E1], TEMPLATE, [self.DED])
        self.assertIn('"deds": [', p)
        self.assertIn('Alphaville', p)
        self.assertIn(build.BOUNDARY_CREDIT, p)
        self.assertIn('function dedLevel(deds)', TEMPLATE)
        self.assertIn("map.on('zoomend',sync)", TEMPLATE)         # zooming out hides the townlands again
        self.assertIn('map.fitBounds(group.getBounds()', TEMPLATE)  # no DEDs: every townland at once, as before

    def test_without_deds_the_page_is_unchanged_in_kind(self):
        self.assertNotIn('"deds"', self.page())

    def test_townland_records_which_ded_they_are_in(self):
        p = build.index_page([dict(E1, ded='1372439')], TEMPLATE)
        self.assertIn('"ded": "1372439"', p)

    def test_cards_carry_a_summary_of_what_is_held(self):
        e = dict(E1, summary=[('Census', '1901 (93 people), 1911 (72)'), ("Griffith's Valuation", '25 entries transcribed')])
        p = build.index_page([e], TEMPLATE)
        self.assertIn('<ul class="card-sum">', p)
        self.assertIn('<li><b>Census</b> 1901 (93 people), 1911 (72)</li>', p)
        self.assertIn("<b>Griffith&#x27;s Valuation</b> 25 entries transcribed", p)

    def test_a_case_with_nothing_says_so(self):
        p = build.index_page([dict(E1, summary=[])], TEMPLATE)
        self.assertIn('No records held yet', p)
        self.assertNotIn('<ul class="card-sum">', p)

    def test_a_tap_on_the_map_opens_a_card_and_does_not_leave(self):
        self.assertIn('function openSheet(', TEMPLATE)
        self.assertIn("m.on('click',function(){ openSheet(", TEMPLATE)
        self.assertNotIn("if(p.doc) leave(c[1],c[0],p.href); else window.location.href=p.href;", TEMPLATE)
        self.assertEqual(TEMPLATE.count('bubblingMouseEvents:false'), 2)   # outline and dot, so a tap does not also close it
        self.assertIn('id="sheet"', TEMPLATE)
        self.assertIn("map.on('click',closeSheet)", TEMPLATE)

    def test_no_outline_no_credit(self):
        p = self.page()
        self.assertNotIn(build.BOUNDARY_CREDIT, p)
        self.assertNotIn('"attribution"', p)
        self.assertNotIn('"type": "Polygon"', p)

    def test_outline_loader_is_empty_without_the_file(self):
        saved = build.BOUNDARY_FILE
        try:
            build.BOUNDARY_FILE = build.ROOT / 'data' / 'processed' / 'places' / 'no_such_file.geojson'
            self.assertEqual(build.load_outlines(), {})
        finally:
            build.BOUNDARY_FILE = saved

    def test_committed_outlines_are_keyed_by_logainm_id(self):
        o = build.load_outlines()
        self.assertIn('13967', o)                                # Cullionboy
        self.assertIn(o['13967']['type'], ('Polygon', 'MultiPolygon'))


if __name__ == '__main__':
    unittest.main()
