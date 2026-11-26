"""Census form images for townland stories: keep the originals as supplied, make the web images from them.

Usage:
    python tools/census_form_images.py add <townland> <year> <form> <pdf> [<pdf> ...] --archive-ref REF --date DATE
    python tools/census_form_images.py build <townland> [--force]
    python tools/census_form_images.py check

`add` copies the National Archives PDFs you downloaded into data/source/census_images/<year>/<townland>/ exactly as
supplied (the file name is kept, the bytes are never changed) and records each one in that folder's manifest.csv
with its SHA-256 and the archive reference. The pdfs are taken in page order. REF is the archive reference printed
on the form, with {page} where the page number goes, for example STAT/1/8/36/DRUMININ/B/{page}.

`build` makes one web image per page (1600 px wide JPEG) in townlands/<townland>/media/ and adds or updates its row
in that folder's media.csv (scope `census`). The converted images are derived files: they can always be made
again from the originals. They are converted and resized, never cropped. Needs PyMuPDF (pip install pymupdf).

`check` verifies every original against its SHA-256 and that every manifest row has its web image.

Only years with credit wording in tools/credits.py can be added. Specified in docs/MEDIA_SPEC.md (scope `census`).
"""
import csv
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'data' / 'source' / 'census_images'
MANIFEST = SOURCE / 'manifest.csv'
MANIFEST_COLUMNS = ['file', 'townland', 'census_year', 'form', 'page', 'archive_ref', 'form_date', 'origin',
                    'date_acquired', 'licence_note', 'sha256']
MEDIA_COLUMNS = ['file', 'scope', 'slot', 'family', 'caption', 'alt', 'source', 'reference', 'date', 'people_shown',
                 'link', 'lat', 'lon', 'year', 'credit', 'focus']
