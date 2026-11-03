"""Media files for townland pages: read, check and describe them.

Specified in docs/MEDIA_SPEC.md. Each townland keeps its images and a mapping file in

    townlands/<name>/media/media.csv      one row per image
    townlands/<name>/media/<image files>  as supplied, never resized

An optional townlands/media_config.json holds {"base_url": "https://..."}. When it is set
the page loads images from that address and nothing is copied.

This module has no dependencies outside the standard library. It reads files and never
writes them. Used by tools/validate.py (checks) and tools/build.py (page data).
"""
import csv
import json
import pathlib
import struct
from urllib.parse import quote

ALLOWED = ('.jpg', '.jpeg', '.png', '.webp')
SCOPES = ('townland', 'family')
MAX_SLOTS = 3
REQUIRED = ('file', 'scope', 'caption', 'source')
WARN_FILE_BYTES = 8 * 1024 * 1024
WARN_TOTAL_BYTES = 500 * 1024 * 1024
EM_DASH = '\u2014'
MB = 1024 * 1024


def read_config(townlands_dir):
    """Return (base_url, errors). base_url is '' or an address ending in a slash."""
    path = pathlib.Path(townlands_dir) / 'media_config.json'
    if not path.is_file():
        return '', []
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as exc:
        return '', ['townlands/media_config.json is not valid JSON: ' + str(exc)]
    base = data.get('base_url', '') if isinstance(data, dict) else None
    if not isinstance(base, str):
        return '', ['townlands/media_config.json: base_url must be text']
    base = base.strip()
    if base and not base.startswith(('http://', 'https://')):
        return '', ['townlands/media_config.json: base_url must start with http:// or https://']
    if base and not base.endswith('/'):
        base += '/'
    return base, []


def family_names(case_dir):
    """Family names authored in content.json, in order."""
    path = pathlib.Path(case_dir) / 'content.json'
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return []
    return [f['name'] for f in data.get('families', []) if isinstance(f, dict) and f.get('name')]


def image_files(media_dir):
    """Names of image files present in a media folder."""
    media_dir = pathlib.Path(media_dir)
    if not media_dir.is_dir():
        return []
    return sorted(p.name for p in media_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED)


