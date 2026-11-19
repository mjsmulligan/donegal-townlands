"""Build a family timeline: every source event that names a surname, across all townlands held.
An experiment beside the townland timeline (tools/build_timeline.py), using the same template.
Usage:
    python tools/build_family_timeline.py Gildea

The unit is a surname, not a person. An event appears because a surname is written on the record,
never because anyone has been identified or linked, and the page says so. The surname is taken as
a verified family in data/reference/surname_variants.csv (every spelling the dictionary lists), or
as the single spelling given when the dictionary has no family for it.

Events collected, one per source record unless stated:
  baptism    a register baptism whose father's or mother's surname matches (agreed or resolved
             reading, exact date, 100 or more years old). The place is whatever the page wrote.
  marriage   a register marriage whose groom's or bride's surname matches (exact date, 75 or more
             years old). The register gives no townland for marriages, so none is shown.
  valuation  Griffith's Valuation, one event per townland, from the askaboutireland index files, or
             from the authored transcription for a townland with no index.
  census     one event per census year, summing the matching people across every townland in the
             five DEDs held, with the count for each townland.
Sponsors and marriage witnesses are not matched: a surname there says little about the family.

A record matches on the surname as written on the page (or in the census or index), or on the
spelling the project's normalised register file gives it (shown as read as). Nothing is
interpreted beyond that.

Writes data/processed/family_timelines/<slug>.json (the event feed) and docs/families/<slug>.html.
"""
import csv, datetime, glob, json, pathlib, re, sys
try:
    from tools import build, build_timeline as bt
except ImportError:                  # run as a script: python tools/build_family_timeline.py
    import build, build_timeline as bt

ROOT = build.ROOT
REG = ROOT / 'data' / 'source' / 'nli_parish' / 'tawnawilly'
MARRIAGE_MIN_AGE = 75
REGISTER_LABEL = bt.REGISTER_LABEL
TYPE_ORDER = {'valuation': 0, 'baptism': 1, 'marriage': 1, 'census': 2}


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def surname_of(full):
    """The last word of a name as written, without trailing punctuation: 'Patk. Griffith' -> 'Griffith'."""
    words = (full or '').split()
    return words[-1].rstrip('.,;[]?') if words else ''


def family_for(surname, reference=None):
    """(label, spellings) for a surname. The dictionary family when there is one, else just the surname."""
    path = pathlib.Path(reference) if reference else ROOT / 'data' / 'reference' / 'surname_variants.csv'
    wanted = surname.strip().lower()
    with path.open(encoding='utf-8', newline='') as h:
        for row in csv.DictReader(h):
            spellings = [s.strip() for s in row['spellings'].split('|') if s.strip()]
            if wanted in (s.lower() for s in spellings):
                return row['label'], spellings
    return surname.strip().title(), [surname.strip().title()]


def matches(surnames, spellings):
    lowered = {s.lower() for s in spellings}
    return any(s and s.lower() in lowered for s in surnames)


def read_csv(path):
    with pathlib.Path(path).open(encoding='utf-8-sig', newline='') as h:
        return list(csv.DictReader(h))


def read_label(written, normalised, spellings):
    """How a matched surname is described: as written, plus the normalised reading when it differs."""
    if written and written.lower() != (normalised or '').lower() and normalised and \
            normalised.lower() in {s.lower() for s in spellings}:
        return f'{written} (read as {normalised})'
    return written or normalised


def baptism_events(slug_, spellings, today, register=None, normalised=None):
    reg = pathlib.Path(register) if register else REG / 'raw' / 'tawnawilly_baptisms_raw.csv'
    nor = pathlib.Path(normalised) if normalised else REG / 'normalised' / 'tawnawilly_baptisms_normalised.csv'
    norm = {r['row_id']: r for r in read_csv(nor)} if nor.is_file() else {}
    events = []
    for row in read_csv(reg):
        if row.get('record_type') != 'baptism' or row.get('status') not in ('agreed', 'resolved'):
            continue
        parsed = bt.parse_baptism(row.get('resolved_reading') or '')
        if not parsed:
            continue
        n = norm.get(row['row_id'], {})
        father = surname_of(parsed['father']); mother = surname_of(parsed['mother'])
        hits = []
        if matches([father, n.get('father_surname', '')], spellings):
            hits.append("The father's surname is written " + read_label(father, n.get('father_surname', ''), spellings) + '.')
        if matches([mother, n.get('mother_surname', '')], spellings):
            hits.append("The mother's surname is written " + read_label(mother, n.get('mother_surname', ''), spellings) + '.')
        if not hits:
            continue
        day = bt.parse_date(parsed['date'])
        if not day or today.year - day.year < bt.BAPTISM_MIN_AGE:
            continue
        bits = []
        if parsed['father']: bits.append('Father: ' + parsed['father'] + '.')
        if parsed['mother']: bits.append('Mother: ' + parsed['mother'] + '.')
        if parsed['sponsors']: bits.append('Sponsors: ' + ' and '.join(parsed['sponsors']) + '.')
        place = parsed['place'].rstrip('?[] ').strip()
        events.append({
            'id': f'{slug_}:baptism:{row["row_id"]}', 'type': 'baptism',
            'date': {'kind': 'exact', 'label': bt.long_date(day), 'iso': day.isoformat()}, 'sort': day.isoformat(),
            'title': bt.baptism_title(parsed), 'text': ' '.join(bits), 'place': place, 'people': [], 'media': [],
            'association': {'basis': 'surname', 'label': ' '.join(hits)},
            'source': {'label': REGISTER_LABEL + ', page ' + str(row['page']), 'url': row.get('image_url', ''),
                       'reference': row['row_id']},
            'recorded': row['resolved_reading']})
    return events


