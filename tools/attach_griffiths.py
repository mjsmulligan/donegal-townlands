#!/usr/bin/env python3
"""
Attach the askaboutireland Griffith's index to townland cases.

Usage:
    python tools/attach_griffiths.py

Inputs (kept exactly as retrieved, never edited):
    data/source/griffiths/donegal_griffiths_parish_master_complete.csv
        the parish master: one row per townland with its askaboutireland place id
    data/source/griffiths/<townland>_griffiths_individuals.csv
        one row per index entry for one townland

Outputs, per townland that has an individuals file:
    townlands/<case>/records/griffiths_index.json    tier 1 rows, ready for the page
    townlands/<case>/records/griffiths_match.json    only when the case also holds an
                                                     authored transcription (content.json)
Output for the whole run: a report on screen.

Three tiers of effort (DECISIONS.md, 2026-11-04):
    1  the index: names, page position, record id (the minimum, retrieved first)
    2  the detail page: holding number, lessor, description, area
    3  the page image: valuations, which need real transcription
A row's tier comes from its two status columns. A row matched to the authored
transcription in content.json counts as tier 3 whatever the status columns say.

Rules.
- The CSVs carry session ids in their URLs. These expire, so only the record and
  place ids are kept and the links are rebuilt without a session. The rebuilt links
  have not been opened from the build environment (network access is restricted).
  Mike to spot-check one.
- Index entries that are not occupiers (a blank name, a title such as EARL OF ARRAN
  at the foot of the page) are kept and labelled "foot_entry", as a proposed reading
  for Mike to confirm. They are never counted as households.
- Matching to a transcription is by page order, then checked name by name. A mismatch
  is reported and recorded, never silently resolved.
- Authored content.json is never changed."""
import csv, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'source' / 'griffiths'
BASE = 'https://www.askaboutireland.ie/griffith-valuation/'
FOOT_TITLES = ('EARL OF', 'MARQUIS OF', 'MARQUESS OF', 'VISCOUNT', 'LORD', 'LADY', 'DUKE OF', 'COUNTESS OF')


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.casefold()).strip('-')


def details_url(record_id):
    return BASE + 'details.xml?action=showDetails&ID=%s&la=' % record_id


def image_url(record_id, position):
    return BASE + 'details.xml?action=showImage&ID=%s&rs=%s' % (record_id, position)


def tier_of(row):
    if (row.get('image_transcription_status') or '').strip().lower() == 'transcribed':
        return 3
    if (row.get('website_transcription_status') or '').strip().lower() == 'captured':
        return 2
    return 1


def role_of(surname, forename):
    if not surname.strip() and not forename.strip():
        return 'foot_entry', 'blank name in the source index'
    if any(forename.strip().upper().startswith(t) for t in FOOT_TITLES):
        return 'foot_entry', 'a title in the forename field, probably a proprietor line at the foot of the page'
    return 'occupier', ''


def read_index(path):
    out = []
    with path.open(encoding='utf-8-sig', newline='') as h:
        for r in csv.DictReader(h):
            surname = (r.get('occupier_surname_as_indexed') or '').strip()
            forename = (r.get('occupier_forename_as_indexed') or '').strip()
            role, why = role_of(surname, forename)
            rid = int(r['askaboutireland_record_id'])
            pos = int(r['original_page_position_rs'])
            out.append({
                'record_id': rid, 'position': pos,
                'surname': surname, 'forename': forename,
                'role': role, 'role_note': why,
                'sheet': r.get('valuation_sheet_reference', ''),
                'tier': tier_of(r), 'note': (r.get('notes') or '').strip(),
                'details_url': details_url(rid), 'image_url': image_url(rid, pos),
            })
    out.sort(key=lambda x: x['position'])
    return out


def tokens(text):
    text = re.sub(r'\([^)]*\)', ' ', text)          # nicknames such as (Wee), (Long)
    return sorted(t for t in re.sub(r'[^a-z0-9 ]+', ' ', text.casefold()).split() if t)


