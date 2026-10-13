"""Export local PDF questions as JSON; merge matching questions with provenance."""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path
from app import parse_pdf


def normalize(text, number):
    text = unicodedata.normalize('NFC', text)
    text = re.sub(rf'(?m)^\s*{number}[.)]\s+', '', text, count=1)
    return re.sub(r'\s+', ' ', text).strip()


def convert(folder, recursive=False, dedupe='visual'):
    paths = sorted((folder.rglob('*') if recursive else folder.iterdir()), key=lambda p: str(p).lower())
    questions, by_key, errors = [], {}, []
    total, pdf_count = 0, 0
    for pdf in paths:
        if not pdf.is_file() or pdf.suffix.lower() != '.pdf':
            continue
        pdf_count += 1
        filename = pdf.relative_to(folder).as_posix()
        print(f'Parsing {filename}…', file=sys.stderr)
        try:
            parsed = parse_pdf(pdf)
        except Exception as exc:
            errors.append({'filename': filename, 'error': str(exc)})
            continue
        for ordinal, question in enumerate(parsed, 1):
            total += 1
            content = '\n'.join(question['text'])
            canonical = normalize(content, question['number'])
            visual = question.get('visual_hashes', [])
            key_data = {'text': canonical}
            if dedupe == 'visual':
                # Conservative: do not merge matching text with different diagrams.
                key_data['images'] = visual or [hashlib.sha256(png).hexdigest() for _, png in question['images']]
            key = hashlib.sha256(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            source = {'filename': filename, 'question_number': question['number'], 'order': ordinal,
                      'pages': sorted(set(page for page, _ in question['images']))}
            if key in by_key:
                by_key[key]['sources'].append(source)
                continue
            stem_match = re.search(rf'(?m)^\s*{question["number"]}[.)]\s+', content)
            diagram_text = content[:stem_match.start()].strip() if stem_match else ''
            body = content[stem_match.end():] if stem_match else content
            choices = list(re.finditer(r'(?m)^\s*\(([A-Z])\)\s*', body))
            obj = {
                'id': key, 'question_number': question['number'], 'order': ordinal,
                'filename': filename, 'text': content,
                'stem': body[:choices[0].start()].strip() if choices else body.strip(),
                'diagram_text': diagram_text,
                'choices': [{'label': match[1], 'text': body[match.end():choices[i+1].start() if i+1<len(choices) else len(body)].strip()} for i, match in enumerate(choices)],
                'images': [{'page': page, 'mime_type': 'image/png', 'base64': base64.b64encode(png).decode('ascii')} for page, png in question['images']],
                'sources': [source],
            }
            questions.append(obj)
            by_key[key] = obj
    return {'schema_version': 1, 'deduplication': dedupe,
            'summary': {'pdf_files': pdf_count, 'extracted_questions': total, 'unique_questions': len(questions), 'duplicates_merged': total-len(questions), 'failed_files': len(errors)},
            'questions': questions, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path, help='Folder containing PDF files')
    parser.add_argument('-o', '--output', type=Path, help='JSON output path (default: FOLDER/questions.json)')
    parser.add_argument('--recursive', action='store_true', help='Include PDFs in subfolders')
    parser.add_argument('--dedupe', choices=['visual', 'text'], default='visual', help='visual: matching text and rendering; text: matching normalized text only')
    args = parser.parse_args()
    folder = args.folder.resolve()
    if not folder.is_dir(): parser.error(f'Not a directory: {folder}')
    for tool in ('pdftotext', 'pdftoppm'):
        if not shutil.which(tool): parser.error(f'{tool} is required; install Poppler.')
    output = args.output.resolve() if args.output else folder/'questions.json'
    if output.suffix.lower() == '.pdf': parser.error('Output must not overwrite a PDF. Choose a .json path.')
    result = convert(folder, args.recursive, args.dedupe)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=output.parent, delete=False) as temp:
            temp_path = temp.name
            json.dump(result, temp, ensure_ascii=False, indent=2)
            temp.write('\n')
        os.replace(temp_path, output)
    finally:
        if temp_path and os.path.exists(temp_path): os.unlink(temp_path)
    print(json.dumps(result['summary'], indent=2))
    print(f'Saved: {output}')
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