def marriage_events(slug_, spellings, today, register=None, normalised=None):
    reg = pathlib.Path(register) if register else REG / 'raw' / 'tawnawilly_marriages_raw.csv'
    nor = pathlib.Path(normalised) if normalised else REG / 'normalised' / 'tawnawilly_marriages_normalised.csv'
    norm = {r['row_id']: r for r in read_csv(nor)} if nor.is_file() else {}
    events = []
    if not reg.is_file():
        return events
    for row in read_csv(reg):
        if row.get('record_type') != 'marriage' or row.get('status') not in ('agreed', 'resolved'):
            continue
        parts = [p.strip() for p in (row.get('resolved_reading') or '').split(' | ')]
        if len(parts) < 3 or ' x ' not in parts[1]:
            continue
        groom, bride = [s.strip() for s in parts[1].split(' x ', 1)]
        n = norm.get(row['row_id'], {})
        hits = []
        if matches([surname_of(groom), n.get('groom_surname', '')], spellings):
            hits.append("The groom's surname is written " + read_label(surname_of(groom), n.get('groom_surname', ''), spellings) + '.')
        if matches([surname_of(bride), n.get('bride_surname', '')], spellings):
            hits.append("The bride's surname is written " + read_label(surname_of(bride), n.get('bride_surname', ''), spellings) + '.')
        if not hits:
            continue
        day = bt.parse_date(parts[0])
        if not day or today.year - day.year < MARRIAGE_MIN_AGE:
            continue
        witnesses = parts[2][2:].strip() if parts[2].startswith('W:') else ''
        events.append({
            'id': f'{slug_}:marriage:{row["row_id"]}', 'type': 'marriage',
            'date': {'kind': 'exact', 'label': bt.long_date(day), 'iso': day.isoformat()}, 'sort': day.isoformat(),
            'title': f'Marriage of {groom} and {bride}',
            'text': ('Witnesses: ' + ' and '.join(w.strip() for w in witnesses.split(';') if w.strip()) + '.') if witnesses else '',
            'place': '', 'people': [], 'media': [],
            'association': {'basis': 'surname', 'label': ' '.join(hits) + ' The register gives no townland for marriages.'},
            'source': {'label': REGISTER_LABEL + ', page ' + str(row['page']), 'url': row.get('image_url', ''),
                       'reference': row['row_id']},
            'recorded': row['resolved_reading']})
    return events


def title_case(name):
    return ' '.join(w.capitalize() if w.isupper() else w for w in (name or '').split())


def valuation_events(slug_, spellings):
    events, indexed = [], set()
    for path in sorted(glob.glob(str(ROOT / 'data' / 'source' / 'griffiths' / '*_individuals.csv'))):
        rows = read_csv(path)
        if not rows:
            continue
        town = rows[0]['townland']; indexed.add(town.lower())
        hit = [r for r in rows if matches([r['occupier_surname_as_indexed']], spellings)]
        if hit:
            events.append(valuation_event(slug_, town, [f"{title_case(r['occupier_forename_as_indexed'])} {title_case(r['occupier_surname_as_indexed'])}".strip() for r in hit],
                                          "Griffith's Valuation, askaboutireland.ie index", hit[0].get('details_url', '')))
    for content in sorted(glob.glob(str(ROOT / 'townlands' / '*' / 'content.json'))):
        case = pathlib.Path(content).parent
        town = json.loads((case / 'townland.json').read_text(encoding='utf-8')).get('name', case.name.title()) \
            if (case / 'townland.json').is_file() else case.name.title()
        if town.lower() in indexed:
            continue
        rows = (json.loads(pathlib.Path(content).read_text(encoding='utf-8')).get('griffiths') or {}).get('rows', [])
        hit = [r['occ'] for r in rows if (r.get('occ') or '').strip() and matches([surname_of(r['occ'])], spellings)]
        if hit:
            events.append(valuation_event(slug_, town, hit, "Griffith's Valuation, our transcription", ''))
    return events


