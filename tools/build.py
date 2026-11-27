"""Build the map index (docs/index.html) and hold the helpers the story builder shares.
Usage:
    python tools/build.py        rewrite docs/index.html from engine/index.html

The townland pages are the stories written by tools/build_story.py (docs/<name>/story.html). This script
only lists them: one card per case, tagged Townland Study, Census Returns or Townland Record by the
case's state, and a link to its story where one exists. A case with too few records for a story gets a
card and no link. The walk and the timeline pages were removed on 2026-11-26 (DECISIONS.md).

States, used for the index: ready (authored study with census), partial (some evidence)
and empty (place record only).

Building never deletes a page and never changes a case folder. docs/index.html is never edited by
hand (its layout is engine/index.html). To rebuild everything: python tools/build_story.py --all, then this."""
import collections, csv, datetime, html as htmllib, json, re, shutil, sys, pathlib
try:
    from tools import media, variants_reference
except ImportError:                  # run as a script: python tools/build.py
    import media, variants_reference
ROOT = pathlib.Path(__file__).resolve().parent.parent
NEEDED = ('townland.json', 'content.json', 'records/census.json')
EVIDENCE = NEEDED + ('records/events.csv', 'records/corrections.json')
CENSUS_YEARS = ('1901', '1911', '1926')
LOGAINM_CREDIT = 'Irish-language placename data by Logainm, Government of Ireland, licensed under CC BY 4.0.'
NAT_ARCHIVES = 'https://www.census.nationalarchives.ie/'
INDEX_MARK = '<!-- generated: donegal-townlands index -->'


def load(p):
    with open(p, encoding='utf-8') as h:
        return json.load(h)


def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;')
def q(t): return htmllib.escape(str(t), quote=True)




def case_state(base):
    """Return (state, missing_files) for a case folder."""
    missing = [f for f in NEEDED if not (base / f).is_file()]
    if not missing:
        return 'ready', []
    if any((base / f).is_file() for f in EVIDENCE):
        return 'partial', missing
    return 'empty', missing
















# Where each published census return can be opened. The patterns are the National
# Archives of Ireland viewer URLs, copied from GRA docs/repositories.md v1.6
# (Sources 3 to 5). Only the URL patterns are taken, no data. {ref} is the
# row's ref: the first image id for 1901 and 1911, the aform_name for 1926.
CENSUS_URLS = {
    '1901': 'https://nationalarchives.ie/collections/search-the-census/view-pdf/?doc={ref}',
    '1911': 'https://nationalarchives.ie/collections/search-the-census/view-pdf/?doc={ref}',
    '1926': 'https://nationalarchives.ie/collections/search-the-1926-census/view-1926-pdf/?doc={ref}',
}






def media_for(name):
    """The case's checked media (tools/media.py) plus the repo's CDN base address."""
    base = ROOT / 'townlands' / name
    base_url, config_errors = media.read_config(ROOT / 'townlands')
    found = media.load_case(base, base_url, media.family_names(base))
    found['errors'] = config_errors + found['errors']
    found['base_url'] = base_url
    return found


def copy_media(name, found):
    """Copy the images the page uses, unchanged, to docs/<name>/media/. Nothing is copied
    when a CDN base address is set, and nothing is ever deleted."""
    if found['base_url']:
        return 0
    src, dest = ROOT / 'townlands' / name / 'media', ROOT / 'docs' / name / 'media'
    copied = 0
    for file in sorted({r['file'] for r in found['rows']}):
        target = dest / file
        if target.is_file() and target.read_bytes() == (src / file).read_bytes():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / file, target)
        copied += 1
    return copied




INDEX_TAGS = {'ready': 'Townland Study', 'partial': 'Census Returns', 'empty': 'Townland Record'}
INDEX_FOOTER = 'Placename data sourced from Logainm (Government of Ireland) & historical cartographic surveys. ' + LOGAINM_CREDIT
BOUNDARY_FILE = ROOT / 'data' / 'processed' / 'places' / 'townland_boundaries.geojson'
BOUNDARY_CREDIT = 'Townland boundaries \u00a9 Tailte \u00c9ireann, CC BY 4.0'
DED_FILE = ROOT / 'data' / 'processed' / 'places' / 'ded_boundaries.geojson'


