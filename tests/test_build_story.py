"""Tests for tools/build_story.py (docs/TOWNLAND_STORY_SPEC.md, DOC-01 to DOC-11 and DOC-06a).
Run from the repo root:

    python -m pytest -q tests/test_build_story.py

The generator is tested through `generate`, which takes already collected events, so no real
repository file is read or written."""

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import build_story as bd

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

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


def estate(year, holdings, tenants):
    return {'id': f'cullionboy:estate:{year}', 'type': 'estate', 'milestone': True,
            'date': {'kind': 'year', 'label': str(year), 'iso': str(year)}, 'sort': f'{year}-01-01',
            'approximate_sort': True, 'title': f'The estate record of {year}',
            'text': f'{tenants} tenants are named in {holdings} holdings.',
            'estate': {'holdings': holdings, 'tenants': tenants},
            'people': [], 'media': [], 'association': {'basis': 'townland_entry', 'label': ''},
            'source': {'label': 'Estate', 'url': '', 'reference': ''}}


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
        self.assertEqual(doc['generated_by'], 'donegal-townlands.build_story')


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


class EstateBeatTests(unittest.TestCase):
    """Estate records before Griffith's (the user, 2026-11-24): one beat per dated estate source."""

    def test_estate_beats_come_first_and_say_the_numbers(self):
        doc, _ = build([estate(1825, 17, 22), estate(1831, 22, 22)] + FULL)
        beats = beats_of(doc)
        kinds = [b['kind'] for b in beats]
        self.assertEqual(kinds[:4], ['title', 'estate', 'estate', 'valuation'])
        caps = [b['caption'] for b in beats if b['kind'] == 'estate']
        self.assertIn('seventeen holdings', caps[0])
        self.assertIn('22 tenants', caps[0])
        self.assertIn('1831', caps[1])
        self.assertEqual(beats[0]['caption'].split('. ')[1][:23], 'Its story here runs fro')
        self.assertIn('from 1825', beats[0]['caption'])

    def test_estate_counts_are_carried(self):
        doc, _ = build([estate(1825, 17, 22)] + FULL)
        b = [b for b in beats_of(doc) if b['kind'] == 'estate'][0]
        self.assertEqual(b['counts'], {'holdings': 17, 'tenants': 22})


class NoChangeBeatTests(unittest.TestCase):
    """The user chose on 2026-11-22 to drop the second telling of each census year."""

    def test_each_census_year_is_told_once(self):
        doc, _ = build(FULL)
        kinds = [b['kind'] for b in beats_of(doc)]
        self.assertEqual(kinds.count('census'), 3)
        self.assertNotIn('change', kinds)
        self.assertFalse(hasattr(bd, 'change_beat'))

    def test_people_are_written_like_households(self):
        doc, _ = build([census(1911, 6, 2), census(1926, 3, 2)])
        caps = [b['caption'] for b in beats_of(doc) if b['kind'] == 'census']
        self.assertTrue(any('six people in two households' in c for c in caps), caps)
        self.assertTrue(any('three people in two households' in c for c in caps), caps)
        doc, _ = build(FULL)
        self.assertTrue(any('93 people in eighteen households' in b['caption'] for b in beats_of(doc)))


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
        self.assertEqual(bs[-1]['caption'], 'The story reaches 1954 here.')   # no repeated census figure after a later photograph

    def test_undated_or_loose_dates_are_not_placed(self):
        row = dict(self.ROW, date='c. 1950s')
        doc, _ = bd.generate('Cullionboy', 'cullionboy', PLACE, FULL, today=TODAY, dated=[row])
        self.assertFalse([b for b in beats_of(doc) if b['kind'] == 'photo'])

    def test_census_beats_carry_counts(self):
        doc, _ = build(FULL)
        c = next(b for b in beats_of(doc) if b['id'].endswith('census:1911'))
        self.assertEqual(c['counts'], {'people': 72, 'households': 16})


class ParishPhotoTests(unittest.TestCase):
    def test_parish_photograph_rides_on_baptism_beats_only(self):
        evs = FULL + [baptism('A', '1875-06-11', 'Joseph Kelly', 'Thomas Kelly', 'Margaret Carr')]
        doc, _ = bd.generate('Cullionboy', 'cullionboy', PLACE, evs, today=TODAY, parish_files=['church.jpg'])
        for b in beats_of(doc):
            self.assertEqual(b['media'], ['church.jpg'] if b['kind'] == 'baptism' else [] if b['kind'] != 'title' else b['media'])


