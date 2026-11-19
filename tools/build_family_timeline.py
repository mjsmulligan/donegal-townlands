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
import collections, csv, datetime, difflib, glob, json, pathlib, re, sys
try:
    from tools import build, build_timeline as bt, census_links as cl, given_names_reference, variants_reference
except ImportError:                  # run as a script: python tools/build_family_timeline.py
    import build, build_timeline as bt, census_links as cl, given_names_reference, variants_reference

ROOT = build.ROOT
REG = ROOT / 'data' / 'source' / 'nli_parish' / 'tawnawilly'
MARRIAGE_MIN_AGE = 75
REGISTER_LABEL = bt.REGISTER_LABEL
TYPE_ORDER = {'valuation': 0, 'baptism': 1, 'marriage': 1, 'census': 2}
# Census night for each return (the date the households were counted), used to place a census card
# among exact-dated register events.
CENSUS_NIGHT = {'1901': '1901-03-31', '1911': '1911-04-02', '1926': '1926-04-18'}
CENSUS_WINDOW = 30          # years either side of a baptism within which a household can be linked to it.
                            # The register's baptisms are 1872 to 1889 and the first return is 1901, so a shorter
                            # window could never match. The note on each link states the gap.
MARRIAGE_YEARS_DRIFT = 2    # years married as the return gives it, against the marriage date
CHILD_AGE_DRIFT = 2         # age of a child in a household, against the years since the baptism


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
    """One card for Griffith's Valuation: every townland where the surname is an occupier, in name order."""
    found, indexed = {}, set()
    for path in sorted(glob.glob(str(ROOT / 'data' / 'source' / 'griffiths' / '*_individuals.csv'))):
        rows = read_csv(path)
        if not rows:
            continue
        town = rows[0]['townland']; indexed.add(town.lower())
        hit = [r for r in rows if matches([r['occupier_surname_as_indexed']], spellings)]
        if hit:
            found[town] = ([f"{title_case(r['occupier_forename_as_indexed'])} {title_case(r['occupier_surname_as_indexed'])}".strip() for r in hit],
                           "askaboutireland.ie index", hit[0].get('details_url', ''))
    for content in sorted(glob.glob(str(ROOT / 'townlands' / '*' / 'content.json'))):
        case = pathlib.Path(content).parent
        town = json.loads((case / 'townland.json').read_text(encoding='utf-8')).get('name', case.name.title()) \
            if (case / 'townland.json').is_file() else case.name.title()
        if town.lower() in indexed:
            continue
        rows = (json.loads(pathlib.Path(content).read_text(encoding='utf-8')).get('griffiths') or {}).get('rows', [])
        hit = [r['occ'] for r in rows if (r.get('occ') or '').strip() and matches([surname_of(r['occ'])], spellings)]
        if hit:
            found[town] = (hit, 'our transcription', '')
    if not found:
        return []
    towns = sorted(found)
    lines = [f"{t}: " + '; '.join(sorted(set(found[t][0]))) + '.' for t in towns]
    more = [{'label': f'{t}, {found[t][1]}', 'url': found[t][2]} for t in towns]
    return [{'id': f'{slug_}:valuation', 'type': 'valuation',
             'date': {'kind': 'range', 'label': 'The 1850s', 'iso': '1850/1859'}, 'sort': '1855-07-01',
             'approximate_sort': True, 'title': "Griffith's Valuation",
             'text': f"Named as occupiers in {len(towns)} townland{'s' if len(towns) != 1 else ''}:\n" + '\n'.join(lines),
             'place': '', 'people': [], 'media': [],
             'association': {'basis': 'surname', 'label': 'The occupier surname is written to match the family.'},
             'source': {'label': "Griffith's Valuation", 'url': '', 'reference': ', '.join(towns), 'more': more}}]


