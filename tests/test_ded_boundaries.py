"""DED outlines made by dissolving the townland outlines (tools/build_ded_boundaries.py)."""
import json
import unittest
from tools import build_ded_boundaries as bd, build


def square(x, y, s=1.0):
    return [[[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]]


def area(ring):
    return abs(bd.ring_area(ring))


class DissolveTests(unittest.TestCase):
    def test_two_neighbours_merge_into_one_ring(self):
        merged = bd.dissolve([square(0, 0), square(1, 0)])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]), 1)
        self.assertAlmostEqual(area(merged[0][0]), 2.0)

    def test_a_ring_of_neighbours_leaves_a_hole(self):
        tiles = [square(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)]
        merged = bd.dissolve(tiles)
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]), 2)                       # outer ring and one hole
        self.assertAlmostEqual(area(merged[0][0]), 9.0)
        self.assertAlmostEqual(area(merged[0][1]), 1.0)

    def test_separate_shapes_stay_separate(self):
        merged = bd.dissolve([square(0, 0), square(5, 5)])
        self.assertEqual(len(merged), 2)

    def test_outer_rings_run_counter_clockwise(self):
        merged = bd.dissolve([square(0, 0), square(1, 0)])
        self.assertGreater(bd.ring_area(merged[0][0]), 0)

    def test_the_same_input_gives_the_same_output(self):
        a = bd.dissolve([square(0, 0), square(1, 0), square(2, 0)])
        b = bd.dissolve([square(2, 0), square(0, 0), square(1, 0)])
        self.assertEqual(a, b)


class CommittedFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo = json.loads(bd.Path(build.DED_FILE).read_text(encoding='utf-8'))

    def test_five_deds_each_with_a_name_and_a_townland_count(self):
        names = sorted(f['properties']['name_en'] for f in self.geo['features'])
        self.assertEqual(names, ['Clogher', 'Donegal', 'Laghy', 'Tawnawully', 'Tullynaught'])
        for f in self.geo['features']:
            self.assertGreater(f['properties']['townlands'], 0)
            self.assertLessEqual(f['properties']['with_outline'], f['properties']['townlands'])

    def test_every_ded_is_one_closed_ring_and_credits_tailte(self):
        for f in self.geo['features']:
            self.assertEqual(f['geometry']['type'], 'Polygon')
            ring = f['geometry']['coordinates'][0]
            self.assertEqual(ring[0], ring[-1])
        self.assertIn('Tailte', self.geo['attribution'])

    def test_loader_gives_the_index_what_it_needs(self):
        deds = build.load_ded_outlines()
        self.assertEqual(len(deds), 5)
        self.assertEqual(sorted(deds[0]['properties']), ['ded_id', 'name', 'name_ga', 'townlands'])


if __name__ == '__main__':
    unittest.main()
