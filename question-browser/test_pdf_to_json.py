import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pdf_to_json import convert, normalize

class ExportTests(unittest.TestCase):
    def test_normalization_preserves_math(self):
        self.assertEqual(normalize('1. Mass is  10 kg\n(A) +2',1),normalize('9) Mass is 10 kg (A) +2',9))
        self.assertNotEqual(normalize('1. +2',1),normalize('1. -2',1))
    def test_merge_sources_and_keep_distinct_diagrams(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name in ('a.pdf','b.PDF','c.pdf','broken.pdf'):(folder/name).touch()
            def parse(path):
                if path.name=='broken.pdf':raise ValueError('Scanned PDF')
                n=9 if path.name=='b.PDF' else 1
                return [{'number':n,'text':[f'{n}. Mass?\n(A) 2 kg\n(B) 3 kg'], 'images':[(1,b'png')], 'visual_hashes':['other' if path.name=='c.pdf' else 'same']}]
            with patch('pdf_to_json.parse_pdf',side_effect=parse):
                result=convert(folder)
                self.assertEqual(result['summary']['unique_questions'],2)
                self.assertEqual(result['summary']['duplicates_merged'],1)
                self.assertEqual(result['summary']['failed_files'],1)
                first=result['questions'][0]
                self.assertEqual([s['question_number'] for s in first['sources']],[1,9])
                self.assertEqual(first['stem'],'Mass?')
                self.assertEqual(first['choices'],[{'label':'A','text':'2 kg'},{'label':'B','text':'3 kg'}])
                self.assertEqual(first['images'][0]['base64'],'cG5n')
                self.assertEqual(convert(folder,dedupe='text')['summary']['unique_questions'],1)

if __name__=='__main__':unittest.main()
