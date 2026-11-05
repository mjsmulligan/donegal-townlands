#!/usr/bin/env python3
"""
Turn saved askaboutireland Griffith's search-result pages into a townland individuals CSV.

Usage:
    python tools/parse_griffiths_pages.py PAGE.html [PAGE2.html ...]

How the pages are made (by hand, in a browser): open the askaboutireland.ie Griffith's
Valuation search for one townland (the search URL is in the parish master), then use
Save Page As for each results page ("Results 1 to 20 of 38", then the [next] link, and so
on). Keep the saved .html files as retrieved in data/source/griffiths/raw/<townland>/.

Output:
    data/source/griffiths/<townland>_griffiths_individuals.csv   (same columns as the
    Cullionboy file, every row tier 1: not yet captured, not yet transcribed)

Two kinds of saved page are read: a browser's Save Page As (quoted attributes, a saved-from
comment holding the PlaceID) and the raw page source (unquoted attributes, relative links,
no PlaceID). Without a PlaceID the townland is found from the placename in the map link
and the parish master, and the run stops if that is not exactly one townland.

Checks, all reported on screen and any failure stops the run:
- every page is for one place (the PlaceID, or the placename when there is no PlaceID)
- the "of N" total on the pages equals the rows found
- a record id appears once
Gaps in the run of record ids are reported, not hidden: they may be entries the search
does not show, and they are left for Mike to look at. Rows are written in record id order.
The session id in the saved links expires. It is kept in this CSV only because the file is
a record of what was retrieved. attach_griffiths.py never uses it."""
import csv, html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = 'https://www.askaboutireland.ie/griffith-valuation/'
SRC = ROOT / 'data' / 'source' / 'griffiths'
FIELDS = ['townland', 'civil_parish', 'county', 'barony', 'askaboutireland_place_id', 'askaboutireland_record_id',
          'occupier_surname_as_indexed', 'occupier_forename_as_indexed', 'original_page_position_rs',
          'valuation_sheet_reference', 'details_url', 'original_page_url', 'map_url',
          'website_transcription_status', 'image_transcription_status', 'notes']


def absolute(url):
    return url if url.startswith('http') else SITE + url.lstrip('./')


def parse_page(text):
    """One saved results page -> (place_id or None, total, rows)."""
    place = re.search(r'PlaceID=(\d+)', text)
    total = re.search(r'Results \d+ to \d+ of (\d+)', text)
    if not total or not re.search(r'class=["\']?gv-results', text):
        raise ValueError('not an askaboutireland results page')
    rows = []
    start = re.search(r'class=["\']?gv-results', text).start()
    # Split on <tr> because the raw page source leaves rows unclosed. Stop at the end of the table.
    for chunk in re.split(r'<tr\b[^>]*>', text[start:].split('</table>')[0])[1:]:
        if not re.match(r'\s*<td class=["\']?results["\']?>', chunk):
            continue                      # the header row
        cells = re.findall(r'<td class=["\']?results["\']?[^>]*>(.*?)</td>', chunk, flags=re.S)
        name = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip() for c in cells[:4]]
        hrefs = [absolute(html.unescape(h)) for h in re.findall(r'href=["\']?([^"\' >]+)', chunk)]
        details = next((h for h in hrefs if 'action=showDetails' in h), '')
        image = next((h for h in hrefs if 'action=showImage' in h), '')
        mapv = next((h for h in hrefs if 'action=i8' in h), '')
        rid = re.search(r'ID=(\d+)', details or image)
        rs = re.search(r'rs=(\d+)', image)
        if not (rid and rs):
            raise ValueError('a result row has no record id or page position')
        image = re.sub(r'&width=\d+&height=\d+', '', image)
        sheet = re.search(r'sheet=([^&]*)', mapv)
        baron = re.search(r'barony=([^&]*)', mapv)
        rows.append({'surname': name[0], 'forename': name[1], 'county': name[2], 'parish': name[3],
                     'record_id': int(rid.group(1)), 'rs': int(rs.group(1)),
                     'details': details, 'image': image, 'map': mapv,
                     'sheet': sheet.group(1) if sheet else '', 'barony': baron.group(1) if baron else ''})
    return (int(place.group(1)) if place else None), int(total.group(1)), rows


