"""JSON question classification storage, separate from PDF import lifecycle."""
import json
import re
import sqlite3
from pathlib import Path
import portable_db

UNITS = {
    1: 'Kinematics', 2: 'Force and Translational Dynamics',
    3: 'Work, Energy, and Power', 4: 'Linear Momentum',
    5: 'Torque and Rotational Dynamics', 6: 'Energy and Momentum of Rotating Systems',
    7: 'Oscillations', 8: 'Fluids',
}

def initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS question_classifications (
        question_id TEXT PRIMARY KEY, unit_number INTEGER NOT NULL CHECK(unit_number BETWEEN 1 AND 8),
        reason TEXT NOT NULL, raw_response TEXT NOT NULL, question_json TEXT NOT NULL,
        classified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    columns = {row[1] for row in con.execute('PRAGMA table_info(question_classifications)')}
    if 'unit_numbers' not in columns:
        con.execute('ALTER TABLE question_classifications ADD COLUMN unit_numbers TEXT')
    for qid, unit, encoded in con.execute('SELECT question_id,unit_number,question_json FROM question_classifications WHERE unit_numbers IS NULL').fetchall():
        question = json.loads(encoded)
        question.update(unit_numbers=[unit], unit_names=[UNITS[unit]])
        con.execute('UPDATE question_classifications SET unit_numbers=?,question_json=? WHERE question_id=?', (json.dumps([unit]),json.dumps(question,ensure_ascii=False),qid))


def load_export(path):
    if not Path(path).is_file():
        raise ValueError('questions.json is missing. Run python3 pdf_to_json.py . -o questions.json first.')
    questions = json.loads(Path(path).read_text(encoding='utf-8'))['questions']
    if not isinstance(questions, list): raise ValueError('Invalid questions.json')
    return questions

def queue(con, path=None):
    saved = {row[0]: json.loads(row[1]) for row in con.execute('SELECT question_id,unit_numbers FROM question_classifications')}
    return [{key: q.get(key) for key in ('id','filename','question_number','order','text','stem','sources')} | {'unit_numbers': saved.get(q['id'], []), 'unit_number': (saved[q['id']][0] if q['id'] in saved else None)} for q in portable_db.catalog(con,path)]

def save(con, path, payload):
    qid = payload.get('question_id')
    numbers = payload.get('unit_numbers', [payload.get('unit_number')])
    if not isinstance(numbers,list) or not numbers or any(type(n) is not int or n not in UNITS for n in numbers):
        raise ValueError('unit_numbers must be a nonempty array of integers from 1 to 8.')
    numbers = sorted(set(numbers))
    unit = numbers[0]  # Compatibility with previously installed extension versions.

    question = next((q for q in portable_db.catalog(con,path) if q['id'] == qid), None)
    if question is None: raise ValueError('Question ID is not in this database. Refresh the extension queue.')
    reason, raw = payload.get('reason',''), payload.get('raw_response','')
    if not isinstance(reason,str) or not isinstance(raw,str) or len(raw)>100000: raise ValueError('Invalid response text.')
    question = dict(question, unit_numbers=numbers, unit_names=[UNITS[n] for n in numbers], unit_number=unit, unit_name=UNITS[unit], classification_reason=reason)
    con.execute('''INSERT INTO question_classifications(question_id,unit_number,reason,raw_response,question_json,unit_numbers)
    VALUES(?,?,?,?,?,?) ON CONFLICT(question_id) DO UPDATE SET unit_number=excluded.unit_number,
    reason=excluded.reason, raw_response=excluded.raw_response, question_json=excluded.question_json,
    unit_numbers=excluded.unit_numbers, classified_at=CURRENT_TIMESTAMP''', (qid,unit,reason,raw,json.dumps(question,ensure_ascii=False),json.dumps(numbers)))
    return {'question_id':qid,'unit_numbers':numbers,'unit_names':[UNITS[n] for n in numbers],'unit_number':unit,'unit_name':UNITS[unit]}

def export(con):
    return {'questions':[json.loads(row[0]) for row in con.execute('SELECT question_json FROM question_classifications ORDER BY classified_at,question_id')]}


def for_question(con, filename, number, content):
    """Match a library question to a saved export occurrence without stale labels."""
    def normalized(text, question_number):
        text = re.sub(rf'(?m)^\s*{question_number}[.)]\s+', '', text, count=1)
        return re.sub(r'\s+', ' ', text).strip()
    for row in con.execute('SELECT question_id,unit_number,reason,question_json,classified_at FROM question_classifications ORDER BY classified_at DESC'):
        saved = json.loads(row[3])
        sources = saved.get('sources') or [{'filename':saved.get('filename',''), 'question_number':saved.get('question_number')}]
        matches = any(Path(source['filename']).name == filename and source.get('question_number') == number for source in sources)
        if matches and normalized(saved.get('text',''), saved.get('question_number')) == normalized(content, number):
            return {'question_id':row[0], 'unit_number':row[1], 'unit_name':UNITS[row[1]], 'unit_numbers':saved.get('unit_numbers',[row[1]]), 'unit_names':saved.get('unit_names',[UNITS[row[1]]]), 'reason':row[2], 'classified_at':row[4]}
    return None
