"""Build a townland page.  Usage: python tools/build.py cullionboy
Reads engine/walk.html and, from townlands/<name>/:
  townland.json         name, page title, storage key, census spellings
  content.json          family stories, Griffith's rows, open questions, plate copy
  records/census.json   census rows (python tools/extract_census.py <name>)
Writes docs/<name>/index.html (served by GitHub Pages from /docs)."""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
name = sys.argv[1]
base = ROOT / 'townlands' / name
def load(p): return json.load(open(p, encoding='utf-8'))
townland = load(base / 'townland.json')
content = load(base / 'content.json')
census = load(base / 'records' / 'census.json')
html = (ROOT / 'engine' / 'walk.html').read_text(encoding='utf-8')
def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;')
payload = json.dumps({'census': census, 'content': content, 'townland': townland}, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
out = (html.replace('__TITLE__', esc(townland['page_title']))
           .replace('__BRAND__', esc(townland['name']))
           .replace('__DATA__', payload))
dest = ROOT / 'docs' / name
dest.mkdir(parents=True, exist_ok=True)
(dest / 'index.html').write_text(out, encoding='utf-8')
print('wrote', dest / 'index.html', len(out), 'bytes')
