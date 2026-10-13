"""Create a cached searchable copy of a scanned PDF without modifying the original."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def searchable_copy(pdf, cache_dir=None):
    pdf=Path(pdf).resolve()
    cache=Path(cache_dir) if cache_dir else Path(__file__).resolve().parent/'.ocr-cache'
    language=os.environ.get('QUESTION_OCR_LANGUAGE','eng')
    digest=hashlib.sha256(pdf.read_bytes()+language.encode()+b'ocr-200dpi-v1').hexdigest()
    output=cache/(digest+'.pdf')
    if output.is_file():return output
    missing=[tool for tool in ('tesseract','pdftoppm','pdfunite','pdfinfo') if not shutil.which(tool)]
    if missing:
        raise ValueError('Scanned PDF needs OCR. Missing: '+', '.join(missing)+'. Run ./start.sh --with-ocr to install OCR support, then import again.')
    cache.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ocr-',dir=cache) as temp:
        directory=Path(temp)
        info=subprocess.run(['pdfinfo',str(pdf)],capture_output=True,text=True,check=True,timeout=30).stdout
        import re
        match=re.search(r'^Pages:\s+(\d+)',info,re.M)
        if not match:raise ValueError('Could not determine scanned PDF page count.')
        pages=[]
        for page in range(1,int(match[1])+1):
            prefix=directory/f'page-{page:05d}'
            print(f'OCR {pdf.name}: page {page}/{match[1]}',flush=True)
            subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-r','200','-singlefile','-png',str(pdf),str(prefix)],capture_output=True,check=True,timeout=120)
            result=subprocess.run(['tesseract',str(prefix)+'.png',str(prefix),'-l',language,'--dpi','200','pdf'],capture_output=True,text=True,timeout=180)
            if result.returncode:raise ValueError('OCR failed: '+result.stderr.strip())
            pages.append(str(prefix)+'.pdf')
            Path(str(prefix)+'.png').unlink()
        combined=directory/'combined.pdf'
        if len(pages)==1:shutil.copyfile(pages[0],combined)
        else:subprocess.run(['pdfunite',*pages,str(combined)],capture_output=True,check=True,timeout=120)
        os.replace(combined,output)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('pdf',type=Path);parser.add_argument('-o','--output',type=Path);args=parser.parse_args()
    try:
        copy=searchable_copy(args.pdf)
        if args.output:
            if args.output.resolve()==args.pdf.resolve():raise ValueError('Choose an output different from the original PDF.')
            shutil.copyfile(copy,args.output);copy=args.output
        print(f'Searchable PDF: {copy}')
    except (ValueError,subprocess.SubprocessError) as exc:parser.exit(1,str(exc)+'\n')
