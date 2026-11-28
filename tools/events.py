"""The event feed behind the townland story (tools/build_story.py, tools/story_families.py).
Not run on its own. It collects the source events that genuinely name or belong to a townland, one event
per source record, and nothing is attributed to the townland unless the source says so.

Events collected:
  valuation   Griffith's Valuation, from the askaboutireland index (an approximate date, the 1850s)
  estate      the 1825 and 1831 estate records, counts only
  census      the 1901, 1911 and 1926 returns for the townland, from records/census.json
  baptism     a register baptism whose own place field reads exactly the townland name and whose
              reading is agreed or resolved. A disputed row is left out and reported. A row whose
              place is noted as blotted or doubtful is kept and marked, not hidden.
  media       a photograph is attached to an event by the optional `event` column in media.csv.

Marriages are never collected: the register records no townland for them.

Privacy (CLAUDE.md, 100/75/50): a baptism is published only when it is 100 or more years old.
Census returns are published as the custodian released them.

This module reads files and writes nothing. Until 2026-11-26 it also rendered a timeline page; the
timeline was removed when the story became the only townland page (DECISIONS.md, 2026-11-26)."""
import csv, datetime, json, pathlib, re
try:
    from tools import build, media
except ImportError:                  # run from the tools folder
    import build, media

ROOT = build.ROOT
REGISTER = ROOT / 'data' / 'source' / 'nli_parish' / 'tawnawilly' / 'raw' / 'tawnawilly_baptisms_raw.csv'
NORMALISED = ROOT / 'data' / 'source' / 'nli_parish' / 'tawnawilly' / 'normalised' / 'tawnawilly_baptisms_normalised.csv'
PLACE_STATED = ('verified', 'dictionary')
PLACE_DOUBTFUL = ('probable', 'possible')
REGISTER_LABEL = 'Tawnawilly parish register (Raphoe), NLI microfilm 04599/04'
CENSUS_SOURCE = 'National Archives of Ireland, census of Ireland'
MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], start=1)}
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
               'September', 'October', 'November', 'December']
BAPTISM_MIN_AGE = 100
ASSOC_DIR = ROOT / 'data' / 'research' / 'associations'
TYPE_ORDER = {'family': 0, 'estate': -1, 'valuation': 0, 'baptism': 1, 'census': 2}
ESTATE_DIR = ROOT / 'data' / 'source' / 'estate_records' / 'arran_donegal' / 'normalised'


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
    if row.get('status') == 'resolved' and (row.get('resolution_by') or '').strip() and \
            re.search(r'place', row.get('resolution_note', ''), re.I):
        return False          # a person has adjudicated the place against the page image
    return bool(re.search(r'place\s+(blotted|illegible|unclear|doubtful)', note, re.I) or '[?]' in parsed['place'])


def read_rows(path):
    with pathlib.Path(path).open(encoding='utf-8-sig', newline='') as h:
        return list(csv.DictReader(h))


def join_name(first, last):
    return ' '.join(x for x in ((first or '').strip(), (last or '').strip()) if x)


def baptism_events(name, today, register=None, normalised=None):
    """Return (events, skipped). Baptisms are read from the normalised register (DECISIONS.md,
    2026-11-21): the place, date, names and sponsors are the normalised spellings, and a baptism is
    attached to a townland only when its normalised place is that townland. The raw file is joined by
    row_id for the page image, the reading status and the clerk's place notes, and its string stays
    on the event as `recorded`. A place that is verified or from the dictionary is stated; a probable
    place is kept and marked doubtful, so it is told with 'possibly'. Ambiguous, unresolved and
    unmapped places are never attributed. skipped lists rows that name the townland but are not
    published, with the reason, so nothing disappears silently."""
    raw_path = pathlib.Path(register) if register else REGISTER
    nor_path = pathlib.Path(normalised) if normalised else NORMALISED
    events, skipped = [], []
    if not nor_path.is_file():
        return events, skipped
    raw = {r['row_id']: r for r in read_rows(raw_path)} if raw_path.is_file() else {}
    for n in read_rows(nor_path):
        if (n.get('townland') or '').strip().casefold() != name.casefold():
            continue
        status = (n.get('townland_status') or '').strip()
        if status not in PLACE_STATED + PLACE_DOUBTFUL:
            continue
        row = raw.get(n['row_id'], {})
        if (n.get('raw_status') or row.get('status')) not in ('agreed', 'resolved'):
            skipped.append((n['row_id'], 'reading ' + (n.get('raw_status') or 'unset') + ', not published'))
            continue
        iso = (n.get('date_iso') or '').strip()
        try:
            day = datetime.date.fromisoformat(iso)
        except ValueError:
            skipped.append((n['row_id'], 'no exact date, not placed'))
            continue
        if today.year - day.year < BAPTISM_MIN_AGE:
            skipped.append((n['row_id'], 'under 100 years old, not published'))
            continue
        raw_parsed = parse_baptism(row.get('resolved_reading') or '') or {'place': ''}
        doubt = status in PLACE_DOUBTFUL or place_doubtful(row, raw_parsed)
        parsed = {'child': (n.get('child_forename') or '').strip(),
                  'father': join_name(n.get('father_forename'), n.get('father_surname')),
                  'mother': join_name(n.get('mother_forename'), n.get('mother_surname')),
                  'sponsors': [n[k].strip() for k in ('sponsor1', 'sponsor2', 'sponsor3', 'sponsor4') if (n.get(k) or '').strip()]}
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
        written = raw_parsed['place'].rstrip('?[] ').strip()
        if written and written.casefold() != name.casefold():
            label = f'The page writes the place as {written}, read as {name}.'
        elif doubt:
            label = 'The place is blotted on the page and reads as ' + name + '.'
        else:
            label = 'The page gives the place as ' + name + '.'
        events.append({
            'id': f'{name.lower()}:baptism:{n["row_id"]}',
            'type': 'baptism',
            'date': {'kind': 'exact', 'label': long_date(day), 'iso': day.isoformat()},
            'sort': day.isoformat(),
            'title': baptism_title(parsed),
            'text': ' '.join(bits),
            'people': people,
            'media': [],
            'association': {'basis': 'page_place_doubtful' if doubt else 'page_place', 'label': label},
            'source': {'label': REGISTER_LABEL + ', page ' + str(n['page']),
                       'url': row.get('image_url', ''), 'reference': n['row_id']},
            'recorded': row.get('resolved_reading', ''),
        })
    return events, skipped


