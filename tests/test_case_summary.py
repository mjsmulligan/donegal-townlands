"""The record summary shown on index cards (tools/build.py case_summary)."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from tools import build

TODAY = datetime.date(2026, 11, 23)


class CaseSummaryTests(unittest.TestCase):
    def summary(self, slug, label):
        return dict(build.case_summary(build.ROOT / 'townlands' / slug, label, TODAY))

    def test_a_studied_case_lists_every_source_it_holds(self):
        s = self.summary('cullionboy', 'Cullionboy')
        self.assertEqual(list(s), ['Census', "Griffith's Valuation", 'Parish register', 'Family tree', 'Images'])
        self.assertTrue(s['Census'].startswith('1901 ('))
        self.assertIn('1911', s['Census'])
        self.assertIn('1926', s['Census'])
        self.assertIn('transcribed', s["Griffith's Valuation"])

    def test_census_counts_match_the_returns(self):
        census = json.loads((build.ROOT / 'townlands' / 'aghlem' / 'records' / 'census.json').read_text(encoding='utf-8'))
        s = self.summary('aghlem', 'Aghlem')
        self.assertIn('1901 (%d people)' % len(census['1901']), s['Census'])
        self.assertIn('1926 (%d)' % len(census['1926']), s['Census'])

    def test_a_case_with_only_an_index_says_index_not_transcribed(self):
        self.assertIn('in the index', self.summary('carnbeagh-north', 'Carnbeagh North')["Griffith's Valuation"])

    def test_a_transcribed_case_does_not_say_index(self):
        self.assertNotIn('in the index', self.summary('druminnin', 'Druminnin')["Griffith's Valuation"])

    def test_baptisms_are_the_published_ones(self):
        from tools import build_timeline as bt
        n = len(bt.baptism_events('Cullionboy', TODAY)[0])
        self.assertEqual(self.summary('cullionboy', 'Cullionboy')['Parish register'], '%d baptisms, Tawnawilly (NLI)' % n)

    def test_a_place_record_alone_has_no_lines(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / 'nowhere'
            base.mkdir()
            (base / 'place.json').write_text('{"name_en": "Nowhere"}', encoding='utf-8')
            self.assertEqual(build.case_summary(base, 'Nowhere', TODAY), [])

    def test_no_em_dashes(self):
        for slug in ('cullionboy', 'clogher', 'aghlem'):
            for k, v in self.summary(slug, slug.title()).items():
                self.assertNotIn(chr(0x2014), k + v)


if __name__ == '__main__':
    unittest.main()


class DruminninStudyTests(unittest.TestCase):
    """Druminnin is an authored study (2026-11-24): printed-page plots and the estate records."""

    def test_payload_holds_the_printed_plots_and_estate_records(self):
        payload = build.payload_for('druminnin')
        rows = payload['content']['griffiths']['rows']
        self.assertEqual(len(rows), 38)
        self.assertIn('51', [r['lot'] for r in rows])
        self.assertEqual([e['year'] for e in payload['estate']], ['1825', '1831'])
        self.assertEqual([len(e['rows']) for e in payload['estate']], [22, 22])

    def test_a_case_without_estate_records_has_no_estate_key(self):
        self.assertNotIn('estate', build.payload_for('cullionboy'))
