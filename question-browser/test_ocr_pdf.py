import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import ocr_pdf

class OcrTests(unittest.TestCase):
    def test_missing_tools_have_actionable_message(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf=Path(folder)/'scan.pdf';pdf.write_bytes(b'scan')
            with patch('ocr_pdf.shutil.which',return_value=None):
                with self.assertRaisesRegex(ValueError,'start.sh --with-ocr'):
                    ocr_pdf.searchable_copy(pdf,Path(folder)/'cache')
            self.assertEqual(pdf.read_bytes(),b'scan')
    def test_existing_cache_does_not_require_tesseract(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf=Path(folder)/'scan.pdf';pdf.write_bytes(b'scan')
            cache=Path(folder)/'cache';cache.mkdir()
            digest=hashlib.sha256(b'scanengocr-200dpi-v1').hexdigest()
            output=cache/(digest+'.pdf');output.write_bytes(b'%PDF-cache')
            with patch.dict('os.environ',{'QUESTION_OCR_LANGUAGE':'eng'}),patch('ocr_pdf.shutil.which',return_value=None):
                self.assertEqual(ocr_pdf.searchable_copy(pdf,cache),output)
    def test_importer_retries_using_searchable_copy(self):
        page={'width':600,'height':800,'lines':[]}
        with patch('app.read_pages',return_value=[page]) as read,patch('app.searchable_copy',return_value=Path('cached.pdf')) as ocr:
            with self.assertRaisesRegex(ValueError,'OCR completed'):
                app.parse_pdf(Path('scan.pdf'))
            ocr.assert_called_once_with(Path('scan.pdf'))
            self.assertEqual(read.call_args_list[-1].args,(Path('cached.pdf'),))

if __name__=='__main__':unittest.main()
