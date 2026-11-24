"""Survey every townland case and report how rich its data is and what story it would get
(docs/TOWNLAND_STORY_ROLLOUT_SPEC.md, WP-R1 and RO-06).

Usage:
    python tools/story_report.py                 print the summary, write the CSV
    python tools/story_report.py cullionboy ...  only the named cases
    python tools/story_report.py --no-csv        print only

The report is read only. It runs the generator's own pure logic (`build_story.generate`) in
memory, so the beats it counts are the beats a build would write, and it writes nothing to
`townlands/` or `docs/`. The one file it writes is `data/processed/story_report.csv`, which is
not committed (see .gitignore). A case that fails is reported with its error and never stops the run.
"""
import csv, datetime, json, math, statistics, sys

try:
    from tools import build_story as bd, build_timeline as bt
except ImportError:                  # run as a script: python tools/story_report.py
    import build_story as bd
    import build_timeline as bt

ROOT = bt.ROOT
OUT = ROOT / 'data' / 'processed' / 'story_report.csv'
KINDS = ('title', 'valuation', 'baptism', 'census', 'photo', 'closing')
FIELDS = ['townland', 'name', 'tier', 'census_years', 'census_people_max', 'baptisms', 'baptisms_left_out',
          'griffiths_occupiers', 'authored_content', 'media_files', 'people_json', 'lat', 'lon', 'coords',
          'events', 'has_story', 'beats'] + ['beats_' + k for k in KINDS] + ['duration_s', 'refused', 'files_written', 'note']
# Donegal sits roughly inside this box. A point outside it is a data error, not a judgement call.
DONEGAL_BOX = (54.4, 55.5, -8.9, -7.0)
OUTLIER_KM = 12.0


def km(a, b):
    """Great circle distance in kilometres between two (lat, lon) pairs."""
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def tier(row):
    """A plain label for how much a case holds. Not a quality score."""
    if row['authored_content'] and row['events'] and row['baptisms'] and row['griffiths_occupiers']:
        return 'A full'
    if row['authored_content']:
        return 'B authored'
    if row['griffiths_occupiers'] and row['census_years']:
        return 'C valuation+census'
    if row['baptisms'] and row['census_years']:
        return 'D census+baptisms'
    if row['census_years']:
        return 'E census only'
    return 'F thin'


def survey_case(name, today):
    """One row for one case. Never raises."""
    base = ROOT / 'townlands' / name
    row = {f: '' for f in FIELDS}
    row.update(townland=name, name=name.title(), refused='', note='')
    try:
        inputs, problems = bd.collect(name, today)
        if inputs is None:
            row['tier'] = 'error'
            row['note'] = ' '.join(problems)
            return row
        place, feed = inputs['place'], inputs['feed']
        events = feed['events']
        display = inputs['display']
        row['name'] = display
        cens = [e for e in events if e['type'] == 'census']
        baps = [e for e in events if e['type'] == 'baptism']
        vals = [e for e in events if e['type'] == 'valuation']
        row['census_years'] = ' '.join(e['date']['label'] for e in cens)
        row['baptisms'] = len(baps)
        row['baptisms_left_out'] = len(feed['skipped'])
        row['griffiths_occupiers'] = bd_count(vals)
        row['authored_content'] = (base / 'content.json').is_file()
        row['people_json'] = (base / 'records' / 'people.json').is_file()
        census_file = base / 'records' / 'census.json'
        if census_file.is_file():
            data = json.loads(census_file.read_text(encoding='utf-8'))
            row['census_people_max'] = max([len(v) for v in data.values()] or [0])
        row['media_files'] = len(inputs['found']['rows'])
        lat, lon = bd._num(place.get('latitude')), bd._num(place.get('longitude'))
        row['lat'], row['lon'] = '' if lat is None else lat, '' if lon is None else lon
        row['coords'] = 'none' if lat is None or lon is None else 'ok'
        if row['coords'] == 'ok' and not (DONEGAL_BOX[0] <= lat <= DONEGAL_BOX[1] and DONEGAL_BOX[2] <= lon <= DONEGAL_BOX[3]):
            row['coords'] = 'outside Donegal'
        row['events'] = len(events)
        row['tier'] = tier(row)
        doc, refused = bd.generate(*inputs['args'])
        beats = [b for c in doc['chapters'] for b in c['beats']]
        row['has_story'] = len(events) >= 2
        row['beats'] = len(beats)
        for k in KINDS:
            row['beats_' + k] = sum(1 for b in beats if b['kind'] == k)
        row['duration_s'] = round(sum(b['duration_ms'] for b in beats) / 1000, 1)
        row['refused'] = '; '.join(f'{i}: {w}' for i, w in refused + list(feed['skipped']))
        row['note'] = doc.get('note', '')
    except Exception as e:           # RO-01: a survey never stops on one case
        row['tier'] = row['tier'] or 'error'
        row['note'] = f'error: {type(e).__name__}: {e}'
    return row