def printed_plots(rows):
    """The plot numbers a printed Griffith's page carries: '4 to 6', '8, 9', '41 a' and the like, as a set."""
    out = set()
    for r in rows:
        t = str(r.get('lot', '')).strip()
        for a, b in re.findall(r'(\d+)\s*to\s*(\d+)', t):
            out |= set(range(int(a), int(b) + 1))
        out |= {int(x) for x in re.findall(r'\d+', re.sub(r'\d+\s*to\s*\d+', '', t))}
    return out


def valuation_event(base, name):
    """Griffith's as one milestone. Taken from the askaboutireland index when the case has one,
    otherwise from the authored transcription in content.json."""
    label, url, ref, count, noun = "Griffith's Valuation", '', '', 0, 'occupiers are named for the townland'
    idx = base / 'records' / 'griffiths_index.json'
    content = base / 'content.json'
    printed = []
    if content.is_file():
        printed = (json.loads(content.read_text(encoding='utf-8')).get('griffiths') or {}).get('rows', [])
    plots = printed_plots(printed)
    if plots and plots == set(range(1, max(plots) + 1)):
        # the printed page, as the user transcribed it, is the count: its numbered plots, not index entries
        count, noun = len(plots), 'plots are numbered for the townland'
        sub = ((json.loads(content.read_text(encoding='utf-8')).get('griffiths') or {}).get('sheet') or {}).get('sub', '')
        where = sub.split('. Ord')[0].strip().rstrip('.') if sub else ''
        label = "Griffith's Valuation" + (', ' + where if where else '') + ', our transcription'
        ref = 'content.json griffiths.rows'
        if idx.is_file():
            idata = json.loads(idx.read_text(encoding='utf-8'))
            irows = [r for r in idata.get('rows', []) if r.get('role') == 'occupier']
            if irows:
                label, url = label + ', and the askaboutireland.ie index', irows[0].get('listing_url', '')
    elif idx.is_file():
        data = json.loads(idx.read_text(encoding='utf-8'))
        rows = [r for r in data.get('rows', []) if r.get('role') == 'occupier']
        count = len(rows)
        if rows:
            label, url = "Griffith's Valuation, askaboutireland.ie index", rows[0].get('listing_url', '')
            ref = f"index place {data.get('askaboutireland_place_id', '')}"
    elif content.is_file():
        g = json.loads(content.read_text(encoding='utf-8')).get('griffiths') or {}
        count = len([r for r in g.get('rows', []) if (r.get('occ') or '').strip()])
        noun = 'entries name an occupier (a person may appear in more than one)'
        sub = (g.get('sheet') or {}).get('sub', '')
        where = sub.split('. Ord')[0].strip().rstrip('.') if sub else ''
        label = "Griffith's Valuation" + (', ' + where if where else '') + ', our transcription'
        ref = 'content.json griffiths.rows'
    if not count:
        return None
    return {
        'id': f'{name.lower()}:valuation:griffiths',
        'type': 'valuation',
        'milestone': True,
        'date': {'kind': 'range', 'label': 'The 1850s', 'iso': '1850/1859'},
        'sort': '1855-07-01',
        'approximate_sort': True,
        'title': "Griffith's Valuation",
        'text': f'The land and its occupiers were valued and listed. {count} {noun}.',
        'people': [],
        'media': [],
        'association': {'basis': 'townland_entry', 'label': 'A valuation entry for the townland.'},
        'source': {'label': label, 'url': url, 'reference': ref},
    }


