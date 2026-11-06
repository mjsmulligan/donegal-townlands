"""Shared surname-variant reference (DECISIONS.md, 2026-11-05).

data/reference/surname_variants.csv holds spelling families as they are captured, because
variants recur across records and geography. One row is one family:

    family_id    short slug, unique
    label        the name a family plate would carry. A handle, not a correction
    spellings    the spellings as recorded, separated by |  (at least two)
    status       verified (Mike confirmed), proposed (a lead) or rejected (Mike said no)
    authority    who confirmed it. Required for a verified row
    basis        why. Required for a verified row
    observed_in  where it was seen. Required for a verified row
    added        the date the row was added
    notes        anything else

This file is the single surname dictionary (DECISIONS.md, 2026-11-06). Mike verifies a row
using local knowledge and a verified row applies to every townland: the build gives each
page the verified families whose spellings it holds. A proposed row is a lead and never
changes a page. An assistant adds rows only as proposed. A spelling may sit in only one
verified family, and a verified spelling may not appear in any other row.
Matching ignores case, spaces and punctuation."""
import csv
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / 'data' / 'reference' / 'surname_variants.csv'
FIELDS = ['family_id', 'label', 'spellings', 'status', 'authority', 'basis', 'observed_in', 'added', 'notes']
STATUSES = ('verified', 'proposed', 'rejected')


def key(spelling):
    return re.sub(r'[^a-z]', '', str(spelling).casefold())


def load(path=PATH):
    """Rows as dicts, with spellings as a list. An absent file is an empty reference."""
    if not pathlib.Path(path).is_file():
        return []
    with open(path, encoding='utf-8-sig', newline='') as h:
        rows = list(csv.DictReader(h))
    for r in rows:
        r['spellings'] = [s.strip() for s in (r.get('spellings') or '').split('|') if s.strip()]
    return rows


def check(path=PATH):
    """Problems with the reference file, as a list of messages. Empty means fine."""
    path = pathlib.Path(path)
    if not path.is_file():
        return []
    with open(path, encoding='utf-8-sig', newline='') as h:
        header = next(csv.reader(h), [])
    if header != FIELDS:
        return ['surname_variants.csv header is %s, expected %s' % (header, FIELDS)]
    errors, seen = [], set()
    for i, r in enumerate(load(path), 2):
        where = 'surname_variants.csv line %d (%s)' % (i, r.get('family_id') or '?')
        fid = r.get('family_id', '')
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', fid):
            errors.append(where + ': family_id must be a lower case slug')
        if fid in seen:
            errors.append(where + ': family_id repeats')
        seen.add(fid)
        if r['status'] not in STATUSES:
            errors.append(where + ': status must be one of ' + ', '.join(STATUSES))
        if len({key(s) for s in r['spellings']}) < 2:
            errors.append(where + ': needs at least two different spellings')
        if key(r['label']) not in {key(s) for s in r['spellings']}:
            errors.append(where + ': label must be one of the spellings')
        if r['status'] == 'verified':
            for f in ('authority', 'basis', 'observed_in'):
                if not r.get(f, '').strip():
                    errors.append(where + ': a verified row needs ' + f)
    errors += [m for m, severe in overlaps(load(path)) if severe]
    return errors


def overlaps(rows):
    """(message, severe) for each spelling held by more than one row, rejected rows left out.
    Severe when a verified row is involved, because that would change a page."""
    holders = {}
    for r in rows:
        if r['status'] == 'rejected':
            continue
        for sp in r['spellings']:
            holders.setdefault(key(sp), []).append(r)
    out = []
    for k, rs in sorted(holders.items()):
        if len(rs) > 1:
            ids = ', '.join(r['family_id'] for r in rs)
            out.append(('surname_variants.csv: the spelling %s is in more than one family (%s)' % (k, ids),
                        any(r['status'] == 'verified' for r in rs)))
    return out


def warnings(path=PATH):
    """Overlaps that involve only proposed rows. They do not fail validation."""
    return [m for m, severe in overlaps(load(path)) if not severe]


def page_families(present, rows=None):
    """Verified families for a page: label and spellings, for families with a spelling in `present`
    (an iterable of surnames the case holds). Only verified rows ever reach a page."""
    rows = load() if rows is None else rows
    have = {key(x) for x in present}
    return [{'label': r['label'], 'recorded_as': list(r['spellings'])} for r in rows
            if r['status'] == 'verified' and have & {key(sp) for sp in r['spellings']}]


def lookup(spelling, rows=None):
    """Families that list this spelling, rejected ones left out. Leads for Mike, never a rule."""
    rows = load() if rows is None else rows
    k = key(spelling)
    return [r for r in rows if r['status'] != 'rejected' and k in {key(s) for s in r['spellings']}]
