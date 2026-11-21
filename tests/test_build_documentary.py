"""Tests for tools/build_documentary.py (docs/DOCUMENTARY_SPEC.md, DOC-01 to DOC-11 and DOC-06a).
Run from the repo root:

    python -m pytest -q tests/test_build_documentary.py

The generator is tested through `generate`, which takes already collected events, so no real
repository file is read or written."""

import datetime
import json
import unittest

from tools import build_documentary as bd

TODAY = datetime.date(2026, 11, 20)
PLACE = {'logainm_id': 13967, 'latitude': 54.68, 'longitude': -7.97, 'name_ga': 'Cuilleann Buí'}


def census(year, people, houses):
    return {'id': f'cullionboy:census:{year}', 'type': 'census', 'milestone': True,
            'date': {'kind': 'year', 'label': str(year), 'iso': str(year)}, 'sort': f'{year}-01-01',
            'approximate_sort': True, 'title': f'The {year} census',
            'text': f'{people} people in {houses} households were recorded in the townland.',
            'people': [], 'media': [], 'association': {'basis': 'return_for_townland', 'label': ''},
            'source': {'label': 'NAI', 'url': '', 'reference': str(year)}}


def valuation(count=25):
    return {'id': 'cullionboy:valuation:griffiths', 'type': 'valuation', 'milestone': True,
            'date': {'kind': 'range', 'label': 'The 1850s', 'iso': '1850/1859'}, 'sort': '1855-07-01',
            'approximate_sort': True, 'title': "Griffith's Valuation",
            'text': f'The land and its occupiers were valued and listed. {count} occupiers are named for the townland.',
            'people': [], 'media': [], 'association': {'basis': 'townland_entry', 'label': ''},
            'source': {'label': "Griffith's", 'url': '', 'reference': ''}}


def baptism(row, iso, child, father='', mother='', doubt=False):
    y, m, d = iso.split('-')
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
              'October', 'November', 'December']
    people = [{'name': child, 'role': 'child baptised'}]
    if father:
        people.append({'name': father, 'role': 'father'})
    if mother:
        people.append({'name': mother, 'role': 'mother'})
    return {'id': f'cullionboy:baptism:{row}', 'type': 'baptism',
            'date': {'kind': 'exact', 'label': f'{int(d)} {months[int(m) - 1]} {y}', 'iso': iso},
            'sort': iso, 'title': 'Baptism of ' + child, 'text': '', 'people': people, 'media': [],
            'association': {'basis': 'page_place_doubtful' if doubt else 'page_place', 'label': ''},
            'source': {'label': 'Register', 'url': '', 'reference': row}}


def build(events, **kw):
    return bd.generate('Cullionboy', 'cullionboy', PLACE, events, today=TODAY, **kw)


def beats_of(doc):
    return [b for c in doc['chapters'] for b in c['beats']]


FULL = [valuation(), census(1901, 93, 18), census(1911, 72, 16), census(1926, 79, 15)]


class GenerationTests(unittest.TestCase):
    def test_required_fields_and_unique_ids(self):  # DOC-02
        doc, _ = build(FULL)
        ids = [b['id'] for b in beats_of(doc)]
        self.assertEqual(len(ids), len(set(ids)))
        for b in beats_of(doc):
            for f in bd.REQUIRED:
                self.assertTrue(b[f] not in (None, '', {}), (b['id'], f))

    def test_deterministic(self):  # DOC-03
        a, _ = build(FULL)
        b, _ = build(list(reversed(FULL)))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_beats_in_time_order_and_no_empty_chapter(self):  # DOC-04
        doc, _ = build(FULL + [baptism('A', '1875-06-11', 'Joseph Kelly', 'Thomas Kelly', 'Margaret Carr')])
        sorts = [b['time']['sort'] for b in beats_of(doc)]
        self.assertEqual(sorts, sorted(sorts))
        for c in doc['chapters']:
            self.assertTrue(c['beats'])

    def test_every_evidence_event_exists(self):  # DOC-05
        doc, _ = build(FULL)
        known = {e['id'] for e in FULL}
        for b in beats_of(doc):
            for eid in b['evidence']['events']:
                self.assertIn(eid, known)
        bad = dict(beats_of(doc)[2])
        bad['evidence'] = dict(bad['evidence'], events=['cullionboy:census:1999'])
        self.assertTrue(any('not found' in p for p in bd.check_beat(bad, {e['id']: e for e in FULL}, known)))

    def test_missing_caption_is_named(self):  # DOC-02
        doc, _ = build(FULL)
        b = dict(beats_of(doc)[1], caption='')
        self.assertIn('missing caption', bd.check_beat(b, {e['id']: e for e in FULL}, {e['id'] for e in FULL}))

    def test_the_same_pages_produce_one_file_only(self):  # DOC-01
        doc, refused = build(FULL)
        self.assertEqual(refused, [])
        self.assertEqual(doc['schema'], 1)
        self.assertEqual(doc['generated_by'], 'donegal-townlands.build_documentary')