def census_households(spellings, census_dir=None):
    """Every household in the five DEDs held with at least one person whose surname matches.
    A household is the list of census rows that share a house (1901, 1911) or a form (1926)."""
    rows = cl.load_census(pathlib.Path(census_dir) if census_dir else cl.CENSUS_DIR)
    by_hh = collections.OrderedDict()
    for r in rows:
        by_hh.setdefault(r['hh'], []).append(r)
    return [m for m in by_hh.values() if any(matches([x['surname']], spellings) for x in m)]


def person_entry(r, spellings):
    """One person as the return recorded them. `match` says whether the surname is the one studied."""
    name = ' '.join(x for x in (r['first'].strip(), r['surname'].strip()) if x)
    bits = [name]
    if r['age'] is not None:
        bits.append(f"age {r['age']}")
    bits += [r[k] for k in ('rel', 'occ', 'lang') if r[k]]
    return {'obs': r['obs'], 'name': name, 'age': r['age'], 'relation': r['rel'], 'marital': r['marital_raw'],
            'occupation': r['occ'], 'language': r['lang'], 'birthplace': r['birth'],
            'match': matches([r['surname']], spellings), 'line': ', '.join(bits), 'prev': [], 'next': []}


def _house_key(members):
    house = members[0]['house']
    return (0, int(house), members[0]['loc']) if house.isdigit() else (1, 0, members[0]['loc'])


def census_events(slug_, spellings, census_dir=None):
    """One card per census year and townland (as the return spelled it), listing every household in which
    the surname is written, with everyone recorded in it. Returns (events, homes): homes keeps each
    household's census rows and its card id, for the links."""
    cards = {}
    for members in census_households(spellings, census_dir):
        first = members[0]
        cards.setdefault((str(first['year']), first['ded'].strip(), first['townland'].strip()), []).append(members)
    events, homes, used = [], [], set()
    for (year, ded, town) in sorted(cards, key=lambda k: (k[0], slug(k[2]), k[1])):
        eid = f'{slug_}:census:{year}:{slug(ded)}:{slug(town)}'
        while eid in used:
            eid += '-2'
        used.add(eid)
        households = []
        for n, members in enumerate(sorted(cards[(year, ded, town)], key=_house_key), 1):
            first = members[0]
            label = 'House ' + first['house'] if year != '1926' and first['house'] else f'Household {n}'
            url = build.CENSUS_URLS[year].format(ref=first['ref']) if first['ref'] else ''
            households.append({'label': label, 'url': url, 'people': [person_entry(r, spellings) for r in members]})
            homes.append({'card': eid, 'year': int(year), 'townland': town, 'label': label, 'members': members})
        mine = [p for h in households for p in h['people'] if p['match']]
        everyone = sum(len(h['people']) for h in households)
        spelled = sorted({r['surname'].strip() for h in homes if h['card'] == eid for r in h['members']
                          if matches([r['surname']], spellings)})
        events.append({
            'id': eid, 'type': 'census', 'milestone': True,
            'date': {'kind': 'year', 'label': year, 'iso': year}, 'sort': CENSUS_NIGHT[year],
            'title': f'The {year} census: {town}',
            'text': (f"{len(mine)} {'person' if len(mine) == 1 else 'people'} written as {', '.join(spelled)} in "
                     f"{len(households)} household{'' if len(households) == 1 else 's'}, among {everyone} recorded."),
            'place': ded + ' DED', 'people': [], 'media': [], 'households': households,
            'association': {'basis': 'surname', 'label': 'Each household listed has at least one person whose surname is written to match. '
                                                          'Names, ages and townland are as the return recorded them.'},
            'source': {'label': bt.CENSUS_SOURCE + ', ' + year, 'url': build.NAT_ARCHIVES, 'reference': year}})
    return events, homes


def surname_relation(a, b, spellings):
    """How two surnames as normalised compare: 'same', 'family' (both in the dictionary family studied),
    'similar' (spelling differs slightly, same first letter) or None."""
    a, b = (a or '').strip().lower(), (b or '').strip().lower()
    if not a or not b:
        return None
    if a == b:
        return 'same'
    fam = {x.lower() for x in spellings}
    if a in fam and b in fam:
        return 'family'
    if a[0] == b[0] and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
        return 'similar'
    return None