def load_master(src=SRC):
    p = src / 'donegal_griffiths_parish_master_complete.csv'
    out = {}
    if p.is_file():
        with p.open(encoding='utf-8-sig', newline='') as h:
            for r in csv.DictReader(h):
                out[r['askaboutireland_place_id']] = r['townland']
    return out


def load_names(src=SRC):
    """askaboutireland placename (upper case) -> (place id, townland), from the parish master."""
    p = src / 'donegal_griffiths_parish_master_complete.csv'
    out = {}
    if p.is_file():
        with p.open(encoding='utf-8-sig', newline='') as h:
            for r in csv.DictReader(h):
                out.setdefault((r.get('askaboutireland_placename') or r['townland']).upper(), []).append(
                    (int(r['askaboutireland_place_id']), r['townland']))
    return out


def build(pages, master, say=print, names=None):
    """pages: list of page texts. Returns (townland, csv_rows)."""
    place_ids, totals, rows, placenames, named = set(), set(), [], set(), None
    for text in pages:
        pid, total, got = parse_page(text)
        place_ids.add(pid); totals.add(total); rows += got
        placenames |= {re.search(r'placename=([^&]*)', r['map']).group(1).upper() for r in got
                       if re.search(r'placename=([^&]*)', r['map'])}
    if len(totals) != 1:
        raise ValueError('pages disagree on the total: %s' % sorted(totals))
    if None in place_ids:
        if len(place_ids) > 1 or len(placenames) != 1:
            raise ValueError('pages are for different places or a page names none')
        found = (names or {}).get(next(iter(placenames)).replace('%2C', ',').replace('%20', ' '), [])
        if len(found) != 1:
            raise ValueError('placename %s is not exactly one townland in the parish master' % sorted(placenames))
        place_ids = {found[0][0]}
        named = found[0][1]
        say('  no PlaceID in the pages: townland found from the placename %s' % next(iter(placenames)))
    if len(place_ids) != 1:
        raise ValueError('pages are for different places: %s' % sorted(place_ids))
    pid, total = place_ids.pop(), totals.pop()
    ids = [r['record_id'] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('a record id appears more than once (the same page given twice?)')
    if len(rows) != total:
        raise ValueError('pages say %d entries but %d rows were found (a page is missing?)' % (total, len(rows)))
    rows.sort(key=lambda r: r['record_id'])
    gaps = [(a, b) for a, b in zip(ids and sorted(ids), sorted(ids)[1:]) if b - a > 1]
    for a, b in gaps:
        say('  record ids %d to %d are not in the listing (%d ids)' % (a + 1, b - 1, b - a - 1))
    guess = re.search(r'townland=([^&]*)', rows[0]['map'])
    townland = master.get(str(pid)) or named or (guess.group(1).title() if guess else '')
    if not townland:
        raise ValueError('cannot tell which townland these pages are for')
    out = []
    for r in rows:
        blank = not r['surname'] and not r['forename']
        out.append({'townland': townland, 'civil_parish': r['parish'].title(), 'county': r['county'].title(),
                    'barony': r['barony'].title(), 'askaboutireland_place_id': pid,
                    'askaboutireland_record_id': r['record_id'], 'occupier_surname_as_indexed': r['surname'],
                    'occupier_forename_as_indexed': r['forename'], 'original_page_position_rs': r['rs'],
                    'valuation_sheet_reference': r['sheet'], 'details_url': r['details'], 'original_page_url': r['image'],
                    'map_url': r['map'], 'website_transcription_status': 'not yet captured',
                    'image_transcription_status': 'not yet transcribed',
                    'notes': 'Blank occupier name in source index; retain as an entry' if blank else ''})
    return townland, out


def main(argv):
    if not argv:
        print(__doc__); return 2
    pages = [pathlib.Path(a).read_bytes().decode('cp1252', errors='replace') for a in argv]
    try:
        townland, rows = build(pages, load_master(), names=load_names())
    except ValueError as e:
        print('stopped: ' + str(e)); return 1
    out = SRC / ('%s_griffiths_individuals.csv' % re.sub(r'[^a-z0-9]+', '-', townland.casefold()).strip('-'))
    if out.exists():
        print('stopped: %s already exists. Retrieved sources are never overwritten.' % out.name); return 1
    with out.open('w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, FIELDS); w.writeheader(); w.writerows(rows)
    print('%s: %d entries written to %s' % (townland, len(rows), out.relative_to(ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