class CaptionTests(unittest.TestCase):
    def check(self, caption, certainty='stated', kind='census'):
        doc, _ = build(FULL)
        b = dict(next(x for x in beats_of(doc) if x['kind'] == kind), caption=caption)
        b['evidence'] = dict(b['evidence'], certainty=certainty)
        by = {e['id']: e for e in FULL}
        return bd.check_beat(b, by, set(by))

    def test_dash_characters_fail(self):  # DOC-06
        self.assertTrue(any('dash' in p for p in self.check('In 1901 there were 93 people ' + chr(0x2014) + ' many.')))

    def test_source_talk_and_hedges_fail(self):  # DOC-06
        self.assertTrue(any('source talk' in p for p in self.check('The records show 93 people in 1901.')))
        self.assertTrue(any('hedge' in p for p in self.check('In 1901 there were probably 93 people.')))

    def test_possibly_only_where_possible(self):  # DOC-06a
        self.assertTrue(any('not possible' in p for p in self.check('In 1901 there were possibly 93 people.')))
        self.assertTrue(any('must say' in p for p in self.check('In 1901 there were 93 people.', 'possible')))
        self.assertEqual(self.check('In 1901 there were possibly 93 people.', 'possible'), [])
        self.assertTrue(any('must say' in p for p in
                            self.check('Possibly possibly 93 people in 1901.', 'possible')))

    def test_number_not_in_evidence_fails(self):  # DOC-07
        self.assertTrue(any('not in the evidence' in p for p in self.check('In 1901 there were 94 people.')))
        self.assertTrue(any('not in the evidence' in p for p in self.check('In 1901 there were ninety-four people.')))
        self.assertEqual(self.check('In 1901 there were 93 people.'), [])

    def test_numbers_up_to_twenty_are_words(self):
        self.assertEqual(bd.num(16), 'sixteen')
        self.assertEqual(bd.num(93), '93')


class ChangeTests(unittest.TestCase):
    def test_change_states_counts_only(self):  # DOC-08
        doc, _ = build(FULL)
        changes = [b for b in beats_of(doc) if b['kind'] == 'change']
        self.assertEqual(len(changes), 2)
        self.assertIn('down from 93 in 1901', changes[0]['caption'])
        for c in changes:
            for word in bd.CHANGE_BANNED:
                self.assertNotIn(word, c['caption'].lower())

    def test_a_cause_is_refused(self):  # DOC-08
        doc, _ = build(FULL)
        b = dict(next(x for x in beats_of(doc) if x['kind'] == 'change'),
                 caption='By 1911 Cullionboy had 72 people, down from 93 in 1901, because many left.')
        by = {e['id']: e for e in FULL}
        self.assertTrue(any('more than counts' in p for p in bd.check_beat(b, by, set(by))))


class PrivacyTests(unittest.TestCase):
    def test_recent_baptism_is_refused_and_listed(self):  # DOC-09
        recent = baptism('R', '1930-01-02', 'Recent Child')
        doc, refused = build(FULL + [recent])
        self.assertEqual([r[0] for r in refused], [recent['id']])
        self.assertFalse([b for b in beats_of(doc) if b['kind'] == 'baptism'])

    def test_census_is_not_withheld(self):  # CLAUDE.md, 2026-11-02
        doc, refused = build(FULL)
        self.assertEqual(refused, [])
        self.assertEqual(len([b for b in beats_of(doc) if b['kind'] == 'census']), 3)


