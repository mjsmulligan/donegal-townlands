"""Build a townland's story beats (docs/TOWNLAND_STORY_SPEC.md).
Usage:
    python tools/build_story.py cullionboy
    python tools/build_story.py --all     only cases that have a story; also writes the survey report

Reads the case's records through tools/events.py (Griffith's, census and baptism events,
media) and place.json, and writes townlands/<name>/records/story.json. Nothing else is written.
The file is generated and never edited by hand.

A beat is one moment in the story: a kind, a time, a place and camera level, a card to open, a
caption, the evidence behind it and how certain it is. Captions are rule based and deterministic:
the same records give the same file. They follow docs/STORY_SPEC.md (third person, plain words,
evidence only) with one softening agreed 2026-11-20: a link that is possible but not certain may
carry the single word "possibly". The generator checks every beat before writing and stops if one
fails, naming the beat.
"""
import datetime, hashlib, json, pathlib, re, shutil, sys

try:
    from tools import events as bt, story_families as sf, credits
except ImportError:                  # run as a script: python tools/build_story.py
    import events as bt, story_families as sf, credits

ROOT = bt.ROOT
SCHEMA = 1
BAPTISM_MIN_AGE = bt.BAPTISM_MIN_AGE
KIND_ORDER = {'title': 0, 'estate': 1, 'valuation': 1, 'familyintro': 0, 'familyhead': 1, 'family': 2, 'baptism': 2, 'register': 2, 'census': 3, 'familycensus': 3, 'photo': 5, 'closing': 9}
CERTAINTY = ('stated', 'accepted', 'possible')
CAMERAS = ('parish', 'townland', 'household')

# The cover of the Tawnawilly parish register, one image for the whole parish. It is not in any townland's media
# folder: the one web image lives in shared_media/ and is copied once to docs/shared/, and every register beat
# points at it (docs/MEDIA_SPEC.md section 3.5). The original is in data/source/nli_parish/tawnawilly/images/.
COVER_FILE = 'shared/tawnawilly-register-cover.jpg'
COVER_MEDIA = {
    'url': '../shared/tawnawilly-register-cover.jpg',
    'caption': 'The cover of the Tawnawilly parish register, Diocese of Raphoe. Baptisms run from 18 December 1872 '
               'to 30 December 1880 and marriages from 9 January 1873 to 2 October 1880.',
    'alt': 'The handwritten label on the cover of the parish register: Diocese of Raphoe, Parish Tawnawilly, '
           'baptisms December 18 1872 to December 30 1880, marriages January 9 1873 to October 2 1880',
    'source': 'National Library of Ireland, Catholic Parish Registers, microfilm 04599/04',
    'credit': 'nli', 'reference': 'NLI microfilm 04599/04, cover',
}
STAGES = ('map', 'walk', 'timeline')
REQUIRED = ('id', 'kind', 'chapter', 'time', 'place', 'scene', 'caption', 'evidence', 'duration_ms')
WORDS_PER_SECOND = 2.5
MIN_MS, MAX_MS, PHOTO_MS = 4000, 14000, 1000

# Built from code points so this file holds no em dash or en dash character.
DASHES = (chr(0x2014), chr(0x2013))
SOURCE_TALK = ('the records show', 'is recorded as', 'are recorded as', 'was recorded as', 'were recorded as',
               'according to', 'the census taker', 'the register records', 'on the register')
HEDGES = ('probably', 'perhaps', 'maybe', 'presumably', 'likely', 'it seems', 'seems to', 'tempting to think',
          'one imagines', 'must have')

ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
        'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
WORD_VALUE = {w: i for i, w in enumerate(ONES)}
MONTH_ORDER = {n: i + 1 for i, n in enumerate(bt.MONTH_NAMES)}


# ---------------------------------------------------------------- wording

def pick(beat_id, count):
    """A stable choice among `count` wordings, so a rebuild never changes a caption."""
    return int(hashlib.sha1(beat_id.encode('utf-8')).hexdigest(), 16) % count


def num(n):
    """Words up to twenty and figures above (STORY_SPEC, Names, dates and numbers)."""
    return ONES[n] if 0 <= n <= 20 else str(n)


def plural(n, one, many):
    return f'{num(n)} {one if n == 1 else many}'


def capital(text):
    return text[:1].upper() + text[1:]


def numbers_in(text):
    """Every number a caption mentions, written as a figure or as a word."""
    found = {int(m) for m in re.findall(r'\d+', text)}
    low = text.lower()
    for tens, value in TENS.items():
        for m in re.finditer(r'\b' + tens + r'(?:-(one|two|three|four|five|six|seven|eight|nine))?\b', low):
            found.add(value + (WORD_VALUE[m.group(1)] if m.group(1) else 0))
    for word, value in WORD_VALUE.items():
        if value and re.search(r'\b' + word + r'\b', low):
            found.add(value)
    return found


def duration_ms(caption, has_media):
    words = len(caption.split())
    ms = int(round(words / WORDS_PER_SECOND * 1000))
    ms = max(MIN_MS, min(MAX_MS, ms))
    return ms + (PHOTO_MS if has_media else 0)


# ---------------------------------------------------------------- beats

def year_of(event):
    return int(event['sort'][:4])


def span_label(event):
    """A year, or a decade phrased for a sentence ("the 1850s")."""
    label = event['date']['label']
    if label.startswith('The '):
        return label.lower()
    return label.split()[-1] if event['date']['kind'] == 'exact' else label