def estate_events(base, name):
    """Estate records before Griffith's (the Lough 1825 map, the 1831 Arran rental), one event per dated
    source. Read from data/source/estate_records/arran_donegal/normalised/<slug>_holdings_observations.csv
    when the case has one. Rows dated to a decade (Griffith's) are left to the valuation event."""
    path = ESTATE_DIR / (base.name + '_holdings_observations.csv')
    if not path.is_file():
        return []
    groups = {}
    for row in read_rows(path):
        year = (row.get('source_date') or '').strip()
        if year.isdigit():
            groups.setdefault((year, row['source']), []).append(row)
    out = []
    for (year, source), rows in sorted(groups.items()):
        holdings = len({r['holding_id'] for r in rows})
        tenants = len(rows)
        text = f'{tenants} tenants are named in {holdings} holdings.' if holdings != tenants else f'{tenants} tenants are named.'
        sheet = []
        for r in rows:
            who = ' '.join(x for x in (r.get('forename_as_written', '').strip(), r.get('surname_as_written', '').strip()) if x)
            sheet.append({'ref': r['holding_id'], 'name': who, 'rent': (r.get('yearly_rent') or '').strip(),
                          'note': (r.get('notes') or '').strip()})
        out.append({
            'id': f'{name.lower()}:estate:{year}',
            'type': 'estate',
            'milestone': True,
            'date': {'kind': 'year', 'label': year, 'iso': year},
            'sort': f'{year}-01-01',
            'approximate_sort': True,
            'title': f'The estate record of {year}',
            'text': text,
            'estate': {'holdings': holdings, 'tenants': tenants, 'source': source, 'id_type': rows[0].get('id_type', ''), 'rows': sheet},
            'people': [],
            'media': [],
            'association': {'basis': 'townland_entry', 'label': 'An estate record for the townland.'},
            'source': {'label': source, 'url': '', 'reference': path.name},
        })
    return out


def family_events(base, name):
    """Family beats for the story, from `<slug>_family_beats.csv` in data/research/associations. Each row
    names the crosswalk families it draws on, and is used only when every one of those crosswalk rows is
    `accepted` by the user (`<slug>_holdings_crosswalk.csv`). Captions are authored in plain voice."""
    beats = ASSOC_DIR / (base.name + '_family_beats.csv')
    cross = ASSOC_DIR / (base.name + '_holdings_crosswalk.csv')
    if not (beats.is_file() and cross.is_file()):
        return []
    status = {r['family']: r['status'] for r in read_rows(cross)}
    out = []
    for i, row in enumerate(read_rows(beats), start=1):
        fams = [f.strip() for f in row['crosswalk_families'].split(';')]
        if any(status.get(f) != 'accepted' for f in fams):
            continue
        out.append({
            'id': f'{name.lower()}:family:{i:02d}',
            'type': 'family',
            'milestone': True,
            'date': {'kind': 'range', 'label': 'From 1825', 'iso': ''},
            'sort': row['sort'],
            'approximate_sort': True,
            'title': 'The ' + ' and '.join(fams) + (' family' if len(fams) == 1 else ' families'),
            'text': row['caption'],
            'people': [],
            'media': [],
            'association': {'basis': 'accepted_crosswalk', 'label': 'A holdings link the user has accepted.'},
            'source': {'label': 'Estate records and Griffith\'s Valuation, holdings crosswalk',
                       'url': '', 'reference': beats.name},
        })
    return out


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
        # the people in each household, in the order the return lists the households, for the dots
        sizes = {}
        for p in people:
            sizes[p.get('h')] = sizes.get(p.get('h'), 0) + 1
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
            'household_sizes': list(sizes.values()),
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


def case_identity(base):
    """The case's name and census spellings. An authored townland.json wins. A case that is only a
    Logainm place record (no authored files) takes its name from place.json, so every case can have
    a timeline from the records it holds."""
    authored = base / 'townland.json'
    if authored.is_file():
        return json.loads(authored.read_text(encoding='utf-8'))
    place = json.loads((base / 'place.json').read_text(encoding='utf-8'))
    return {'name': place['name_en'], 'census_spelling': {}}


def events_for(name, today=None):
    """The event feed for one case: {'events': [...], 'skipped': [...], 'town': {...}}"""
    today = today or datetime.date.today()
    base = ROOT / 'townlands' / name
    town = case_identity(base)
    spell = town.get('census_spelling', {})
    display = town.get('name', name.title())
    events = []
    val = valuation_event(base, display)
    if val:
        events.append(val)
    events += estate_events(base, display)
    events += family_events(base, display)
    events += census_events(base, display, spell)
    bap, skipped = baptism_events(display, today)
    events += bap
    events.sort(key=lambda e: (e['sort'], TYPE_ORDER.get(e['type'], 9), e['id']))
    return {'events': events, 'skipped': skipped, 'town': town}