class BaptismTests(unittest.TestCase):
    def test_doubtful_place_says_possibly_once_and_is_possible(self):  # DOC-06a
        doc, _ = build(FULL + [baptism('B', '1875-06-11', 'Joseph Kelly', 'Thomas Kelly', 'Margaret Carr', doubt=True)])
        b = next(x for x in beats_of(doc) if x['kind'] == 'baptism')
        self.assertEqual(b['evidence']['certainty'], 'possible')
        self.assertEqual(b['caption'].lower().count('possibly'), 1)

    def test_certain_place_is_stated_and_not_hedged(self):
        doc, _ = build(FULL + [baptism('B', '1875-06-11', 'Joseph Kelly', 'Thomas Kelly', 'Margaret Carr')])
        b = next(x for x in beats_of(doc) if x['kind'] == 'baptism')
        self.assertEqual(b['evidence']['certainty'], 'stated')
        self.assertNotIn('possibly', b['caption'].lower())

    def test_several_in_one_year_make_one_beat(self):
        evs = [baptism('A', '1875-03-31', 'Edward Harraghy'), baptism('B', '1875-06-11', 'Joseph Kelly'),
               baptism('C', '1875-07-10', 'Margaret McGinty')]
        doc, _ = build(FULL + evs)
        bs = [x for x in beats_of(doc) if x['kind'] == 'baptism']
        self.assertEqual(len(bs), 1)
        self.assertEqual(len(bs[0]['evidence']['events']), 3)
        self.assertTrue(bs[0]['caption'].startswith('Three children'))


class ThinCaseTests(unittest.TestCase):
    def test_no_events_builds_a_title_and_a_note(self):  # DOC-10
        doc, _ = build([])
        self.assertEqual([b['kind'] for b in beats_of(doc)], ['title'])
        self.assertIn('no story', doc['note'])

    def test_one_event_builds_a_title_and_a_note(self):  # DOC-10
        doc, _ = build([census(1901, 93, 18)])
        self.assertEqual([b['kind'] for b in beats_of(doc)], ['title'])
        self.assertIn('no story', doc['note'])


class MediaTests(unittest.TestCase):
    def test_without_media_there_are_no_photo_beats(self):  # DOC-11
        doc, _ = build(FULL)
        self.assertFalse([b for b in beats_of(doc) if b['kind'] == 'photo'])

    def test_photo_on_an_event_adds_a_beat_and_time(self):  # DOC-11
        row = {'file': 'kelly.jpg', 'caption': 'Bella, Rose & Mary Kate Kelly', 'alt': '', 'source': 'Personal photo'}
        plain, _ = build(FULL)
        withp, _ = build(FULL, by_event={'cullionboy:census:1911': [row]})
        photos = [b for b in beats_of(withp) if b['kind'] == 'photo']
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0]['media'], ['kelly.jpg'])
        self.assertEqual(len(beats_of(withp)), len(beats_of(plain)) + 1)
        self.assertEqual(photos[0]['duration_ms'], bd.duration_ms(photos[0]['caption'], False) + bd.PHOTO_MS)


class DatedPhotoAndCountTests(unittest.TestCase):
    ROW = {'file': 'k.jpg', 'caption': 'Visitors on the farm', 'alt': '', 'source': 'Personal photo',
           'date': '1954', 'scope': 'family'}

    def test_dated_photo_is_placed_by_its_year_and_closing_follows(self):
        doc, _ = bd.generate('Cullionboy', 'cullionboy', PLACE, FULL, today=TODAY, dated=[self.ROW])
        bs = beats_of(doc)
        ph = [b for b in bs if b['kind'] == 'photo']
        self.assertEqual(len(ph), 1)
        self.assertEqual(ph[0]['time']['label'], '1954')
        self.assertEqual(ph[0]['evidence']['certainty'], 'stated')
        self.assertEqual(bs[-1]['kind'], 'closing')
        self.assertIn('1954', bs[-1]['caption'])
        self.assertIn('1954', bs[0]['caption'])

    def test_undated_or_loose_dates_are_not_placed(self):
        row = dict(self.ROW, date='c. 1950s')
        doc, _ = bd.generate('Cullionboy', 'cullionboy', PLACE, FULL, today=TODAY, dated=[row])
        self.assertFalse([b for b in beats_of(doc) if b['kind'] == 'photo'])

    def test_census_and_change_beats_carry_counts(self):
        doc, _ = build(FULL)
        bs = beats_of(doc)
        c = next(b for b in bs if b['id'].endswith('census:1911'))
        self.assertEqual(c['counts'], {'people': 72, 'households': 16})
        ch = next(b for b in bs if b['kind'] == 'change')
        self.assertEqual(ch['counts']['from_people'], 93)


class TimingTests(unittest.TestCase):
    def test_duration_has_a_floor_and_a_ceiling(self):
        self.assertEqual(bd.duration_ms('Short.', False), bd.MIN_MS)
        self.assertEqual(bd.duration_ms('word ' * 200, False), bd.MAX_MS)

    def test_duration_follows_word_count(self):
        self.assertEqual(bd.duration_ms(' '.join(['w'] * 20), False), 8000)


if __name__ == '__main__':
    unittest.main()