def beat(kind, key, chapter, event_ref, caption, place, certainty='stated', basis='', events=(), media=(), camera='townland', counts=None):
    """event_ref: the event (or events) whose date places the beat. `events` are the evidence ids."""
    first = event_ref[0] if isinstance(event_ref, (list, tuple)) else event_ref
    last = event_ref[-1] if isinstance(event_ref, (list, tuple)) else event_ref
    bid = f"{place['townland']}:beat:{kind}:{key}"
    when = last if kind == 'closing' else first
    time = {'label': when['date']['label'], 'iso': when['date']['iso'], 'sort': when['sort'],
            'approximate': bool(when.get('approximate_sort'))}
    card = events[0] if events else ''
    out = {
        'id': bid, 'kind': kind, 'chapter': chapter, 'time': time,
        'place': dict(place, camera=camera),
        'scene': {'stage': 'map', 'open_card': card},
        'caption': caption,
        'people': [], 'media': list(media),
        'evidence': {'events': list(events), 'basis': basis, 'certainty': certainty},
        'duration_ms': duration_ms(caption, bool(media)),
        'audio': None,
    }
    if counts:
        out['counts'] = counts
    return out


def vr_key(spelling):
    return sf.vr.key(spelling)


def name_list(labels):
    labels = [x for x in labels if x]
    return labels[0] if len(labels) == 1 else ', '.join(labels[:-1]) + ' and ' + labels[-1] if labels else ''


def place_names(record):
    """The civil parish and barony of a case, from the hand kept place_names.csv, by the ids on its place record."""
    path = ROOT / 'data' / 'processed' / 'places' / 'place_names.csv'
    if not path.is_file():
        return '', ''
    import csv
    with open(path, encoding='utf-8-sig', newline='') as h:
        by_id = {r['logainm_id']: r['name_en'] for r in csv.DictReader(h)}
    return by_id.get(str(record.get('civil_parish_id', '')), ''), by_id.get(str(record.get('barony_id', '')), '')


def title_beat(display, name_ga, events, place, header, end_label='', families=0, parish='', barony=''):
    if events:
        a, b = span_label(events[0]), end_label or span_label(events[-1])
        runs = f'Its story here runs from {a} to {b}.' if a != b else f'Its story here is {a}.'
    else:
        runs = ''
    irish = f', in Irish {name_ga}' if name_ga else ''
    where = ''
    if parish and barony:
        where = f', in the civil parish of {parish} and the barony of {barony}'
    elif parish:
        where = f', in the civil parish of {parish}'
    if events and families > 1:
        a, b = span_label(events[0]), end_label or span_label(events[-1])
        tail = f'from {a} to {b}.' if a != b else f'in {a}.'
        caption = f'{display}{irish}{where}. Here is the story of {display} and its {num(families)} families, {tail}'
    else:
        caption = (f'{display}{irish}{where}. {runs}').strip() if runs else f'This is {display}{irish}{where}.'
    first = events[0] if events else {'date': {'label': '', 'iso': ''}, 'sort': '0000-01-01'}
    ids = [events[0]['id'], events[-1]['id']] if events else []
    b = beat('title', 'title', f"{place['townland']}:ch:intro", first, caption, place,
             basis='place_record', events=ids, media=[r['file'] for r in header], camera='parish')
    b['scene']['open_card'] = ''
    b['time'] = {'label': '', 'iso': '', 'sort': first['sort'], 'approximate': True}
    return b


