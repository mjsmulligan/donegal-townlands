"""Tests for tools/build_timeline.py. Run from the repo root:

    python -m unittest tests.test_build_timeline -v

The register tests use a temporary CSV. The real repository is not written to."""

import csv
import datetime
import tempfile
import unittest
from pathlib import Path

from tools import build_timeline as bt

TODAY = datetime.date(2026, 11, 17)
COLS = ['row_id', 'record_type', 'page', 'record_no', 'image_url', 'reading_1_source', 'reading_1',
        'reading_2_source', 'reading_2', 'status', 'resolved_reading', 'resolution_basis',
        'resolution_by', 'resolution_date', 'resolution_note', 'comment']


def row(row_id, reading, status='agreed', comment='', rtype='baptism'):
    r = {c: '' for c in COLS}
    r.update(row_id=row_id, record_type=rtype, page='10', record_no='1', image_url='https://example.org/p10',
             reading_1=reading, status=status, comment=comment,
             resolved_reading=reading if status in ('agreed', 'resolved') else '')
    return r


def events_from(rows):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'b.csv'
        with path.open('w', encoding='utf-8', newline='') as h:
            w = csv.DictWriter(h, fieldnames=COLS)
            w.writeheader()
            w.writerows(rows)
        return bt.baptism_events('Cullionboy', TODAY, register=path)


GOOD = '11 Jun 1875 | Joseph | F: Thomas Kelly | M: Margaret Carr | Cullionboy | S: James Hone; Bridgt. Harvey | J. W.'


class DateTests(unittest.TestCase):
    def test_exact_date(self):
        self.assertEqual(bt.parse_date('11 Jun 1875'), datetime.date(1875, 6, 11))

    def test_incomplete_dates_are_not_placed(self):
        for text in ('Jun 1875', '1875', 'Decr. 18th', ''):
            self.assertIsNone(bt.parse_date(text), text)


class BaptismTests(unittest.TestCase):
    def test_explicit_townland_is_collected_with_recorded_names(self):
        events, skipped = events_from([row('A', GOOD)])
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e['date']['label'], '11 June 1875')
        self.assertEqual(e['association']['basis'], 'page_place')
        self.assertEqual([p['name'] for p in e['people']][:3], ['Joseph', 'Thomas Kelly', 'Margaret Carr'])
        self.assertEqual(skipped, [])

    def test_disputed_reading_is_left_out_and_reported(self):
        events, skipped = events_from([row('D', GOOD, status='disputed')])
        self.assertEqual(events, [])
        self.assertEqual(skipped[0][0], 'D')

    def test_other_townland_is_not_collected(self):
        other = GOOD.replace('Cullionboy', 'Clogher')
        events, skipped = events_from([row('C', other)])
        self.assertEqual((events, skipped), ([], []))

    def test_blank_place_is_never_attributed(self):
        blank = GOOD.replace('Cullionboy', '')
        events, _ = events_from([row('B', blank)])
        self.assertEqual(events, [])

    def test_blotted_place_is_kept_and_marked_doubtful(self):
        events, _ = events_from([row('K', GOOD, comment='Page notes: Place blotted, reads Cullionboy or similar')])
        self.assertEqual(events[0]['association']['basis'], 'page_place_doubtful')

    def test_marriages_are_never_collected(self):
        events, _ = events_from([row('M', GOOD, rtype='marriage')])
        self.assertEqual(events, [])

    def test_baptism_under_100_years_is_withheld(self):
        recent = GOOD.replace('1875', '1930')
        events, skipped = events_from([row('R', recent)])
        self.assertEqual(events, [])
        self.assertIn('100 years', skipped[0][1])

    def test_title_carries_the_fathers_surname(self):
        events, _ = events_from([row('A', GOOD)])
        self.assertEqual(events[0]['title'], 'Baptism of Joseph Kelly')

    def test_title_without_a_father_names_the_mother_and_gives_no_surname(self):
        events, _ = events_from([row('N', GOOD.replace('F: Thomas Kelly', 'F:'))])
        self.assertEqual(events[0]['title'], 'Baptism of Joseph, child of Margaret Carr')

    def test_every_event_has_a_media_list(self):
        events, _ = events_from([row('A', GOOD)])
        self.assertEqual(events[0]['media'], [])

    def test_inexact_date_is_not_placed(self):
        events, skipped = events_from([row('X', GOOD.replace('11 Jun 1875', 'Jun 1875'))])
        self.assertEqual(events, [])
        self.assertIn('no exact date', skipped[0][1])


class RealCaseTests(unittest.TestCase):
    def test_cullionboy_feed_is_ordered_and_needs_no_links(self):
        feed = bt.events_for('cullionboy', TODAY)
        keys = [(e['sort']) for e in feed['events']]
        self.assertEqual(keys, sorted(keys))
        types = {e['type'] for e in feed['events']}
        self.assertTrue({'valuation', 'census'} <= types)
        for e in feed['events']:
            self.assertTrue(e['id'] and e['source']['label'] and e['association']['basis'])
            self.assertNotIn('person_id', e)
            self.assertNotIn('family', e)

    def test_every_real_event_has_a_media_field_and_nothing_undated(self):
        feed = bt.events_for('cullionboy', TODAY)
        for e in feed['events']:
            self.assertIn('media', e)
            self.assertTrue(e['date']['label'])

    def test_clogher_valuation_comes_from_the_authored_transcription(self):
        feed = bt.events_for('clogher', TODAY)
        val = [e for e in feed['events'] if e['type'] == 'valuation'][0]
        self.assertIn('Parish of Donegal', val['source']['label'])
        self.assertEqual(val['date']['label'], 'The 1850s')

    def test_clogher_baptisms_are_only_those_whose_place_is_clogher(self):
        feed = bt.events_for('clogher', TODAY)
        bap = [e for e in feed['events'] if e['type'] == 'baptism']
        self.assertTrue(bap)
        for e in bap:
            self.assertIn('Clogher.', e['association']['label'])
            self.assertTrue(e['title'].startswith('Baptism of '))

    def test_valuation_is_approximate(self):
        feed = bt.events_for('cullionboy', TODAY)
        val = [e for e in feed['events'] if e['type'] == 'valuation'][0]
        self.assertEqual(val['date']['label'], 'The 1850s')
        self.assertTrue(val['approximate_sort'])


if __name__ == '__main__':
    unittest.main()
