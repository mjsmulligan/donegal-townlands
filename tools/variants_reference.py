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

A row is a lead and never a rule. A spelling that is one family in one townland may be
unrelated families in another, so nothing here groups spellings on a page by itself.
A townland's own records/name_families.json does that, once Mike has confirmed it.
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
    return errors


def lookup(spelling, rows=None):
    """Families that list this spelling, rejected ones left out. Leads for Mike, never a rule."""
    rows = load() if rows is None else rows
    k = key(spelling)
    return [r for r in rows if r['status'] != 'rejected' and k in {key(s) for s in r['spellings']}]