def match(rows, transcribed):
    """Pair authored rows with occupier index rows by page order and check names."""
    occ = [r for r in rows if r['role'] == 'occupier']
    pairs, problems = [], []
    for i, t in enumerate(transcribed):
        if i >= len(occ):
            problems.append('transcribed row %d (%s) has no index entry' % (i + 1, t.get('occ')))
            continue
        r = occ[i]
        same = tokens(t.get('occ', '')) == tokens(r['forename'] + ' ' + r['surname'])
        pairs.append({'record_id': r['record_id'], 'position': r['position'],
                      'lot': t.get('lot'), 'transcribed_occupier': t.get('occ'),
                      'index_name': (r['forename'] + ' ' + r['surname']).strip(), 'names_agree': same})
        if not same:
            problems.append('page order pairs %r with index %r: names differ' % (t.get('occ'), r['forename'] + ' ' + r['surname']))
    for r in occ[len(transcribed):]:
        problems.append('index entry %s %s (position %d) has no transcribed row' % (r['forename'], r['surname'], r['position']))
    return pairs, problems


def case_folder(townland):
    return ROOT / 'townlands' / slug(townland)


def run(src=SRC, root=ROOT, say=print):
    master = {}
    mp = src / 'donegal_griffiths_parish_master_complete.csv'
    if mp.is_file():
        with mp.open(encoding='utf-8-sig', newline='') as h:
            for r in csv.DictReader(h):
                master[r['townland']] = r
    problems_total = 0
    for path in sorted(src.glob('*_griffiths_individuals.csv')):
        name = path.name.split('_griffiths_individuals.csv')[0]
        with path.open(encoding='utf-8-sig', newline='') as h:
            first = next(csv.DictReader(h), None)
        if not first:
            say('%s: empty file, skipped' % path.name); continue
        townland = first[[k for k in first if k.endswith('townland')][0]]
        folder = root / 'townlands' / slug(townland)
        if not folder.is_dir():
            say('%s: no case folder townlands/%s, skipped' % (townland, slug(townland))); problems_total += 1; continue
        rows = read_index(path)
        m = master.get(townland, {})
        index = {
            'source': 'askaboutireland.ie Griffith\'s Valuation index',
            'townland': townland, 'civil_parish': first.get('civil_parish', ''), 'barony': first.get('barony', ''),
            'askaboutireland_place_id': int(first['askaboutireland_place_id']),
            'parish_master_entries': int(m['number_of_entries']) if m.get('number_of_entries') else None,
            'rows': rows,
        }
        (folder / 'records').mkdir(exist_ok=True)
        (folder / 'records' / 'griffiths_index.json').write_text(json.dumps(index, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        say('%s: %d index entries (%d occupiers), tiers %s' % (townland, len(rows), sum(r['role'] == 'occupier' for r in rows),
            sorted({r['tier'] for r in rows})))
        if index['parish_master_entries'] is not None and index['parish_master_entries'] != len(rows):
            say('  parish master says %s entries, file has %d' % (index['parish_master_entries'], len(rows))); problems_total += 1
        cp = folder / 'content.json'
        authored = json.loads(cp.read_text(encoding='utf-8')) if cp.is_file() else {}
        trows = (authored.get('griffiths') or {}).get('rows')
        if trows:
            pairs, problems = match(rows, trows)
            out = {'basis': 'page order, then names compared without nicknames', 'pairs': pairs, 'problems': problems,
                   'tier_for_matched_rows': 3}
            (folder / 'records' / 'griffiths_match.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
            say('  matched %d of %d transcribed rows, %d problems' % (sum(p['names_agree'] for p in pairs), len(trows), len(problems)))
            for p in problems: say('    ' + p)
            problems_total += len(problems)
    return problems_total


if __name__ == '__main__':
    sys.exit(1 if run() else 0)
