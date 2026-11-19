"""Tests for tools/build_family_timeline.py. Run: python -m pytest -q tests/test_build_family_timeline.py"""
import datetime
import unittest

from tools import build_family_timeline as bf

TODAY = datetime.date(2026, 11, 19)


class FamilyTests(unittest.TestCase):
    def test_dictionary_family_gives_all_spellings(self):
        label, spellings = bf.family_for('guildea')
        self.assertEqual(label, 'Gildea')
        self.assertIn('Gildea', spellings)

    def test_unknown_surname_is_itself(self):
        self.assertEqual(bf.family_for('Zzyzx'), ('Zzyzx', ['Zzyzx']))

    def test_surname_of(self):
        self.assertEqual(bf.surname_of('Patk. Gildea'), 'Gildea')
        self.assertEqual(bf.surname_of(''), '')

    def test_gildea_feed(self):
        feed = bf.events_for('Gildea', TODAY)
        ev = feed['events']
        keys = [e['sort'] for e in ev]
        self.assertEqual(keys, sorted(keys))
        types = {e['type'] for e in ev}
        self.assertTrue({'baptism', 'marriage', 'valuation', 'census'} <= types)
        self.assertEqual(len([e for e in ev if e['type'] == 'valuation']), 1)
        for e in ev:
            self.assertEqual(e['association']['basis'], 'surname')
            self.assertTrue(e['source']['label'])
            if e['type'] == 'marriage':
                self.assertEqual(e['place'], '')
        for e in ev:
            if e['type'] == 'baptism':
                self.assertGreaterEqual(TODAY.year - int(e['sort'][:4]), 100)
            if e['type'] == 'marriage':
                self.assertGreaterEqual(TODAY.year - int(e['sort'][:4]), 75)


class LinkTests(unittest.TestCase):
    def test_surname_relation(self):
        sp = ['Gildea', 'Guildea']
        self.assertEqual(bf.surname_relation('Hilly', 'hilly', sp), 'same')
        self.assertEqual(bf.surname_relation('Gildea', 'Guildea', sp), 'family')
        self.assertEqual(bf.surname_relation('Quigly', 'Quigley', sp), 'similar')
        self.assertIsNone(bf.surname_relation('Kelly', 'Carr', sp))

    def test_gildea_links_are_forward_and_labelled(self):
        feed = bf.events_for('Gildea', TODAY)
        ids = {e['id']: e for e in feed['events']}
        self.assertEqual({l['kind'] for l in feed['links']}, {'names', 'accepted'})
        for l in feed['links']:
            self.assertLess(ids[l['from']]['sort'], ids[l['to']]['sort'])
            self.assertTrue(l['note'])
        for l in feed['links']:
            if l['kind'] == 'names':
                self.assertEqual((ids[l['from']]['type'], ids[l['to']]['type']), ('marriage', 'baptism'))


if __name__ == '__main__':
    unittest.main()
