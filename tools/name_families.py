"""Verified surname-spelling families for a townland case (DECISIONS.md, 2026-11-05).

A case may hold townlands/<name>/records/name_families.json:

    {"families": [{
        "label": "McAnaw",                       the name the family plate carries
        "status": "verified",                    verified, proposed or rejected
        "scope": "townland",                     applies to every entry in this townland with these spellings
        "recorded_as": ["McKenna", "McAna"],     the spellings, exactly as recorded
        "authority": "Mike", "decided": "2026-11-05",
        "basis": "...", "note": "..."            research detail, kept in the data and never put on the page
    }]}

Spelling belongs to the record: the label is a handle chosen for the family, not a
correction, and no spelling is the right one. Only verified families change the page, and
the page gets only the label and the spellings. basis and note are for the researcher view.
A spelling may belong to one family in a case. Matching ignores case, spaces and punctuation."""
import json
import re

STATUSES = ('verified', 'proposed', 'rejected')
REQUIRED = ('label', 'status', 'scope', 'recorded_as', 'authority', 'decided', 'basis')


def key(spelling):
    return re.sub(r'[^a-z]', '', str(spelling).casefold())


def load_case(base):
    """(families for the page, errors) for townlands/<name>/. The page list holds verified families only."""
    path = base / 'records' / 'name_families.json'
    if not path.is_file():
        return [], []
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as e:
        return [], ['records/name_families.json is not valid JSON: %s' % e]
    errors, shown, owner = [], [], {}
    for i, f in enumerate(raw.get('families') or [], 1):
        where = 'name_families.json family %d' % i
        missing = [k for k in REQUIRED if not f.get(k)]
        if missing:
            errors.append('%s is missing %s' % (where, ', '.join(missing))); continue
        if f['status'] not in STATUSES:
            errors.append('%s: status must be one of %s' % (where, ', '.join(STATUSES))); continue
        if f['scope'] != 'townland':
            errors.append('%s: scope must be townland for now' % where); continue
        if not isinstance(f['recorded_as'], list) or len(f['recorded_as']) < 2:
            errors.append('%s: recorded_as needs at least two spellings' % where); continue
        keys = [key(s) for s in f['recorded_as']]
        if key(f['label']) not in keys:
            errors.append('%s: the label %s is not one of the recorded spellings' % (where, f['label']))
        for s, k in zip(f['recorded_as'], keys):
            if k in owner:
                errors.append('%s: %s is already in the family %s' % (where, s, owner[k]))
            owner[k] = f['label']
        if f['status'] == 'verified':
            shown.append({'label': f['label'], 'recorded_as': list(f['recorded_as'])})
    return shown, errors
