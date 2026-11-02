"""Build townland pages.
Usage:
    python tools/build.py cullionboy     build one case
    python tools/build.py --all          report on, and build where possible, every case

For a case with everything the page needs, reads engine/walk.html and, from
townlands/<name>/:
  townland.json         name, page title, storage key, census spellings
  content.json          family stories, Griffith's rows, open questions, plate copy
  records/census.json   census rows (python tools/extract_census.py <name>)
Writes docs/<name>/index.html (served by GitHub Pages from /docs).

A case may hold less than that. That is a valid research state, not an error:
  ready       all three files present: the page is built
  partial     some evidence present but not enough for a page: nothing is built
  empty       place identity only (place.json, STATUS.md): nothing is built
Building never invents content, never deletes a published page and never
changes a case folder. Only a name with no case folder at all is an error."""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
NEEDED = ('townland.json', 'content.json', 'records/census.json')
EVIDENCE = NEEDED + ('records/events.csv', 'records/corrections.json')


def load(p): return json.load(open(p, encoding='utf-8'))
def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;')


def case_state(base):
    """Return (state, missing_files) for a case folder."""
    missing = [f for f in NEEDED if not (base / f).is_file()]
    if not missing:
        return 'ready', []
    if any((base / f).is_file() for f in EVIDENCE):
        return 'partial', missing
    return 'empty', missing


def build(name):
    """Build one case if it can be built. Returns its state."""
    base = ROOT / 'townlands' / name
    if not base.is_dir():
        sys.exit('No case folder townlands/' + name)
    state, missing = case_state(base)
    if state == 'empty':
        print(name + ': empty case (place identity only). Nothing to publish yet.')
        return state
    if state == 'partial':
        print(name + ': partial case. Not built. Missing: ' + ', '.join(missing))
        return state
    townland = load(base / 'townland.json')
    content = load(base / 'content.json')
    census = load(base / 'records' / 'census.json')
    html = (ROOT / 'engine' / 'walk.html').read_text(encoding='utf-8')
    payload = json.dumps({'census': census, 'content': content, 'townland': townland}, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = (html.replace('__TITLE__', esc(townland['page_title']))
               .replace('__BRAND__', esc(townland['name']))
               .replace('__DATA__', payload))
    dest = ROOT / 'docs' / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'index.html').write_text(out, encoding='utf-8')
    print('wrote', dest / 'index.html', len(out), 'bytes')
    return state


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__)
    if argv[0] != '--all':
        build(argv[0])
        return
    counts = {'ready': 0, 'partial': 0, 'empty': 0}
    for base in sorted((ROOT / 'townlands').iterdir()):
        if base.is_dir():
            if case_state(base)[0] == 'empty':
                counts['empty'] += 1   # summarised, not listed 53 times
            else:
                counts[build(base.name)] += 1
    print('Cases: %(ready)d built or buildable, %(partial)d partial, %(empty)d empty (nothing to publish yet).' % counts)


if __name__ == '__main__':
    main(sys.argv[1:])
