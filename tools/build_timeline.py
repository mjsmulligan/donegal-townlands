"""Build a townland timeline page.  Separate from the gallery walk (tools/build.py).
Usage:
    python tools/build_timeline.py cullionboy

Two steps, both derived and regenerated every run:

  1. Collect the source events that genuinely name or belong to the townland and write them to
     townlands/<name>/records/timeline_events.json (one event per source record, never edited by hand).
  2. Render engine/timeline.html with that feed into docs/<name>/timeline.html.

The page is an event-led chronology (docs/TIMELINE_SPEC.md). An event never needs a person or
family link to appear, and nothing is attributed to the townland unless the source says so.

Events collected:
  valuation   Griffith's Valuation, from the askaboutireland index (an approximate date, the 1850s)
  census      the 1901, 1911 and 1926 returns for the townland, from records/census.json
  baptism     a register baptism whose own place field reads exactly the townland name and whose
              reading is agreed or resolved. A disputed row is left out and reported. A row whose
              place is noted as blotted or doubtful is kept and marked, not hidden.
  media       every event carries a `media` list. The first header image is the page background.
              Another photograph is attached to an event by the optional `event` column in media.csv.
              Nothing undated is shown: a photograph with no event is left off the timeline

Marriages are never collected: the register records no townland for them.

Privacy (CLAUDE.md, 100/75/50): a baptism is published only when it is 100 or more years old.
Census returns are published as the custodian released them.

This module reads files and writes only the two outputs above. Nothing is ever deleted."""
import csv, datetime, json, pathlib, re, sys
try:
    from tools import build, media
except ImportError:                  # run as a script: python tools/build_timeline.py
    import build, media

ROOT = build.ROOT
REGISTER = ROOT / 'data' / 'source' / 'nli_parish' / 'tawnawilly' / 'raw' / 'tawnawilly_baptisms_raw.csv'
REGISTER_LABEL = 'Tawnawilly parish register (Raphoe), NLI microfilm 04599/04'
CENSUS_SOURCE = 'National Archives of Ireland, census of Ireland'
CENSUS_CREDIT = ('Census returns: National Archives of Ireland. The 1926 census is licensed CC BY 4.0. '
                 'Names are given as the census recorded them.')
MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], start=1)}
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
               'September', 'October', 'November', 'December']
BAPTISM_MIN_AGE = 100
TYPE_ORDER = {'valuation': 0, 'baptism': 1, 'census': 2}


def parse_date(text):
    """'11 Jun 1875' -> datetime.date. Anything incomplete (a month and year only, a year only,
    a clerk's 'Decr. 18th') returns None: the event is then not placed on an exact day."""
    m = re.fullmatch(r'\s*(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})\s*', text or '')
    if not m or m.group(2).lower() not in MONTHS:
        return None
    try:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def long_date(d):
    return f'{d.day} {MONTH_NAMES[d.month - 1]} {d.year}'


def parse_baptism(reading):
    """Split one register string ('date | child | F: x | M: y | place | S: a; b | priest') into
    the recorded parts, exactly as written. Returns None if it is not that shape."""
    parts = [p.strip() for p in (reading or '').split(' | ')]
    if len(parts) < 6:
        return None
    date, child, father, mother, place, sponsors = parts[:6]
    strip = lambda s, tag: s[len(tag):].strip() if s.startswith(tag) else s
    return {'date': date, 'child': child, 'father': strip(father, 'F:'), 'mother': strip(mother, 'M:'),
            'place': place, 'sponsors': [s.strip() for s in strip(sponsors, 'S:').split(';') if s.strip()]}


def baptism_title(parsed):
    """The card title. The register writes only the child's first name, so the surname shown is the
    father's recorded surname (his last word as written). With no father recorded the title names
    the mother in full instead, and never invents a surname for the child."""
    child = parsed['child']
    words = parsed['father'].split()
    if words:
        return f"Baptism of {child} {words[-1].rstrip('.,;')}"
    if parsed['mother'].strip():
        return f"Baptism of {child}, child of {parsed['mother'].strip()}"
    return f'Baptism of {child}'


def place_doubtful(row, parsed):
    note = row.get('comment', '')
    return bool(re.search(r'place\s+(blotted|illegible|unclear|doubtful)', note, re.I) or '[?]' in parsed['place'])


