"""The map index (RO-11 to RO-14): documentary links, walk fallback, no brown, credit."""
import unittest
from tools import build

E1 = {'slug': 'alpha', 'name': 'Alpha', 'state': 'ready', 'name_ga': 'Alfa', 'lat': '54.6', 'lng': '-8.0', 'doc': True}
E2 = {'slug': 'beta', 'name': 'Beta', 'state': 'empty', 'name_ga': '', 'lat': '', 'lng': '', 'doc': False}
TEMPLATE = (build.ROOT / 'engine' / 'index.html').read_text(encoding='utf-8')


class IndexTests(unittest.TestCase):
    def page(self):
        return build.index_page([E2, E1], TEMPLATE)

    def test_documentary_card_plays_first_and_keeps_the_walk(self):
        p = self.page()
        self.assertIn('<a class="pill main" href="./alpha/documentary.html">Play the documentary</a>', p)
        self.assertIn('<a class="pill" href="./alpha/">Gallery walk</a>', p)
        self.assertIn('<a class="card-en" href="./alpha/documentary.html">Alpha</a>', p)

    def test_card_without_documentary_opens_the_walk(self):
        p = self.page()
        self.assertIn('<a class="card-en" href="./beta/">Beta</a>', p)
        self.assertNotIn('beta/documentary.html', p)

    def test_case_without_coordinates_has_a_card_and_no_pin(self):
        p = self.page()
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


if __name__ == '__main__':
    unittest.main()
