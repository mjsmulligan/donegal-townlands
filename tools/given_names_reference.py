"""Shared given-name equivalence reference (WP18, DECISIONS.md 2026-11-07).

data/reference/given_name_variants.csv holds families of first names that people used for
one another in the records, such as Bella and Isabella. It works like the surname
dictionary (tools/variants_reference.py). One row is one family:

    family_id    short slug, unique
    label        the name the family is known by. A handle, not a correction
    names        the names as recorded, separated by |  (at least two)
    status       verified (Mike confirmed), proposed (a lead) or rejected (Mike said no)
    authority    who confirmed it. Required for a verified row
    basis        why. Required for a verified row
    observed_in  where it was seen. Required for a verified row
    added        the date the row was added
    notes        anything else

Only Mike verifies a row. An assistant adds rows only as proposed. The census linker uses
verified rows. It uses proposed rows only when it is asked to, and then caps the link at
medium confidence. A name may sit in only one verified family and a verified name may not
appear in any other row. Matching ignores case, spaces and punctuation."""
import csv
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / 'data' / 'reference' / 'given_name_variants.csv'
FIELDS = ['family_id', 'label', 'names', 'status', 'authority', 'basis', 'observed_in', 'added', 'notes']
STATUSES = ('verified', 'proposed', 'rejected')


def key(name):
    return re.sub(r'[^a-z]', '', str(name).casefold())


def load(path=PATH):
    """Rows as dicts, with names as a list. An absent file is an empty reference."""
    if not pathlib.Path(path).is_file():
        return []
    with open(path, encoding='utf-8-sig', newline='') as h:
        rows = list(csv.DictReader(h))
    for r in rows:
        r['names'] = [s.strip() for s in (r.get('names') or '').split('|') if s.strip()]
    return rows


def check(path=PATH):
    """Problems with the reference file, as a list of messages. Empty means fine."""
    path = pathlib.Path(path)
    if not path.is_file():
        return []
    with open(path, encoding='utf-8-sig', newline='') as h:
        header = next(csv.reader(h), [])
    if header != FIELDS:
        return ['given_name_variants.csv header is %s, expected %s' % (header, FIELDS)]
    errors, seen = [], set()
    rows = load(path)
    for i, r in enumerate(rows, 2):
        where = 'given_name_variants.csv line %d (%s)' % (i, r.get('family_id') or '?')
        fid = r.get('family_id', '')
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', fid):
            errors.append(where + ': family_id must be a lower case slug')
        if fid in seen:
            errors.append(where + ': family_id repeats')
        seen.add(fid)
        if r['status'] not in STATUSES:
            errors.append(where + ': status must be one of ' + ', '.join(STATUSES))
        if len({key(s) for s in r['names']}) < 2:
            errors.append(where + ': needs at least two different names')
        if key(r['label']) not in {key(s) for s in r['names']}:
            errors.append(where + ': label must be one of the names')
        if r['status'] == 'verified':
            for f in ('authority', 'basis', 'observed_in'):
                if not r.get(f, '').strip():
                    errors.append(where + ': a verified row needs ' + f)
    holders = {}
    for r in rows:
        if r['status'] == 'verified':
            for n in r['names']:
                holders.setdefault(key(n), []).append(r['family_id'])
    for k, ids in sorted(holders.items()):
        if len(ids) > 1:
            errors.append('given_name_variants.csv: the name %s is in more than one verified family (%s)'
                          % (k, ', '.join(ids)))
    return errors


def groups(include_proposed=False, rows=None):
    """Name-key to family_id for verified rows, and for proposed rows when asked.
    Returns (map, proposed_ids) where proposed_ids are the families that are only proposed."""
    rows = load() if rows is None else rows
    out, proposed = {}, set()
    for r in rows:
        if r['status'] == 'verified' or (include_proposed and r['status'] == 'proposed'):
            if r['status'] == 'proposed':
                proposed.add(r['family_id'])
            for n in r['names']:
                out.setdefault(key(n), r['family_id'])
    return out, proposed
