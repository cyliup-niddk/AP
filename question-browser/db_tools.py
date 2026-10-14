"""Back up a portable database or recreate its complete JSON question export."""
import argparse
import json
from pathlib import Path
import sqlite3
import app
import portable_db


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backup','export-json'])
    parser.add_argument('--database',type=Path,default=app.ROOT/'questions.sqlite3')
    parser.add_argument('-o','--output',type=Path,required=True)
    args=parser.parse_args()
    source=args.database.expanduser().resolve();output=args.output.expanduser().resolve()
    if not source.is_file():parser.error(f'Database not found: {source}')
    if output.exists():parser.error('Output already exists; choose a new filename.')
    output.parent.mkdir(parents=True,exist_ok=True)
    # Capture a consistent snapshot, including when the service is running.
    with app.connect(source) as con:
        if args.action=='backup':
            with sqlite3.connect(output) as target:con.backup(target)
        else:
            questions=portable_db.catalog(con)
            assigned={row[0]:json.loads(row[1]) for row in con.execute('SELECT question_id,question_json FROM question_classifications')}
            questions=[assigned.get(q['id'],q) for q in questions]
            output.write_text(json.dumps({'schema_version':1,'questions':questions},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Saved: {output}')

if __name__=='__main__':main()