def bd_count(valuations):
    """Occupiers named in the Griffith's event text, or 0."""
    for v in valuations:
        words = v['text'].split('. ', 1)[-1].split()
        if words and words[0].isdigit():
            return int(words[0])
    return 0


def flag_coordinates(rows):
    """RO-08: flag points far from the other cases. Reports, never corrects."""
    pts = [(float(r['lat']), float(r['lon'])) for r in rows if r['coords'] == 'ok']
    if not pts:
        return
    centre = (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts))
    for r in rows:
        if r['coords'] == 'ok' and km((float(r['lat']), float(r['lon'])), centre) > OUTLIER_KM:
            r['coords'] = f'far from the others ({km((float(r["lat"]), float(r["lon"])), centre):.0f} km)'


def write_csv(rows, path=OUT):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as h:
        w = csv.DictWriter(h, fieldnames=FIELDS, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def summary(rows):
    lines = [f'{len(rows)} cases surveyed.']
    tiers = {}
    for r in rows:
        tiers.setdefault(r['tier'], []).append(r)
    for t in sorted(tiers):
        group = tiers[t]
        stories = sum(1 for r in group if r['has_story'])
        lines.append(f'  {t}: {len(group)} cases, {stories} with a story.')
    years = {}
    for r in rows:
        n = len(str(r['census_years']).split())
        years[n] = years.get(n, 0) + 1
    lines.append('  Census years held: ' + ', '.join(f'{n} year(s) in {c}' for n, c in sorted(years.items())) + '.')
    for t in ('A full', 'B authored'):
        for r in tiers.get(t, []):
            lines.append(f"  {r['townland']}: {r['beats']} beats, {r['duration_s']} s.")
    bad = [r for r in rows if r['coords'] != 'ok']
    if bad:
        lines.append('Coordinates to look at: ' + ', '.join(f"{r['townland']} ({r['coords']})" for r in bad) + '.')
    errors = [r for r in rows if str(r['note']).startswith('error')]
    if errors:
        lines.append('Errors: ' + ', '.join(f"{r['townland']} ({r['note']})" for r in errors) + '.')
    lines.append('Largest census population: ' + ', '.join(
        f"{r['townland']} {r['census_people_max']}" for r in sorted(
            (r for r in rows if r['census_people_max'] != ''), key=lambda r: -r['census_people_max'])[:3]) + '.')
    return '\n'.join(lines)


def report(names, today, files=None, csv_out=True):
    """Survey `names`, flag coordinates, optionally record the files a build wrote, write the CSV and print
    the summary (RO-06). Returns the rows."""
    rows = [survey_case(n, today) for n in names]
    for r in rows:
        r['files_written'] = '; '.join((files or {}).get(r['townland'], []))
    flag_coordinates(rows)
    if csv_out:
        write_csv(rows)
    print(summary(rows))
    return rows


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    if any(a.startswith('--') and a != '--no-csv' for a in argv[1:]):
        sys.exit(__doc__)
    report(args or bd.all_cases(), datetime.date.today(), csv_out='--no-csv' not in argv)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
