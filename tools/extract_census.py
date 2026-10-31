"""Extract one townland's census rows from the Clogher DED files into records/census.json.
usage: python tools/extract_census.py <townland-folder-name>      e.g. cullionboy
Reads townlands/<name>/townland.json (townland spellings per census year) and, if present,
townlands/<name>/records/corrections.json (explicit researcher corrections, each with a reason).
Writes townlands/<name>/records/census.json."""
import csv, json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
D = str(ROOT / 'data' / 'census') + '/'
# Source files are in data/census/. Note: the sister repo (irish-genealogy-research, data/Clogher_*.csv) holds an older
# 1926 file that lacks about 500 researcher-filled relationship values, so these local copies are the verified source for now.
def L(f): return list(csv.DictReader(open(D + f, encoding='utf-8')))
def num(v):
    try: return int(float(v))
    except: return None
if len(sys.argv) != 2:
    sys.exit(__doc__)
name = sys.argv[1]
base = ROOT / 'townlands' / name
meta = json.load(open(base / 'townland.json', encoding='utf-8'))
sp = meta['census_spelling']
cpath = base / 'records' / 'corrections.json'
corrections = json.load(open(cpath, encoding='utf-8')) if cpath.exists() else {}
out = {}
for y, f in ((1901, '1901_Clogher.csv'), (1911, '1911_Clogher.csv')):
    r = [x for x in L(f) if x['townland'] == sp[str(y)]]
    out[str(y)] = [{'h': num(x['house_number']), 's': x['surname'], 'f': x['firstname'], 'a': num(x['age']), 'x': x['sex'], 'r': x['relation_to_head_updated'], 'm': x['marriage_status'], 'o': x['occupation_updated'], 'i': 1 if 'Irish' in x['language_updated'] else 0} for x in r]
r = [x for x in L('1926_Clogher.csv') if x['townland'] == sp['1926']]
rows = []
for x in r:
    fo = x['aform_name'].split('_')[3]
    cl = x['children_living']
    m = x['updated_marriage'] or ((cl + ' children living') if cl.isdigit() else '')
    rows.append({'h': fo, 'fo': fo, 's': x['surname'], 'f': x['first_name'], 'a': num(x['updated_age']), 'x': x['updated_sex'], 'r': x['updated_relationship_to_head'] or x['relationship_to_head'], 'm': m, 'o': '', 'i': 1 if 'Irish' in x['updated_irish_language'] else 0})
rows.sort(key=lambda z: z['fo'])
out['1926'] = rows
for y, rules in corrections.items():
    for rule in rules:
        hit = [z for z in out[y] if all(z.get(k) == v for k, v in rule['match'].items())]
        for z in hit:
            z.update(rule['set'])
        print('correction', y, rule['match'], '->', rule['set'], ':', len(hit), 'rows.', rule['reason'])
json.dump(out, open(base / 'records' / 'census.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print({k: len(v) for k, v in out.items()})
