"""Build a townland page.  Usage: python tools/build.py cullionboy
Reads engine/walk.html and townlands/<name>/records/census.json,
writes docs/<name>/index.html (served by GitHub Pages from /docs)."""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
name = sys.argv[1]
census = json.load(open(ROOT / 'townlands' / name / 'records' / 'census.json', encoding='utf-8'))
html = (ROOT / 'engine' / 'walk.html').read_text(encoding='utf-8')
out = html.replace('__DATA__', json.dumps({'census': census}, ensure_ascii=False, separators=(',', ':')))
dest = ROOT / 'docs' / name
dest.mkdir(parents=True, exist_ok=True)
(dest / 'index.html').write_text(out, encoding='utf-8')
print('wrote', dest / 'index.html', len(out), 'bytes')
