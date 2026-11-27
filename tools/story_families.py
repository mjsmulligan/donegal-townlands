"""Families for the townland story (docs/TOWNLAND_STORY_SPEC.md, section 10).

For the story a family is a surname (DECISIONS.md, 2026-11-25). Spellings group only through verified rows of
data/reference/surname_variants.csv, as everywhere else in the project. This module reads the records a case
holds and gives the story four things:

  names      the family names each source carries, for the milestone captions, and the number of families
  threads    one thread for each told family: its census households by year, as events the story can cite,
             and where the family appears, which is what the highlight rule ranks
  highlights the threads the lean-back run tells, chosen by rule or by the user's list
  the rule   longest presence first (first source to last), then the most sources, then the most census households

Nothing here changes a source or a variant row. A family with no census household in a year gets no beat for
that year: absence from a return is not told as a departure (TOWNLAND_STORY_SPEC D6)."""
import csv
import json
import re

try:
    from tools import build, events as bt, variants_reference as vr
except ImportError:                  # run as a script from tools/
    import build, events as bt, variants_reference as vr

HIGHLIGHTS = 2
CERTAINTY_NOTE = 'Households headed by the surname.'


def _read(path):
    with open(path, encoding='utf-8-sig', newline='') as h:
        return list(csv.DictReader(h))


def _head(row):
    return str(row.get('r', '')).lower().startswith('head')


class Labels:
    """Spelling to family label. A verified row gives its label; otherwise the spelling as recorded, in the
    mixed case a source gave it (Griffith's index is in capitals, so the case comes from another source)."""

    def __init__(self, mixed_case_spellings):
        self.verified = {}
        for r in vr.load():
            if r['status'] == 'verified':
                for s in r['spellings']:
                    self.verified[vr.key(s)] = r['label']
        self.shown = {}
        for s in mixed_case_spellings:
            if s and s != s.upper():
                self.shown.setdefault(vr.key(s), s)

    def __call__(self, spelling):
        k = vr.key(spelling)
        return self.verified.get(k) or self.shown.get(k) or str(spelling).strip().title()

    def spellings_of(self, label):
        """Every spelling a label stands for: the verified row's list, or the label itself. A label like
        'Gethins (McGettigan)' stands for each name in it."""
        out = set()
        for token in re.split(r'[()]', label):
            token = token.strip()
            if not token:
                continue
            k = vr.key(token)
            out.add(k)
            for r in vr.load():
                if r['status'] == 'verified' and k in {vr.key(s) for s in r['spellings']}:
                    out |= {vr.key(s) for s in r['spellings']}
        return out


def _estate_rows(base):
    path = bt.ESTATE_DIR / (base.name + '_holdings_observations.csv')
    return [r for r in _read(path) if (r.get('source_date') or '').strip().isdigit()] if path.is_file() else []


def _griffiths_rows(base):
    """The occupiers of Griffith's, as {'surname', 'forename'}. The printed page transcribed in content.json is
    the count the story uses (see events.valuation_event); the askaboutireland index is the fallback."""
    content = base / 'content.json'
    if content.is_file():
        rows = (json.loads(content.read_text(encoding='utf-8')).get('griffiths') or {}).get('rows', [])
        if bt.printed_plots(rows):
            return [{'surname': r['occ'].split()[-1], 'forename': ' '.join(r['occ'].split()[:-1]), 'role': 'occupier'}
                    for r in rows if (r.get('occ') or '').strip() and not r.get('nofamily')]
    path = base / 'records' / 'griffiths_index.json'
    if not path.is_file():
        return []
    return [r for r in json.loads(path.read_text(encoding='utf-8')).get('rows', []) if r.get('role') == 'occupier']


def _census(base):
    path = base / 'records' / 'census.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def _top(counter, n=3):
    return [k for k, _ in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0].casefold()))[:n]]


def names(base):
    """{'labels': Labels, 'estate': {year: [label]}, 'valuation': [label], 'census': {year: [label]},
    'families': int}. The lists are the most common family names in each source, for the milestone captions.
    `families` counts the distinct family names across every source the case holds."""
    estate, grif, census = _estate_rows(base), _griffiths_rows(base), _census(base)
    labels = Labels([r.get('interpreted_surname', '') for r in estate] + [p.get('s', '') for y in census for p in census[y]])
    every = set()
    out = {'labels': labels, 'estate': {}, 'valuation': [], 'census': {}}
    by_year = {}
    for r in estate:
        by_year.setdefault(r['source_date'].strip(), {}).setdefault(labels(r.get('interpreted_surname', '')), 0)
        by_year[r['source_date'].strip()][labels(r.get('interpreted_surname', ''))] += 1
    for year, c in by_year.items():
        out['estate'][year] = _top(c)
        every |= set(c)
    c = {}
    for r in grif:
        lab = labels(r.get('surname', ''))
        c[lab] = c.get(lab, 0) + 1
    out['valuation'] = _top(c)
    every |= set(c)
    for year, people in census.items():
        c = {}
        for p in people:
            if _head(p):
                lab = labels(p.get('s', ''))
                c[lab] = c.get(lab, 0) + 1
        out['census'][year] = _top(c)
        every |= set(c)
    out['families'] = len({vr.key(x) for x in every})
    return out


