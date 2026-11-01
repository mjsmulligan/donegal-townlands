"""Checks run before every commit: python tools/validate.py
1. No em dashes in project text and code files.
2. Living-people rule (100/75/50) for townland event records.
3. Census files stay at 1926 or earlier.
4. Preserved census source files match data/source/manifest.csv.
Exit code 1 on any failure.
"""
import csv
import datetime
import pathlib
import re
import sys

from source_manifest import verify_manifest

ROOT = pathlib.Path(__file__).resolve().parent.parent
THIS = datetime.date.today().year
LIMIT = {'birth': 100, 'baptism': 100, 'marriage': 75, 'death': 50, 'burial': 50}
bad = []

for path in ROOT.rglob('*'):
    if path.is_file() and path.suffix in {'.md', '.py', '.html', '.yaml', '.yml', '.json', '.txt'} and '.git' not in path.parts and path.name != 'validate.py':
        if '\u2014' in path.read_text(encoding='utf-8', errors='ignore'):
            bad.append(f'em dash in {path.relative_to(ROOT)}')

overrides = {}
override_path = ROOT / 'privacy_overrides.csv'
if override_path.exists():
    with override_path.open(encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            overrides[row['person']] = row['decision']

for path in ROOT.glob('townlands/*/records/events.csv'):
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    deceased = {row['person'] for row in rows if row['event'] in ('death', 'burial')}
    for row in rows:
        if overrides.get(row['person']) == 'allow':
            continue
        year = int(row['year'])
        limit = LIMIT[row['event']]
        if THIS - year < limit:
            bad.append(f"{path.parent.parent.name}: {row['person']} {row['event']} {year} is less than {limit} years old")
        if row['event'] in ('birth', 'baptism') and THIS - year < 100 and row['person'] not in deceased:
            bad.append(f"{path.parent.parent.name}: {row['person']} presumed living")

for path in (ROOT / 'data' / 'census').glob('*.csv'):
    match = re.match(r'(\d{4})_', path.name)
    if match and int(match.group(1)) > 1926:
        bad.append(f'census year after 1926: {path.name}')

# Verify the source manifest and its exact file inventory. This is also called
# by the command-line tool, but importing the function keeps one implementation.
if verify_manifest() != 0:
    bad.append('source manifest verification failed')

print('\n'.join(bad) or 'validate: ok')
sys.exit(1 if bad else 0)