def baptism_events(name, today, register=None):
    """Return (events, skipped). skipped lists rows that name the townland but are not published,
    with the reason, so nothing disappears silently."""
    path = pathlib.Path(register) if register else REGISTER
    events, skipped = [], []
    if not path.is_file():
        return events, skipped
    with path.open(encoding='utf-8', newline='') as h:
        for row in csv.DictReader(h):
            if row.get('record_type') != 'baptism':
                continue
            seen = ' '.join([row.get('reading_1', ''), row.get('reading_2', ''), row.get('resolved_reading', '')])
            if name.casefold() not in seen.casefold():
                continue
            if row.get('status') not in ('agreed', 'resolved'):
                skipped.append((row['row_id'], 'reading ' + (row.get('status') or 'unset') + ', not published'))
                continue
            parsed = parse_baptism(row.get('resolved_reading') or '')
            if not parsed or parsed['place'].rstrip('?[] ').casefold() != name.casefold():
                continue
            day = parse_date(parsed['date'])
            if not day:
                skipped.append((row['row_id'], 'no exact date, not placed'))
                continue
            if today.year - day.year < BAPTISM_MIN_AGE:
                skipped.append((row['row_id'], 'under 100 years old, not published'))
                continue
            doubt = place_doubtful(row, parsed)
            people = [{'name': parsed['child'], 'role': 'child baptised'}]
            if parsed['father']:
                people.append({'name': parsed['father'], 'role': 'father'})
            if parsed['mother']:
                people.append({'name': parsed['mother'], 'role': 'mother'})
            people += [{'name': s, 'role': 'sponsor'} for s in parsed['sponsors']]
            bits = []
            if parsed['father']:
                bits.append('Father: ' + parsed['father'] + '.')
            if parsed['mother']:
                bits.append('Mother: ' + parsed['mother'] + '.')
            if parsed['sponsors']:
                bits.append('Sponsors: ' + ' and '.join(parsed['sponsors']) + '.')
            events.append({
                'id': f'{name.lower()}:baptism:{row["row_id"]}',
                'type': 'baptism',
                'date': {'kind': 'exact', 'label': long_date(day), 'iso': day.isoformat()},
                'sort': day.isoformat(),
                'title': baptism_title(parsed),
                'text': ' '.join(bits),
                'people': people,
                'media': [],
                'association': {
                    'basis': 'page_place_doubtful' if doubt else 'page_place',
                    'label': ('The place is blotted on the page and reads as ' if doubt else 'The page gives the place as ')
                             + name + '.'},
                'source': {'label': REGISTER_LABEL + ', page ' + str(row['page']),
                           'url': row.get('image_url', ''), 'reference': row['row_id']},
                'recorded': row['resolved_reading'],
            })
    return events, skipped


def valuation_event(base, name):
    idx = base / 'records' / 'griffiths_index.json'
    if not idx.is_file():
        return None
    data = json.loads(idx.read_text(encoding='utf-8'))
    rows = [r for r in data.get('rows', []) if r.get('role') == 'occupier']
    if not rows:
        return None
    return {
        'id': f'{name.lower()}:valuation:griffiths',
        'type': 'valuation',
        'milestone': True,
        'date': {'kind': 'range', 'label': 'The 1850s', 'iso': '1850/1859'},
        'sort': '1855-07-01',
        'approximate_sort': True,
        'title': "Griffith's Valuation",
        'text': f'The land and its occupiers were valued and listed. {len(rows)} occupiers are named for the townland.',
        'people': [],
        'media': [],
        'association': {'basis': 'townland_entry', 'label': 'A valuation entry for the townland.'},
        'source': {'label': "Griffith's Valuation, askaboutireland.ie index", 'url': rows[0].get('listing_url', ''),
                   'reference': f"index place {data.get('askaboutireland_place_id', '')}"},
    }


def census_events(base, name, spellings):
    path = base / 'records' / 'census.json'
    if not path.is_file():
        return []
    census = json.loads(path.read_text(encoding='utf-8'))
    out = []
    for year in sorted(census):
        people = census[year]
        if not people:
            continue
        houses = len({p.get('h') for p in people})
        spelled = spellings.get(year, name)
        out.append({
            'id': f'{name.lower()}:census:{year}',
            'type': 'census',
            'milestone': True,
            'date': {'kind': 'year', 'label': year, 'iso': year},
            'sort': f'{year}-01-01',
            'approximate_sort': True,
            'title': f'The {year} census',
            'text': f'{len(people)} people in {houses} households were recorded in the townland.',
            'people': [],
            'media': [],
            'association': {'basis': 'return_for_townland',
                            'label': ('The return names the townland as ' + spelled + '.'
                                      if spelled != name else 'A return for the townland.')},
            'source': {'label': CENSUS_SOURCE + ', ' + year, 'url': build.NAT_ARCHIVES, 'reference': year},
        })
    return out


