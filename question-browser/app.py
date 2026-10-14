"""Independent local PDF question library. Requires Poppler and Pillow."""
import argparse
import errno
import hashlib
import io
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from PIL import Image, ImageChops, ImageDraw
import classifications
import unit_pdf
from ocr_pdf import searchable_copy

ROOT = Path(__file__).resolve().parent
NS = {'h': 'http://www.w3.org/1999/xhtml'}
LOCK = threading.Lock()

class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

def connect(db):
    con = sqlite3.connect(db, factory=Connection)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con

def initialize(db):
    with connect(db) as con:
        classifications.initialize(con)
        con.executescript('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY, filename TEXT NOT NULL UNIQUE, sha256 TEXT NOT NULL,
        imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        number INTEGER NOT NULL, ordinal INTEGER NOT NULL, content TEXT NOT NULL,
        UNIQUE(document_id, number));
        CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        page INTEGER NOT NULL, position INTEGER NOT NULL, png BLOB NOT NULL);
        ''')

def read_pages(pdf):
    data = subprocess.run(['pdftotext', '-bbox-layout', str(pdf), '-'], capture_output=True, check=True, timeout=90).stdout
    pages = []
    for page in ET.fromstring(data).findall('.//h:page', NS):
        lines = []
        for line in page.findall('.//h:line', NS):
            text = ' '.join(word.text or '' for word in line)
            text = re.sub(r'(?<=\d)\s+([.)])', r'\1', text)
            lines.append({'text': text, 'x': float(line.attrib['xMin']), 'y': float(line.attrib['yMin']), 'bottom': float(line.attrib['yMax'])})
        pages.append({'width': float(page.attrib['width']), 'height': float(page.attrib['height']), 'lines': sorted(lines, key=lambda l: (round(l['y']), l['x']))})
    return pages

def question_starts(page):
    result = []
    for line in page['lines']:
        match = re.match(r'^(\d{1,3})[.)]\s+\S', line['text'])
        if match and line['x'] < page['width'] * .15:
            result.append((int(match[1]), line['y']))
    return result

def split_starts(page):
    """Find MCQ stems from repeated answer-choice groups, independent of numbering."""
    lines = page['lines']
    starts = []
    for i, line in enumerate(lines):
        if not re.match(r'^\(?A\s*[.)](?:\s|$)', line['text']):
            continue
        # Require a real answer group instead of an isolated diagram label.
        labels = []
        for following in lines[i:]:
            match = re.match(r'^\(?([A-H])\s*[.)](?:\s|$)', following['text'])
            if match:
                if labels and match[1] == 'A': break
                labels.append(match[1])
        if not all(label in labels for label in ('A','B','C')): continue
        candidates = [l for l in lines[:i] if l['x'] < page['width']*.17
                      and len(l['text']) >= 30
                      and not re.match(r'^\(?[A-H]\s*[.)]',l['text'])
                      and not re.match(r'^(Directions|Instructions|Note:)',l['text'],re.I)]
        if not candidates: continue
        stem = candidates[-1]
        for preceding in reversed(candidates[:-1]):
            if stem['y']-preceding['bottom'] > 30: break
            stem = preceding
        printed = re.match(r'^(\d{1,3})[.)]\s+',stem['text'])
        if not starts or stem['y'] != starts[-1][1]:
            starts.append((int(printed[1]) if printed else None,stem['y']))
    # Number markers remain useful hints for non-MCQ formats, never question IDs.
    return starts or question_starts(page)

def split_boundary(image, low, high, scale):
    """Prefer the widest white gutter; this preserves drawings above the next stem."""
    low, high = int(low * scale), int(high * scale)
    gray = image.convert('L')
    longest = (0, low)
    run = 0
    for y in range(max(0, low), min(gray.height, high)):
        row = gray.crop((12, y, gray.width-12, y+1))
        if row.getextrema()[0] > 242:
            run += 1
            if run > longest[0]: longest = (run, y-run//2)
        else:
            run = 0
    return longest[1] / scale if longest[0] > 5 else (low+high)/2/scale

def parse_pdf(pdf):
    pages = read_pages(pdf)
    if not any(split_starts(p) for p in pages):
        pages = read_pages(searchable_copy(pdf))
        if not any(split_starts(p) for p in pages):
            raise ValueError('OCR completed but no question boundaries were detected. Use clearly separated question stems and answer choices (A), (B), (C), (D).')
    result, current = [], None
    with tempfile.TemporaryDirectory(prefix='questions-') as tmp:
        for index, page in enumerate(pages, 1):
            starts = split_starts(page)
            if not starts and current is None: continue
            prefix = str(Path(tmp)/'page')
            subprocess.run(['pdftoppm', '-f', str(index), '-l', str(index), '-scale-to', '1440', '-singlefile', '-png', str(pdf), prefix], capture_output=True, check=True, timeout=90)
            with Image.open(prefix+'.png') as rendered:
                image = rendered.convert('RGB')
            scale = image.height / page['height']
            footer = page['height'] - 36
            for line in page['lines']:
                if re.search(r'Page\s+\d+\s+of\s+\d+', line['text'], re.I): footer = min(footer, line['y']-8)
            boundaries = []
            for j, (number, y) in enumerate(starts):
                if j == 0:
                    boundary = 10
                    if index == 1:
                        # Exclude the opening instructions while retaining the first diagram.
                        intro = [l['bottom'] for l in page['lines'] if l['y'] < y and re.search(r'best in each case', l['text'], re.I)]
                        if intro: boundary = max(intro)+12
                else:
                    prev_y = starts[j-1][1]
                    answers = [l for l in page['lines'] if prev_y < l['y'] < y and re.match(r'^\(?D\)', l['text'])]
                    low = answers[-1]['bottom']+4 if answers else prev_y+30
                    boundary = split_boundary(image, low, y-8, scale)
                boundaries.append(boundary)
            segments=[]
            if starts:
                if current and boundaries[0] > 20: segments.append((current, 10, boundaries[0]))
                for j, (number,y) in enumerate(starts):
                    current={'number':len(result)+1, 'source_number':number,'text':[], 'images':[], 'visual_hashes':[]}
                    result.append(current)
                    segments.append((current,boundaries[j],boundaries[j+1] if j+1<len(starts) else footer))
            elif current:
                segments.append((current,10,footer))
            for question,top,bottom in segments:
                text='\n'.join(l['text'] for l in page['lines'] if top<=l['y']<bottom)
                if question.get('source_number') is not None:
                    text=re.sub(rf'(?m)^(\s*){question["source_number"]}[.)]\s+',rf'\g<1>{question["number"]}. ',text,count=1)
                elif not question['text']:
                    stem_y = next((y for _,y in starts if top <= y < bottom),None)
                    stem_line = next((l['text'] for l in page['lines'] if l['y']==stem_y),None)
                    if stem_line: text=text.replace(stem_line,str(question['number'])+'. '+stem_line,1)
                question['text'].append(text)
                crop=image.crop((0,int(top*scale),image.width,int(bottom*scale)))
                bbox=ImageChops.difference(crop,Image.new('RGB',crop.size,'white')).convert('L').point(lambda v:255 if v>20 else 0).getbbox()
                if bbox:
                    x0,y0,x1,y1=bbox
                    crop=crop.crop((max(0,x0-14),max(0,y0-14),min(crop.width,x1+14),min(crop.height,y1+14)))
                    buf=io.BytesIO();crop.save(buf,format='PNG')
                    question['images'].append((index,buf.getvalue()))
                    # Ignore the printed question number when comparing visual content.
                    visual = image.crop((0,int(top*scale),image.width,int(bottom*scale)))
                    draw = ImageDraw.Draw(visual)
                    for line in page['lines']:
                        if top <= line['y'] < bottom and re.match(rf'^{question.get("source_number")}[.)]\s+', line['text']):
                            draw.rectangle((0, int((line['y']-top)*scale)-2, int(70*scale), int((line['bottom']-top)*scale)+2), fill='white')
                    bounds = ImageChops.difference(visual, Image.new('RGB',visual.size,'white')).getbbox()
                    if bounds: visual = visual.crop(bounds)
                    question['visual_hashes'].append(hashlib.sha256(str(visual.size).encode()+visual.tobytes()).hexdigest())
    return result

def import_files(folder, db):
    statuses=[]
    with LOCK:
        for pdf in sorted(folder.glob('*.pdf')):
            try:
                digest=hashlib.sha256(pdf.read_bytes()+b'choice-split-v2').hexdigest()
                with connect(db) as con:
                    old=con.execute('SELECT * FROM documents WHERE filename=?',(pdf.name,)).fetchone()
                    if old and old['sha256']==digest:
                        statuses.append({'filename':pdf.name,'status':'unchanged'});continue
                questions=parse_pdf(pdf)
                with connect(db) as con:
                    con.execute('DELETE FROM documents WHERE filename=?',(pdf.name,))
                    doc=con.execute('INSERT INTO documents(filename,sha256) VALUES(?,?)',(pdf.name,digest)).lastrowid
                    for ordinal,q in enumerate(questions,1):
                        qid=con.execute('INSERT INTO questions(document_id,number,ordinal,content) VALUES(?,?,?,?)',(doc,q['number'],ordinal,'\n'.join(q['text']))).lastrowid
                        for pos,(page,png) in enumerate(q['images']):
                            con.execute('INSERT INTO images(question_id,page,position,png) VALUES(?,?,?,?)',(qid,page,pos,png))
                statuses.append({'filename':pdf.name,'status':'imported','questions':len(questions)})
            except Exception as e:
                statuses.append({'filename':pdf.name,'status':'error','error':str(e)})
    return statuses

class Handler(BaseHTTPRequestHandler):
    def respond(self,body,status=200,kind='application/json',headers=None):
        if kind=='application/json':body=json.dumps(body).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        for key,value in (headers or {}).items(): self.send_header(key,value)
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        p=urlsplit(self.path);args=parse_qs(p.query)
        try:
            with connect(self.server.db) as con:
                if p.path=='/': return self.respond((ROOT/'index.html').read_bytes(),kind='text/html; charset=utf-8')
                if p.path == '/api/export/unit.pdf':
                    unit = int(args.get('unit',['0'])[0])
                    pdf, count = unit_pdf.build_pdf(con, unit)
                    return self.respond(pdf,kind='application/pdf',headers={'Content-Disposition':f'attachment; filename="unit-{unit}-questions.pdf"','X-Question-Count':str(count)})
                if p.path == '/api/classifier/questions': return self.respond(classifications.queue(con, ROOT/'questions.json'))
                if p.path == '/api/classifier/export': return self.respond(classifications.export(con))
                if p.path=='/api/documents': return self.respond([dict(r) for r in con.execute('SELECT d.id,d.filename,d.imported_at,COUNT(q.id) AS count FROM documents d LEFT JOIN questions q ON q.document_id=d.id GROUP BY d.id ORDER BY filename')])
                if p.path == '/api/questions':
                    questions = []
                    for row in con.execute('SELECT id,number,ordinal,content FROM questions WHERE document_id=? ORDER BY ordinal', (int(args.get('document', ['0'])[0]),)):
                        question = dict(row)
                        content = question.pop('content')
                        stem = re.search(rf'(?m)^\s*{question["number"]}[.)]\s+(.+)', content)
                        question['summary'] = (content[stem.start():] if stem else content)[:400]
                        questions.append(question)
                    return self.respond(questions)
                if p.path.startswith('/api/question/'):
                    q=con.execute('SELECT q.*,d.filename FROM questions q JOIN documents d ON d.id=q.document_id WHERE q.id=?',(int(p.path.rsplit('/',1)[-1]),)).fetchone()
                    if not q:return self.respond({'error':'Question not found'},404)
                    data=dict(q);data['classification']=classifications.for_question(con,q['filename'],q['number'],q['content']);data['images']=[dict(r) for r in con.execute('SELECT id,page FROM images WHERE question_id=? ORDER BY position',(q['id'],))];return self.respond(data)
                if p.path.startswith('/api/image/'):
                    r=con.execute('SELECT png FROM images WHERE id=?',(int(p.path.rsplit('/',1)[-1]),)).fetchone()
                    if r:return self.respond(r['png'],kind='image/png')
                return self.respond({'error':'Not found'},404)
        except (ValueError,sqlite3.Error) as e:return self.respond({'error':str(e)},400)
    def do_POST(self):
        if self.path == '/api/classifier/result':
            origin = self.headers.get('Origin')
            allowed = origin in (None, f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}') or bool(re.fullmatch(r'chrome-extension://[a-p]{32}', origin or ''))
            if not allowed: return self.respond({'error':'Origin rejected'},403)
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                return self.respond({'error':'Use application/json'},415)
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 120000: raise ValueError('Invalid payload size')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload,dict): raise ValueError('Expected a JSON object')
                with connect(self.server.db) as con:
                    result = classifications.save(con, ROOT/'questions.json', payload)
                return self.respond(result)
            except (ValueError, sqlite3.Error) as exc:
                return self.respond({'error':str(exc)},400)
        if self.path!='/api/import':return self.respond({'error':'Not found'},404)
        if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self.respond({'error':'Origin rejected'},403)
        return self.respond(import_files(self.server.folder,self.server.db))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pdf-dir',type=Path,default=ROOT);parser.add_argument('--port',type=int,default=8001);parser.add_argument('--import-only',action='store_true');args=parser.parse_args()
    for command in ('pdftotext','pdftoppm'):
        if not shutil.which(command):parser.error(f'{command} is required. Install Poppler; see README.md.')
    db=ROOT/'questions.sqlite3';initialize(db)
    print(json.dumps(import_files(args.pdf_dir.resolve(),db),indent=2),flush=True)
    if not args.import_only:
        try:
            server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                parser.exit(1, f'Port {args.port} is already in use. Open http://127.0.0.1:{args.port} if the library is running, or start another instance with python3 app.py --port {args.port + 1}\n')
            raise
        server.db = db
        server.folder = args.pdf_dir.resolve()
        print(f'Question library: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nQuestion library stopped.', flush=True)
        raise SystemExit(130)