def load_case(case_dir, base_url='', families=()):
    """Read and check one townland's media.

    Returns a dict: rows (checked, normalised, in file order), errors, warnings, files
    (image files present) and bytes (their total size). Nothing is raised for bad data;
    problems are listed in errors so every one is reported at once."""
    case_dir = pathlib.Path(case_dir)
    media_dir = case_dir / 'media'
    label = case_dir.name
    out = {'rows': [], 'errors': [], 'warnings': [], 'files': image_files(media_dir), 'bytes': 0}
    out['bytes'] = sum((media_dir / f).stat().st_size for f in out['files'])
    sheet = media_dir / 'media.csv'
    if not sheet.is_file():
        if out['files']:
            out['warnings'].append(label + ': media folder has images but no media.csv. They are not shown.')
        return out

    def bad(row_no, text):
        out['errors'].append(label + ' media.csv row ' + str(row_no) + ': ' + text)

    with sheet.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        header = [(h or '').strip().lower() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED if c not in header]
        if missing:
            out['errors'].append(label + ' media.csv has no column ' + ', '.join(missing))
            return out
        slots = {}
        used = set()
        for row_no, raw in enumerate(reader, start=2):
            row = {(k or '').strip().lower(): (v or '').strip() for k, v in raw.items() if k is not None}
            if not any(row.values()):
                continue
            ok = True
            for col, value in row.items():
                if EM_DASH in value:
                    bad(row_no, col + ' contains an em dash. Use a comma, colon or full stop.')
                    ok = False
            name, scope = row.get('file', ''), row.get('scope', '').lower()
            for col in REQUIRED:
                if not row.get(col):
                    bad(row_no, col + ' is required')
                    ok = False
            if name:
                if '/' in name or '\\' in name or name.startswith('.'):
                    bad(row_no, 'file must be a plain file name inside the media folder, not a path: ' + name)
                    ok = False
                elif pathlib.PurePath(name).suffix.lower() not in ALLOWED:
                    bad(row_no, 'file type not allowed (use ' + ', '.join(ALLOWED) + '): ' + name)
                    ok = False
                elif not base_url and not (media_dir / name).is_file():
                    bad(row_no, 'file not found in the media folder: ' + name)
                    ok = False
                elif (media_dir / name).is_file() and (media_dir / name).stat().st_size > WARN_FILE_BYTES:
                    out['warnings'].append(label + ' media.csv row ' + str(row_no) + ': ' + name + ' is over '
                                           + str(WARN_FILE_BYTES // MB) + ' MB')
                if ok and (media_dir / name).is_file() and image_size(media_dir / name) is None:
                    out['warnings'].append(label + ' media.csv row ' + str(row_no) + ': could not read the size of '
                                           + name + ', so it will show at its natural size')
            if scope and scope not in SCOPES:
                bad(row_no, "scope must be 'townland' or 'family', not '" + row.get('scope', '') + "'")
                ok = False
            slot = None
            if scope == 'townland' and name and (media_dir / name).is_file():
                size = image_size(media_dir / name)
                if size and size[0] <= size[1]:
                    out['warnings'].append(label + ' media.csv row ' + str(row_no) + ': ' + name
                                           + ' is not landscape. Header photographs should be wider than tall.')
            if scope == 'townland':
                try:
                    slot = int(row.get('slot', ''))
                except ValueError:
                    slot = 0
                if not 1 <= slot <= MAX_SLOTS:
                    bad(row_no, 'a townland row needs slot 1, 2 or 3 (at most ' + str(MAX_SLOTS) + ' header images)')
                    ok, slot = False, None
                elif slot in slots:
                    bad(row_no, 'slot ' + str(slot) + ' is already used by row ' + str(slots[slot]))
                    ok = False
                else:
                    slots[slot] = row_no
            names = []
            if scope == 'family':
                names = [n.strip() for n in row.get('family', '').split(';') if n.strip()]
                if not names:
                    bad(row_no, 'a family row needs a family name')
                    ok = False
                unknown = [n for n in names if n not in families]
                if unknown:
                    valid = ', '.join(families) if families else 'none (content.json has no families)'
                    bad(row_no, 'unknown family ' + '; '.join(unknown) + '. Valid names: ' + valid)
                    ok = False
            link = row.get('link', '')
            if link and not link.startswith(('http://', 'https://')):
                bad(row_no, 'link must start with http:// or https://')
                ok = False
            if not ok:
                continue
            used.add(name)
            out['rows'].append({
                'file': name, 'scope': scope, 'slot': slot, 'families': names,
                'caption': row['caption'], 'alt': row.get('alt') or row['caption'], 'source': row['source'],
                'reference': row.get('reference', ''), 'date': row.get('date', ''),
                'people': row.get('people_shown', ''), 'link': link,
            })
    for name in out['files']:
        if name not in used and not any(label + ' media.csv row' in e and name in e for e in out['errors']):
            out['warnings'].append(label + ': ' + name + ' is not used by any row in media.csv')
    return out


def describe(rows, case_dir, base_url=''):
    """Page data for checked rows, or None when there are none.

    {'header': [... by slot], 'families': {name: [... in file order]}}. Each image has url
    (relative to the page, or under base_url) and w and h in pixels when the file can be read."""
    if not rows:
        return None
    media_dir = pathlib.Path(case_dir) / 'media'

    def item(row):
        local = media_dir / row['file']
        size = image_size(local) if local.is_file() else None
        url = (base_url or 'media/') + quote(row['file'])
        out = {'url': url, 'w': size[0] if size else None, 'h': size[1] if size else None,
               'caption': row['caption'], 'alt': row['alt'], 'source': row['source']}
        for key in ('reference', 'date', 'people', 'link'):
            if row[key]:
                out[key] = row[key]
        return out

    header = sorted((r for r in rows if r['scope'] == 'townland'), key=lambda r: r['slot'])
    families = {}
    for r in rows:
        if r['scope'] == 'family':
            for name in r['families']:
                families.setdefault(name, []).append(item(r))
    return {'header': [item(r) for r in header], 'families': families}


# ---- image size from the file header, standard library only ----

_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def image_size(path):
    """(width, height) of a JPEG, PNG or WebP as a browser will show it, or None."""
    try:
        with open(path, 'rb') as f:
            head = f.read(32)
            f.seek(0)
            if head[:2] == b'\xff\xd8':
                return _jpeg_size(f)
            if head[:8] == b'\x89PNG\r\n\x1a\n':
                w, h = struct.unpack('>II', head[16:24])
                return (w, h) if w and h else None
            if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
                return _webp_size(head)
    except (OSError, struct.error):
        return None
    return None


def _jpeg_size(f):
    f.read(2)
    orientation = 1
    while True:
        b = f.read(1)
        if not b:
            return None
        if b != b'\xff':
            continue
        m = f.read(1)
        while m == b'\xff':
            m = f.read(1)
        if not m:
            return None
        marker = m[0]
        if marker == 0x00 or marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        if marker == 0xD9:
            return None
        raw = f.read(2)
        if len(raw) < 2:
            return None
        length = struct.unpack('>H', raw)[0]
        if marker in _SOF:
            seg = f.read(5)
            if len(seg) < 5:
                return None
            _, h, w = struct.unpack('>BHH', seg)
            if not w or not h:
                return None
            return (h, w) if orientation in (5, 6, 7, 8) else (w, h)
        body = f.read(length - 2)
        if marker == 0xE1 and body[:6] == b'Exif\x00\x00':
            orientation = _exif_orientation(body[6:]) or orientation


def _exif_orientation(tiff):
    """EXIF orientation (1 to 8) from a TIFF block, or 0 if absent or unreadable."""
    try:
        end = '<' if tiff[:2] == b'II' else '>' if tiff[:2] == b'MM' else None
        if end is None:
            return 0
        ifd = struct.unpack(end + 'I', tiff[4:8])[0]
        count = struct.unpack(end + 'H', tiff[ifd:ifd + 2])[0]
        for i in range(count):
            at = ifd + 2 + 12 * i
            tag, kind = struct.unpack(end + 'HH', tiff[at:at + 4])
            if tag == 0x0112 and kind == 3:
                return struct.unpack(end + 'H', tiff[at + 8:at + 10])[0]
    except struct.error:
        return 0
    return 0


def _webp_size(head):
    kind = head[12:16]
    if kind == b'VP8 ':
        w = struct.unpack('<H', head[26:28])[0] & 0x3FFF
        h = struct.unpack('<H', head[28:30])[0] & 0x3FFF
    elif kind == b'VP8L':
        bits = struct.unpack('<I', head[21:25])[0]
        w, h = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    elif kind == b'VP8X':
        w = int.from_bytes(head[24:27], 'little') + 1
        h = int.from_bytes(head[27:30], 'little') + 1
    else:
        return None
    return (w, h) if w and h else None


def check_repo(root):
    """Check every townland's media. Returns (errors, warnings, summary_line)."""
    root = pathlib.Path(root)
    towns = root / 'townlands'
    base_url, errors = read_config(towns)
    warnings = []
    files = total = 0
    if towns.is_dir():
        for case in sorted(p for p in towns.iterdir() if p.is_dir()):
            res = load_case(case, base_url, family_names(case))
            errors += res['errors']
            warnings += res['warnings']
            files += len(res['files'])
            total += res['bytes']
    if total > WARN_TOTAL_BYTES:
        warnings.append('media totals ' + format(total / MB, '.0f') + ' MB, over ' + str(WARN_TOTAL_BYTES // MB)
                        + ' MB. Consider a CDN (docs/MEDIA_SPEC.md, MP8).')
    return errors, warnings, 'media: ' + str(files) + ' image files, ' + format(total / MB, '.1f') + ' MB'
