"""Tests for tools/build_family_timeline.py. Run: python -m pytest -q tests/test_build_family_timeline.py"""
import csv
import datetime
import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual({l['kind'] for l in feed['links']}, {'names', 'accepted', 'household'})
        for l in feed['links']:
            self.assertLess(ids[l['from']]['sort'], ids[l['to']]['sort'])
            self.assertTrue(l['note'])
        for l in feed['links']:
            pair = (ids[l['from']]['type'], ids[l['to']]['type'])
            if l['kind'] == 'names':
                self.assertEqual(pair, ('marriage', 'baptism'))
            elif l['kind'] == 'accepted':
                self.assertEqual(pair, ('census', 'census'))
            else:
                self.assertIn('census', pair)
                self.assertIn('not reviewed', l['note'])


H1 = ['census_year', 'ded', 'townland', 'firstname', 'surname', 'age', 'sex', 'house_number', 'relation_to_head',
      'relation_to_head_updated', 'marriage_status', 'marriage_years', 'children_born', 'id', 'images', 'occupation',
      'occupation_updated', 'birthplace', 'language', 'language_updated']
HB = ['row_id', 'page', 'record_no', 'date_iso', 'child_forename', 'father_forename', 'father_surname', 'mother_forename',
      'mother_surname', 'townland', 'townland_status', 'sponsor1', 'sponsor2', 'sponsor3', 'sponsor4', 'priest',
      'raw_status', 'confidence', 'rules_applied']
HM = ['row_id', 'page', 'record_no', 'date_iso', 'groom_forename', 'groom_surname', 'bride_forename', 'bride_surname',
      'witness1', 'witness2', 'priest', 'raw_status', 'confidence', 'rules_applied']
_id = [4000]


def person(year, town, house, first, surname, age, rel, years=''):
    _id[0] += 1
    return {'census_year': year, 'ded': 'Test', 'townland': town, 'firstname': first, 'surname': surname, 'age': age,
            'sex': 'M', 'house_number': house, 'relation_to_head': rel, 'relation_to_head_updated': rel,
            'marriage_status': 'Married', 'marriage_years': years, 'children_born': '', 'id': str(_id[0]),
            'images': "[{'id': 'nai000111'}]", 'occupation': 'Farmer', 'occupation_updated': 'Farmer',
            'birthplace': 'Donegal', 'language': 'Irish and English', 'language_updated': 'Irish and English'}


