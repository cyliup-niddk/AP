"""Self-contained question JSON archive stored inside SQLite."""
import base64
import hashlib
import json
import re
from pathlib import Path


def initialize(con):
    con.execute('CREATE TABLE IF NOT EXISTS question_archive (id TEXT PRIMARY KEY, question_json TEXT NOT NULL)')


def seed(con, path=None):
    initialize(con)
    if path and Path(path).is_file():
        for q in json.loads(Path(path).read_text(encoding='utf-8'))['questions']:
            con.execute('INSERT OR IGNORE INTO question_archive VALUES(?,?)',(q['id'],json.dumps(q,ensure_ascii=False)))
    for row in con.execute('SELECT question_id,question_json FROM question_classifications'):
        con.execute('INSERT OR IGNORE INTO question_archive VALUES(?,?)',(row[0],row[1]))


def catalog(con, path=None):
    seed(con,path)
    return [json.loads(row[0]) for row in con.execute('SELECT question_json FROM question_archive ORDER BY id')]


def archive_library(con, path=None):
    existing=catalog(con,path)
    def normal(text):
        return re.sub(r'\s+',' ',re.sub(r'(?m)^\s*\d+[.)]\s+','',text,count=1)).strip()
    for row in con.execute('SELECT q.id,q.number,q.ordinal,q.content,d.filename FROM questions q JOIN documents d ON d.id=q.document_id ORDER BY d.filename,q.ordinal').fetchall():
        qid,number,order,text,filename=row
        found=next((q for q in existing if normal(q.get('text',''))==normal(text) and any(Path(s['filename']).name==filename and s.get('question_number')==number for s in q.get('sources',[]))),None)
        if found:continue
        images=[{'page':r[0],'mime_type':'image/png','base64':base64.b64encode(r[1]).decode()} for r in con.execute('SELECT page,png FROM images WHERE question_id=? ORDER BY position',(qid,))]
        key=hashlib.sha256(json.dumps({'text':normal(text),'images':[i['base64'] for i in images]},sort_keys=True).encode()).hexdigest()
        source={'filename':filename,'question_number':number,'order':order,'pages':sorted(set(i['page'] for i in images))}
        if any(q['id']==key for q in existing):
            obj=next(q for q in existing if q['id']==key)
            if source not in obj['sources']:obj['sources'].append(source)
        else:
            stem=re.sub(r'(?m)^\s*\d+[.)]\s+','',text,count=1)
            obj={'id':key,'filename':filename,'question_number':number,'order':order,'text':text,'stem':stem,'images':images,'sources':[source]}
            existing.append(obj)
        con.execute('INSERT OR REPLACE INTO question_archive VALUES(?,?)',(key,json.dumps(obj,ensure_ascii=False)))