def _first(forename):
    return (forename or '').strip().lower().split(' ')[0]


def marriage_baptism_links(events, spellings, register_dir=None, max_years=15):
    """A marriage and a later baptism where the groom and bride are written as the father and mother.
    The match is on forenames and surnames as normalised by the project, nothing more."""
    base = pathlib.Path(register_dir) if register_dir else REG / 'normalised'
    mar = {r['row_id']: r for r in read_csv(base / 'tawnawilly_marriages_normalised.csv')}
    bap = {r['row_id']: r for r in read_csv(base / 'tawnawilly_baptisms_normalised.csv')}
    links = []
    for m in (e for e in events if e['type'] == 'marriage'):
        mr = mar.get(m['id'].split(':')[-1])
        if not mr:
            continue
        for b in (e for e in events if e['type'] == 'baptism'):
            br = bap.get(b['id'].split(':')[-1])
            if not br or not (0 < int(b['sort'][:4]) - int(m['sort'][:4]) + 0.5 <= max_years + 1) or b['sort'] <= m['sort']:
                continue
            if _first(mr['groom_forename']) != _first(br['father_forename']) or _first(mr['bride_forename']) != _first(br['mother_forename']):
                continue
            g = surname_relation(mr['groom_surname'], br['father_surname'], spellings)
            w = surname_relation(mr['bride_surname'], br['mother_surname'], spellings)
            if not g or not w:
                continue
            note = "The groom and bride are written as the father and mother."
            diff = [f"{x} and {y}" for x, y, r in ((mr['groom_surname'], br['father_surname'], g), (mr['bride_surname'], br['mother_surname'], w)) if x.lower() != y.lower()]
            if diff:
                note += ' Surnames differ in spelling: ' + '; '.join(diff) + '.'
            links.append({'from': m['id'], 'to': b['id'], 'kind': 'names', 'label': 'Same parents\' names', 'note': note})
    return links


def _who(p):
    return p['name'] + (f" (age {p['age']})" if p['age'] is not None else '')


def census_accepted_links(events, path=None):
    """Census links Mike has accepted (data/research/associations/census_links.csv). A link is used only
    when both rows are on this page, in a household that is listed. Each person gets a pointer to the
    other return, and each pair of cards one note naming the people linked between them."""
    path = pathlib.Path(path) if path else ROOT / 'data' / 'research' / 'associations' / 'census_links.csv'
    if not path.is_file():
        return []
    where = {}
    for e in events:
        for h in e.get('households', []):
            for p in h['people']:
                where[p['obs']] = (e, p)
    pairs = collections.OrderedDict()
    for r in read_csv(path):
        if r.get('status') != 'accepted':
            continue
        a, b = where.get(r['from_obs']), where.get(r['to_obs'])
        if not a or not b:
            continue
        if a[0]['sort'] > b[0]['sort']:
            a, b = b, a
        (ea, pa), (eb, pb) = a, b
        pa['next'].append({'event': eb['id'], 'text': f"{eb['date']['label']}: {_who(pb)}"})
        pb['prev'].append({'event': ea['id'], 'text': f"{ea['date']['label']}: {_who(pa)}"})
        pairs.setdefault((ea['id'], eb['id']), []).append((pa, pb))
    links = []
    for (a, b), people in pairs.items():
        n = len(people)
        links.append({'from': a, 'to': b, 'kind': 'accepted', 'label': 'Reviewed link',
                      'note': f"{n} {'person' if n == 1 else 'people'} linked between these returns in the review: "
                              + '; '.join(f'{_who(x)} and {_who(y)}' for x, y in people) + '.'})
    return links


def _names():
    """Given-name and surname tables as the census matcher uses them: verified rows only."""
    return cl.Names(given_names_reference.load(cl.GIVEN), variants_reference.load())


def _same_forename(names, a, b):
    return names.given(a, b) in ('exact', 'verified')


def _couples(homes):
    """Households with a head and a wife both present: (home, head row, wife row)."""
    out = []
    for h in homes:
        head = next((r for r in h['members'] if r['relc'] == 'head'), None)
        wife = next((r for r in h['members'] if r['relc'] == 'wife'), None)
        if head and wife:
            out.append((h, head, wife))
    return out