def write(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=header, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


class CensusCardTests(unittest.TestCase):
    """Invented rows in a temporary folder. The surname Zzyzx is in no dictionary, so it stands alone."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write(self.dir / '1901_Test.csv', H1, [
            person(1901, 'Alpha', '1', 'John', 'Zzyzx', 40, 'Head'), person(1901, 'Alpha', '1', 'Mary', 'Zzyzx', 38, 'Wife'),
            person(1901, 'Alpha', '1', 'Anne', 'Smith', 20, 'Servant'),
            person(1901, 'Alpha', '2', 'Pat', 'Other', 50, 'Head'),
            person(1901, 'Beta', '1', 'Joe', 'Zzyzx', 30, 'Head')])
        write(self.dir / '1911_Test.csv', H1, [
            person(1911, 'Alpha', '4', 'John', 'Zzyzx', 50, 'Head', '21'), person(1911, 'Alpha', '4', 'Mary', 'Zzyzx', 48, 'Wife', '21'),
            person(1911, 'Alpha', '4', 'Peter', 'Zzyzx', 10, 'Son')])
        self.events, self.homes = bf.census_events('zzyzx', ['Zzyzx'], self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_card_per_year_and_townland_with_whole_households(self):
        self.assertEqual([e['title'] for e in self.events],
                         ['The 1901 census: Alpha', 'The 1901 census: Beta', 'The 1911 census: Alpha'])
        alpha = self.events[0]
        self.assertEqual(len(alpha['households']), 1)          # House 2 has no Zzyzx and is left out
        people = alpha['households'][0]['people']
        self.assertEqual([p['match'] for p in people], [True, True, False])
        self.assertEqual(people[0]['line'], 'John Zzyzx, age 40, Head, Farmer, Irish and English')
        self.assertEqual(alpha['households'][0]['label'], 'House 1')
        self.assertIn('nai000111', alpha['households'][0]['url'])
        self.assertEqual(alpha['sort'], '1901-03-31')
        self.assertIn('2 people written as Zzyzx in 1 household, among 3 recorded', alpha['text'])

    def accepted(self, rows):
        path = self.dir / 'links.csv'
        write(path, ['from_obs', 'to_obs', 'status'], rows)
        return path

    def test_accepted_links_join_people_and_cards_and_only_when_both_are_listed(self):
        john1901 = self.events[0]['households'][0]['people'][0]['obs']
        john1911 = self.events[2]['households'][0]['people'][0]['obs']
        anne1901 = self.events[0]['households'][0]['people'][2]['obs']
        path = self.accepted([
            {'from_obs': john1901, 'to_obs': john1911, 'status': 'accepted'},
            {'from_obs': anne1901, 'to_obs': 'census1911:test:99999', 'status': 'accepted'},      # other end not on the page
            {'from_obs': self.events[0]['households'][0]['people'][1]['obs'],
             'to_obs': self.events[2]['households'][0]['people'][1]['obs'], 'status': 'rejected'}])
        links = bf.census_accepted_links(self.events, path)
        self.assertEqual(len(links), 1)
        self.assertEqual((links[0]['from'], links[0]['to']), (self.events[0]['id'], self.events[2]['id']))
        self.assertEqual(links[0]['kind'], 'accepted')
        self.assertIn('John Zzyzx (age 40) and John Zzyzx (age 50)', links[0]['note'])
        self.assertEqual(self.events[0]['households'][0]['people'][0]['next'][0]['event'], self.events[2]['id'])
        self.assertEqual(self.events[2]['households'][0]['people'][0]['prev'][0]['event'], self.events[0]['id'])
        self.assertEqual(self.events[0]['households'][0]['people'][1]['next'], [])

    def test_a_missing_links_file_gives_no_links(self):
        self.assertEqual(bf.census_accepted_links(self.events, self.dir / 'none.csv'), [])


class RegisterCensusLinkTests(unittest.TestCase):
    """Marriage and baptism to census household, on names, with the rules that hold a link back."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.names = bf._names()

    def tearDown(self):
        self.tmp.cleanup()

    def world(self, census, marriages=(), baptisms=()):
        write(self.dir / '1911_Test.csv', H1, [r for r in census if r['census_year'] == 1911])
        write(self.dir / '1901_Test.csv', H1, [r for r in census if r['census_year'] == 1901])
        write(self.dir / '1926_skip.csv', H1, [])
        reg = self.dir / 'reg'
        reg.mkdir(exist_ok=True)
        write(reg / 'tawnawilly_marriages_normalised.csv', HM, list(marriages))
        write(reg / 'tawnawilly_baptisms_normalised.csv', HB, list(baptisms))
        census_events, homes = bf.census_events('zzyzx', ['Zzyzx'], self.dir)
        return census_events, homes, reg

    @staticmethod
    def marriage(date='1880-05-01', groom='John', gs='Zzyzx', bride='Mary', bs='Walsh'):
        return {'row_id': 'M1', 'date_iso': date, 'groom_forename': groom, 'groom_surname': gs,
                'bride_forename': bride, 'bride_surname': bs}

    @staticmethod
    def marriage_event(date='1880-05-01'):
        return {'id': 'zzyzx:marriage:M1', 'type': 'marriage', 'sort': date, 'title': 'Marriage of John Zzyzx and Mary Walsh',
                'date': {'label': date}}

    @staticmethod
    def baptism(date='1880-06-01', child='Peter', town='Alpha', status='verified'):
        return {'row_id': 'B1', 'date_iso': date, 'child_forename': child, 'father_forename': 'John', 'father_surname': 'Zzyzx',
                'mother_forename': 'Mary', 'mother_surname': 'Walsh', 'townland': town, 'townland_status': status}

    @staticmethod
    def baptism_event(date='1880-06-01'):
        return {'id': 'zzyzx:baptism:B1', 'type': 'baptism', 'sort': date, 'title': 'Baptism of Peter Zzyzx',
                'date': {'label': date}, 'recorded': '1 Jun 1880 | Peter | F: John Zzyzx | M: Mary Walsh | Alpha | S: A; B | P'}

    def couple(self, year, town='Alpha', house='4', years='', extra=()):
        return [person(year, town, house, 'John', 'Zzyzx', 40, 'Head', years), person(year, town, house, 'Mary', 'Zzyzx', 38, 'Wife', years)] + list(extra)

    def run_links(self, census, marriages=(), baptisms=(), events=()):
        cev, homes, reg = self.world(census, marriages, baptisms)
        all_events = sorted(list(cev) + list(events), key=lambda e: e['sort'])
        links, held = bf.census_register_links(all_events, ['Zzyzx'], homes, reg, self.names)
        return links, held, cev

    def test_marriage_links_to_a_household_whose_years_married_fit(self):
        links, held, cev = self.run_links(self.couple(1911, years='31'), [self.marriage()], events=[self.marriage_event()])
        self.assertEqual(len(links), 1)
        self.assertEqual((links[0]['from'], links[0]['to']), ('zzyzx:marriage:M1', cev[0]['id']))
        self.assertEqual(links[0]['kind'], 'household')
        self.assertIn('31 years married, which fits', links[0]['note'])
        self.assertIn('House 4', links[0]['note'])
        self.assertIn('not reviewed', links[0]['note'])

    def test_years_married_that_do_not_fit_hold_the_link_back(self):
        links, _, _ = self.run_links(self.couple(1911, years='12'), [self.marriage()], events=[self.marriage_event()])
        self.assertEqual(links, [])

    def test_no_years_married_links_on_names_and_says_so(self):
        links, _, _ = self.run_links(self.couple(1901), [self.marriage()], events=[self.marriage_event()])
        self.assertEqual(len(links), 1)
        self.assertIn('gives no years married', links[0]['note'])

    def test_a_marriage_after_the_census_never_links_to_it(self):
        links, _, _ = self.run_links(self.couple(1901), [self.marriage('1905-01-01')], events=[self.marriage_event('1905-01-01')])
        self.assertEqual(links, [])

    def test_the_wifes_married_surname_is_not_compared(self):
        # The register has the maiden name Walsh, the return has the husband's name Zzyzx: still the same couple.
        links, _, _ = self.run_links(self.couple(1911, years='31'), [self.marriage(bs='Walsh')], events=[self.marriage_event()])
        self.assertEqual(len(links), 1)

    def test_a_different_forename_does_not_link(self):
        links, _, _ = self.run_links(self.couple(1911, years='31'), [self.marriage(bride='Bridget')], events=[self.marriage_event()])
        self.assertEqual(links, [])

    def test_two_households_that_both_fit_are_held_open_not_chosen_between(self):
        census = self.couple(1911, house='4', years='31') + self.couple(1911, town='Beta', house='9', years='31')
        links, held, _ = self.run_links(census, [self.marriage()], events=[self.marriage_event()])
        self.assertEqual(links, [])
        self.assertEqual(held, [{'event': 'zzyzx:marriage:M1', 'census': 1911, 'households': 2}])

    def test_a_close_spelling_links_and_the_difference_is_stated(self):
        census = [person(1911, 'Alpha', '4', 'John', 'Zzyzxx', 40, 'Head', '31'), person(1911, 'Alpha', '4', 'Mary', 'Zzyzxx', 38, 'Wife', '31'),
                  person(1911, 'Alpha', '4', 'Tom', 'Zzyzx', 10, 'Son')]
        links, _, _ = self.run_links(census, [self.marriage()], events=[self.marriage_event()])
        self.assertEqual(len(links), 1)
        self.assertIn('the register writes Zzyzx and the return writes Zzyzxx', links[0]['note'])

    def test_an_unrelated_surname_does_not_link(self):
        census = [person(1911, 'Alpha', '4', 'John', 'Quill', 40, 'Head', '31'), person(1911, 'Alpha', '4', 'Mary', 'Quill', 38, 'Wife', '31'),
                  person(1911, 'Alpha', '4', 'Tom', 'Zzyzx', 10, 'Son')]
        links, _, _ = self.run_links(census, [self.marriage()], events=[self.marriage_event()])
        self.assertEqual(links, [])

    def test_baptism_links_parents_in_the_same_townland(self):
        links, _, cev = self.run_links(self.couple(1901), baptisms=[self.baptism()], events=[self.baptism_event()])
        self.assertEqual(len(links), 1)
        self.assertEqual((links[0]['from'], links[0]['to']), ('zzyzx:baptism:B1', cev[0]['id']))
        self.assertEqual(links[0]['label'], 'Parents in household')
        self.assertIn('21 years after the baptism', links[0]['note'])

    def test_a_child_whose_name_and_age_fit_is_the_stronger_label(self):
        son = person(1901, 'Alpha', '4', 'Peter', 'Zzyzx', 20, 'Son')
        links, _, _ = self.run_links(self.couple(1901, extra=[son]), baptisms=[self.baptism()], events=[self.baptism_event()])
        self.assertEqual(links[0]['label'], 'Child and parents in household')
        self.assertIn('a son named Peter, age 20', links[0]['note'])

    def test_a_child_of_the_wrong_age_gives_the_parents_label_only(self):
        son = person(1901, 'Alpha', '4', 'Peter', 'Zzyzx', 5, 'Son')
        links, _, _ = self.run_links(self.couple(1901, extra=[son]), baptisms=[self.baptism()], events=[self.baptism_event()])
        self.assertEqual(links[0]['label'], 'Parents in household')

    def test_baptism_needs_the_same_townland_and_a_sound_reading(self):
        for town, status in (('Beta', 'verified'), ('Alpha', 'ambiguous'), ('', ''), ('Alpha', 'probable')):
            links, _, _ = self.run_links(self.couple(1901), baptisms=[self.baptism(town=town, status=status)], events=[self.baptism_event()])
            self.assertEqual(links, [], (town, status))

    def test_baptism_beyond_the_window_does_not_link(self):
        links, _, _ = self.run_links(self.couple(1911), baptisms=[self.baptism('1870-01-01')], events=[self.baptism_event('1870-01-01')])
        self.assertEqual(links, [])

    def test_link_runs_from_the_earlier_record_to_the_later(self):
        links, _, cev = self.run_links(self.couple(1901), baptisms=[self.baptism('1910-01-01')], events=[self.baptism_event('1910-01-01')])
        self.assertEqual((links[0]['from'], links[0]['to']), (cev[0]['id'], 'zzyzx:baptism:B1'))


if __name__ == '__main__':
    unittest.main()
