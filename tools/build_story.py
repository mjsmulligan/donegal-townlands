"""Build a townland's story beats (docs/TOWNLAND_STORY_SPEC.md).
Usage:
    python tools/build_story.py cullionboy
    python tools/build_story.py --all     only cases that have a story; also writes the survey report

Reads the case's records through tools/build_timeline.py (Griffith's, census and baptism events,
media) and place.json, and writes townlands/<name>/records/story.json. Nothing else is written.
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
except ImportError:                  # run as a script: python tools/build_story.py
    import build_timeline as bt

ROOT = bt.ROOT
SCHEMA = 1
BAPTISM_MIN_AGE = bt.BAPTISM_MIN_AGE
KIND_ORDER = {'title': 0, 'estate': 1, 'valuation': 1, 'family': 2, 'baptism': 2, 'census': 3, 'photo': 5, 'closing': 9}
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


def estate_beat(ev, place):
    y = ev['date']['label']
    town = place['name']
    h, t = ev['estate']['holdings'], ev['estate']['tenants']
    if y == '1825':
        lead = f"In {y} a map of the Arran estate laid out {town} in {plural(h, 'holding', 'holdings')}."
    else:
        lead = f"In {y} the Arran estate rental listed {town}."
    cap = f"{lead} In all, {num(t)} tenants were named." if t != 1 else f"{lead} One tenant was named."
    return beat('estate', y, f"{place['townland']}:ch:{y}", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']], counts={'holdings': h, 'tenants': t})


def family_beat(ev, place):
    key = ev['id'].rsplit(':', 1)[1]
    return beat('family', key, f"{place['townland']}:ch:families", ev, ev['text'], place, certainty='accepted',
                basis=ev['association']['basis'], events=[ev['id']])


def valuation_beat(ev, place, media=()):
    town = place['name']
    parts = ev['text'].split('. ', 1)
    tail = re.sub(r'\s*\([^)]*\)', '', parts[1]).rstrip('.').replace('the townland', town) if len(parts) == 2 else ''
    patterns = [f"In the 1850s the land was valued and its occupiers listed. In all, {tail}.",
                f"Griffith's Valuation listed the land and its occupiers in the 1850s. Here, {tail}."]
    cap = patterns[pick(ev['id'], len(patterns))] if tail else "In the 1850s the land was valued and its occupiers listed."
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


def census_beat(ev, place):
    y = ev['date']['label']
    people, houses = census_counts(ev)
    town = place['name']
    if people is None:
        cap = f'{town} had a return in {y}.'
    else:
        patterns = [f"In {y}, {num(people)} people in {plural(houses, 'household', 'households')} lived in {town}.",
                    f"{town} had {num(people)} people in {plural(houses, 'household', 'households')} in {y}."]
        cap = patterns[pick(ev['id'], len(patterns))]
    counts = {'people': people, 'households': houses} if people is not None else None
    return beat('census', y, f"{place['townland']}:ch:{y}", ev, cap, place,
                basis=ev['association']['basis'], events=[ev['id']], counts=counts)


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
    if key == 'families':
        return 'The families on the land'
    if key == 'baptisms':
        years = sorted({b['time']['sort'][:4] for b in beats if b['kind'] == 'baptism'})
        if not years:
            return 'Baptisms'
        return 'Baptisms, ' + (years[0] if len(years) == 1 else f'{years[0]} to {years[-1]}')
    return key


def generate(display, slug, place_record, events, by_event=None, header=None, today=None, dated=None, parish_files=None, griffiths_files=None):
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
    beats = [title_beat(display, place_record.get('name_ga', ''), events, place, header,
                        later['date']['label'] if later else '')]
    note = ''
    if len(events) < 2:
        note = 'Fewer than two events are held, so there is no story to play yet.'
    else:
        vals = [e for e in events if e['type'] == 'valuation']
        baps = [e for e in events if e['type'] == 'baptism']
        cens = [e for e in events if e['type'] == 'census']
        beats += [estate_beat(e, place) for e in events if e['type'] == 'estate']
        beats += [valuation_beat(e, place, griffiths_files or ()) for e in vals]
        beats += [family_beat(e, place) for e in events if e['type'] == 'family']
        beats += baptism_beats(baps, place, parish_files or ())
        beats += [census_beat(e, place) for e in cens]
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
        'generated_by': 'donegal-townlands.build_story',
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


def render_page(doc, found, outline=None):
    """The page text for one story. Pure: the same inputs give the same bytes (RO-03). `outline` is the
    townland's boundary geometry (WGS84), drawn on the map and used to frame it; with none the page frames the
    place point at zoom 16 as before. It goes into the page only, never into story.json."""
    media = {}
    for r in found['rows']:
        media[r['file']] = {'caption': r.get('caption', ''), 'alt': r.get('alt', ''),
                            'source': r.get('source', ''), 'lat': r.get('lat', ''), 'lon': r.get('lon', '')}
    payload = dict(doc, media=media, foot='')
    if outline:
        payload['outline'] = outline
        payload['outline_credit'] = bt.build.BOUNDARY_CREDIT
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = (ROOT / 'engine' / 'story.html').read_text(encoding='utf-8')
    return (html.replace('__TITLE__', bt.build.esc(doc['townland'] + ' story'))
                .replace('__BRAND__', bt.build.esc(doc['townland']))
                .replace('__DATA__', data))


def write_page(name, doc, found):
    """Render engine/story.html to docs/<name>/story.html, a page beside the walk and the
    timeline. It does not replace either (docs/TOWNLAND_STORY_SPEC.md, DP9). Returns the path written."""
    dest = ROOT / 'docs' / name / 'story.html'
    dest.parent.mkdir(parents=True, exist_ok=True)
    place_file = ROOT / 'townlands' / name / 'place.json'
    place = json.loads(place_file.read_text(encoding='utf-8')) if place_file.is_file() else {}
    outline = bt.build.load_outlines().get(str(place.get('logainm_id', '')))
    dest.write_text(render_page(doc, found, outline), encoding='utf-8')
    bt.build.copy_media(name, found)
    return dest


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
                 [r['file'] for r in found['rows'] if r.get('scope') == 'griffiths']),
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
        written.append(str(write_page(name, doc, found).relative_to(ROOT)))
    for row_id, why in refused + [(r, w) for r, w in feed['skipped']]:
        print('  left out ' + row_id + ': ' + why)
    return 0


# ---------------------------------------------------------------- committed files (RO-04)

TOP_KEYS = ('schema', 'townland', 'slug', 'generated_by', 'title', 'span', 'chapters')


def check_document(doc, events):
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
    sorts = [(b.get('time') or {}).get('sort', '') for b in beats]
    if sorts != sorted(sorts):
        problems.append('beats are not in time order')
    by_id = {e['id']: e for e in events}
    years = {int(b['time']['sort'][:4]) for b in beats
             if b.get('kind') == 'photo' and (b.get('evidence') or {}).get('basis') == 'dated_photograph'}
    for b in beats:
        problems += [f"{b.get('id', '?')}: {p}" for p in
                     check_beat(b, by_id, set(by_id), years if b.get('kind') == 'title' else ())]
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
            events = bt.events_for(name, today)['events']
        except (ValueError, OSError) as e:
            problems.append(f'{name}: story.json cannot be checked: {e}')
            continue
        problems += [f'{name}: story.json: {p}' for p in check_document(doc, events)]
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