def load_outlines():
    """Townland outlines from tools/fetch_townland_boundaries.py, as {logainm_id: geometry}. An empty dict when the
    file is absent, so a checkout without it builds exactly as before (DECISIONS.md, 2026-11-22)."""
    if not BOUNDARY_FILE.is_file():
        return {}
    gj = json.loads(BOUNDARY_FILE.read_text(encoding='utf-8'))
    return {str(f['properties']['logainm_id']): f['geometry'] for f in gj.get('features', []) if f.get('geometry')}


def load_ded_outlines():
    """DED outlines from tools/build_ded_boundaries.py, as a list of GeoJSON features (empty when the file is absent)."""
    if not DED_FILE.is_file():
        return []
    gj = json.loads(DED_FILE.read_text(encoding='utf-8'))
    return [{'type': 'Feature',
             'properties': {'ded_id': f['properties']['ded_id'], 'name': f['properties']['name_en'],
                            'name_ga': f['properties'].get('name_ga', ''), 'townlands': f['properties']['townlands']},
             'geometry': f['geometry']} for f in gj.get('features', []) if f.get('geometry')]


KIND = {'ready': 'study', 'partial': 'census', 'empty': 'record'}


def index_page(entries, template, deds=None):
    """The index page: a satellite map and a card for each case, from engine/index.html. entries are dicts with
    slug, name, state, name_ga, lat, lng and doc (True when docs/<slug>/story.html exists). A case with no
    coordinates, or with no records (state empty, a Logainm place record only), gets a card and no map pin. A case with a story opens it; a case without one has a card and no link. deds is a list of DED outline features:
    with them the map opens on the DEDs and shows the townlands once the view is close enough (DECISIONS.md,
    2026-11-22); without them it shows every townland at once."""
    entries = sorted(entries, key=lambda e: e['name'].casefold())
    cards = []
    for e in entries:
        main = './%s/story.html' % q(e['slug']) if e.get('doc') else ''
        where = (' data-lat="%s" data-lng="%s"' % (q(e['lat']), q(e['lng']))) if e['lat'] and e['lng'] else ''
        ga = '<div class="card-ga">%s</div>' % q(e['name_ga']) if e['name_ga'] else ''
        links = '<a class="pill main" href="%s">Play the story</a>' % main if main else ''
        name_link = ('<a class="card-en" href="%s">%s</a>' % (main, q(e['name']))) if main else '<span class="card-en">%s</span>' % q(e['name'])
        if e.get('summary'):
            held = '<ul class="card-sum">%s</ul>' % ''.join(
                '<li><b>%s</b> %s</li>' % (q(k), q(v)) for k, v in e['summary'])
        else:
            held = '<p class="card-sum none">No records held yet, only the place name from Logainm.</p>'
        cards.append(
            '        <article class="townland-card" data-slug="%s" data-name="%s"%s>\n'
            '            %s\n'
            '            %s\n'
            '            %s\n'
            '            <div class="card-foot">\n'
            '                <span class="card-tag">%s</span>\n'
            '                %s\n'
            '            </div>\n'
            '        </article>\n' % (q(e['slug']), q(e['name']), where, name_link, ga, held, INDEX_TAGS[e['state']], links))
    features = []
    for e in entries:
        if not (e['lat'] and e['lng']) or e['state'] == 'empty':
            continue
        props = {'name': e['name'], 'name_ga': e['name_ga'], 'slug': e['slug'], 'kind': KIND[e['state']],
                 'doc': bool(e.get('doc')), 'ded': str(e.get('ded', '')),
                 'href': './%s/story.html' % e['slug'] if e.get('doc') else ''}
        if e.get('outline'):
            props['outline'] = e['outline']          # drawn instead of the dot; the point stays as the centre
        features.append({'type': 'Feature', 'properties': props,
                         'geometry': {'type': 'Point', 'coordinates': [float(e['lng']), float(e['lat'])]}})
    collection = {'type': 'FeatureCollection', 'features': features}
    if deds:
        collection['deds'] = deds
    if deds or any(f['properties'].get('outline') for f in features):
        collection['attribution'] = BOUNDARY_CREDIT
    geo = json.dumps(collection, ensure_ascii=False).replace('</', '<\\/')
    return (template.replace('__MARK__', INDEX_MARK).replace('__COUNT__', str(len(entries)))
                    .replace('__FOOTER__', q(INDEX_FOOTER))
                    .replace('__GEOJSON__', geo).replace('__CARDS__', ''.join(cards)))