def _heads_phrase(forenames):
    """Hugh, two named Patrick and Neil: a forename that repeats is counted, so nobody is listed twice."""
    seen = []
    for f in forenames:
        if f not in [s for s, _ in seen]:
            seen.append((f, forenames.count(f)))
    bits = [f if n == 1 else f'{n_word(n)} named {f}' for f, n in seen]
    return bits[0] if len(bits) == 1 else ', '.join(bits[:-1]) + ' and ' + bits[-1]


def n_word(n):
    words = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
    return words[n] if n < len(words) else str(n)


def _thread(name, i, fams, caption, sort, census, estate, grif, labels):
    """One family thread: the census households of the family by year and where it appears. `caption` is the
    user's own family caption when there is one; a census year it speaks of gets no second account."""
    spell = {f: labels.spellings_of(f) for f in fams}
    every = set().union(*spell.values())
    years, sources = [], 0
    for y in sorted({r['source_date'].strip() for r in estate}):
        if any(vr.key(r.get('interpreted_surname', '')) in every for r in estate if r['source_date'].strip() == y):
            years.append(int(y)); sources += 1
    if any(vr.key(r.get('surname', '')) in every for r in grif):
        years.append(1855); sources += 1
    events, houses = [], 0
    fid = f'{name.lower()}:family:{i:02d}'
    for y in sorted(census):
        heads = [p for p in census[y] if _head(p) and vr.key(p.get('s', '')) in every]
        if not heads:
            continue
        years.append(int(y)); sources += 1; houses += len(heads)
        if caption and re.search(r'\b' + y + r'\b', caption):
            continue        # the user's own caption already speaks of this census year, so no second account of it
        groups = []
        for f in fams:
            fh = [p for p in heads if vr.key(p.get('s', '')) in spell[f]]
            if fh:
                groups.append((f, [p.get('f', '').strip() for p in fh]))
        events.append(census_event(name, fid, i, y, groups))
    presence = None
    if years:
        a, z = min(years), max(years)
        lab = str(a) if a == z else f'{a} to {z}'
        presence = {'id': f'{name.lower()}:familypresence:{i:02d}', 'type': 'family_presence', 'milestone': False,
                    'date': {'kind': 'range', 'label': lab, 'iso': str(a)}, 'sort': f'{a}-01-01',
                    'approximate_sort': True, 'title': f'The {" and ".join(fams)} family in the records',
                    'text': f'In the records from {lab}.', 'people': [], 'media': [], 'first': a, 'last': z}
    return {'id': fid, 'label': ' and '.join(fams), 'presence': presence, 'labels': fams, 'start_sort': f'{min(years)}-01-01' if years else sort,
            'span': (max(years) - min(years)) if years else 0, 'sources': sources, 'households': houses,
            'events': events, 'spellings': sorted(every)}


def threads(base, name):
    """One thread for each told family, in file order. Where the user has accepted family beats (a family beats
    file and its crosswalk) those are the families, as they have always been. Otherwise every family the
    records hold is a thread, a family being a surname (DECISIONS.md, 2026-11-25 and 2026-11-27).
    {'id', 'label', 'labels', 'start_sort', 'years', 'sources', 'households', 'events'} where `events` are
    the census households of the family, one event for each census year it appears in."""
    beats_file = bt.ASSOC_DIR / (base.name + '_family_beats.csv')
    cross = bt.ASSOC_DIR / (base.name + '_holdings_crosswalk.csv')
    census, estate, grif = _census(base), _estate_rows(base), _griffiths_rows(base)
    labels = Labels([r.get('interpreted_surname', '') for r in estate] + [p.get('s', '') for y in census for p in census[y]])
    if not (beats_file.is_file() and cross.is_file()):
        return auto_threads(name, census, estate, grif, labels)
    status = {r['family']: r['status'] for r in _read(cross)}
    out = []
    for i, row in enumerate(_read(beats_file), start=1):
        fams = [f.strip() for f in row['crosswalk_families'].split(';')]
        if any(status.get(f) != 'accepted' for f in fams):
            continue
        out.append(_thread(name, i, fams, row['caption'], row['sort'], census, estate, grif, labels))
    return out


