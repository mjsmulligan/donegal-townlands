"""Review report for the surname dictionary (DECISIONS.md, 2026-11-06).

    python tools/variants_report.py            each dictionary row with where each spelling occurs
    python tools/variants_report.py --unassigned   surnames in the records that are in no row

Counts come from every case's records/census.json (household heads and members, by return year)
and records/griffiths_index.json (occupiers). It reads data and writes nothing, so Mike can
verify or reject rows with the evidence in front of him."""
import collections
import json
import pathlib
import sys

try:
    from tools import variants_reference as vr
except ImportError:
    import variants_reference as vr

ROOT = pathlib.Path(__file__).resolve().parent.parent


def observed():
    """{spelling key: {'name': most common recorded form, 'where': Counter of 'townland census 1901' etc}}"""
    seen = {}

    def add(sn, where):
        if not str(sn).strip():
            return
        e = seen.setdefault(vr.key(sn), {'forms': collections.Counter(), 'where': collections.Counter()})
        e['forms'][str(sn).strip().title()] += 1
        e['where'][where] += 1

    for case in sorted((ROOT / 'townlands').iterdir()):
        cj, gj = case / 'records' / 'census.json', case / 'records' / 'griffiths_index.json'
        if cj.is_file():
            c = json.loads(cj.read_text(encoding='utf-8'))
            for year, rows in (c.get('years') or c).items():
                for r in rows if isinstance(rows, list) else []:
                    add(r.get('s', ''), '%s %s' % (case.name, year))
        if gj.is_file():
            for r in json.loads(gj.read_text(encoding='utf-8')).get('rows', []):
                if r.get('role') == 'occupier':
                    add(r.get('surname', ''), '%s Griffith\'s' % case.name)
    return seen


def main(argv):
    seen, rows = observed(), vr.load()
    if '--unassigned' in argv:
        known = {vr.key(s) for r in rows if r['status'] != 'rejected' for s in r['spellings']}
        for k, e in sorted(seen.items(), key=lambda kv: -sum(kv[1]['where'].values())):
            if k not in known:
                print('%4d  %s' % (sum(e['where'].values()), e['forms'].most_common(1)[0][0]))
        return 0
    for r in rows:
        print('%s  [%s]  label %s' % (r['family_id'], r['status'], r['label']))
        for s in r['spellings']:
            e = seen.get(vr.key(s))
            where = ', '.join('%s x%d' % kv for kv in sorted(e['where'].items())) if e else 'not in the records held'
            print('    %-12s %s' % (s, where))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