class TimingTests(unittest.TestCase):
    def test_duration_has_a_floor_and_a_ceiling(self):
        self.assertEqual(bd.duration_ms('Short.', False), bd.MIN_MS)
        self.assertEqual(bd.duration_ms('word ' * 200, False), bd.MAX_MS)

    def test_duration_follows_word_count(self):
        self.assertEqual(bd.duration_ms(' '.join(['w'] * 20), False), 8000)


class HardeningTests(unittest.TestCase):
    """docs/TOWNLAND_STORY_ROLLOUT_SPEC.md, RO-01 to RO-05."""

    def inputs(self, events, place=PLACE):
        return {'found': {'rows': [], 'errors': []}, 'notes': [], 'feed': {'skipped': [], 'events': events},
                'args': ('Cullionboy', 'cullionboy', place, events, {}, [], TODAY, [], [], [])}

    def run_build(self, events, place=PLACE, only_story=False, collect=None):
        written = []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(bd, 'ROOT', Path(tmp)), \
                mock.patch.object(bd, 'collect', collect or (lambda n, t: (self.inputs(events, place), []))), \
                mock.patch.object(bd, 'write_page', mock.Mock(return_value=Path(tmp) / 'docs' / 'x.html')) as page:
            code = bd.build_story('cullionboy', TODAY, only_story=only_story, written=written)
            return code, written, page, (Path(tmp) / 'townlands' / 'cullionboy' / 'records' / 'story.json').is_file()

    def test_a_failure_is_printed_and_never_raised(self):  # RO-01
        def boom(n, t):
            raise KeyError('x')
        code, written, _, _ = self.run_build([], collect=boom)
        self.assertEqual((code, written), (1, []))

    def test_no_coordinates_builds_the_data_but_no_page(self):  # RO-01
        code, written, page, wrote_json = self.run_build(FULL, place={'logainm_id': 1})
        self.assertEqual(code, 0)
        self.assertTrue(wrote_json)
        page.assert_not_called()
        self.assertEqual(len(written), 1)

    def test_with_coordinates_the_page_is_built(self):
        code, written, page, _ = self.run_build(FULL)
        page.assert_called_once()
        self.assertEqual(len(written), 2)

    def test_only_story_writes_nothing_for_a_thin_case(self):  # RO-05
        code, written, page, wrote_json = self.run_build([census(1901, 93, 18)], only_story=True)
        self.assertEqual((code, written, wrote_json), (0, [], False))
        page.assert_not_called()

    def test_only_story_still_writes_a_case_with_a_story(self):  # RO-05
        code, written, _, wrote_json = self.run_build(FULL, only_story=True)
        self.assertTrue(wrote_json)

    def test_a_missing_case_is_reported_not_raised(self):  # RO-01
        self.assertEqual(bd.build_story('no-such-townland', TODAY), 1)

    def test_the_page_is_byte_identical_on_a_rebuild(self):  # RO-03
        a, _ = build(FULL)
        b, _ = build(list(reversed(FULL)))
        self.assertEqual(bd.render_page(a, {'rows': []}), bd.render_page(b, {'rows': []}))
        self.assertEqual(json.dumps(a, ensure_ascii=False, indent=1), json.dumps(b, ensure_ascii=False, indent=1))

    def test_the_outline_goes_into_the_page_and_never_into_the_story(self):
        doc, _ = build(FULL)
        outline = {'type': 'Polygon', 'coordinates': [[[-8.0, 54.6], [-7.9, 54.6], [-7.9, 54.7], [-8.0, 54.6]]]}
        plain = bd.render_page(doc, {'rows': []})
        drawn = bd.render_page(doc, {'rows': []}, outline)
        self.assertNotIn('"outline_credit"', plain)
        self.assertIn('"outline":{"type":"Polygon"', drawn)
        self.assertIn('"outline_credit":"Townland boundaries', drawn)
        self.assertNotIn('outline', json.dumps(doc))
        self.assertEqual(drawn, bd.render_page(doc, {'rows': []}, outline))      # still deterministic


