"""Build townland pages.  Every case is built the same way.
Usage:
    python tools/build.py cullionboy     build one case
    python tools/build.py --all          build every case

Each page is a gallery walk from engine/walk.html, written to docs/<name>/index.html
(served by GitHub Pages from /docs). The page shows whatever the case holds:

  place record     townlands/<name>/place.json (Logainm, a source as well as the place authority)
  census returns   townlands/<name>/records/census.json and census_match.json
  authored study   townlands/<name>/townland.json and content.json (Griffith's rows,
                   family stories, plate copy, open questions)

Anything the case does not hold is generated honestly from what it does hold, or left
out. Authored content always wins over generated content. Nothing is invented: a case
with only a place record gets a short walk that says so. Adding records to a case adds
plates to the same page at the same address.

States, used for the index: ready (authored study with census), partial (some evidence)
and empty (place record only). All three build.

Building never replaces a page it did not generate, never deletes a page and never
changes a case folder. Every build regenerates docs/index.html, the list of every place,
so the index is never edited by hand. Only a name with no case folder is an error."""
import collections, csv, html as htmllib, json, re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
NEEDED = ('townland.json', 'content.json', 'records/census.json')
EVIDENCE = NEEDED + ('records/events.csv', 'records/corrections.json')
CENSUS_YEARS = ('1901', '1911', '1926')
LOGAINM_CREDIT = 'Irish-language placename data by Logainm, Government of Ireland, licensed under CC BY 4.0.'
NAT_ARCHIVES = 'https://www.census.nationalarchives.ie/'
OTHER_COLOUR = '#A9B7B3'
PLACE_MARK = '<!-- generated: donegal-townlands place page -->'   # earlier plain pages, replaced by the walk
GALLERY_SIGNATURE = 'id="walk"'
INDEX_MARK = '<!-- generated: donegal-townlands index -->'


def load(p):
    with open(p, encoding='utf-8') as h:
        return json.load(h)


def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;')
def q(t): return htmllib.escape(str(t), quote=True)


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.casefold()).strip('-') or 'townland'


def case_state(base):
    """Return (state, missing_files) for a case folder."""
    missing = [f for f in NEEDED if not (base / f).is_file()]
    if not missing:
        return 'ready', []
    if any((base / f).is_file() for f in EVIDENCE):
        return 'partial', missing
    return 'empty', missing


def read_names():
    """(logainm_id -> name) for places.csv DED rows plus the hand-kept place_names.csv."""
    names = {}
    for path, only_ded in ((ROOT / 'data' / 'processed' / 'places' / 'places.csv', True),
                           (ROOT / 'data' / 'processed' / 'places' / 'place_names.csv', False)):
        if path.is_file():
            with path.open(encoding='utf-8-sig', newline='') as h:
                for r in csv.DictReader(h):
                    if not only_ded or r.get('place_type') == 'ded':
                        names[r['logainm_id']] = r['name_en']
    return names


def join_words(items):
    items = list(items)
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def count_word(n, is_are=True):
    words = ['None', 'One', 'Two', 'Three', 'Four', 'Five', 'Six']
    return words[n] + (' is' if n < 2 else ' are') + ' filled'


def place_facts(place, names):
    """Place record fields for the page. Names are looked up, never guessed."""
    if not place:
        return {}
    lid = str(place.get('logainm_id', ''))
    out = {
        'logainm_id': lid,
        'name_en': place.get('name_en', ''),
        'name_ga': place.get('name_ga', ''),
        'ded': names.get(str(place.get('ded_id', '')), ''),
        'civil_parish': names.get(str(place.get('civil_parish_id', '')), ''),
        'barony': names.get(str(place.get('barony_id', '')), ''),
        'county': names.get(str(place.get('county_id', '')), ''),
        'latitude': place.get('latitude', ''),
        'longitude': place.get('longitude', ''),
        'snapshot_date': place.get('snapshot_date', ''),
        'logainm_url': 'https://www.logainm.ie/en/' + lid if lid else '',
        'credit': LOGAINM_CREDIT,
    }
    if out['latitude'] and out['longitude']:
        out['osm_url'] = ('https://www.openstreetmap.org/?mlat=' + out['latitude']
                          + '&mlon=' + out['longitude'] + '&zoom=15')
    return out


