"""Tests for tools/story_report.py (docs/TOWNLAND_STORY_ROLLOUT_SPEC.md, WP-R1 and RO-06).
Run from the repo root:

    python -m pytest -q tests/test_story_report.py
"""

import datetime
import unittest

from tools import story_report as dr

TODAY = datetime.date(2026, 11, 21)


def row(**kw):
    base = {'authored_content': False, 'events': 0, 'baptisms': 0, 'griffiths_occupiers': 0, 'census_years': ''}
    base.update(kw)
    return base


class TierTests(unittest.TestCase):
    def test_tiers_follow_what_is_held(self):
        self.assertEqual(dr.tier(row(authored_content=True, events=8, baptisms=2, griffiths_occupiers=5,
                                     census_years='1901')), 'A full')
        self.assertEqual(dr.tier(row(authored_content=True)), 'B authored')
        self.assertEqual(dr.tier(row(griffiths_occupiers=5, census_years='1901')), 'C valuation+census')
        self.assertEqual(dr.tier(row(baptisms=2, census_years='1901')), 'D census+baptisms')
        self.assertEqual(dr.tier(row(census_years='1901')), 'E census only')
        self.assertEqual(dr.tier(row()), 'F thin')


class CoordinateTests(unittest.TestCase):
    def test_distance_is_in_kilometres(self):
        self.assertAlmostEqual(dr.km((54.68, -7.97), (54.68, -7.97)), 0.0)
        self.assertTrue(10 < dr.km((54.68, -7.97), (54.77, -7.97)) < 11)

    def test_a_far_point_is_flagged_and_not_moved(self):
        rows = [{'coords': 'ok', 'lat': 54.68 + i * 0.001, 'lon': -7.97} for i in range(5)]
        rows.append({'coords': 'ok', 'lat': 55.3, 'lon': -7.97})
        dr.flag_coordinates(rows)
        self.assertTrue(rows[-1]['coords'].startswith('far from the others'))
        self.assertEqual(rows[-1]['lat'], 55.3)
        self.assertTrue(all(r['coords'] == 'ok' for r in rows[:-1]))


class SurveyTests(unittest.TestCase):
    def test_a_missing_case_is_reported_not_raised(self):  # RO-01
        r = dr.survey_case('no-such-townland', TODAY)
        self.assertEqual(r['tier'], 'error')
        self.assertIn('not built', r['note'])

    def test_cullionboy_is_a_full_case_with_a_story(self):
        r = dr.survey_case('cullionboy', TODAY)
        self.assertEqual(r['tier'], 'A full')
        self.assertTrue(r['has_story'])
        self.assertGreater(r['beats'], 5)
        self.assertEqual(r['beats'], sum(r['beats_' + k] for k in dr.KINDS))

    def test_a_logainm_only_case_has_no_story(self):
        r = dr.survey_case('meenabrock', TODAY)
        self.assertEqual(r['tier'], 'F thin')
        self.assertFalse(r['has_story'])
        self.assertEqual(r['beats'], 1)


if __name__ == '__main__':
    unittest.main()