class CheckDocumentTests(unittest.TestCase):
    """RO-04: the checks that tools/validate.py applies to every committed story.json."""

    def good(self):
        doc, _ = build(FULL)
        return json.loads(json.dumps(doc))

    def problems(self, doc, events=FULL):
        return bd.check_document(doc, events)

    def first(self, doc, kind):
        return next(b for c in doc['chapters'] for b in c['beats'] if b['kind'] == kind)

    def test_a_generated_document_passes(self):
        self.assertEqual(self.problems(self.good()), [])

    def test_wrong_schema_and_missing_keys(self):
        doc = self.good()
        doc['schema'] = 2
        del doc['span']
        got = self.problems(doc)
        self.assertTrue(any('schema' in p for p in got))
        self.assertIn('missing span', got)

    def test_duplicate_ids(self):
        doc = self.good()
        doc['chapters'][-1]['beats'].append(dict(self.first(doc, 'census')))
        self.assertTrue(any('duplicate beat id' in p for p in self.problems(doc)))

    def test_evidence_that_does_not_exist(self):
        doc = self.good()
        self.first(doc, 'census')['evidence']['events'] = ['cullionboy:census:1999']
        self.assertTrue(any('evidence event not found' in p for p in self.problems(doc)))

    def test_a_dash_a_hedge_and_a_loose_number(self):
        doc = self.good()
        b = self.first(doc, 'census')
        for caption, word in ((b['caption'] + ' ' + chr(0x2014), 'dash'), ('There were probably 93 people.', 'hedge'),
                              ('There were 94 people in 1901.', 'not in the evidence')):
            b['caption'] = caption
            self.assertTrue(any(word in p for p in self.problems(doc)), word)

    def test_possibly_only_on_a_possible_beat(self):
        doc = self.good()
        self.first(doc, 'census')['caption'] = 'In 1911, possibly 72 people lived in Cullionboy.'
        self.assertTrue(any('not possible' in p for p in self.problems(doc)))

    def test_beats_out_of_time_order(self):
        doc = self.good()
        doc['chapters'][0]['beats'], doc['chapters'][-1]['beats'] = doc['chapters'][-1]['beats'], doc['chapters'][0]['beats']
        self.assertTrue(any('time order' in p for p in self.problems(doc)))

    def test_an_empty_chapter(self):
        doc = self.good()
        doc['chapters'].append({'id': 'x:ch:y', 'title': 'Y', 'beats': []})
        self.assertTrue(any('empty chapter' in p for p in self.problems(doc)))

    def test_a_thin_case_is_title_and_note_only(self):  # RO-02
        thin, _ = build([census(1901, 93, 18)])
        self.assertEqual(self.problems(thin, [census(1901, 93, 18)]), [])
        del thin['note']
        self.assertTrue(any('needs its note' in p for p in self.problems(thin, [census(1901, 93, 18)])))
        story = self.good()
        self.assertTrue(any('only the title beat' in p for p in self.problems(story, [census(1901, 93, 18)])))


class CensusShapeTests(unittest.TestCase):
    """WP-R2: cases with few census years and cases with a very large population."""

    def test_two_census_years_make_two_census_beats(self):
        doc, _ = build([census(1911, 72, 16), census(1926, 79, 15)])
        kinds = [b['kind'] for b in beats_of(doc)]
        self.assertEqual(kinds.count('census'), 2)
        self.assertNotIn('change', kinds)
        self.assertNotIn('note', doc)

    def test_a_large_population_passes_every_check(self):
        events = [census(1901, 148, 31), census(1911, 139, 29), census(1926, 147, 30)]
        doc, _ = build(events)
        self.assertEqual(bd.check_document(doc, events), [])
        first = next(b for b in beats_of(doc) if b['kind'] == 'census')
        self.assertIn('148', first['caption'])
        self.assertEqual(first['counts'], {'people': 148, 'households': 31})
        self.assertLessEqual(first['duration_ms'], bd.MAX_MS)


@unittest.skipIf(sync_playwright is None, 'Playwright is not installed')
class LargePopulationPlayerTests(unittest.TestCase):
    def test_every_person_is_a_dot_and_the_card_stays_inside_the_screen(self):
        events = [census(1901, 148, 31), census(1911, 139, 29), census(1926, 147, 30)]
        doc, _ = build(events)
        target = next(b for b in beats_of(doc) if b['kind'] == 'census')['id']
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            f = Path(tmp) / 'story.html'
            f.write_text(bd.render_page(doc, {'rows': []}), encoding='utf-8')
            browser = pw.chromium.launch()
            for width in (360, 375, 1440):
                pg = browser.new_page(viewport={'width': width, 'height': 740})
                pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
                pg.goto(f.as_uri() + '#beat=' + target)
                pg.wait_for_timeout(500)
                self.assertEqual(pg.locator('#dotgrid i').count(), 148, width)
                self.assertLessEqual(pg.evaluate('document.documentElement.scrollWidth'), width, width)
                pg.close()
            browser.close()