WIDTH = 1600
JPEG_QUALITY = 82
# year -> (credit key in tools/credits.py, source text, licence note)
YEARS = {
    '1926': ('nai1926', 'National Archives of Ireland, 1926 Census',
             'National Archives of Ireland 1926 Census: CC BY 4.0. Include the NAI attribution and identify modifications '
             'when sharing. See https://nationalarchives.ie/search-the-1926-census-2/permission-to-reuse-census-1926/'),
}
FORMS = {'B': 'Form B, house and building return'}
# where the names of the heads of household sit on the page, across and down as fractions, for the zoom view
FOCUS = {('1926', 'B'): '0.7,0.5'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_manifest():
    if not MANIFEST.is_file():
        return []
    with MANIFEST.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_manifest(rows):
    rows = sorted(rows, key=lambda r: (r['census_year'], r['townland'], r['form'], int(r['page'])))
    SOURCE.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def image_name(row):
    return f"census-{row['census_year']}-form-{row['form'].lower()}-p{row['page']}.jpg"


def display_name(townland):
    place = ROOT / 'townlands' / townland / 'place.json'
    if place.is_file():
        return json.loads(place.read_text(encoding='utf-8')).get('name_en') or townland.title()
    return townland.title()


def add(townland, year, form, pdfs, archive_ref, form_date, today=None):
    import datetime
    if year not in YEARS:
        sys.exit(f'No credit wording for {year} in tools/credits.py yet. Add it first (1926 only so far).')
    if form not in FORMS:
        sys.exit('Form must be one of: ' + ', '.join(FORMS))
    if not (ROOT / 'townlands' / townland).is_dir():
        sys.exit('No case folder townlands/' + townland)
    if '{page}' not in archive_ref:
        sys.exit('--archive-ref must contain {page}, for example STAT/1/8/36/DRUMININ/B/{page}')
    sources = [pathlib.Path(p) for p in pdfs]
    for p in sources:
        if not p.is_file() or p.suffix.lower() != '.pdf':
            sys.exit('Not a PDF file: ' + str(p))
    dest = SOURCE / year / townland
    dest.mkdir(parents=True, exist_ok=True)
    rows = [r for r in read_manifest() if not (r['townland'] == townland and r['census_year'] == year and r['form'] == form)]
    _, _, licence = YEARS[year]
    for page, p in enumerate(sources, start=1):
        target = dest / p.name
        if target.exists() and sha256(target) != sha256(p):
            sys.exit(f'{target.relative_to(ROOT)} already exists with different content. Not overwritten.')
        shutil.copyfile(p, target)
        rows.append({'file': f'{year}/{townland}/{p.name}', 'townland': townland, 'census_year': year, 'form': form,
                     'page': str(page), 'archive_ref': archive_ref.replace('{page}', str(page)), 'form_date': form_date,
                     'origin': 'Downloaded by the user from the National Archives of Ireland census website, saved as supplied',
                     'date_acquired': (today or datetime.date.today()).isoformat(), 'licence_note': licence,
                     'sha256': sha256(target)})
    write_manifest(rows)
    print(f'{townland} {year} Form {form}: {len(sources)} originals kept in {dest.relative_to(ROOT)}. Now run: '
          f'python tools/census_form_images.py build {townland}')
    return 0


def render(pdf, out_path):
    try:
        import pymupdf
    except ImportError:
        sys.exit('Converting needs PyMuPDF. Install it with: pip install pymupdf')
    with pymupdf.open(str(pdf)) as doc:
        if doc.page_count != 1:
            sys.exit(f'{pdf.name} has {doc.page_count} pages. Each census form file is expected to hold one page.')
        page = doc[0]
        scale = WIDTH / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        pix.save(str(out_path), jpg_quality=JPEG_QUALITY)


def read_media(path):
    if not path.is_file():
        return list(MEDIA_COLUMNS), []
    with path.open(encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def build(townland, force=False):
    rows = [r for r in read_manifest() if r['townland'] == townland]
    if not rows:
        sys.exit(f'Nothing in {MANIFEST.relative_to(ROOT)} for {townland}. Run the add command first.')
    media_dir = ROOT / 'townlands' / townland / 'media'
    media_dir.mkdir(parents=True, exist_ok=True)
    sheet = media_dir / 'media.csv'
    header, existing = read_media(sheet)
    header = header + [c for c in MEDIA_COLUMNS if c not in header]
    by_file = {r['file']: r for r in existing}
    town = display_name(townland)
    groups = {}
    for r in rows:
        groups.setdefault((r['census_year'], r['form']), []).append(r)
    made = 0
    for (year, form), pages in sorted(groups.items()):
        credit, source, _ = YEARS[year]
        for r in sorted(pages, key=lambda x: int(x['page'])):
            pdf = SOURCE / r['file']
            if not pdf.is_file() or sha256(pdf) != r['sha256']:
                sys.exit(f'{r["file"]} is missing or does not match its SHA-256 in the manifest.')
            name = image_name(r)
            if force or not (media_dir / name).is_file():
                render(pdf, media_dir / name)
                made += 1
            caption = f'{town}, {year} census, {FORMS[form]}, page {r["page"]} of {len(pages)}'
            by_file[name] = dict(by_file.get(name, {}), file=name, scope='census', caption=caption, alt=caption,
                                 source=source, reference=r['archive_ref'], date=r['form_date'], year=year,
                                 credit=credit, focus=FOCUS.get((year, form), ''))
    order = [r['file'] for r in existing] + [n for n in by_file if n not in {r['file'] for r in existing}]
    with sheet.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator='\n', extrasaction='ignore', restval='')
        w.writeheader()
        for n in order:
            w.writerow(by_file[n])
    print(f'{townland}: {made} web images made, media.csv has {len(order)} rows.')
    return 0


def check():
    problems = []
    for r in read_manifest():
        pdf = SOURCE / r['file']
        if not pdf.is_file():
            problems.append(f'{r["file"]}: original missing')
        elif sha256(pdf) != r['sha256']:
            problems.append(f'{r["file"]}: SHA-256 differs from the manifest')
        if not (ROOT / 'townlands' / r['townland'] / 'media' / image_name(r)).is_file():
            problems.append(f'{r["file"]}: no web image {image_name(r)} (run build {r["townland"]})')
    listed = {r['file'] for r in read_manifest()}
    for p in sorted(SOURCE.rglob('*.pdf')):
        if str(p.relative_to(SOURCE)).replace('\\', '/') not in listed:
            problems.append(f'{p.relative_to(SOURCE)}: not in the manifest')
    return problems


def main(argv):
    args = argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == 'check':
        problems = check()
        print('\n'.join(problems) if problems else f'census images: ok ({len(read_manifest())} originals)')
        return 1 if problems else 0
    if cmd == 'build' and len(args) >= 2:
        return build(args[1], force='--force' in args)
    if cmd == 'add' and len(args) >= 6:
        opts, rest = {}, []
        it = iter(args[1:])
        for a in it:
            if a in ('--archive-ref', '--date'):
                opts[a] = next(it, '')
            else:
                rest.append(a)
        if len(rest) < 4 or '--archive-ref' not in opts or '--date' not in opts:
            sys.exit(__doc__)
        return add(rest[0], rest[1], rest[2], rest[3:], opts['--archive-ref'], opts['--date'])
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
