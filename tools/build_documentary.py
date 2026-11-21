"""Build a townland's documentary beats (docs/DOCUMENTARY_SPEC.md).
Usage:
    python tools/build_documentary.py cullionboy
    python tools/build_documentary.py --all

Reads the case's records through tools/build_timeline.py (Griffith's, census and baptism events,
media) and place.json, and writes townlands/<name>/records/documentary.json. Nothing else is written.
The file is generated and never edited by hand.

A beat is one moment in the story: a kind, a time, a place and camera level, a card to open, a
caption, the evidence behind it and how certain it is. Captions are rule based and deterministic:
the same records give the same file. They follow docs/STORY_SPEC.md (third person, plain words,
evidence only) with one softening agreed 2026-11-20: a link that is possible but not certain may
carry the single word "possibly". The generator checks every beat before writing and stops if one
fails, naming the beat.
"""
import datetime, hashlib, json, pathlib, re, sys

try:
    from tools import build_timeline as bt
except ImportError:                  # run as a script: python tools/build_documentary.py
    import build_timeline as bt

ROOT = bt.ROOT
SCHEMA = 1
BAPTISM_MIN_AGE = bt.BAPTISM_MIN_AGE
KIND_ORDER = {'title': 0, 'valuation': 1, 'baptism': 2, 'census': 3, 'change': 4, 'photo': 5, 'closing': 9}
CERTAINTY = ('stated', 'accepted', 'possible')
CAMERAS = ('parish', 'townland', 'household')
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
CHANGE_BANNED = ('left', 'leave', 'leaving', 'moved', 'emigrat', 'depart', 'died', 'death', 'because', 'after the',
                 'fled', 'lost', 'gone', 'vanish')

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
    when = last if kind in ('change', 'closing') else first
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


def title_beat(display, name_ga, events, place, header, end_label=''):
    if events:
        a, b = span_label(events[0]), end_label or span_label(events[-1])
        runs = f'Its story here runs from {a} to {b}.' if a != b else f'Its story here is {a}.'
    else:
        runs = ''
    irish = f', in Irish {name_ga}' if name_ga else ''
    caption = (f'{display}{irish}. {runs}').strip() if runs else f'This is {display}{irish}.'
    first = events[0] if events else {'date': {'label': '', 'iso': ''}, 'sort': '0000-01-01'}
    ids = [events[0]['id'], events[-1]['id']] if events else []
    b = beat('title', 'title', f"{place['townland']}:ch:intro", first, caption, place,
             basis='place_record', events=ids, media=[r['file'] for r in header], camera='parish')
    b['scene']['open_card'] = ''
    b['time'] = {'label': '', 'iso': '', 'sort': first['sort'], 'approximate': True}
    return b