def estate_beat(ev, place, names=()):
    y = ev['date']['label']
    town = place['name']
    h, t = ev['estate']['holdings'], ev['estate']['tenants']
    if y == '1825':
        lead = f"In {y} a map of the Arran estate laid out {town} in {plural(h, 'holding', 'holdings')}."
    else:
        lead = f"In {y} the Arran estate rental listed {town}."
    cap = f"{lead} In all, {num(t)} tenants were named." if t != 1 else f"{lead} One tenant was named."
    if names:
        cap += f' They included {name_list(names)}.'
    return beat('estate', y, f"{place['townland']}:ch:{y}", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']], counts={'holdings': h, 'tenants': t})


def family_beat(ev, place):
    key = ev['id'].rsplit(':', 1)[1]
    return beat('family', key, f"{place['townland']}:ch:families", ev, ev['text'], place, certainty='accepted',
                basis=ev['association']['basis'], events=[ev['id']])


def valuation_beat(ev, place, media=(), names=()):
    town = place['name']
    parts = ev['text'].split('. ', 1)
    tail = re.sub(r'\s*\([^)]*\)', '', parts[1]).rstrip('.').replace('the townland', town) if len(parts) == 2 else ''
    patterns = [f"In the 1850s the land was valued and its occupiers listed. In all, {tail}.",
                f"Griffith's Valuation listed the land and its occupiers in the 1850s. Here, {tail}."]
    cap = patterns[pick(ev['id'], len(patterns))] if tail else "In the 1850s the land was valued and its occupiers listed."
    if names:
        cap += f' The occupiers included {name_list(names)}.'
    return beat('valuation', 'griffiths', f"{place['townland']}:ch:1850s", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']], media=media)


def baptism_beats(events, place, media=()):
    out = []
    by_year = {}
    for ev in events:
        by_year.setdefault(year_of(ev), []).append(ev)
    town = place['name']
    for year in sorted(by_year):
        group = by_year[year]
        ids = [e['id'] for e in group]
        doubtful = [e for e in group if e['association']['basis'] == 'page_place_doubtful']
        cert = 'possible' if doubtful else 'stated'
        chapter = f"{place['townland']}:ch:baptisms"
        if len(group) == 1:
            e = group[0]
            child = e['title'][len('Baptism of '):] if e['title'].startswith('Baptism of ') else e['title']
            father = next((p['name'] for p in e['people'] if p['role'] == 'father'), '')
            mother = next((p['name'] for p in e['people'] if p['role'] == 'mother'), '')
            parents = ' and '.join(x for x in (father, mother) if x)
            cap = f"{child} was baptised on {e['date']['label']}."
            if parents:
                cap += f" {parents} were the parents." if father and mother else f" {parents} was the parent."
            if doubtful:
                cap += f' The family was possibly from {town}.'
            out.append(beat('baptism', e['sort'] + '-' + e['id'].split(':')[-1], chapter, e, cap, place, media=media,
                            certainty=cert, basis=e['association']['basis'], events=ids))
        else:
            shown = group[:4]
            bits = []
            for e in shown:
                child = e['title'][len('Baptism of '):] if e['title'].startswith('Baptism of ') else e['title']
                day = e['date']['label'].rsplit(' ', 1)[0]
                bits.append(f'{child} on {day}')
            more = len(group) - len(shown)
            listed = ', '.join(bits[:-1]) + ' and ' + bits[-1] if len(bits) > 1 else bits[0]
            if more:
                listed += f', and {num(more)} more'
            cap = f'{capital(num(len(group)))} children were baptised in {year}: {listed}.'
            if doubtful:
                names = [e['title'][len('Baptism of '):] if e['title'].startswith('Baptism of ') else e['title']
                         for e in doubtful]
                who = ' and '.join(names) if len(names) < 3 else ', '.join(names[:-1]) + ' and ' + names[-1]
                cap += f' {who} {"was" if len(names) == 1 else "were"} possibly from {town}.'
            out.append(beat('baptism', f'{year}', chapter, group[0], cap, place, certainty=cert, media=media,
                            basis=group[0]['association']['basis'], events=ids))
    return out


def census_counts(ev):
    m = re.match(r'(\d+) people in (\d+) households', ev['text'])
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def census_beat(ev, place, names=(), media=()):
    y = ev['date']['label']
    people, houses = census_counts(ev)
    town = place['name']
    if people is None:
        cap = f'{town} had a return in {y}.'
    else:
        patterns = [f"In {y}, {num(people)} people in {plural(houses, 'household', 'households')} lived in {town}.",
                    f"{town} had {num(people)} people in {plural(houses, 'household', 'households')} in {y}."]
        cap = patterns[pick(ev['id'], len(patterns))]
    if names and people is not None:
        cap += f' Heads of household included {name_list(names)}.'
    counts = {'people': people, 'households': houses} if people is not None else None
    return beat('census', y, f"{place['townland']}:ch:{y}", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']], counts=counts, media=media)


def census_returns_beat(cens, place, names=(), media=()):
    """All the census returns in one milestone, so the townland section lays the sources out briefly. The
    individual years come back in each family's own thread."""
    counts = [census_counts(e) for e in cens]
    town = place['name']
    years = [e['date']['label'] for e in cens]
    when = ', '.join(years[:-1]) + ' and ' + years[-1]
    if any(p is None for p, _ in counts):
        cap = f'{town} had returns in {when}.'
    else:
        ppl = ', '.join(str(p) for p, _ in counts[:-1]) + ' and ' + str(counts[-1][0])
        hh = ', '.join(str(h) for _, h in counts[:-1]) + ' and ' + str(counts[-1][1])
        cap = f'The censuses of {when} counted {ppl} people in {town}, in {hh} households.'
        if names:
            cap += f' Heads of household included {name_list(names)}.'
    # without form images the milestone shows the people of each return as dots; with images it shows them
    returns = None if media or any(p is None for p, _ in counts) else \
        {'returns': [{'year': y, 'people': p, 'households': h} for y, (p, h) in zip(years, counts)]}
    b = beat('census', 'returns', f"{place['townland']}:ch:census", cens[0], cap, place,
             basis=cens[0]['association']['basis'], events=[e['id'] for e in cens], media=media, counts=returns)
    b['time']['label'] = f'{years[0]} to {years[-1]}'
    return b


def register_beat(ev, place, names=()):
    """The parish register as one milestone: how many baptisms and marriages it holds for the townland."""
    town = place['name']
    n, m = ev['baptisms'], ev['marriages']
    cap = f"The parish register of Tawnawilly records {num(n)} {'baptism' if n == 1 else 'baptisms'}"
    lab = ev['date']['label']
    when = 'between ' + lab.replace(' to ', ' and ') if ' to ' in lab else 'in ' + lab
    if ev['marriages_placed']:
        cap += f" and {num(m)} {'marriage' if m == 1 else 'marriages'} at {town} {when}."
    else:
        cap += f" at {town} {when}. Its marriage entries give no townland, so none are placed here."
    return beat('register', 'tawnawilly', f"{place['townland']}:ch:register", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']], media=[COVER_FILE])


def family_head_beat(t, place):
    """The header slide of a family: where it appears in the records, from first to last."""
    pe = t['presence']
    first, last = pe['first'], pe['last']
    span = f'from {first} to {last}' if first != last else f'in {first}'
    b = beat('familyhead', t['id'].rsplit(':', 1)[1], f"{place['townland']}:ch:{t['key']}", pe,
             f"The {t['label']} family appear in the records {span}.", place, certainty='accepted',
             basis='census_surname', events=[pe['id']])
    b['time']['label'] = f"The {t['label']} family"
    return b


def families_intro_beat(display, place, events, end_label, names, sort):
    """Opens the families section: the families of the townland over the span of the story."""
    a, z = span_label(events[0]), end_label or span_label(events[-1])
    span = f'from {a} to {z}' if a != z else f'in {a}'
    who = name_list(names)
    cap = f'Here are the families of {display}, {span}.' + (f' First, the {who} {"family" if len(names) == 1 else "families"}.' if who else '')
    b = beat('familyintro', 'families', f"{place['townland']}:ch:families", events[0], cap, place,
             basis='place_record', events=[events[0]['id'], events[-1]['id']])
    b['time'] = {'label': f'The families of {display}', 'iso': events[0]['date']['iso'], 'sort': sort, 'approximate': True}
    return b


def family_census_beat(ev, place, thread):
    """One family's households in one census year, told in the family's own thread."""
    y, town = ev['date']['label'], place['name']
    groups = ev['groups']
    counts = [len(fn) for _, fn in groups]
    total = sum(counts)
    bits = [f"{num(c)} {lab} " + ('household' if c == 1 else 'households') for (lab, _), c in zip(groups, counts)]
    cap = f"{town} had {' and '.join(bits)} in {y}"
    named = [f for f in groups[0][1] if f] if len(groups) == 1 else []
    cap += f', headed by {sf._heads_phrase(named)}.' if named else '.'
    key = ev['id'].split(':familycensus:')[1].replace(':', '-')
    return beat('familycensus', key, f"{place['townland']}:ch:{thread['key']}", ev, cap, place, certainty='accepted',
                basis=ev['association']['basis'], events=[ev['id']])


def photo_beats(feed_events, by_event, place):
    out = []
    for ev in feed_events:
        for r in by_event.get(ev['id'], []):
            cap = f"A photograph: {r['caption'].rstrip('.')}."
            chapter = f"{place['townland']}:ch:" + ('1850s' if ev['type'] == 'valuation' else
                                                     'baptisms' if ev['type'] == 'baptism' else ev['date']['label'])
            out.append(beat('photo', r['file'], chapter, ev, cap, place, basis='media_attached_to_event',
                            events=[ev['id']], media=[r['file']]))
    return out


def dated_photo_beats(rows, place):
    """A photograph with a plain four figure year in its `date` and no event is placed by that year.
    The year is the one the user gave, so the beat is stated. The caption is the media.csv caption."""
    out = []
    for r in rows:
        y = (r.get('date') or '').strip()
        if not re.fullmatch(r'\d{4}', y):
            continue
        ref = {'date': {'kind': 'year', 'label': y, 'iso': y}, 'sort': f'{y}-07-01', 'approximate_sort': True}
        cap = f"A photograph from {y}: {r['caption'].rstrip('.')}."
        out.append(beat('photo', r['file'], f"{place['townland']}:ch:{y}", ref, cap, place,
                        basis='dated_photograph', media=[r['file']]))
    return out


def closing_beat(events, place, later=None):
    last = events[-1]
    people, houses = census_counts(last) if last['type'] == 'census' else (None, None)
    y = span_label(last)
    cap = (f"The story reaches {y} here, with {plural(houses, 'household', 'households')} in {place['name']}."
           if houses else f'The story reaches {y} here.')
    if later:
        ly = later['date']['label']
        cap = f'The story reaches {ly} here.'
        return beat('closing', 'end', f"{place['townland']}:ch:{ly}", later, cap, place,
                    basis=last['association']['basis'], events=[last['id']])
    return beat('closing', 'end', f"{place['townland']}:ch:" + (last['date']['label'] if last['type'] == 'census' else
                                                 '1850s' if last['type'] == 'valuation' else 'baptisms'),
                last, cap, place, basis=last['association']['basis'], events=[last['id']])


# ---------------------------------------------------------------- checks

def evidence_numbers(b, by_id):
    """Numbers the beat may use: those in its source events, in its time label, and counts derived from
    the evidence list itself."""
    allowed = set()
    texts = [b['time']['label'], b['time'].get('iso', '')]
    for eid in b['evidence']['events']:
        ev = by_id.get(eid)
        if ev:
            texts += [ev['title'], ev['text'], ev['date']['label'], ev['date']['iso']]
    for t in texts:
        allowed |= numbers_in(t)
    n = len(b['evidence']['events'])
    allowed |= set(range(0, n + 1))
    return allowed


def hedge_in(caption, phrase):
    """True when the caption hedges with this phrase. The phrase is matched as whole words, in lower case or
    opening a sentence, so a surname such as Likely (Mullanasole census) is not read as a hedge."""
    opening = phrase[:1].upper() + phrase[1:]
    return bool(re.search(r'\b' + re.escape(phrase) + r'\b|(?:^|[.!?]\s+)' + re.escape(opening) + r'\b', caption))


def check_beat(b, by_id, known_ids, extra=frozenset()):
    """Return a list of problems for one beat. Empty means it passes DOC-02, 05, 06, 06a, 07 and 08."""
    problems = []
    for f in REQUIRED:
        if b.get(f) in (None, '', {}):
            problems.append(f'missing {f}')
    if problems:
        return problems
    if b['kind'] not in KIND_ORDER:
        problems.append('unknown kind ' + b['kind'])
    if b['place'].get('camera') not in CAMERAS:
        problems.append('bad camera')
    if b['scene'].get('stage') not in STAGES:
        problems.append('bad stage')
    cert = b['evidence'].get('certainty')
    if cert not in CERTAINTY:
        problems.append('bad certainty')
    for eid in b['evidence']['events']:
        if eid not in known_ids:
            problems.append('evidence event not found: ' + eid)
    cap, low = b['caption'], b['caption'].lower()
    if any(d in cap for d in DASHES):
        problems.append('caption has a dash character')
    for phrase in SOURCE_TALK:
        if phrase in low:
            problems.append('source talk: ' + phrase)
    for phrase in HEDGES:
        if hedge_in(cap, phrase):
            problems.append('hedge: ' + phrase)
    count = len(re.findall(r'\bpossibly\b', low))
    if cert == 'possible' and count != 1:
        problems.append('a possible beat must say "possibly" once')
    if cert != 'possible' and count:
        problems.append('"possibly" on a beat that is not possible')
    loose = numbers_in(cap) - evidence_numbers(b, by_id) - set(extra)
    if loose:
        problems.append('number not in the evidence: ' + ', '.join(str(x) for x in sorted(loose)))
    return problems


def privacy_refusals(events, today):
    """DOC-09: a baptism must be 100 or more years old. Census returns to 1926 are exempt (CLAUDE.md)."""
    keep, refused = [], []
    for ev in events:
        if ev['type'] == 'baptism' and today.year - year_of(ev) < BAPTISM_MIN_AGE:
            refused.append((ev['id'], 'under 100 years old, no beat built'))
        else:
            keep.append(ev)
    return keep, refused


# ---------------------------------------------------------------- assembly

def chapter_title(key, beats, display, threads=None):
    if threads and key in threads:
        return f'The {threads[key]} family'
    if key == 'intro':
        return display
    if key == '1850s':
        return 'The land'
    if key == 'families':
        return f'The families of {display}'
    if key == 'register':
        return 'The parish register'
    if key == 'census':
        return beats[0]['time']['label']
    if key == 'baptisms':
        years = sorted({b['time']['sort'][:4] for b in beats if b['kind'] == 'baptism'})
        if not years:
            return 'Baptisms'
        return 'Baptisms, ' + (years[0] if len(years) == 1 else f'{years[0]} to {years[-1]}')
    return key


def generate(display, slug, place_record, events, by_event=None, header=None, today=None, dated=None, parish_files=None, griffiths_files=None, fam=None, census_files=None):
    """Pure: build the story dict and the list of refused items from already collected inputs."""
    today = today or datetime.date.today()
    by_event = by_event or {}
    header = header or []
    events, refused = privacy_refusals(events, today)
    events = sorted(events, key=lambda e: (e['sort'], bt.TYPE_ORDER.get(e['type'], 9), e['id']))
    place = {'townland': slug, 'name': display, 'logainm_id': str(place_record.get('logainm_id', '')),
             'lat': _num(place_record.get('latitude')), 'lon': _num(place_record.get('longitude'))}
    dated_beats = dated_photo_beats(dated or [], place) if len(events) >= 2 else []
    later = None
    if dated_beats:
        top = max(dated_beats, key=lambda b: b['time']['sort'])
        if top['time']['sort'] > events[-1]['sort']:
            later = {'date': {'kind': 'year', 'label': top['time']['label'], 'iso': top['time']['iso']},
                     'sort': top['time']['sort'], 'approximate_sort': True}
    fam = fam or {}
    nm = fam.get('names') or {}
    threads = fam.get('threads') or []
    for t in threads:
        t['key'] = 'family-' + t['id'].rsplit(':', 1)[1]
    parish, barony = place_names(place_record)
    beats = [title_beat(display, place_record.get('name_ga', ''), events, place, header,
                        later['date']['label'] if later else '', nm.get('families', 0), parish, barony)]
    tbeats = {}
    note = ''
    if len(events) < 2:
        note = 'Fewer than two events are held, so there is no story to play yet.'
    else:
        vals = [e for e in events if e['type'] == 'valuation']
        baps = [e for e in events if e['type'] == 'baptism']
        cens = [e for e in events if e['type'] == 'census']
        beats += [estate_beat(e, place, (nm.get('estate') or {}).get(e['date']['label'], ())) for e in events if e['type'] == 'estate']
        beats += [valuation_beat(e, place, griffiths_files or (), nm.get('valuation') or ()) for e in vals]
        by_thread = {t['id']: t for t in threads}
        for e in events:
            if e['type'] == 'family' and e['id'] in by_thread:
                t = by_thread[e['id']]
                fb = family_beat(e, place)
                fb['chapter'] = f"{slug}:ch:{t['key']}"
                fb['time']['label'] = f"The {t['label']} family"
                if t['start_sort'] < fb['time']['sort']:
                    fb['time']['sort'] = t['start_sort']
                head = [family_head_beat(t, place)] if t.get('presence') else []
                tbeats[t['id']] = head + [fb] + [family_census_beat(x, place, t) for x in t['events']]
            elif e['type'] == 'family':
                beats.append(family_beat(e, place))
        for t in threads:       # a family told by the records alone (a surname), with no authored caption
            if t.get('auto') and t.get('presence') and t['id'] not in tbeats:
                tbeats[t['id']] = [family_head_beat(t, place)] + [family_census_beat(x, place, t) for x in t['events']]
        # a baptism joins the thread of the family named by the father's surname; the rest stay in the townland story
        left = []
        for e in baps:
            father = next((p['name'] for p in e['people'] if p['role'] == 'father'), '')
            home = next((t for t in threads if t['id'] in tbeats and father and
                         vr_key(father.split()[-1]) in set(t.get('spellings', ()))), None)
            if home:
                for bb in baptism_beats([e], place, parish_files or ()):
                    bb['chapter'] = f"{slug}:ch:{home['key']}"
                    tbeats[home['id']].append(bb)
            else:
                left.append(e)
        reg = fam.get('register')
        if reg:
            beats.append(register_beat(reg, place))
        beats += baptism_beats(left, place, parish_files or ())
        if len(cens) > 1 and threads:
            seen = list(dict.fromkeys(x for e in cens for x in (nm.get('census') or {}).get(e['date']['label'], ())))
            # the milestone for all the returns shows the forms of the latest return that has them
            latest = max((y for y in (census_files or {})), default=None)
            beats.append(census_returns_beat(cens, place, seen[:3], (census_files or {}).get(latest, ())))
        else:
            beats += [census_beat(e, place, (nm.get('census') or {}).get(e['date']['label'], ()),
                                  (census_files or {}).get(e['date']['label'], ())) for e in cens]
        beats += photo_beats(events, by_event, place)
        beats += dated_beats
        beats.append(closing_beat(events, place, later))
    order = lambda b: (b['time']['sort'], KIND_ORDER[b['kind']], b['id'])
    # the title opens the story: it is dated no later than the earliest beat (the register beat is dated
    # 1 January of its first year, which can fall before the first baptism the title was dated from)
    beats[0]['time']['sort'] = min(b['time']['sort'] for b in beats)
    beats.sort(key=order)
    closing = [b for b in beats if b['kind'] == 'closing']
    beats = [b for b in beats if b['kind'] != 'closing']
    picked = set(fam.get('highlights') or [])
    told, rest = [], []
    for t in threads:
        if t['id'] not in tbeats:
            continue
        tb = sorted(tbeats[t['id']], key=order)
        for b in tb:
            b['thread'] = {'id': t['id'], 'label': t['label'], 'run': t['id'] in picked}
        (told if t['id'] in picked else rest).append(tb)
    for group in (told, rest):
        group.sort(key=lambda tb: order(tb[0]))
    if told and events:
        first = told[0][0]
        intro = families_intro_beat(display, place, events, later['date']['label'] if later else '',
                                    [tb[0]['thread']['label'] for tb in told], first['time']['sort'])
        intro['thread'] = dict(first['thread'])
        told[0].insert(0, intro)
    beats = beats + [b for tb in told for b in tb] + closing + [b for tb in rest for b in tb]
    extra_events = [x for t in threads for x in t['events'] + ([t['presence']] if t.get('presence') else [])] + ([fam['register']] if fam.get('register') else [])
    by_id = {e['id']: e for e in events + extra_events}
    known = set(by_id)
    years = {int(b['time']['sort'][:4]) for b in dated_beats} | {nm.get('families', 0)}
    known |= set(by_id)
    for b in beats:
        problems = check_beat(b, by_id, known, years if b['kind'] in ('title', 'familyintro') else ())
        if problems:
            raise ValueError(b.get('id', '?') + ': ' + '; '.join(problems))
    ids = [b['id'] for b in beats]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate beat ids')
    chapters, order, seen_keys = {}, [], {}
    for b in beats:
        key = b['chapter'].split(':ch:')[1]
        if order and order[-1][0] == key:
            chapters[order[-1][1]].append(b)
            b['chapter'] = f'{slug}:ch:{order[-1][1]}'
            continue
        n = seen_keys.get(key, 0)
        seen_keys[key] = n + 1
        cid = key if n == 0 else f'{key}-{n + 1}'      # a moment that comes back to a chapter (the closing card) is its own chapter
        order.append((key, cid))
        chapters[cid] = [b]
        b['chapter'] = f'{slug}:ch:{cid}'
    doc = {
        'schema': SCHEMA, 'townland': display, 'slug': slug,
        'generated_by': 'donegal-townlands.build_story',
        'title': display,
        'span': {'from': span_label(events[0]) if events else '', 'to': span_label(events[-1]) if events else ''},
        'chapters': [{'id': f'{slug}:ch:{cid}', 'title': chapter_title(k, chapters[cid], display, {t['key']: t['label'] for t in threads}), 'beats': chapters[cid]}
                     for k, cid in order],
    }
    if note:
        doc['note'] = note
    return doc, refused


def _num(v):
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return None


def page_sources(doc, events):
    """What the footnotes name: for each event a beat cites, the third-party sources behind it, as
    {label, url}. Internal process (association basis, crosswalk status, event ids) is never shown.
    A family beat is built from our own crosswalk, so it names the records the crosswalk joins: the estate
    records and Griffith's, and a census year only where the caption speaks of it."""
    by_id = {e['id']: e for e in events}

    def one(ev):
        src = ev.get('source') or {}
        return {'label': src.get('label', ''), 'url': src.get('url', '')} if src.get('label') else None

    out = {}
    for c in doc['chapters']:
        for b in c['beats']:
            if b['kind'] == 'title' and b['place'].get('logainm_id'):
                out[b['id']] = [{'label': 'Logainm, the placenames database of Ireland',
                                 'url': 'https://www.logainm.ie/en/' + b['place']['logainm_id']}]
            for eid in b['evidence']['events']:
                ev = by_id.get(eid)
                if not ev or eid in out:
                    continue
                if ev['type'] == 'family':
                    pool = [e for e in events if e['type'] in ('estate', 'valuation')]
                    pool += [e for e in events if e['type'] == 'census' and e['date']['label'] in ev['text']]
                else:
                    pool = [ev]
                seen, rows = set(), []
                for e in pool:
                    row = one(e)
                    if row and row['label'] not in seen:
                        seen.add(row['label'])
                        rows.append(row)
                out[eid] = rows
    return out


def explore_block(doc):
    """The explore hub the player opens from the Explore button and the closing card: the families the story
    tells and the record sources it draws on, each pointing at the first beat that tells it."""
    families, sources, seen = [], [], set()
    names = {'estate': 'Estate records', 'valuation': "Griffith's Valuation", 'register': 'Parish register',
             'baptism': 'Parish baptisms', 'census': 'Census returns'}
    for c in doc['chapters']:
        for b in c['beats']:
            if b['kind'] in ('familyhead', 'family') and (b.get('thread') or {}).get('id') not in {f['thread'] for f in families}:
                t = b.get('thread') or {}
                families.append({'beat': b['id'], 'label': t.get('label', ''), 'thread': t.get('id', '')})
            elif b['kind'] in names and b['kind'] not in seen:
                seen.add(b['kind'])
                sources.append({'beat': b['id'], 'label': names[b['kind']]})
    return {'families': families, 'sources': sources}


def render_page(doc, found, outline=None, events=None):
    """The page text for one story. Pure: the same inputs give the same bytes (RO-03). `outline` is the
    townland's boundary geometry (WGS84), drawn on the map and used to frame it; with none the page frames the
    place point at zoom 16 as before. It goes into the page only, never into story.json. `events` are the
    case's events, from which the footnote sources are named (page only, also never in story.json)."""
    media = {}
    used = {f for c in doc['chapters'] for b in c['beats'] for f in b.get('media', [])}
    if COVER_FILE in used:
        media[COVER_FILE] = dict(COVER_MEDIA)
    for r in found['rows']:
        media[r['file']] = {'caption': r.get('caption', ''), 'alt': r.get('alt', ''),
                            'source': r.get('source', ''), 'lat': r.get('lat', ''), 'lon': r.get('lon', '')}
        for key in ('credit', 'focus', 'reference', 'date'):
            if r.get(key):
                media[r['file']][key] = r[key]
    # the credits the page must show: only those of images a beat actually uses
    keys = sorted({m['credit'] for f, m in media.items() if f in used and m.get('credit')})
    payload = dict(doc, media=media, foot='', credits={k: credits.credit_block(k) for k in keys})
    if events is not None:
        payload['sources'] = page_sources(doc, events)
        titles = {e['id']: e['title'] for e in events if e['type'] == 'family'}
        ex = explore_block(doc)
        for f in ex['families']:
            if not f['label']:
                eid = next(b['evidence']['events'][0] for c in doc['chapters'] for b in c['beats'] if b['id'] == f['beat'])
                f['label'] = re.sub(r'\s+(family|families)$', '', re.sub(r'^The ', '', titles.get(eid, '')))
        payload['explore'] = ex
    if outline:
        payload['outline'] = outline
        payload['outline_credit'] = bt.build.BOUNDARY_CREDIT
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = (ROOT / 'engine' / 'story.html').read_text(encoding='utf-8')
    return (html.replace('__TITLE__', bt.build.esc(doc['townland'] + ' story'))
                .replace('__BRAND__', bt.build.esc(doc['townland']))
                .replace('__DATA__', data))


def write_page(name, doc, found, events=None):
    """Render engine/story.html to docs/<name>/story.html, a page beside the walk and the
    timeline. It does not replace either (docs/TOWNLAND_STORY_SPEC.md, DP9). Returns the path written."""
    dest = ROOT / 'docs' / name / 'story.html'
    dest.parent.mkdir(parents=True, exist_ok=True)
    place_file = ROOT / 'townlands' / name / 'place.json'
    place = json.loads(place_file.read_text(encoding='utf-8')) if place_file.is_file() else {}
    outline = bt.build.load_outlines().get(str(place.get('logainm_id', '')))
    dest.write_text(render_page(doc, found, outline, events), encoding='utf-8')
    bt.build.copy_media(name, found)
    if COVER_FILE in {f for c in doc['chapters'] for b in c['beats'] for f in b.get('media', [])}:
        copy_shared(COVER_FILE)
    return dest


def copy_shared(file):
    """Copy one shared image, unchanged, from shared_media/ to docs/shared/ (once, whatever the number of pages)."""
    src, target = ROOT / "shared_media" / pathlib.Path(file).name, ROOT / 'docs' / file
    if target.is_file() and target.read_bytes() == src.read_bytes():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    return True


def family_inputs(base, name, today=None, display=None):
    """The families of a case for the story (tools/story_families.py): names for the milestone captions, one thread
    for each told family, and the threads the lean-back run tells."""
    found = sf.threads(base, name)
    reg = sf.register_event(name, today or datetime.date.today(), display or name.title())
    return {'names': sf.names(base), 'threads': found, 'highlights': sf.highlights(found, base) if found else [],
            'register': reg}


def thread_events(name, today=None, display=None):
    reg = sf.register_event(name, today or datetime.date.today(), display or name.title())
    return [e for t in sf.threads(ROOT / 'townlands' / name, name) for e in t['events'] + ([t['presence']] if t.get('presence') else [])] + ([reg] if reg else [])


def census_files_by_year(rows):
    """The census form images of a case, by census year, each year's pages in page order (file name order)."""
    out = {}
    for r in sorted((r for r in rows if r.get('scope') == 'census'), key=lambda r: r['file']):
        out.setdefault(r['year'], []).append(r['file'])
    return out


def collect(name, today):
    """Gather everything `generate` needs for one case, reading files and writing none.
    Returns (inputs, problems). `inputs` is None when the case cannot be built, and `problems` says why.
    The survey in tools/story_report.py uses this too, so it predicts exactly what a build does."""
    base = ROOT / 'townlands' / name
    if not ((base / 'townland.json').is_file() or (base / 'place.json').is_file()):
        return None, [name + ': no townland.json or place.json, not built.']
    found, _background, by_event, unplaced = bt.media_items(name)
    if found['errors']:
        return None, [name + ': media problems, story not built:'] + ['  ' + e for e in found['errors']]
    feed = bt.events_for(name, today)
    place_file = base / 'place.json'
    place = json.loads(place_file.read_text(encoding='utf-8')) if place_file.is_file() else {}
    display = feed['town'].get('name', name.title())
    header = sorted([r for r in found['rows'] if r.get('scope') == 'townland'], key=lambda r: int(r.get('slot') or 0))
    known = {e['id'] for e in feed['events']}
    notes = [name + ': media.csv names an event that does not exist, no photo beat: ' + event_id
             for event_id in sorted(set(by_event) - known)]
    inputs = {
        'found': found, 'feed': feed, 'display': display, 'place': place, 'notes': notes,
        'args': (display, name, place, feed['events'], by_event, header, today,
                 [r for r in found['rows'] if r['file'] in unplaced and r.get('scope') == 'family'],
                 [r['file'] for r in found['rows'] if r.get('scope') == 'parish'],
                 [r['file'] for r in found['rows'] if r.get('scope') == 'griffiths'], family_inputs(base, name, today, display),
                 census_files_by_year(found['rows'])),
    }
    return inputs, []


def build_story(name, today=None, only_story=False, written=None):
    """Build one case. Never raises (RO-01): a failure is printed and returns 1. With `only_story` a case
    that has no story writes nothing (RO-05). `written` is an optional list that receives the paths written."""
    try:
        return _build(name, today or datetime.date.today(), only_story, written if written is not None else [])
    except Exception as e:
        print(f'{name}: story not built. {type(e).__name__}: {e}')
        return 1


def _build(name, today, only_story, written):
    base = ROOT / 'townlands' / name
    inputs, problems = collect(name, today)
    if inputs is None:
        print('\n'.join(problems))
        return 1
    found, feed = inputs['found'], inputs['feed']
    for line in inputs['notes']:
        print(line)
    try:
        doc, refused = generate(*inputs['args'])
    except ValueError as e:
        print(name + ': story not built. ' + str(e))
        return 1
    if only_story and doc.get('note'):
        print(name + ': no story, nothing written. ' + doc['note'])
        return 0
    (base / 'records').mkdir(parents=True, exist_ok=True)
    out = base / 'records' / 'story.json'
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    written.append(str(out.relative_to(ROOT)))
    beats = [b for c in doc['chapters'] for b in c['beats']]
    counts = {}
    for b in beats:
        counts[b['kind']] = counts.get(b['kind'], 0) + 1
    print(name + ': story built, ' + str(len(beats)) + ' beats (' +
          ', '.join(f'{n} {k}' for k, n in sorted(counts.items())) + ').')
    if doc.get('note'):
        print('  ' + doc['note'])
    place = inputs['args'][2]
    if _num(place.get('latitude')) is None or _num(place.get('longitude')) is None:
        print('  no usable coordinates, so no page was built.')      # RO-01
    else:
        written.append(str(write_page(name, doc, found, feed['events'] + [e for t in (inputs['args'][10] if len(inputs['args']) > 10 else {}).get('threads', []) for e in t['events'] + ([t['presence']] if t.get('presence') else [])] + [r for r in [(inputs['args'][10] if len(inputs['args']) > 10 else {}).get('register')] if r]).relative_to(ROOT)))
    for row_id, why in refused + [(r, w) for r, w in feed['skipped']]:
        print('  left out ' + row_id + ': ' + why)
    return 0


# ---------------------------------------------------------------- committed files (RO-04)

TOP_KEYS = ('schema', 'townland', 'slug', 'generated_by', 'title', 'span', 'chapters')


def check_document(doc, events, families=0):
    """Problems with one committed story.json, given the case's current events. Empty means it
    passes: schema, unique ids, beats in time order, evidence ids that exist, no dashes, no source talk,
    hedges or loose numbers, "possibly" only on possible beats, and the thin case rule (RO-02)."""
    problems = []
    if not isinstance(doc, dict):
        return ['not a JSON object']
    if doc.get('schema') != SCHEMA:
        problems.append(f'schema is {doc.get("schema")!r}, expected {SCHEMA}')
    problems += [f'missing {k}' for k in TOP_KEYS if k not in doc]
    beats = []
    for c in doc.get('chapters') or []:
        if not c.get('beats'):
            problems.append('empty chapter ' + str(c.get('id')))
        beats += c.get('beats') or []
    if not beats:
        return problems + ['no beats']
    ids = [b.get('id') for b in beats]
    problems += ['duplicate beat id ' + i for i in sorted({i for i in ids if ids.count(i) > 1})]
    tracks = {}
    for b in beats:      # the townland's moments run in time order, and so do the moments of each family (each rewinds)
        tracks.setdefault((b.get('thread') or {}).get('id', ''), []).append((b.get('time') or {}).get('sort', ''))
    for t, sorts in tracks.items():
        if sorts != sorted(sorts):
            problems.append('beats are not in time order' + (f' in thread {t}' if t else ''))
    by_id = {e['id']: e for e in events}
    years = {int(b['time']['sort'][:4]) for b in beats
             if b.get('kind') == 'photo' and (b.get('evidence') or {}).get('basis') == 'dated_photograph'} | {families}
    for b in beats:
        problems += [f"{b.get('id', '?')}: {p}" for p in
                     check_beat(b, by_id, set(by_id), years if b.get('kind') in ('title', 'familyintro') else ())]
    if len(events) < 2:
        if len(beats) > 1:
            problems.append('a case with fewer than two events may hold only the title beat')
        if not doc.get('note'):
            problems.append('a case with no story needs its note')
    return problems


def check_repo(today=None):
    """RO-04, called by tools/validate.py: check every committed story.json."""
    today = today or datetime.date.today()
    problems = []
    for path in sorted((ROOT / 'townlands').glob('*/records/story.json')):
        name = path.parent.parent.name
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
            events = bt.events_for(name, today)['events'] + thread_events(name, today)
            families = sf.names(ROOT / 'townlands' / name)['families']
        except (ValueError, OSError) as e:
            problems.append(f'{name}: story.json cannot be checked: {e}')
            continue
        problems += [f'{name}: story.json: {p}' for p in check_document(doc, events, families)]
    return problems


def all_cases():
    return sorted(p.name for p in (ROOT / 'townlands').iterdir()
                  if p.is_dir() and ((p / 'townland.json').is_file() or (p / 'place.json').is_file()))


def main(argv):
    if len(argv) != 2 or (argv[1].startswith('-') and argv[1] != '--all'):
        sys.exit(__doc__)
    if argv[1] != '--all':
        return build_story(argv[1])
    try:
        from tools import story_report as dr
    except ImportError:
        import story_report as dr
    today = datetime.date.today()
    names, files, codes = all_cases(), {}, []
    for n in names:
        got = []
        codes.append(build_story(n, today, only_story=True, written=got))
        files[n] = got
    dr.report(names, today, files)       # RO-06: one row per case, a summary, and the CSV
    return max(codes or [0])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