def census_spellings(match):
    """year -> spelling(s) recorded in that census, from census_match.json."""
    out = {}
    for y, info in (match.get('years') or {}).items():
        out[y] = ' and '.join(sorted({s['spelling'] for s in info.get('spellings', [])}))
    return out


def spelling_phrase(spell, name):
    """'Druminnin in 1901 and 1911 and Druminin in 1926', or '' when all agree with the name."""
    by = collections.OrderedDict()
    for y in sorted(spell):
        by.setdefault(spell[y], []).append(y)
    if all(s == name for s in by):
        return ''
    return join_words([s + ' in ' + join_words(ys) for s, ys in by.items()])


def default_content(name, place, census, match, has_griffiths, townland_name):
    """Honest generated content for whatever the case holds. Authored content overrides it."""
    years = [y for y in CENSUS_YEARS if census.get(y)]
    spell = census_spellings(match)
    checked = match.get('status') == 'checked'
    ded = place.get('ded', '')
    medium = 'A townland'
    if ded: medium += ' in ' + ded + ' electoral division'
    if place.get('civil_parish'): medium += ', ' + place['civil_parish'] + ' civil parish'
    if place.get('barony'): medium += ', ' + place['barony'] + ' barony'

    story = ['%s is a townland recognised by Logainm, the placenames database of the Government of Ireland.%s'
             % (name, (' Its Irish name is %s.' % place['name_ga']) if place.get('name_ga') else '')]
    if years:
        story.append('The census returns for %s are held for this townland. Every scene here is drawn from them. '
                     'Cottages stand for households and are not placed on a map.' % join_words(years))
    else:
        story.append('No historical records have been added yet. This page is a starting point, not a finding '
                     'about the history of the townland. It grows as records are added.')

    held = [False, has_griffiths, False, False, False, bool(years)]
    frames = [
        ['Tithe Applotment Books', '1820s and 1830s', 'Not yet added.', False],
        ["Griffith's Valuation", 'Mid 1850s', 'Held.' if has_griffiths else 'Not yet added.', has_griffiths],
        ['Valuation revision books', 'After the 1850s', 'Not yet added.', False],
        ['Civil births, marriages and deaths', 'From 1864', 'Not yet added.', False],
        ['Parish records', 'Various dates', 'Not yet added.', False],
        ['Census returns', '1901, 1911 and 1926',
         ('Held for ' + join_words(years) + '.') if years else
         ('Checked. No return found.' if checked else 'Not yet added.'), bool(years)],
    ]
    filled = sum(1 for f in frames if f[3])

    paras = [{'before': 'Place details come from ', 'link': {'href': place.get('logainm_url', 'https://www.logainm.ie/'), 'text': 'Logainm'},
              'after': ', the placenames database of the Government of Ireland (CC BY 4.0).'
                       + (' The record number is %s.' % place['logainm_id'] if place.get('logainm_id') else '')}]
    if years:
        text = ('The census tables are the %s rows of the census files for %s electoral division, which also hold other '
                'townlands. A household is the set of people on one house number in 1901 and 1911, or on one form number in '
                '1926. Names are shown as spelled in the files. Some values, such as relationships and Irish language, were '
                'filled in or corrected by the researcher in columns marked updated, so they are not always a straight copy '
                'of the printed return.' % (name, ded or 'the'))
        ph = spelling_phrase(spell, name)
        if ph:
            text += ' The townland is spelled %s in the census files.' % ph
        paras.append(text)
        paras.append({'before': 'Census returns are held by the ', 'link': {'href': NAT_ARCHIVES, 'text': 'National Archives of Ireland'}, 'after': '.'})
    else:
        paras.append('No other source has been added for this townland yet.')
    numbers = ''
    if years:
        parts = ['{n%s} %sin %s' % (y, 'people ' if i == 0 else '', y) for i, y in enumerate(years)]
        numbers = 'The census files record ' + join_words(parts) + '.'

    surnames = collections.Counter(r['s'] for y in years for r in census[y] if r.get('s'))
    placeholder = 'for example ' + (surnames.most_common(1)[0][0] if surnames else 'Gallagher')

    qs = []
    ph = spelling_phrase(spell, name)
    if ph:
        qs.append('The census spells this townland %s. Both spellings were accepted as the same place on review. Do other records spell it differently?' % ph)
    if not years and checked:
        qs.append('No census return is linked to this townland for %s. Was it unoccupied then, or is it recorded under a name not yet matched?' % join_words(CENSUS_YEARS))
    elif not years:
        qs.append('Census returns have not yet been attached to this townland.')
    elif len(years) < 3:
        missing = [y for y in CENSUS_YEARS if y not in years]
        qs.append('No census return is linked to this townland for %s. Was it unoccupied then, or is it recorded under a name not yet matched?' % join_words(missing))
    if not has_griffiths:
        qs.append("Griffith's Valuation, the mid 1850s baseline, has not yet been added for this townland.")
    qs.append('The Tithe Applotment Books, valuation revision books, civil records from 1864 and parish registers have not yet been added'
              + (', so no census household can yet be linked to an earlier record.' if years else '.'))

    return {
        'groups': {'colours': {'Other': OTHER_COLOUR}, 'territory': ['Other'], 'map': {}},
        'families': [],
        'questions': qs,
        'plates': {
            'title': {'title': place.get('name_ga') or name, 'irish': place.get('name_ga', ''), 'heading': name,
                      'medium': medium, 'story': story},
            'not_yet_hung': {'title': 'Not yet hung', 'medium': 'Six frames for six kinds of record. ' + count_word(filled),
                             'story': ['Each frame is a kind of record that can be hung here. A dashed frame is empty. A frame with a gold edge holds records for this townland.',
                                       'Records are added one source at a time, and each new source adds to this page instead of replacing it.'],
                             'frames': frames},
            'method': {'paras': paras, 'numbers_intro': numbers},
            'records': {'placeholder': placeholder},
        },
    }