def media_items(name):
    """Return (found, background, rows_by_event, unplaced). The first header image is the page
    background. Any other photograph appears only on an event: media.csv has an optional `event`
    column holding an event id. A photograph with no event is not on the timeline (an undated
    photograph is never placed), and is listed in `unplaced` so it is not lost silently."""
    found = build.media_for(name)
    sheet = ROOT / 'townlands' / name / 'media' / 'media.csv'
    event_of = {}
    if sheet.is_file():
        with sheet.open(encoding='utf-8-sig', newline='') as h:
            for r in csv.DictReader(h):
                row = {(k or '').strip().lower(): (v or '').strip() for k, v in r.items() if k is not None}
                if row.get('event'):
                    event_of[row.get('file', '')] = row['event']
    background, by_event, unplaced = None, {}, []
    for r in found['rows']:
        if r.get('scope') == 'townland' and background is None:
            background = r
        elif r['file'] in event_of:
            by_event.setdefault(event_of[r['file']], []).append(r)
        else:
            unplaced.append(r['file'])
    return found, background, by_event, unplaced


def events_for(name, today=None):
    """The event feed for one case: {'events': [...], 'skipped': [...], 'town': {...}}"""
    today = today or datetime.date.today()
    base = ROOT / 'townlands' / name
    town = json.loads((base / 'townland.json').read_text(encoding='utf-8'))
    spell = town.get('census_spelling', {})
    display = town.get('name', name.title())
    events = []
    val = valuation_event(base, display)
    if val:
        events.append(val)
    events += census_events(base, display, spell)
    bap, skipped = baptism_events(display, today)
    events += bap
    events.sort(key=lambda e: (e['sort'], TYPE_ORDER.get(e['type'], 9), e['id']))
    return {'events': events, 'skipped': skipped, 'town': town}


def media_item(found, r):
    url = (found['base_url'] + r['file']) if found['base_url'] else 'media/' + r['file']
    return {'file': r['file'], 'url': url, 'caption': r['caption'], 'alt': r.get('alt') or r['caption'],
            'source': r['source'], 'date': r.get('date', '')}


def build_timeline(name, today=None):
    base = ROOT / 'townlands' / name
    if not (base / 'townland.json').is_file():
        sys.exit('No townland.json for ' + name + ': a timeline needs an authored case.')
    found, background, by_event, unplaced = media_items(name)
    if found['errors']:
        print(name + ': media problems, timeline not built:')
        for e in found['errors']:
            print('  ' + e)
        return 1
    feed = events_for(name, today)
    if not feed['events']:
        print(name + ': no source events, timeline not built.')
        return 1
    known = {e['id'] for e in feed['events']}
    for event_id, rows in by_event.items():
        if event_id not in known:
            print(name + ': media.csv names an event that does not exist, not placed: ' + event_id)
            continue
        for e in feed['events']:
            if e['id'] == event_id:
                e['media'] = [media_item(found, r) for r in rows]
    (base / 'records').mkdir(exist_ok=True)
    out_json = {'townland': feed['town']['name'], 'generated_by': 'tools/build_timeline.py',
                'events': feed['events']}
    (base / 'records' / 'timeline_events.json').write_text(
        json.dumps(out_json, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    walk = ROOT / 'docs' / name / 'index.html'
    payload = {
        'townland': feed['town']['name'],
        'events': feed['events'],
        'background': media_item(found, background) if background else None,
        'walk': 'index.html' if walk.is_file() else '',
        'credit': CENSUS_CREDIT,
    }
    html = (ROOT / 'engine' / 'timeline.html').read_text(encoding='utf-8')
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    page = (html.replace('__TITLE__', build.esc(feed['town']['name'] + ' timeline'))
                .replace('__BRAND__', build.esc(feed['town']['name']))
                .replace('__DATA__', data))
    dest = ROOT / 'docs' / name / 'timeline.html'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding='utf-8')
    build.copy_media(name, found)
    for f in unplaced:
        print('  not on the timeline (no event named in media.csv): ' + f)
    counts = {}
    for e in feed['events']:
        counts[e['type']] = counts.get(e['type'], 0) + 1
    print(name + ': timeline built, ' + ', '.join(f'{n} {t}' for t, n in sorted(counts.items())) + '.')
    for row_id, why in feed['skipped']:
        print('  left out ' + row_id + ': ' + why)
    return 0


def main(argv):
    if len(argv) != 2 or argv[1].startswith('-'):
        sys.exit(__doc__)
    return build_timeline(argv[1])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