def write_index(entries):
    """Rewrite docs/index.html from engine/index.html. Never edit docs/index.html by hand."""
    page = index_page(entries, (ROOT / 'engine' / 'index.html').read_text(encoding='utf-8'), load_ded_outlines())
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'docs' / 'index.html').write_text(page, encoding='utf-8')
    states = [e['state'] for e in entries]
    print('wrote docs/index.html:', len(entries), 'places on the map index (%d studies, %d with census, %d place records)'
          % (states.count('ready'), states.count('partial'), states.count('empty')))


def case_summary(base, label, today=None):
    """What the project holds for one case, as (source, detail) pairs for the index card. Counts only, taken from
    the same files the pages are built from: the census returns, the Griffith's transcription or index, the
    published baptisms (so the 100-year rule has already been applied), the family tree people and the images.
    A case with only a Logainm place record returns an empty list."""
    out = []
    rec = base / 'records'
    census = load(rec / 'census.json') if (rec / 'census.json').is_file() else {}
    held = [(y, len(census[y])) for y in sorted(census) if census[y]]
    if held:
        out.append(('Census', ', '.join('%s (%d %s)' % (y, n, 'person' if n == 1 else 'people') if i == 0
                                        else '%s (%d)' % (y, n) for i, (y, n) in enumerate(held))))
    rows = 0
    if (base / 'content.json').is_file():
        rows = len((load(base / 'content.json').get('griffiths') or {}).get('rows') or [])
    if rows:
        out.append(("Griffith's Valuation", '%d entries transcribed' % rows))
    elif (rec / 'griffiths_index.json').is_file():
        n = len(load(rec / 'griffiths_index.json').get('rows') or [])
        if n:
            out.append(("Griffith's Valuation", '%d entries in the index' % n))
    try:
        from tools import events as bt
    except ImportError:                  # run as a script: python tools/build.py
        import events as bt
    n = len(bt.baptism_events(label, today or datetime.date.today())[0])
    if n:
        out.append(('Parish register', '%d %s, Tawnawilly (NLI)' % (n, 'baptism' if n == 1 else 'baptisms')))
    if (rec / 'people.json').is_file():
        n = len(load(rec / 'people.json').get('people') or [])
        if n:
            out.append(('Family tree', '%d %s' % (n, 'person' if n == 1 else 'people')))
    media = base / 'media' / 'media.csv'
    if media.is_file():
        with media.open(encoding='utf-8-sig', newline='') as h:
            n = sum(1 for r in csv.DictReader(h) if (r.get('file') or '').strip() and (r.get('scope') or '').strip() != 'census')   # census forms are records, not photographs
        if n:
            out.append(('Images', '%d' % n))
    return out


def index_entries():
    """One dict for every case that has a name to show."""
    entries = []
    outlines = load_outlines()
    for base in sorted((ROOT / 'townlands').iterdir()):
        if not base.is_dir():
            continue
        state = case_state(base)[0]
        place = load(base / 'place.json') if (base / 'place.json').is_file() else {}
        if (base / 'townland.json').is_file():
            label = load(base / 'townland.json').get('name', base.name)
        elif place:
            label = place.get('name_en') or base.name
        else:
            continue
        entries.append({'slug': base.name, 'name': label, 'state': state, 'name_ga': place.get('name_ga', ''),
                        'lat': place.get('latitude', ''), 'lng': place.get('longitude', ''),
                        'outline': outlines.get(str(place.get('logainm_id', ''))), 'ded': place.get('ded_id', ''),
                        'doc': (ROOT / 'docs' / base.name / 'story.html').is_file(),
                        'summary': case_summary(base, label)})
    return entries


def main(argv):
    if argv:
        sys.exit(__doc__)
    entries = index_entries()
    write_index(entries)
    print('%d of %d places have a story page.' % (sum(1 for e in entries if e.get('doc')), len(entries)))


if __name__ == '__main__':
    main(sys.argv[1:])