# Where each published census return can be opened. The patterns are the National
# Archives of Ireland viewer URLs, copied from GRA docs/repositories.md v1.6
# (Sources 3 to 5). Only the URL patterns are taken, no data. {ref} is the
# row's ref: the first image id for 1901 and 1911, the aform_name for 1926.
CENSUS_URLS = {
    '1901': 'https://nationalarchives.ie/collections/search-the-census/view-pdf/?doc={ref}',
    '1911': 'https://nationalarchives.ie/collections/search-the-census/view-pdf/?doc={ref}',
    '1926': 'https://nationalarchives.ie/collections/search-the-1926-census/view-1926-pdf/?doc={ref}',
}


def payload_for(name):
    """Everything the page needs for one case. Pure: reads the case, writes nothing."""
    base = ROOT / 'townlands' / name
    def maybe(rel):
        return load(base / rel) if (base / rel).is_file() else {}
    place = place_facts(maybe('place.json'), read_names())
    meta, authored = maybe('townland.json'), maybe('content.json')
    census, match = maybe('records/census.json'), maybe('records/census_match.json')
    display = meta.get('name') or place.get('name_en') or name
    townland = {
        'name': display,
        'page_title': display + ' | Donegal Townlands',
        'storage_key': slug(display) + '-q',
        'census_spelling': census_spellings(match),
    }
    townland.update({k: v for k, v in meta.items() if v not in (None, '')})
    content = default_content(display, place, census, match, bool(authored.get('griffiths')), display)
    plates = dict(content['plates'])
    plates.update(authored.get('plates', {}))
    content.update({k: v for k, v in authored.items() if k != 'plates'})
    content['plates'] = plates
    urls = {y: u for y, u in CENSUS_URLS.items() if (census.get('years') or census).get(y)}
    return {'census': census, 'content': content, 'townland': townland, 'place': place,
            'census_urls': urls}


