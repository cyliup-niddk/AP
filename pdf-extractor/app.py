"""Local PDF finder for Physics Lab. Python 3.10+, no dependencies."""
import argparse
import html
import json
import re
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

DEFAULT = 'https://physicslab.app/courses/559004/lectures/51787138#MCQ-Practice-Test-1'
ALLOWED = {'physicslab.app', 'www.physicslab.app', 'assets.teachablecdn.com', 'uploads.teachablecdn.com', 'cdn.filestackcontent.com'}
LIMIT = 8 * 1024 * 1024

def validate(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname not in ALLOWED or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Use an HTTPS Physics Lab page or a supported Teachable PDF link.')
    return url

class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(url):
    validate(url)
    with build_opener(Redirects()).open(Request(url, headers={'User-Agent': 'Mozilla/5.0 PDF Finder'}), timeout=25) as response:
        data = response.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError('The page is too large (maximum 8 MB).')
        return data, response.headers.get('Content-Type', ''), response.geturl()

class Finder(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.text, self.items = base, '', []
    def handle_data(self, data):
        self.text = (self.text + ' ' + data)[-1600:]
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('href', 'src', 'data', 'data-src'):
            raw = attrs.get(key, '')
            if not raw:
                continue
            url = urljoin(self.base, html.unescape(raw))
            p = urlsplit(url)
            if p.scheme != 'https':
                continue
            if tag not in ('iframe', 'embed', 'object') and not re.search(r'\.pdf(?:[?#]|$)', url, re.I):
                continue
            # Teachable's viewer embeds the real file in a query parameter.
            for name in ('file', 'url', 'src'):
                values = parse_qs(p.query).get(name)
                if values and values[0].startswith('https://'):
                    url = values[0]
                    break
            if urlsplit(url).hostname not in ALLOWED:
                continue
            labels = re.findall(r'([^<>\n]{1,100}?\.pdf)', self.text, re.I)
            title = labels[-1].strip() if labels else attrs.get('title') or unquote(urlsplit(url).path.rsplit('/', 1)[-1]) or 'Embedded document'
            title = re.sub(r'^.*?(MCQ Practice Test)', r'\1', title)
            self.items.append({'url': url, 'title': title, 'kind': 'Answers' if re.search(r'answer|solution', title, re.I) else 'Questions' if re.search(r'question', title, re.I) else 'Document'})

def extract(source, base):
    parser = Finder(base)
    parser.feed(source)
    seen, results = set(), []
    for item in parser.items:
        if item['url'] not in seen:
            seen.add(item['url'])
            results.append(item)
    return results

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == '/':
            return self.send(200, (Path(__file__).parent / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if path.path != '/api/extract':
            return self.send(404, b'Not found', 'text/plain')
        try:
            url = parse_qs(path.query).get('url', [DEFAULT])[0]
            data, content_type, final_url = fetch(url)
            if 'application/pdf' in content_type or data.startswith(b'%PDF-'):
                files = [{'url': final_url, 'title': unquote(urlsplit(final_url).path.rsplit('/', 1)[-1]) or 'Document.pdf', 'kind': 'Document'}]
            else:
                files = extract(data.decode('utf-8', errors='replace'), final_url)
            self.send(200, json.dumps({'files': files, 'source': final_url}).encode(), 'application/json')
        except Exception as exc:
            self.send(400, json.dumps({'error': str(exc)}).encode(), 'application/json')
    def send(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    print(f'PDF Finder is running at http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
