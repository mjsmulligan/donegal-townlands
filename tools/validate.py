"""Checks run before every commit:  python tools/validate.py
1. No em dashes in any text file we write.
2. Living-people rule (100/75/50): any townlands/*/records/events.csv row must be old enough.
   Columns: person,event,year,source   (event: birth|baptism|marriage|death|burial)
   Rolling: measured against the current year. Overrides in privacy_overrides.csv (person,decision,reason).
3. Census files stay at 1926 or earlier.
Exit code 1 on any failure."""
import csv, datetime, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
THIS = datetime.date.today().year
LIMIT = {'birth': 100, 'baptism': 100, 'marriage': 75, 'death': 50, 'burial': 50}
bad = []
for p in ROOT.rglob('*'):
    if p.is_file() and p.suffix in {'.md', '.py', '.html', '.yaml', '.yml', '.json', '.txt'} and '.git' not in p.parts and p.name != 'validate.py':
        if '—' in p.read_text(encoding='utf-8', errors='ignore'):
            bad.append(f'em dash in {p.relative_to(ROOT)}')
over = {}
op = ROOT / 'privacy_overrides.csv'
if op.exists():
    for r in csv.DictReader(open(op, encoding='utf-8')):
        over[r['person']] = r['decision']
for p in ROOT.glob('townlands/*/records/events.csv'):
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    deceased = {r['person'] for r in rows if r['event'] in ('death', 'burial')}
    for r in rows:
        if over.get(r['person']) == 'allow':
            continue
        y = int(r['year']); lim = LIMIT[r['event']]
        if THIS - y < lim:
            bad.append(f"{p.parent.parent.name}: {r['person']} {r['event']} {y} is less than {lim} years old")
        if r['event'] in ('birth', 'baptism') and THIS - y < 100 and r['person'] not in deceased:
            bad.append(f"{p.parent.parent.name}: {r['person']} presumed living")
for p in (ROOT / 'data' / 'census').glob('*.csv'):
    m = re.match(r'(\d{4})_', p.name)
    if m and int(m.group(1)) > 1926:
        bad.append(f'census year after 1926: {p.name}')
print('\n'.join(bad) or 'validate: ok')
sys.exit(1 if bad else 0)
