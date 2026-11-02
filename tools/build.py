"""Build townland pages.
Usage:
    python tools/build.py cullionboy     build one case
    python tools/build.py --all          report on, and build where possible, every case

For a case with everything the page needs, reads engine/walk.html and, from
townlands/<name>/:
  townland.json         name, page title, storage key, census spellings
  content.json          family stories, Griffith's rows, open questions, plate copy
  records/census.json   census rows (python tools/extract_census.py <name>)
Writes docs/<name>/index.html (served by GitHub Pages from /docs).

A case may hold less than that. That is a valid research state, not an error,
and every place publishes what it has:
  ready       all three files present: the full study page is built
  partial     some evidence present, not enough for a study: a place page is built
  empty       place identity only (place.json, STATUS.md): a place page is built
A place page (engine/place.html) shows the Logainm place record and says plainly
that research has not begun or is incomplete. It uses the same URL the full
study will use later, and it never invents content. Building never replaces a
page it did not generate, never deletes a page and never changes a case folder.
--all also regenerates docs/index.html, the list of every place.
Only a name with no case folder at all is an error."""
import csv, html as htmllib, json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
NEEDED = ('townland.json', 'content.json', 'records/census.json')
EVIDENCE = NEEDED + ('records/events.csv', 'records/corrections.json')


def load(p):
    with open(p, encoding='utf-8') as h:
        return json.load(h)
def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;')
def q(t): return htmllib.escape(str(t), quote=True)

PLACE_MARK = '<!-- generated: donegal-townlands place page -->'
INDEX_MARK = '<!-- generated: donegal-townlands index -->'


def case_state(base):
    """Return (state, missing_files) for a case folder."""
    missing = [f for f in NEEDED if not (base / f).is_file()]
    if not missing:
        return 'ready', []
    if any((base / f).is_file() for f in EVIDENCE):
        return 'partial', missing
    return 'empty', missing


def ded_names():
    """DED Logainm ID -> name, from the place register. Empty if unavailable."""
    path = ROOT / 'data' / 'processed' / 'places' / 'places.csv'
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8-sig', newline='') as h:
        return {r['logainm_id']: r['name_en'] for r in csv.DictReader(h) if r.get('place_type') == 'ded'}


def records_held(base):
    """Plain facts about evidence already in the case, for a partial page."""
    held = []
    cpath = base / 'records' / 'census.json'
    if cpath.is_file():
        for year, rows in sorted(load(cpath).items()):
            held.append('Census ' + year + ': ' + str(len(rows)) + ' people recorded')
    return held


def place_body(place, state, held):
    name = place.get('name_en') or 'Unnamed townland'
    out = ['<h1>' + q(name) + '</h1>']
    if place.get('name_ga'):
        out.append('<p class="ga" lang="ga">' + q(place['name_ga']) + '</p>')
    rows = []
    ded = ded_names().get(str(place.get('ded_id') or ''))
    rows.append(('Place type', 'Townland' + (', in the ' + ded + ' District Electoral Division' if ded else '')))
    rows.append(('Logainm', '<a href="https://www.logainm.ie/en/' + q(place['logainm_id']) + '">Logainm record ' + q(place['logainm_id']) + '</a>'))
    if place.get('latitude') and place.get('longitude'):
        lat, lon = place['latitude'], place['longitude']
        rows.append(('Location', '<a href="https://www.openstreetmap.org/?mlat=' + q(lat) + '&amp;mlon=' + q(lon) + '&amp;zoom=15">' + q(round(float(lat), 4)) + ', ' + q(round(float(lon), 4)) + '</a>'))
    out.append('<div class="card"><h2>Place record</h2><dl>' + ''.join('<dt>' + k + '</dt><dd>' + (v if k in ('Logainm', 'Location') else q(v)) + '</dd>' for k, v in rows) + '</dl></div>')
    if state == 'partial':
        text = 'Some historical records have been added for this townland, but not yet enough for a full study. This page will be replaced by the study as the research is completed.'
    else:
        text = 'No historical records have been added for this townland yet. This is a starting point, not a finding about its history. Records will be added here as they are researched.'
    out.append('<div class="card note"><h2>Research status</h2><p>' + q(text) + '</p></div>')
    if held:
        out.append('<div class="card"><h2>Records held so far</h2><ul>' + ''.join('<li>' + q(x) + '</li>' for x in held) + '</ul></div>')
    return '\n'.join(out)