def valuation_beat(ev, place):
    town = place['name']
    parts = ev['text'].split('. ', 1)
    tail = re.sub(r'\s*\([^)]*\)', '', parts[1]).rstrip('.').replace('the townland', town) if len(parts) == 2 else ''
    patterns = [f"In the 1850s the land was valued and its occupiers listed. In all, {tail}.",
                f"Griffith's Valuation listed the land and its occupiers in the 1850s. Here, {tail}."]
    cap = patterns[pick(ev['id'], len(patterns))] if tail else "In the 1850s the land was valued and its occupiers listed."
    return beat('valuation', 'griffiths', f"{place['townland']}:ch:1850s", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']])


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


def census_beat(ev, place):
    y = ev['date']['label']
    people, houses = census_counts(ev)
    town = place['name']
    if people is None:
        cap = f'{town} had a return in {y}.'
    else:
        patterns = [f"In {y}, {people} people in {plural(houses, 'household', 'households')} lived in {town}.",
                    f"{town} had {people} people in {plural(houses, 'household', 'households')} in {y}."]
        cap = patterns[pick(ev['id'], len(patterns))]
    counts = {'people': people, 'households': houses} if people is not None else None
    return beat('census', y, f"{place['townland']}:ch:{y}", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']], counts=counts)


def change_beat(prev, ev, place):
    pp, ph = census_counts(prev)
    cp, ch = census_counts(ev)
    if None in (pp, cp):
        return None
    y0, y1 = prev['date']['label'], ev['date']['label']
    if cp > pp:
        move = f'up from {pp} in {y0}'
    elif cp < pp:
        move = f'down from {pp} in {y0}'
    else:
        move = f'the same as the {pp} in {y0}'
    cap = f"By {y1} {place['name']} had {cp} people, {move}. It had {plural(ch, 'household', 'households')}, against {num(ph)}."
    return beat('change', f'{y0}-{y1}', f"{place['townland']}:ch:{y1}", [prev, ev], cap, place,
                basis='counts_between_returns', events=[prev['id'], ev['id']],
                counts={'people': cp, 'households': ch, 'from_people': pp, 'from_households': ph})


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
        cap = (f"The story reaches {ly} here. In {y}, {place['name']} had {plural(houses, 'household', 'households')}."
               if houses else f'The story reaches {ly} here.')
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
        if phrase in low:
            problems.append('hedge: ' + phrase)
    count = len(re.findall(r'\bpossibly\b', low))
    if cert == 'possible' and count != 1:
        problems.append('a possible beat must say "possibly" once')
    if cert != 'possible' and count:
        problems.append('"possibly" on a beat that is not possible')
    if b['kind'] == 'change':
        for phrase in CHANGE_BANNED:
            if phrase in low:
                problems.append('change beat says more than counts: ' + phrase)
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

def chapter_title(key, beats, display):
    if key == 'intro':
        return display
    if key == '1850s':
        return 'The land'
    if key == 'baptisms':
        years = sorted({b['time']['sort'][:4] for b in beats if b['kind'] == 'baptism'})
        if not years:
            return 'Baptisms'
        return 'Baptisms, ' + (years[0] if len(years) == 1 else f'{years[0]} to {years[-1]}')
    return key


def generate(display, slug, place_record, events, by_event=None, header=None, today=None, dated=None, parish_files=None):
    """Pure: build the documentary dict and the list of refused items from already collected inputs."""
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
    beats = [title_beat(display, place_record.get('name_ga', ''), events, place, header,
                        later['date']['label'] if later else '')]
    note = ''
    if len(events) < 2:
        note = 'Fewer than two events are held, so there is no story to play yet.'
    else:
        vals = [e for e in events if e['type'] == 'valuation']
        baps = [e for e in events if e['type'] == 'baptism']
        cens = [e for e in events if e['type'] == 'census']
        beats += [valuation_beat(e, place) for e in vals]
        beats += baptism_beats(baps, place, parish_files or ())
        for i, e in enumerate(cens):
            beats.append(census_beat(e, place))
            if i:
                c = change_beat(cens[i - 1], e, place)
                if c:
                    beats.append(c)
        beats += photo_beats(events, by_event, place)
        beats += dated_beats
        beats.append(closing_beat(events, place, later))
    beats.sort(key=lambda b: (b['time']['sort'], KIND_ORDER[b['kind']], b['id']))
    by_id = {e['id']: e for e in events}
    known = set(by_id)
    years = {int(b['time']['sort'][:4]) for b in dated_beats}
    for b in beats:
        problems = check_beat(b, by_id, known, years if b['kind'] == 'title' else ())
        if problems:
            raise ValueError(b.get('id', '?') + ': ' + '; '.join(problems))
    ids = [b['id'] for b in beats]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate beat ids')
    chapters, order = {}, []
    for b in beats:
        key = b['chapter'].split(':ch:')[1]
        if key not in chapters:
            chapters[key] = []
            order.append(key)
        chapters[key].append(b)
    doc = {
        'schema': SCHEMA, 'townland': display, 'slug': slug,
        'generated_by': 'donegal-townlands.build_documentary',
        'title': display,
        'span': {'from': span_label(events[0]) if events else '', 'to': span_label(events[-1]) if events else ''},
        'chapters': [{'id': f'{slug}:ch:{k}', 'title': chapter_title(k, chapters[k], display), 'beats': chapters[k]}
                     for k in order],
    }
    if note:
        doc['note'] = note
    return doc, refused


def _num(v):
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return None


def write_page(name, doc, found):
    """Render engine/documentary.html to docs/<name>/documentary.html, a page beside the walk and the
    timeline. It does not replace either (docs/DOCUMENTARY_SPEC.md, DP9)."""
    media = {}
    for r in found['rows']:
        media[r['file']] = {'caption': r.get('caption', ''), 'alt': r.get('alt', ''),
                            'source': r.get('source', ''), 'lat': r.get('lat', ''), 'lon': r.get('lon', '')}
    payload = dict(doc, media=media, foot='')
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = (ROOT / 'engine' / 'documentary.html').read_text(encoding='utf-8')
    page = (html.replace('__TITLE__', bt.build.esc(doc['townland'] + ' documentary'))
                .replace('__BRAND__', bt.build.esc(doc['townland']))
                .replace('__DATA__', data))
    dest = ROOT / 'docs' / name / 'documentary.html'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding='utf-8')
    bt.build.copy_media(name, found)


def build_documentary(name, today=None):
    today = today or datetime.date.today()
    base = ROOT / 'townlands' / name
    if not ((base / 'townland.json').is_file() or (base / 'place.json').is_file()):
        print(name + ': no townland.json or place.json, not built.')
        return 1
    found, _background, by_event, unplaced = bt.media_items(name)
    if found['errors']:
        print(name + ': media problems, documentary not built:')
        for e in found['errors']:
            print('  ' + e)
        return 1
    feed = bt.events_for(name, today)
    place_file = base / 'place.json'
    place = json.loads(place_file.read_text(encoding='utf-8')) if place_file.is_file() else {}
    display = feed['town'].get('name', name.title())
    header = sorted([r for r in found['rows'] if r.get('scope') == 'townland'], key=lambda r: int(r.get('slot') or 0))
    known = {e['id'] for e in feed['events']}
    for event_id in sorted(set(by_event) - known):
        print(name + ': media.csv names an event that does not exist, no photo beat: ' + event_id)
    try:
        dated = [r for r in found['rows'] if r['file'] in unplaced and r.get('scope') == 'family']
        parish = [r['file'] for r in found['rows'] if r.get('scope') == 'parish']
        doc, refused = generate(display, name, place, feed['events'], by_event, header, today, dated, parish)
    except ValueError as e:
        print(name + ': documentary not built. ' + str(e))
        return 1
    (base / 'records').mkdir(exist_ok=True)
    (base / 'records' / 'documentary.json').write_text(
        json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    beats = [b for c in doc['chapters'] for b in c['beats']]
    counts = {}
    for b in beats:
        counts[b['kind']] = counts.get(b['kind'], 0) + 1
    print(name + ': documentary built, ' + str(len(beats)) + ' beats (' +
          ', '.join(f'{n} {k}' for k, n in sorted(counts.items())) + ').')
    if doc.get('note'):
        print('  ' + doc['note'])
    write_page(name, doc, found)
    for row_id, why in refused + [(r, w) for r, w in feed['skipped']]:
        print('  left out ' + row_id + ': ' + why)
    return 0


def all_cases():
    return sorted(p.name for p in (ROOT / 'townlands').iterdir()
                  if p.is_dir() and ((p / 'townland.json').is_file() or (p / 'place.json').is_file()))


def main(argv):
    if len(argv) != 2 or (argv[1].startswith('-') and argv[1] != '--all'):
        sys.exit(__doc__)
    names = all_cases() if argv[1] == '--all' else [argv[1]]
    return max([build_documentary(n) for n in names] or [0])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