def auto_threads(name, census, estate, grif, labels):
    """A thread for each family name in the records, in name order. The name is the label of a verified
    variants row or the spelling as recorded, so spellings group only where the user has verified them. A
    thread built here has no authored family caption: it is told by the records alone (`auto`)."""
    found = {}
    for r in estate:
        found.setdefault(labels(r.get('interpreted_surname', '')), None)
    for r in grif:
        found.setdefault(labels(r.get('surname', '')), None)
    for y in census:
        for p in census[y]:
            if _head(p):
                found.setdefault(labels(p.get('s', '')), None)
    out = []
    for i, label in enumerate(sorted((x for x in found if x.strip()), key=str.casefold), start=1):
        t = _thread(name, i, [label], '', '0000-01-01', census, estate, grif, labels)
        t['auto'] = True
        out.append(t)
    return out


MARRIAGES = bt.NORMALISED.parent / 'tawnawilly_marriages_normalised.csv'


def register_event(name, today, display=None):
    """The parish register as one milestone: how many baptisms and marriages it holds for the townland.
    Counts the same rows the baptism events are made from (place stated or doubtful, reading agreed, 100 years
    old), but also the one with only a month, which the timeline cannot place on a day. A marriage entry has no
    townland column, so marriages are counted only if the file gains one; until then none can be placed."""
    if not bt.NORMALISED.is_file():
        return None
    raw = {r['row_id']: r for r in bt.read_rows(bt.REGISTER)} if bt.REGISTER.is_file() else {}
    years = []
    for n in bt.read_rows(bt.NORMALISED):
        if (n.get('townland') or '').strip().casefold() != name.casefold():
            continue
        if (n.get('townland_status') or '').strip() not in bt.PLACE_STATED + bt.PLACE_DOUBTFUL:
            continue
        if (n.get('raw_status') or raw.get(n['row_id'], {}).get('status')) not in ('agreed', 'resolved'):
            continue
        y = (n.get('date_iso') or '')[:4]
        if y.isdigit() and today.year - int(y) >= bt.BAPTISM_MIN_AGE:
            years.append(int(y))
    if not years:
        return None
    marriages = 0
    placed = False
    if MARRIAGES.is_file():
        rows = bt.read_rows(MARRIAGES)
        placed = bool(rows) and 'townland' in rows[0]
        if placed:
            marriages = sum(1 for r in rows if (r.get('townland') or '').strip().casefold() == name.casefold())
    a, z = min(years), max(years)
    label = str(a) if a == z else f'{a} to {z}'
    text = f'{len(years)} baptisms' + (f' and {marriages} marriages' if placed else '') + f' naming {display or name}, {label}.'
    return {
        'id': f'{name.lower()}:register:tawnawilly', 'type': 'register', 'milestone': False,
        'date': {'kind': 'range', 'label': label, 'iso': str(a)}, 'sort': f'{a}-01-01', 'approximate_sort': True,
        'title': 'The Tawnawilly parish register', 'text': text, 'people': [], 'media': [],
        'baptisms': len(years), 'marriages': marriages, 'marriages_placed': placed,
        'association': {'basis': 'page_place', 'label': 'The place is written on the page.'},
        'source': {'label': bt.REGISTER_LABEL, 'url': 'https://registers.nli.ie/registers/vtls000631954', 'reference': 'baptisms'},
    }


def census_event(name, fid, n, year, groups):
    """The households of one family in one census year, as an event the story cites. The numbers and the
    forenames of the heads are in `text`, so a caption built from it can be checked against it."""
    parts = []
    for label, forenames in groups:
        count = len(forenames)
        part = f'{count} {label} household' + ('' if count == 1 else 's')
        named = [f for f in forenames if f]
        if len(groups) == 1 and named:
            part += ', headed by ' + _heads_phrase(named)
        parts.append(part)
    return {
        'id': f'{name.lower()}:familycensus:{n:02d}:{year}', 'type': 'family_census', 'milestone': False,
        'date': {'kind': 'year', 'label': year, 'iso': year}, 'sort': f'{year}-01-01', 'approximate_sort': True,
        'title': f'The {" and ".join(g[0] for g in groups)} households in {year}',
        'text': ' and '.join(parts) + '.', 'people': [], 'media': [], 'family': fid, 'groups': groups,
        'association': {'basis': 'census_surname', 'label': CERTAINTY_NOTE},
        'source': {'label': bt.CENSUS_SOURCE + ', ' + year, 'url': build.NAT_ARCHIVES, 'reference': year},
    }


def highlights(found, base):
    """The ids of the threads the lean-back run tells. A file `<slug>_story_highlights.csv` in
    data/research/associations, with a `family` column, is the user's own list and replaces the rule.
    Without it: longest presence, then most sources, then most census households, then name."""
    mine = bt.ASSOC_DIR / (base.name + '_story_highlights.csv')
    if mine.is_file():
        wanted = [r['family'].strip().casefold() for r in _read(mine)]
        picked = [t['id'] for w in wanted for t in found if w in {x.casefold() for x in [t['label']] + t['labels']}]
        if picked:
            return picked
    ranked = sorted(found, key=lambda t: (-t['span'], -t['sources'], -t['households'], t['label'].casefold()))
    return [t['id'] for t in ranked[:HIGHLIGHTS]]