def write_place_page(name, base, state, missing):
    place_path = base / 'place.json'
    if not place_path.is_file():
        print(name + ': ' + state + ' case with no place.json. Run tools/create_townland_cases.py. Not built.')
        return
    dest = ROOT / 'docs' / name / 'index.html'
    if dest.exists() and PLACE_MARK not in dest.read_text(encoding='utf-8'):
        print(name + ': docs/' + name + '/index.html was not generated as a place page. Left untouched.')
        return
    place = load(place_path)
    template = (ROOT / 'engine' / 'place.html').read_text(encoding='utf-8')
    page = (template.replace('__TITLE__', q((place.get('name_en') or name) + ' | Donegal Townlands'))
                    .replace('__BODY__', place_body(place, state, records_held(base))))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding='utf-8')
    print(name + ': ' + state + ' case. Place page written.')


def write_index(entries):
    """Rewrite docs/index.html: studies first, then places. entries = [(slug, name, state)]."""
    def links(items):
        return ''.join('    <a class="townland" href="./' + q(s) + '/">\n        ' + q(n) + ' &rarr;\n    </a>\n\n' for s, n, _ in items)
    studies = sorted((e for e in entries if e[2] == 'ready'), key=lambda e: e[1].casefold())
    places = sorted((e for e in entries if e[2] != 'ready'), key=lambda e: e[1].casefold())
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
    <p>Explore the townlands of County Donegal. Every townland has a page. Where research has begun, the page is a full study. The others show the place record and will be enriched as records are added.</p>

    <h2>Townland studies</h2>

""" + links(studies) + """    <h2>Townlands awaiting research</h2>

""" + links(places) + """    <footer>Irish-language placename data by Logainm, Government of Ireland, licensed under CC BY 4.0.</footer>
</body>
</html>
"""
    (ROOT / 'docs' / 'index.html').write_text(page, encoding='utf-8')
    print('wrote docs/index.html:', len(studies), 'studies,', len(places), 'places')


def build(name):
    """Build one case if it can be built. Returns its state."""
    base = ROOT / 'townlands' / name
    if not base.is_dir():
        sys.exit('No case folder townlands/' + name)
    state, missing = case_state(base)
    if state != 'ready':
        write_place_page(name, base, state, missing)
        return state
    townland = load(base / 'townland.json')
    content = load(base / 'content.json')
    census = load(base / 'records' / 'census.json')
    html = (ROOT / 'engine' / 'walk.html').read_text(encoding='utf-8')
    payload = json.dumps({'census': census, 'content': content, 'townland': townland}, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = (html.replace('__TITLE__', esc(townland['page_title']))
               .replace('__BRAND__', esc(townland['name']))
               .replace('__DATA__', payload))
    dest = ROOT / 'docs' / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'index.html').write_text(out, encoding='utf-8')
    print('wrote', dest / 'index.html', len(out), 'bytes')
    return state


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__)
    if argv[0] != '--all':
        build(argv[0])
        return
    counts = {'ready': 0, 'partial': 0, 'empty': 0}
    entries = []
    for base in sorted((ROOT / 'townlands').iterdir()):
        if not base.is_dir():
            continue
        state = build(base.name)
        counts[state] += 1
        if state == 'ready':
            label = load(base / 'townland.json').get('name', base.name)
        elif (base / 'place.json').is_file():
            label = load(base / 'place.json').get('name_en') or base.name
        else:
            continue
        entries.append((base.name, label, state))
    write_index(entries)
    print('Cases: %(ready)d studies, %(partial)d partial, %(empty)d empty. Every case with a place record has a page.' % counts)


if __name__ == '__main__':
    main(sys.argv[1:])