def _differences(pairs):
    """Where the register and the return spell a surname differently, say so: the register writes x, the return y."""
    diff = [f'the register writes {x} and the return writes {y}' for x, y in pairs if x and y and x.lower() != y.lower()]
    return (' Surnames differ in spelling: ' + '; '.join(diff) + '.') if diff else ''


def census_register_links(events, spellings, homes, register_dir=None, names=None):
    """Links between a census household and a register event, on names alone. Nothing here is reviewed.

    marriage to census  the groom and bride are written as the head and wife of a later household, with the
                        same forenames and a surname that matches. The return's years married must fit
                        the marriage date, where it gives them. The register names no townland for a
                        marriage, so none is compared. The wife's surname is not compared: the return
                        gives a married woman her husband's name.
    baptism to census   the father and mother are written as the head and wife of a household in the
                        same townland, within CENSUS_WINDOW years of the baptism. The baptism's townland
                        must be a verified or dictionary reading. A child of the same forename whose age
                        fits is noted as a stronger match.
    A household is linked to a record only when it is the one candidate in that return, so two
    households that both fit are held open and listed in the feed rather than chosen between.
    Returns (links, held_open)."""
    names = names or _names()
    base = pathlib.Path(register_dir) if register_dir else REG / 'normalised'
    mar = {r['row_id']: r for r in read_csv(base / 'tawnawilly_marriages_normalised.csv')}
    bap = {r['row_id']: r for r in read_csv(base / 'tawnawilly_baptisms_normalised.csv')}
    couples = _couples(homes)
    found = []      # (event, year, (home, head, wife), label, note)
    held = []

    for m in (e for e in events if e['type'] == 'marriage'):
        mr = mar.get(m['id'].split(':')[-1])
        if not mr:
            continue
        my = int(m['sort'][:4])
        written_groom = surname_of(m['title'].split(' and ')[0].replace('Marriage of ', ''))
        by_year = collections.defaultdict(list)
        for home, head, wife in couples:
            cy = home['year']
            if CENSUS_NIGHT[str(cy)] <= m['sort'] or cy - my > 60:
                continue
            g = surname_relation(mr['groom_surname'], head['surname'], spellings)
            if not (g and _same_forename(names, mr['groom_forename'], head['first'])
                    and _same_forename(names, mr['bride_forename'], wife['first'])):
                continue
            years = wife['marr_years'] if wife['marr_years'] is not None else head['marr_years']
            if years is not None and abs((cy - my) - years) > MARRIAGE_YEARS_DRIFT:
                continue
            note = f"In {home['label']}, the groom and bride are written as the head and wife. "
            note += (f'The return gives {years} years married, which fits the marriage date.' if years is not None
                     else 'The return gives no years married.')
            note += _differences([(written_groom, head['surname'])])
            by_year[cy].append(((home, head, wife), note))
        for cy, cands in by_year.items():
            if len(cands) == 1:
                found.append((m, cy, cands[0][0], "Couple in household", cands[0][1]))
            else:
                held.append({'event': m['id'], 'census': cy, 'households': len(cands)})

    for b in (e for e in events if e['type'] == 'baptism'):
        br = bap.get(b['id'].split(':')[-1])
        if not br or not br['townland'] or br['townland_status'] not in ('verified', 'dictionary'):
            continue
        by = int(b['sort'][:4])
        written_father = surname_of((bt.parse_baptism(b.get('recorded') or '') or {}).get('father', ''))
        tkey = cl.townland_key(br['townland'])
        by_year = collections.defaultdict(list)
        for home, head, wife in couples:
            cy = home['year']
            if abs(cy - by) > CENSUS_WINDOW or cl.townland_key(home['townland']) != tkey:
                continue
            f = surname_relation(br['father_surname'], head['surname'], spellings)
            if not (f and _same_forename(names, br['father_forename'], head['first'])
                    and _same_forename(names, br['mother_forename'], wife['first'])):
                continue
            note = f"In {home['label']}, the father and mother are written as the head and wife, in the same townland."
            note += f" The return is {abs(cy - by)} years {'after' if cy > by else 'before'} the baptism."
            note += _differences([(written_father, head['surname'])])
            child = [r for r in home['members'] if r['relc'] in ('son', 'daughter') and br['child_forename']
                     and _same_forename(names, br['child_forename'], r['first']) and r['age'] is not None
                     and abs(r['age'] - (cy - by)) <= CHILD_AGE_DRIFT]
            label = 'Parents in household'
            if len(child) == 1:
                label = 'Child and parents in household'
                note += f" The household includes a {child[0]['rel'].lower()} named {child[0]['first']}, age {child[0]['age']}, which fits the baptism date."
            by_year[cy].append(((home, head, wife), label, note))
        for cy, cands in by_year.items():
            if len(cands) == 1:
                found.append((b, cy, cands[0][0], cands[0][1], cands[0][2]))
            else:
                held.append({'event': b['id'], 'census': cy, 'households': len(cands)})

    cards = {e['id']: e for e in events}
    links = []
    for ev, cy, (home, head, wife), label, note in found:
        card = cards[home['card']]
        first, second = (ev, card) if ev['sort'] < card['sort'] else (card, ev)
        links.append({'from': first['id'], 'to': second['id'], 'kind': 'household', 'label': label,
                      'note': note + ' Matched on names only, not reviewed.'})
    return links, held


