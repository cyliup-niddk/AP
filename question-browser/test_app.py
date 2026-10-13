import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app

class LibraryTests(unittest.TestCase):
    def test_real_pdf_number_detection(self):
        pages=app.read_pages(app.ROOT/'test1.pdf')
        numbers=[n for p in pages for n,y in app.question_starts(p)]
        self.assertEqual(numbers,list(range(1,43)))
        self.assertEqual(len(pages),22)
    def test_saved_questions_are_independent(self):
        with app.connect(app.ROOT/'questions.sqlite3') as con:
            rows=con.execute('SELECT number,content FROM questions q JOIN documents d ON d.id=q.document_id WHERE filename=? ORDER BY ordinal', ('test1.pdf',)).fetchall()
            self.assertEqual(len(rows),42)
            for row in rows:
                starts=__import__('re').findall(r'(?m)^\s*(\d+)[.)]\s+', row['content'])
                self.assertEqual(starts,[str(row['number'])])
            self.assertIn('A tube contains',rows[0]['content'])
            self.assertNotIn('A satellite is in a circular orbit',rows[0]['content'])
            self.assertIn('A satellite is in a circular orbit',rows[1]['content'])
            self.assertNotIn('A person is standing',rows[1]['content'])

    def test_file_namespace_idempotence_and_failed_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);db=folder/'test.sqlite3';app.initialize(db)
            for filename in ('a.pdf','b.pdf'):(folder/filename).write_bytes(b'first')
            parsed=[{'number':1,'text':['1. Example? (A) Answer'], 'images':[(1,b'png-data')]}]
            with patch.object(app,'parse_pdf',return_value=parsed) as parse:
                first=app.import_files(folder,db)
                self.assertEqual([r['status'] for r in first],['imported','imported'])
                second=app.import_files(folder,db)
                self.assertTrue(all(r['status']=='unchanged' for r in second))
                self.assertEqual(parse.call_count,2)
            with app.connect(db) as con:
                self.assertEqual(con.execute('SELECT count(*) FROM questions WHERE number=1').fetchone()[0],2)
                self.assertEqual(con.execute('SELECT count(*) FROM images').fetchone()[0],2)
            (folder/'a.pdf').write_bytes(b'changed')
            with patch.object(app,'parse_pdf',side_effect=ValueError('Invalid PDF')):
                failed=app.import_files(folder,db)
                self.assertEqual(failed[0]['status'],'error')
            with app.connect(db) as con:self.assertEqual(con.execute('SELECT count(*) FROM questions').fetchone()[0],2)
            with patch.object(app,'parse_pdf',return_value=[{'number':2,'text':['2. Replaced'], 'images':[(1,b'new-png')]}]):
                app.import_files(folder,db)
            with app.connect(db) as con:
                self.assertEqual(con.execute('SELECT count(*) FROM questions').fetchone()[0],2)
                self.assertEqual(con.execute('SELECT count(*) FROM images').fetchone()[0],2)
                self.assertEqual(con.execute('SELECT number FROM questions JOIN documents d ON d.id=questions.document_id WHERE filename="a.pdf"').fetchone()[0],2)

if __name__=='__main__':unittest.main()
