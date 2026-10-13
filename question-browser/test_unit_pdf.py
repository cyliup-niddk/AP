import base64
import io
import json
import sqlite3
import subprocess
import unittest
from PIL import Image
import classifications
import unit_pdf

class UnitPdfTests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:');classifications.initialize(self.con)
        buffer=io.BytesIO();Image.new('RGB',(200,100),'white').save(buffer,format='PNG')
        image={'base64':base64.b64encode(buffer.getvalue()).decode()}
        for index,numbers in enumerate(([2,8],[3],[8]),1):
            q={'id':str(index),'filename':'test.pdf','question_number':index,'order':index,'unit_numbers':numbers,'images':[image]*(2 if index==1 else 1)}
            self.con.execute('INSERT INTO question_classifications(question_id,unit_number,unit_numbers,reason,raw_response,question_json) VALUES(?,?,?,?,?,?)',(str(index),numbers[0],json.dumps(numbers),'','',json.dumps(q)))
    def tearDown(self):self.con.close()
    def test_matching_includes_secondary_unit_and_excludes_others(self):
        self.assertEqual([q['question_number'] for q in unit_pdf.matching_questions(self.con,8)],[1,3])
        self.assertEqual([q['question_number'] for q in unit_pdf.matching_questions(self.con,2)],[1])
    def test_pdf_contains_all_matching_question_parts(self):
        pdf,count=unit_pdf.build_pdf(self.con,8)
        self.assertEqual(count,2);self.assertTrue(pdf.startswith(b'%PDF-'))
        result=subprocess.run(['pdfinfo','-'],input=pdf,capture_output=True,check=True)
        self.assertRegex(result.stdout.decode(),r'Pages:\s+3\b')
    def test_empty_or_invalid_unit(self):
        for unit in (0,9,True,'8',2.5):
            with self.assertRaises(ValueError):unit_pdf.build_pdf(self.con,unit)
        with self.assertRaisesRegex(ValueError,'No classified questions'):unit_pdf.build_pdf(self.con,7)

if __name__=='__main__':unittest.main()
