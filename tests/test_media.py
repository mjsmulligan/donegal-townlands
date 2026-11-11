"""Tests for tools/media.py. Run from the repo root:

    python -m unittest tests.test_media -v

Every test works in a temporary directory. The real repository is never touched.
Image files are built from a few header bytes, so no imaging library is needed.
"""

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from tools import media

HEADER = 'file,scope,slot,family,caption,alt,source,reference,date,people_shown,link\n'


def png(w, h):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IEND', b'')


def jpeg(w, h, orientation=None):
    out = b'\xff\xd8' + b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    if orientation:
        tiff = (b'MM' + struct.pack('>HI', 42, 8) + struct.pack('>H', 1)
                + struct.pack('>HHI', 0x0112, 3, 1) + struct.pack('>H', orientation) + b'\x00\x00' + struct.pack('>I', 0))
        body = b'Exif\x00\x00' + tiff
        out += b'\xff\xe1' + struct.pack('>H', len(body) + 2) + body
    return out + b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, h, w, 1) + b'\x01\x11\x00' + b'\xff\xd9'


def webp_vp8x(w, h):
    return (b'RIFF' + struct.pack('<I', 22) + b'WEBP' + b'VP8X' + struct.pack('<I', 10) + b'\x00\x00\x00\x00'
            + (w - 1).to_bytes(3, 'little') + (h - 1).to_bytes(3, 'little'))


class ImageSizeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def size(self, name, data):
        path = self.dir / name
        path.write_bytes(data)
        return media.image_size(path)

    def test_png(self):
        self.assertEqual(self.size('a.png', png(1499, 2464)), (1499, 2464))

    def test_jpeg(self):
        self.assertEqual(self.size('a.jpg', jpeg(1499, 2464)), (1499, 2464))

    def test_jpeg_exif_rotation_swaps_the_shape_the_browser_shows(self):
        self.assertEqual(self.size('r.jpg', jpeg(2000, 1000, orientation=6)), (1000, 2000))
        self.assertEqual(self.size('n.jpg', jpeg(2000, 1000, orientation=1)), (2000, 1000))

    def test_webp(self):
        self.assertEqual(self.size('a.webp', webp_vp8x(800, 600)), (800, 600))

    def test_unreadable_gives_none(self):
        self.assertIsNone(self.size('bad.jpg', b'not an image at all'))
        self.assertIsNone(self.size('short.png', b'\x89PNG\r\n\x1a\n'))
        self.assertIsNone(media.image_size(self.dir / 'missing.jpg'))

    def test_agrees_with_a_real_imaging_library_when_present(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow not installed')
        for ext, fmt in (('jpg', 'JPEG'), ('png', 'PNG'), ('webp', 'WEBP')):
            path = self.dir / ('real.' + ext)
            Image.new('RGB', (321, 457), 'white').save(path, fmt)
            self.assertEqual(media.image_size(path), (321, 457), ext)


class CaseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.case = self.root / 'townlands' / 'cullionboy'
        (self.case / 'media').mkdir(parents=True)
        self.families = ['The Dunnions', 'The Gillespies']
        (self.case / 'content.json').write_text(
            json.dumps({'families': [{'name': n} for n in self.families]}), encoding='utf-8')

    def image(self, name, data=None):
        (self.case / 'media' / name).write_bytes(data or jpeg(100, 200))

    def sheet(self, *rows, header=HEADER, bom=False):
        text = header + ''.join(r + '\n' for r in rows)
        (self.case / 'media' / 'media.csv').write_text(text, encoding='utf-8-sig' if bom else 'utf-8')

    def load(self, base_url=''):
        return media.load_case(self.case, base_url, media.family_names(self.case))

    def only_error(self, res):
        self.assertEqual(len(res['errors']), 1, res['errors'])
        return res['errors'][0]

    # ---- MED-01 reading

    def test_valid_sheet_loads_in_order(self):
        self.image('a.jpg'); self.image('b.jpg'); self.image('h.jpg')
        self.sheet('a.jpg,family,,The Dunnions,First,,Family collection,,,,',
                   'b.jpg,family,,The Dunnions,Second,Alt two,Family collection,Ref 7,c. 1930s,A Dunnion,https://example.org/x',
                   'h.jpg,townland,1,,Header,,Family collection,,,,')
        res = self.load()
        self.assertEqual(res['errors'], [])
        self.assertEqual([r['caption'] for r in res['rows']], ['First', 'Second', 'Header'])
        self.assertEqual(res['rows'][0]['alt'], 'First')          # alt falls back to the caption
        self.assertEqual(res['rows'][1]['alt'], 'Alt two')
        self.assertEqual(res['rows'][1]['date'], 'c. 1930s')

    def test_excel_byte_order_mark_and_extra_columns_are_fine(self):
        self.image('a.jpg')
        (self.case / 'media' / 'media.csv').write_text(
            HEADER.strip() + ',notes\na.jpg,family,,The Dunnions,Cap,,Src,,,,,my note\n', encoding='utf-8-sig')
        res = self.load()
        self.assertEqual(res['errors'], [])
        self.assertEqual(len(res['rows']), 1)

    def test_blank_rows_are_skipped(self):
        self.image('a.jpg')
        self.sheet(',,,,,,,,,,', 'a.jpg,family,,The Dunnions,Cap,,Src,,,,', ',,,,,,,,,,')
        self.assertEqual(len(self.load()['rows']), 1)

    # ---- MED-02 required fields

    def test_missing_required_fields_name_the_row_and_column(self):
        self.image('a.jpg')
        for col, row in (('caption', 'a.jpg,family,,The Dunnions,,,Src,,,,'),
                         ('source', 'a.jpg,family,,The Dunnions,Cap,,,,,,'),
                         ('file', ',family,,The Dunnions,Cap,,Src,,,,'),
                         ('scope', 'a.jpg,,,The Dunnions,Cap,,Src,,,,')):
            self.sheet(row)
            msg = self.only_error(self.load())
            self.assertIn('row 2', msg)
            self.assertIn(col + ' is required', msg)

    def test_missing_required_column_in_the_header(self):
        self.sheet(header='file,scope,caption\n')
        self.assertIn('no column source', self.only_error(self.load()))

    def test_optional_fields_may_be_empty_or_unknown(self):
        # decisions M8 and M9: date and people_shown optional, nothing checked about people or dates
        self.image('a.jpg')
        self.sheet('a.jpg,family,,The Dunnions,Cap,,Src,,unknown,Someone not checked,')
        self.sheet('a.jpg,family,,The Dunnions,Cap,,Src,,2024,A living person,')
        res = self.load()
        self.assertEqual((res['errors'], res['warnings']), ([], []))

    # ---- MED-03 slots

    def test_slots_one_to_three_unique(self):
        for n in 'abcd':
            self.image(n + '.jpg')
        self.sheet(*['%s.jpg,townland,%d,,Cap,,Src,,,,' % (n, i) for i, n in enumerate('abc', 1)])
        self.assertEqual(self.load()['errors'], [])
        self.sheet('a.jpg,townland,1,,Cap,,Src,,,,', 'b.jpg,townland,1,,Cap,,Src,,,,')
        self.assertIn('slot 1 is already used by row 2', self.only_error(self.load()))
        self.sheet('d.jpg,townland,4,,Cap,,Src,,,,')
        self.assertIn('slot 1, 2 or 3', self.only_error(self.load()))
        self.sheet('d.jpg,townland,,,Cap,,Src,,,,')
        self.assertIn('slot 1, 2 or 3', self.only_error(self.load()))

    def test_a_fourth_header_image_fails(self):
        for n in 'abcd':
            self.image(n + '.jpg')
        self.sheet(*['%s.jpg,townland,%s,,Cap,,Src,,,,' % (n, s) for n, s in zip('abcd', '1231')])
        self.assertTrue(self.load()['errors'])

    # ---- MED-04 families

    def test_unknown_family_lists_the_valid_names(self):
        self.image('a.jpg')
        self.sheet('a.jpg,family,,The Smiths,Cap,,Src,,,,')
        msg = self.only_error(self.load())
        self.assertIn('unknown family The Smiths', msg)
        self.assertIn('The Dunnions, The Gillespies', msg)

    def test_several_families_separated_by_semicolons(self):
        self.image('a.jpg')
        self.sheet('a.jpg,family,,The Dunnions; The Gillespies,Cap,,Src,,,,')
        res = self.load()
        self.assertEqual(res['errors'], [])
        self.assertEqual(res['rows'][0]['families'], ['The Dunnions', 'The Gillespies'])

    def test_family_row_needs_a_name_and_a_townland_with_no_families_has_none_valid(self):
        self.image('a.jpg')
        self.sheet('a.jpg,family,,,Cap,,Src,,,,')
        self.assertIn('needs a family name', self.only_error(self.load()))
        (self.case / 'content.json').unlink()
        self.sheet('a.jpg,family,,The Dunnions,Cap,,Src,,,,')
        self.assertIn('content.json has no families', self.only_error(self.load()))

    # ---- MED-05, MED-10 files

    def test_missing_file_fails_unless_a_cdn_base_is_set(self):
        self.sheet('gone.jpg,family,,The Dunnions,Cap,,Src,,,,')
        self.assertIn('file not found', self.only_error(self.load()))
        self.assertEqual(self.load('https://cdn.example.org/m/')['errors'], [])

    def test_only_jpg_jpeg_png_webp(self):
        (self.case / 'media' / 'a.gif').write_bytes(b'GIF89a')
        self.sheet('a.gif,family,,The Dunnions,Cap,,Src,,,,')
        self.assertIn('file type not allowed', self.only_error(self.load()))
        self.image('A.JPEG'); self.image('b.PNG', png(5, 5)); self.image('c.webp', webp_vp8x(5, 5))
        self.sheet(*['%s,family,,The Dunnions,Cap,,Src,,,,' % n for n in ('A.JPEG', 'b.PNG', 'c.webp')])
        self.assertEqual(self.load()['errors'], [])

    def test_file_must_be_a_plain_name(self):
        self.sheet('../x.jpg,family,,The Dunnions,Cap,,Src,,,,')
        self.assertIn('plain file name', self.only_error(self.load()))

    # ---- MED-06, MED-07 warnings

    def test_unused_image_is_a_warning_not_an_error(self):
        self.image('a.jpg'); self.image('unused.jpg')
        self.sheet('a.jpg,family,,The Dunnions,Cap,,Src,,,,')
        res = self.load()
        self.assertEqual(res['errors'], [])
        self.assertEqual(len(res['warnings']), 1)
        self.assertIn('unused.jpg is not used', res['warnings'][0])

    def test_images_with_no_sheet_warn_once(self):
        self.image('a.jpg'); self.image('b.jpg')
        res = self.load()
        self.assertEqual(res['errors'], [])
        self.assertEqual(len(res['warnings']), 1)
        self.assertIn('no media.csv', res['warnings'][0])

    def test_large_file_warns(self):
        self.image('a.jpg', jpeg(10, 10) + b'x' * 5000)
        self.sheet('a.jpg,family,,The Dunnions,Cap,,Src,,,,')
        old = media.WARN_FILE_BYTES
        media.WARN_FILE_BYTES = 4000
        self.addCleanup(setattr, media, 'WARN_FILE_BYTES', old)
        res = self.load()
        self.assertEqual(res['errors'], [])
        self.assertIn('a.jpg is over', res['warnings'][0])

    def test_unreadable_image_warns_and_is_still_used(self):
        self.image('odd.jpg', b'not really a jpeg')
        self.sheet('odd.jpg,family,,The Dunnions,Cap,,Src,,,,')
        res = self.load()
        self.assertEqual(len(res['rows']), 1)
        self.assertEqual(res['errors'], [])
        self.assertIn('could not read the size of odd.jpg', res['warnings'][0])
        item = media.describe(res['rows'], self.case)['families']['The Dunnions'][0]
        self.assertEqual((item['w'], item['h']), (None, None))

    # ---- MED-25 header shape

    def test_a_header_photograph_that_is_not_landscape_warns_but_is_used(self):
        self.image('wide.jpg', jpeg(300, 200)); self.image('tall.jpg', jpeg(200, 300)); self.image('sq.jpg', jpeg(200, 200))
        self.sheet('wide.jpg,townland,1,,Cap,,Src,,,,', 'tall.jpg,townland,2,,Cap,,Src,,,,', 'sq.jpg,townland,3,,Cap,,Src,,,,')
        res = self.load()
        self.assertEqual(res['errors'], [])
        self.assertEqual(len(res['rows']), 3)
        self.assertEqual(len(res['warnings']), 2)
        self.assertIn('tall.jpg is not landscape', res['warnings'][0])
        self.assertIn('sq.jpg is not landscape', res['warnings'][1])

    def test_household_photographs_may_be_any_shape(self):
        self.image('tall.jpg', jpeg(200, 300))
        self.sheet('tall.jpg,family,,The Dunnions,Cap,,Src,,,,')
        self.assertEqual(self.load()['warnings'], [])

    def test_a_rotated_phone_photograph_is_judged_by_the_shape_it_shows(self):
        self.image('phone.jpg', jpeg(300, 200, orientation=6))    # stored wide, shown tall
        self.sheet('phone.jpg,townland,1,,Cap,,Src,,,,')
        self.assertIn('is not landscape', self.load()['warnings'][0])

    # ---- MED-08 text checks

    def test_em_dash_in_any_field_fails(self):
        self.image('a.jpg')
        self.sheet('a.jpg,family,,The Dunnions,Two \u2014 words,,Src,,,,')
        self.assertIn('em dash', self.only_error(self.load()))

    def test_link_must_be_a_web_address(self):
        self.image('a.jpg')
        self.sheet('a.jpg,family,,The Dunnions,Cap,,Src,,,,photos.example/x')
        self.assertIn('link must start with http', self.only_error(self.load()))

    def test_every_problem_is_reported_at_once(self):
        self.image('a.jpg')
        self.sheet('a.jpg,family,,The Smiths,,,Src,,,,', 'a.jpg,bogus,,,Cap,,Src,,,,')
        self.assertGreaterEqual(len(self.load()['errors']), 3)

    # ---- page data

    def test_describe_orders_header_by_slot_and_groups_families(self):
        self.image('one.jpg', jpeg(300, 200)); self.image('two.png', png(50, 80)); self.image('my photo.jpg', jpeg(10, 20))
        self.sheet('two.png,townland,2,,Second,,Src,,,,',
                   'one.jpg,townland,1,,First,,Src,,,,',
                   'my photo.jpg,family,,The Dunnions; The Gillespies,Fam,,Src,Ref,1930s,A B,https://example.org/o')
        res = self.load()
        data = media.describe(res['rows'], self.case)
        self.assertEqual([h['caption'] for h in data['header']], ['First', 'Second'])
        self.assertEqual((data['header'][0]['w'], data['header'][0]['h']), (300, 200))
        self.assertEqual((data['header'][1]['w'], data['header'][1]['h']), (50, 80))
        self.assertEqual(sorted(data['families']), ['The Dunnions', 'The Gillespies'])
        photo = data['families']['The Gillespies'][0]
        self.assertEqual(photo['url'], 'media/my%20photo.jpg')
        self.assertEqual((photo['reference'], photo['date'], photo['people'], photo['link']),
                         ('Ref', '1930s', 'A B', 'https://example.org/o'))
        self.assertNotIn('reference', data['header'][0])           # empty optional fields are left out

    def test_describe_with_cdn_base_and_no_local_file_has_no_size(self):
        self.sheet('far.jpg,townland,1,,Cap,,Src,,,,')
        res = self.load('https://cdn.example.org/m/')
        item = media.describe(res['rows'], self.case, 'https://cdn.example.org/m/')['header'][0]
        self.assertEqual(item['url'], 'https://cdn.example.org/m/far.jpg')
        self.assertIsNone(item['w'])

    def test_describe_nothing_is_none(self):
        self.assertIsNone(media.describe([], self.case))


class RepoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'townlands' / 'clogher').mkdir(parents=True)

    def test_config_absent_blank_slash_and_errors(self):
        towns = self.root / 'townlands'
        self.assertEqual(media.read_config(towns), ('', []))
        cfg = towns / 'media_config.json'
        cfg.write_text('{"base_url": "https://cdn.example.org/m"}', encoding='utf-8')
        self.assertEqual(media.read_config(towns), ('https://cdn.example.org/m/', []))
        cfg.write_text('{"base_url": "ftp://x"}', encoding='utf-8')
        self.assertEqual(len(media.read_config(towns)[1]), 1)
        cfg.write_text('not json', encoding='utf-8')
        self.assertEqual(len(media.read_config(towns)[1]), 1)

    def test_no_media_anywhere_is_clean(self):
        errors, warnings, summary = media.check_repo(self.root)
        self.assertEqual((errors, warnings), ([], []))
        self.assertEqual(summary, 'media: 0 image files, 0.0 MB')

    def test_totals_and_the_size_warning(self):
        mdir = self.root / 'townlands' / 'clogher' / 'media'
        mdir.mkdir()
        (mdir / 'a.jpg').write_bytes(jpeg(3, 2) + b'x' * 3000)
        (mdir / 'media.csv').write_text(HEADER + 'a.jpg,townland,1,,Cap,,Src,,,,\n', encoding='utf-8')
        errors, warnings, summary = media.check_repo(self.root)
        self.assertEqual((errors, warnings), ([], []))
        self.assertIn('1 image files', summary)
        old = media.WARN_TOTAL_BYTES
        media.WARN_TOTAL_BYTES = 1000
        self.addCleanup(setattr, media, 'WARN_TOTAL_BYTES', old)
        self.assertIn('media totals', media.check_repo(self.root)[1][0])


if __name__ == '__main__':
    unittest.main()