def events_for(surname, today=None, census_dir=None, register_dir=None, links_path=None):
    today = today or datetime.date.today()
    label, spellings = family_for(surname)
    s = slug(label)
    census, homes = census_events(s, spellings, census_dir)
    events = (baptism_events(s, spellings, today) + marriage_events(s, spellings, today)
              + valuation_events(s, spellings) + census)
    events.sort(key=lambda e: (e['sort'], TYPE_ORDER.get(e['type'], 9), e['id']))
    links = marriage_baptism_links(events, spellings, register_dir) + census_accepted_links(events, links_path)
    household_links, held = census_register_links(events, spellings, homes, register_dir)
    return {'label': label, 'slug': s, 'spellings': spellings, 'events': events,
            'links': links + household_links, 'held_open': held}


def build_family(surname, today=None):
    feed = events_for(surname, today)
    if not feed['events']:
        print(surname + ': no source events, page not built.')
        return 1
    out = ROOT / 'data' / 'processed' / 'family_timelines'
    out.mkdir(parents=True, exist_ok=True)
    (out / (feed['slug'] + '.json')).write_text(json.dumps(
        {'family': feed['label'], 'spellings': feed['spellings'], 'generated_by': 'tools/build_family_timeline.py',
         'events': feed['events'], 'links': feed['links'], 'held_open': feed['held_open']},
        ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    spell = ' or '.join(feed['spellings']) if len(feed['spellings']) < 3 else ', '.join(feed['spellings'][:-1]) + ' or ' + feed['spellings'][-1]
    payload = {
        'townland': feed['label'], 'events': feed['events'], 'links': feed['links'], 'background': None, 'walk': '',
        'lede': f'A timeline of the records that name {feed["label"]}, across every townland held.',
        'honest': f'Each event is a record where the surname is written {spell}. It is the surname that is matched, not a person: '
                  'nothing here says the people named are related. A census card lists each household in one townland where the surname is written, '
                  'with everyone the return recorded in it. The "Followed by" and "Follows" notes join records, and each says what it rests on: '
                  'a link marked as reviewed was accepted by hand, and the others are matched on names alone and have not been reviewed. '
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
    print(f"{len(feed['links'])} links."); print(feed['label'] + ' (' + ', '.join(feed['spellings']) + '): ' + ', '.join(f'{n} {t}' for t, n in sorted(counts.items())) + '.')
    return 0


def main(argv):
    if len(argv) != 2 or argv[1].startswith('-'):
        sys.exit(__doc__)
    return build_family(argv[1])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
