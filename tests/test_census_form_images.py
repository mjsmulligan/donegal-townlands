"""Tests for tools/census_form_images.py. Run from the repo root:

    python -m pytest -q tests/test_census_form_images.py

Every test works in a temporary directory. The real repository is never touched. Converting needs PyMuPDF, so those
tests are skipped where it is not installed.
"""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import census_form_images as cfi

try:
    import pymupdf
except ImportError:
    pymupdf = None


def make_pdf(path, pages=1):
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=842, height=595).insert_text((72, 72), 'Form B')
    doc.save(str(path))
    doc.close()


@unittest.skipIf(pymupdf is None, 'PyMuPDF is not installed')
class CensusFormImageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        old = (cfi.ROOT, cfi.SOURCE, cfi.MANIFEST)
        cfi.ROOT = self.root
        cfi.SOURCE = self.root / 'data' / 'source' / 'census_images'
        cfi.MANIFEST = cfi.SOURCE / 'manifest.csv'
        self.addCleanup(lambda: (setattr(cfi, 'ROOT', old[0]), setattr(cfi, 'SOURCE', old[1]), setattr(cfi, 'MANIFEST', old[2])))
        self.case = self.root / 'townlands' / 'druminnin'
        self.case.mkdir(parents=True)
        (self.case / 'place.json').write_text(json.dumps({'name_en': 'Druminnin'}), encoding='utf-8')
        self.pdfs = []
        for n in (1, 2):
            p = self.root / f'Druminin_0352_0013_0001_{n - 1}_0000{n}.pdf'
            make_pdf(p)
            self.pdfs.append(p)

    def add(self):
        return cfi.add('druminnin', '1926', 'B', self.pdfs, 'STAT/1/8/36/DRUMININ/B/{page}', '12 May 1926')

    def test_add_keeps_the_originals_byte_for_byte_and_records_them(self):
        self.add()
        for src in self.pdfs:
            kept = cfi.SOURCE / '1926' / 'druminnin' / src.name
            self.assertEqual(kept.read_bytes(), src.read_bytes())
        rows = cfi.read_manifest()
        self.assertEqual([r['page'] for r in rows], ['1', '2'])
        self.assertEqual(rows[1]['archive_ref'], 'STAT/1/8/36/DRUMININ/B/2')
        self.assertEqual(rows[0]['sha256'], hashlib.sha256(self.pdfs[0].read_bytes()).hexdigest())

    def test_build_makes_web_images_and_media_rows(self):
        self.add()
        cfi.build('druminnin')
        media = self.case / 'media'
        self.assertTrue((media / 'census-1926-form-b-p1.jpg').is_file())
        with (media / 'media.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r['file'] for r in rows], ['census-1926-form-b-p1.jpg', 'census-1926-form-b-p2.jpg'])
        first = rows[0]
        self.assertEqual((first['scope'], first['year'], first['credit'], first['focus']), ('census', '1926', 'nai1926', '0.7,0.5'))
        self.assertEqual(first['reference'], 'STAT/1/8/36/DRUMININ/B/1')
        self.assertIn('page 1 of 2', first['caption'])
        self.assertIn('Druminnin', first['caption'])

    def test_build_twice_changes_nothing_and_keeps_other_rows(self):
        media = self.case / 'media'
        media.mkdir()
        (media / 'media.csv').write_text('file,scope,slot,family,caption,alt,source,reference,date,people_shown,link\n'
                                         'a.jpg,townland,1,,A header,,Personal photo,,,,\n', encoding='utf-8')
        self.add()
        cfi.build('druminnin')
        first = (media / 'media.csv').read_text(encoding='utf-8')
        cfi.build('druminnin')
        self.assertEqual((media / 'media.csv').read_text(encoding='utf-8'), first)
        self.assertTrue(first.splitlines()[1].startswith('a.jpg,townland,1,,A header'))

    def test_the_web_image_is_1600_wide_and_the_original_is_untouched(self):
        self.add()
        cfi.build('druminnin')
        with pymupdf.open(str(cfi.SOURCE / '1926' / 'druminnin' / self.pdfs[0].name)) as doc:
            self.assertEqual(doc.page_count, 1)
        pix = pymupdf.Pixmap(str(self.case / 'media' / 'census-1926-form-b-p1.jpg'))
        self.assertEqual(pix.width, cfi.WIDTH)

    def test_check_finds_a_changed_original_and_a_missing_image(self):
        self.add()
        self.assertTrue(any('no web image' in p for p in cfi.check()))
        cfi.build('druminnin')
        self.assertEqual(cfi.check(), [])
        kept = cfi.SOURCE / '1926' / 'druminnin' / self.pdfs[0].name
        kept.write_bytes(kept.read_bytes() + b'\n%changed')
        self.assertTrue(any('SHA-256 differs' in p for p in cfi.check()))

    def test_a_year_without_credit_wording_is_refused(self):
        with self.assertRaises(SystemExit):
            cfi.add('druminnin', '1911', 'B', self.pdfs, 'STAT/1/8/36/DRUMININ/B/{page}', '1911')

    def test_a_different_file_under_the_same_name_is_never_overwritten(self):
        self.add()
        make_pdf(self.pdfs[0], pages=2)
        with self.assertRaises(SystemExit):
            self.add()


if __name__ == '__main__':
    unittest.main()