def build(name):
    """Build one case. Returns its state."""
    base = ROOT / 'townlands' / name
    if not base.is_dir():
        sys.exit('No case folder townlands/' + name)
    state = case_state(base)[0]
    if not (base / 'place.json').is_file() and not (base / 'townland.json').is_file():
        print(name + ': no place.json or townland.json. Run tools/create_townland_cases.py. Not built.')
        return state
    dest = ROOT / 'docs' / name / 'index.html'
    if dest.exists():
        old = dest.read_text(encoding='utf-8')
        if GALLERY_SIGNATURE not in old and PLACE_MARK not in old:
            print(name + ': docs/' + name + '/index.html was not generated by this tool. Left untouched.')
            return state
    payload = payload_for(name)
    html = (ROOT / 'engine' / 'walk.html').read_text(encoding='utf-8')
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = (html.replace('__TITLE__', esc(payload['townland']['page_title']))
               .replace('__BRAND__', esc(payload['townland']['name']))
               .replace('__DATA__', data))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding='utf-8')
    print(name + ': ' + state + ' case. Wrote ' + str(dest.relative_to(ROOT)) + ' (' + str(len(out)) + ' bytes).')
    return state


def write_index(entries):
    """Rewrite docs/index.html: studies first, then census, then the rest. entries = [(slug, name, state)]."""
    def links(items):
        return ''.join('    <a class="townland" href="./' + q(s) + '/">\n        ' + q(n) + ' &rarr;\n    </a>\n\n' for s, n, _ in items)
    by_name = lambda e: e[1].casefold()
    studies = sorted((e for e in entries if e[2] == 'ready'), key=by_name)
    census = sorted((e for e in entries if e[2] == 'partial'), key=by_name)
    places = sorted((e for e in entries if e[2] == 'empty'), key=by_name)
    page = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Donegal Townlands</title>
    """ + INDEX_MARK + """
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; color: #333; background: #f7f7f5; }
        h1 { color: #234b35; }
        .townland { display: block; padding: 14px 18px; margin: 10px 0; background: white; border-radius: 6px; text-decoration: none; color: #234b35; border: 1px solid #ddd; }
        .townland:hover { background: #eaf1eb; }
        footer { margin-top: 28px; font-size: 0.85em; color: #5b6f62; }
    </style>
</head>
<body>
    <h1>Donegal Townlands</h1>
    <p>Explore the townlands of County Donegal. Every townland has a page to walk through. Where research has begun the walk is a full study. Others show the census returns held so far, or just the place record, and grow as records are added.</p>

    <h2>Townland studies</h2>

""" + links(studies) + """    <h2>Townlands with census returns</h2>

""" + links(census) + """    <h2>Townlands awaiting research</h2>

""" + links(places) + """    <footer>""" + LOGAINM_CREDIT + """</footer>
</body>
</html>
"""
    (ROOT / 'docs' / 'index.html').write_text(page, encoding='utf-8')
    print('wrote docs/index.html:', len(studies), 'studies,', len(census), 'with census,', len(places), 'awaiting')


def index_entries():
    """(slug, display name, state) for every case that has a name to show."""
    entries = []
    for base in sorted((ROOT / 'townlands').iterdir()):
        if not base.is_dir():
            continue
        state = case_state(base)[0]
        if (base / 'townland.json').is_file():
            label = load(base / 'townland.json').get('name', base.name)
        elif (base / 'place.json').is_file():
            label = load(base / 'place.json').get('name_en') or base.name
        else:
            continue
        entries.append((base.name, label, state))
    return entries


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__)
    if argv[0] != '--all':
        build(argv[0])
    else:
        counts = {'ready': 0, 'partial': 0, 'empty': 0}
        for base in sorted((ROOT / 'townlands').iterdir()):
            if base.is_dir():
                counts[build(base.name)] += 1
        print('Cases: %(ready)d studies, %(partial)d partial, %(empty)d empty. Every case with a place record has a page.' % counts)
    write_index(index_entries())


if __name__ == '__main__':
    main(sys.argv[1:])