def valuation_event(slug_, town, names, source, url):
    names = sorted(set(names))
    return {'id': f'{slug_}:valuation:{slug(town)}', 'type': 'valuation',
            'date': {'kind': 'range', 'label': 'The 1850s', 'iso': '1850/1859'}, 'sort': '1855-07-01',
            'approximate_sort': True, 'title': "Griffith's Valuation, " + town,
            'text': 'Named as occupiers: ' + '; '.join(names) + '.', 'place': town, 'people': [], 'media': [],
            'association': {'basis': 'surname', 'label': 'The occupier surname is written to match the family.'},
            'source': {'label': source, 'url': url, 'reference': town}}


def census_events(slug_, spellings):
    by_year = {}
    for path in sorted(glob.glob(str(ROOT / 'data' / 'source' / 'census' / '*.csv'))):
        year = pathlib.Path(path).stem.rsplit('_', 1)[-1]
        for r in read_csv(path):
            if matches([r['surname']], spellings):
                house = r.get('house_number') or r.get('aform_name') or r.get('id')
                y = by_year.setdefault(year, {})
                t = y.setdefault(r['townland'].strip(), {'people': 0, 'houses': set(), 'spelled': set()})
                t['people'] += 1; t['houses'].add((r['ded'], house)); t['spelled'].add(r['surname'].strip())
    events = []
    for year in sorted(by_year):
        towns = by_year[year]
        total = sum(t['people'] for t in towns.values())
        houses = sum(len(t['houses']) for t in towns.values())
        spelled = sorted({s for t in towns.values() for s in t['spelled']})
        listing = ', '.join(f'{n} {t["people"]}' for n, t in sorted(towns.items(), key=lambda x: (-x[1]['people'], x[0])))
        events.append({'id': f'{slug_}:census:{year}', 'type': 'census', 'milestone': True,
                       'date': {'kind': 'year', 'label': year, 'iso': year}, 'sort': f'{year}-01-01', 'approximate_sort': True,
                       'title': f'The {year} census',
                       'text': f'{total} people in {houses} households across {len(towns)} townlands, written as {", ".join(spelled)}. By townland: {listing}.',
                       'place': f'{len(towns)} townlands', 'people': [], 'media': [],
                       'association': {'basis': 'surname', 'label': 'Counted from the surname as written on the return, in the five DEDs held.'},
                       'source': {'label': bt.CENSUS_SOURCE + ', ' + year, 'url': build.NAT_ARCHIVES, 'reference': year}})
    return events


def events_for(surname, today=None):
    today = today or datetime.date.today()
    label, spellings = family_for(surname)
    s = slug(label)
    events = (baptism_events(s, spellings, today) + marriage_events(s, spellings, today)
              + valuation_events(s, spellings) + census_events(s, spellings))
    events.sort(key=lambda e: (e['sort'], TYPE_ORDER.get(e['type'], 9), e['id']))
    return {'label': label, 'slug': s, 'spellings': spellings, 'events': events}


def build_family(surname, today=None):
    feed = events_for(surname, today)
    if not feed['events']:
        print(surname + ': no source events, page not built.')
        return 1
    out = ROOT / 'data' / 'processed' / 'family_timelines'
    out.mkdir(parents=True, exist_ok=True)
    (out / (feed['slug'] + '.json')).write_text(json.dumps(
        {'family': feed['label'], 'spellings': feed['spellings'], 'generated_by': 'tools/build_family_timeline.py',
         'events': feed['events']}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    spell = ' or '.join(feed['spellings']) if len(feed['spellings']) < 3 else ', '.join(feed['spellings'][:-1]) + ' or ' + feed['spellings'][-1]
    payload = {
        'townland': feed['label'], 'events': feed['events'], 'background': None, 'walk': '',
        'lede': f'A timeline of the records that name {feed["label"]}, across every townland held.',
        'honest': f'Each event is a record where the surname is written {spell}. It is the surname that is matched, not a person: '
                  'nothing here says the people named are related, and none has been linked to another. '
                  'Names are spelled as written. Sponsors and witnesses are not counted.',
        'sources': 'Baptisms and marriages come from our own transcription of the register images held by the National Library of Ireland. '
                   "Griffith's Valuation details come from the askaboutireland.ie index or from our own transcription of the page, as each event says.",
        'credit': bt.CENSUS_CREDIT}
    html = (ROOT / 'engine' / 'timeline.html').read_text(encoding='utf-8')
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    page = (html.replace('__TITLE__', build.esc(feed['label'] + ' family timeline'))
                .replace('__BRAND__', build.esc(feed['label'])).replace('__DATA__', data))
    dest = ROOT / 'docs' / 'families' / (feed['slug'] + '.html')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding='utf-8')
    counts = {}
    for e in feed['events']:
        counts[e['type']] = counts.get(e['type'], 0) + 1
    print(feed['label'] + ' (' + ', '.join(feed['spellings']) + '): ' + ', '.join(f'{n} {t}' for t, n in sorted(counts.items())) + '.')
    return 0


def main(argv):
    if len(argv) != 2 or argv[1].startswith('-'):
        sys.exit(__doc__)
    return build_family(argv[1])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
