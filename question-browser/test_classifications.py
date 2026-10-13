import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import classifications

class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'questions.json'
        self.original={'questions':[{'id':'q1','text':'Pressure in mercury?','images':[{'base64':'abc'}],'sources':[{'filename':'test.pdf','question_number':1}]}]}
        self.path.write_text(json.dumps(self.original))
        self.con=sqlite3.connect(':memory:')
        classifications.initialize(self.con)
    def tearDown(self):
        self.con.close();self.temp.cleanup()
    def test_save_json_and_resume_queue(self):
        self.assertIsNone(classifications.queue(self.con,self.path)[0]['unit_number'])
        payload={'question_id':'q1','unit_number':8,'reason':'Fluid pressure','raw_response':'Gemini JSON'}
        classifications.save(self.con,self.path,payload)
        classifications.save(self.con,self.path,payload)
        self.assertEqual(self.con.execute('SELECT count(*) FROM question_classifications').fetchone()[0],1)
        self.assertEqual(classifications.queue(self.con,self.path)[0]['unit_number'],8)
        self.assertNotIn('images',classifications.queue(self.con,self.path)[0])
        result=classifications.export(self.con)['questions'][0]
        self.assertEqual(result['unit_number'],8)
        self.assertEqual(result['unit_name'],'Fluids')
        self.assertEqual(result['images'],self.original['questions'][0]['images'])
        self.assertEqual(json.loads(self.path.read_text()),self.original)
    def test_library_assignment_matches_source_and_content(self):
        self.original['questions'][0]['question_number']=1
        self.original['questions'][0]['text']='1. Pressure in mercury?'
        self.original['questions'][0]['sources'].append({'filename':'other/test2.pdf','question_number':9})
        self.path.write_text(json.dumps(self.original))
        classifications.save(self.con,self.path,{'question_id':'q1','unit_number':8,'reason':'Fluid pressure'})
        result=classifications.for_question(self.con,'test.pdf',1,'1. Pressure in mercury?')
        self.assertEqual(result['unit_name'],'Fluids')
        self.assertEqual(classifications.for_question(self.con,'test2.pdf',9,'9. Pressure in mercury?')['unit_number'],8)
        self.assertIsNone(classifications.for_question(self.con,'test.pdf',2,'2. Pressure in mercury?'))
        self.assertIsNone(classifications.for_question(self.con,'test.pdf',1,'1. A different question'))

    def test_multiple_units_are_saved_and_validated(self):
        result=classifications.save(self.con,self.path,{'question_id':'q1','unit_numbers':[8,2,8],'reason':'Fluids and force balance'})
        self.assertEqual(result['unit_numbers'],[2,8])
        saved=classifications.export(self.con)['questions'][0]
        self.assertEqual(saved['unit_names'],['Force and Translational Dynamics','Fluids'])
        self.assertEqual(classifications.queue(self.con,self.path)[0]['unit_numbers'],[2,8])
        for numbers in ([],None,8,['8'],[0,8],[8,9],[True],[2.5]):
            with self.assertRaises(ValueError):
                classifications.save(self.con,self.path,{'question_id':'q1','unit_numbers':numbers})
        self.assertEqual(classifications.export(self.con)['questions'][0]['unit_numbers'],[2,8])

    def test_legacy_database_migration(self):
        con=sqlite3.connect(':memory:')
        try:
            con.execute('CREATE TABLE question_classifications(question_id TEXT PRIMARY KEY, unit_number INTEGER, reason TEXT, raw_response TEXT, question_json TEXT, classified_at TEXT)')
            con.execute('INSERT INTO question_classifications VALUES(?,?,?,?,?,?)',('q1',8,'Fluid pressure','original response',json.dumps(self.original['questions'][0]),'2026-10-13 00:00:00'))
            classifications.initialize(con)
            classifications.initialize(con)
            self.assertEqual(classifications.export(con)['questions'][0]['unit_numbers'],[8])
            row=con.execute('SELECT raw_response,classified_at FROM question_classifications').fetchone()
            self.assertEqual(row,('original response','2026-10-13 00:00:00'))
        finally:con.close()

    def test_reject_invalid_or_unknown_results(self):
        for unit in (0,9,'8',True,None):
            with self.assertRaises(ValueError):classifications.save(self.con,self.path,{'question_id':'q1','unit_number':unit})
        with self.assertRaises(ValueError):classifications.save(self.con,self.path,{'question_id':'unknown','unit_number':8})
        self.assertEqual(classifications.export(self.con)['questions'],[])

if __name__=='__main__':unittest.main()