@unittest.skipIf(sync_playwright is None, 'Playwright is not installed')
class PhoneRegressionTests(unittest.TestCase):
    """Faults found by the sample page checks (docs/TOWNLAND_STORY_ROLLOUT_SPEC.md, RO-10)."""

    PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0000003010100c9fe92ef0000000049454e44ae426082')

    def load(self, doc, reduced=False, width=375):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            folder = Path(tmp)
            (folder / 'media').mkdir()
            (folder / 'media' / 'view.png').write_bytes(self.PNG)
            (folder / 'story.html').write_text(bd.render_page(doc, {'rows': []}), encoding='utf-8')
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={'width': width, 'height': 740},
                                      reduced_motion='reduce' if reduced else 'no-preference')
            pg = ctx.new_page()
            pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
            pg.goto((folder / 'story.html').as_uri())
            pg.wait_for_timeout(300)
            pg.evaluate('window.scrollTo(200, 0)')
            seen = {'scrollX': pg.evaluate('window.scrollX'), 'play': pg.locator('#play').inner_text(),
                    'disabled': pg.locator('#play').is_disabled()}
            browser.close()
        return seen

    def test_a_background_photograph_adds_no_horizontal_scroll(self):
        doc, _ = build(FULL, header=[{'file': 'view.png'}])
        for width in (360, 375, 1440):
            self.assertEqual(self.load(doc, width=width)['scrollX'], 0, width)

    def test_reduced_motion_keeps_the_step_through_label(self):
        seen = self.load(build(FULL)[0], reduced=True)
        self.assertEqual((seen['play'], seen['disabled']), ('Step through', True))


@unittest.skipIf(sync_playwright is None, 'Playwright is not installed')
class ThinPlayerTests(unittest.TestCase):
    """RO-02: for a case with no story the player shows the title card and the note and nothing to play."""

    def page(self, doc):
        errors = []
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            f = Path(tmp) / 'story.html'
            f.write_text(bd.render_page(doc, {'rows': []}), encoding='utf-8')
            browser = pw.chromium.launch()
            pg = browser.new_page(viewport={'width': 375, 'height': 700})
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
            pg.goto(f.as_uri())
            pg.wait_for_timeout(300)
            seen = {'note': pg.locator('.card.cur .note').count(), 'caption': pg.locator('.card.cur .caption').inner_text(),
                    'controls': pg.locator('.controls').is_visible(), 'ribbon': pg.locator('#ribbon').is_visible()}
            browser.close()
        return seen, errors

    def test_a_thin_case_shows_the_note_and_no_controls(self):
        doc, _ = build([census(1901, 93, 18)])
        seen, errors = self.page(doc)
        self.assertEqual(errors, [])
        self.assertEqual(seen['note'], 1)
        self.assertFalse(seen['controls'])
        self.assertFalse(seen['ribbon'])

    def test_a_case_with_no_events_at_all_shows_the_title(self):
        doc, _ = build([])
        seen, errors = self.page(doc)
        self.assertEqual(errors, [])
        self.assertIn('Cullionboy', seen['caption'])
        self.assertEqual(seen['note'], 1)

    def test_a_case_with_a_story_keeps_its_controls(self):
        seen, errors = self.page(build(FULL)[0])
        self.assertEqual(errors, [])
        self.assertEqual(seen['note'], 0)
        self.assertTrue(seen['controls'])


if __name__ == '__main__':
    unittest.main()


class EstateEventTests(unittest.TestCase):
    """build_timeline.estate_events reads the normalised estate observations for a case."""

    def test_druminnin_has_the_1825_and_1831_events(self):
        from tools import build_timeline as bt
        evs = bt.estate_events(bt.ROOT / 'townlands' / 'druminnin', 'Druminnin')
        self.assertEqual([e['date']['label'] for e in evs], ['1825', '1831'])
        self.assertEqual(evs[0]['estate'], {'holdings': 17, 'tenants': 22})
        self.assertEqual(evs[1]['estate'], {'holdings': 22, 'tenants': 22})

    def test_a_case_without_estate_records_has_none(self):
        from tools import build_timeline as bt
        self.assertEqual(bt.estate_events(bt.ROOT / 'townlands' / 'cullionboy', 'Cullionboy'), [])
