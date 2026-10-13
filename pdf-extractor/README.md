# Papertrail — Physics Lab PDF Finder

Run with Python 3.10 or later. No packages or accounts to configure.

```sh
cd pdf-extractor
python3 app.py
```

Open http://127.0.0.1:8000 and click **Find PDFs**. The supplied Physics Lab URL is already filled in. Practice Test 1 is selected by default; choose All documents to see other PDFs. Select a PDF to preview it; use the browser PDF viewer's download button or Open / save to save a copy.

Use `python3 app.py --port 8080` to change the port.

The application extracts links from anchors, iframes, embeds and objects and unwraps Teachable's URL-encoded viewer links, preserving signed query parameters. Refresh extraction if a signed link expires. It does not authenticate to Physics Lab or bypass course permissions. Network access to Physics Lab and Teachable is required. Some browsers may require opening the PDF in a new tab instead of displaying the embedded preview.

The server listens only on localhost and allows HTTPS requests only to the supported Physics Lab and PDF CDN hosts, including on redirects. Files are opened directly from their original hosts; PDFs are not stored by the application.

Verification: `python3 -m unittest discover -s pdf-extractor -p 'test_*.py'` from the parent folder.
