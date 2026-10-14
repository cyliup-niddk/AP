import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import app
import classifications
import portable_db
import unit_pdf

class PortableTests(unittest.TestCase):
    def test_copy_without_pdf_or_json_keeps_images_queue_and_assignments(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);db=folder/'original.sqlite3';app.initialize(db)
            buf=io.BytesIO();Image.new('RGB',(200,100),'white').save(buf,format='PNG');png=buf.getvalue()
            with app.connect(db) as con:
                doc=con.execute('INSERT INTO documents(filename,sha256) VALUES(?,?)',('scan.pdf','test')).lastrowid
                qid=con.execute('INSERT INTO questions(document_id,number,ordinal,content) VALUES(?,?,?,?)',(doc,1,1,'1. Pressure in water?')).lastrowid
                con.execute('INSERT INTO images(question_id,page,position,png) VALUES(?,?,?,?)',(qid,1,0,png))
                portable_db.archive_library(con)
                queue=classifications.queue(con)
                self.assertEqual(len(queue),1)
                classifications.save(con,None,{'question_id':queue[0]['id'],'unit_numbers':[2,8],'reason':'Force and pressure'})
            moved=folder/'moved'/'library.sqlite3';app.initialize(moved)
            with app.connect(db) as source,app.connect(moved) as target:source.backup(target)
            db.unlink()
            with app.connect(moved) as con:
                saved=portable_db.catalog(con)
                self.assertEqual(base64.b64decode(saved[0]['images'][0]['base64']),png)
                self.assertEqual(classifications.queue(con)[0]['unit_numbers'],[2,8])
                self.assertEqual(classifications.for_question(con,'scan.pdf',1,'1. Pressure in water?')['unit_numbers'],[2,8])
                pdf,count=unit_pdf.build_pdf(con,8)
                self.assertTrue(pdf.startswith(b'%PDF-'));self.assertEqual(count,1)
                self.assertEqual(con.execute('SELECT png FROM images').fetchone()[0],png)

if __name__=='__main__':unittest.main()
