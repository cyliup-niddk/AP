# Independent PDF Question Library

Imports local PDFs into SQLite and displays each question when its numbered button is clicked. Runs independently of the PDF extractor app. `test1.pdf` is included from the supplied workspace file.

## Install and launch with one command

```sh
cd question-browser
./start.sh
```

To choose the database location:

```sh
cd question-browser
./start.sh --database /path/to/library.sqlite3
```

To open a portable database without importing local PDFs:

```sh
cd question-browser
./start.sh --database /path/to/library.sqlite3 --no-import
```

Replace `/path/to/library.sqlite3` with your database path. If you are already inside `question-browser`, omit `cd question-browser`.

The Bash launcher installs missing Python/Poppler tools using your system package manager (sudo may request your password), creates `.venv`, installs Pillow if needed, prepares `questions.json` if missing, and starts the service in the foreground. It supports Fedora/DNF, Debian/Ubuntu/APT, Arch/pacman, and macOS/Homebrew. Install Homebrew yourself if needed. Compatible system Python packages are reused within the virtual environment to avoid unnecessary downloads.

Open the address printed by the app, normally **http://127.0.0.1:8001**. Press **Ctrl+C** to stop it. Existing PDFs, JSON exports, and saved assignments are preserved; normal app startup imports new or changed PDFs. An existing JSON export is not regenerated automatically—use the JSON exporter when adding PDFs for Gemini classification.

```sh
./start.sh --port 8080
./start.sh --pdf-dir /path/to/pdfs
./start.sh --setup-only
```

The browser extension requires a one-time manual **Load unpacked** step; the launcher prints its directory. It does not install a browser, log in to Gemini, or create a background system service.

## Run

```sh
cd question-browser
python3 app.py
```

Open **http://127.0.0.1:8001**. On startup the app imports all `*.pdf` files beside `app.py`. Choose a filename, then click a question number. Use Previous / Next to move through the questions. Images preserve diagrams, tables, equations, and graphical answer choices. Expand Extracted text to read the parsed text. Search matches question numbers or the beginning of the question text.

Add another PDF to this directory and click **Import local PDFs**. Unchanged files are skipped; changed files replace their previous questions in one database transaction. A failed import leaves the prior saved version intact. Removing a PDF does not delete its saved questions. SQLite retains question text and images, so imported questions remain readable without the original PDF.

Options:

```sh
python3 app.py --port 8080
python3 app.py --pdf-dir /path/to/pdfs
python3 app.py --import-only
```

If the port is already in use, open the existing app at that address or run `python3 app.py --port 8002`. Stop a running instance with Ctrl+C in its terminal.

## Dependencies

Python 3.10+, Pillow, and the Poppler commands `pdftotext` / `pdftoppm`. These are already available in this workspace. For another computer install Pillow with `python3 -m pip install -r requirements.txt`, and install Poppler through the operating system package manager (for example `sudo apt install poppler-utils` on Debian/Ubuntu or `brew install poppler` on macOS).

## Database

`questions.sqlite3` is created alongside `app.py`:

- `documents`: filename (unique), SHA-256, import timestamp.
- `questions`: document ID, printed question number, order within the file, extracted text. `(document_id, number)` is unique.
- `images`: question ID, original PDF page number, image order, PNG bytes.

Each filename is a separate question set. Rename a file to import it as a new set. Back up the SQLite file while the app is stopped.

## Parsing limits

Designed for text-based PDFs with sequential, left-aligned numbered questions (`1.` or `1)`) in a single column. It uses text coordinates and white space in rendered pages to separate questions, retaining diagrams above a question stem. Automatic crop boundaries should be reviewed for unfamiliar layouts. Two-column papers, shared passages/figures across several questions, or numbering that restarts within a file need format-specific handling. Scanned PDFs require OCR first; the importer reports when no numbered questions are detected. No external services are used.

The supplied test has 42 questions across 22 pages. Test with `python3 -m unittest discover -s . -p 'test_*.py'`.

## Export PDFs to JSON and merge duplicates

The independent command-line script reads PDFs directly; it does not require a running web app or use its SQLite database.

From the workspace root:

```sh
python3 question-browser/pdf_to_json.py /path/to/pdf-folder -o /path/to/questions.json
```

From `question-browser` (export the included sample):

```sh
python3 pdf_to_json.py . -o questions.json
```

Options:

- `--recursive`: include PDFs in subfolders; source paths remain relative to the input folder.
- `--dedupe visual` (default): merge identical normalized text and matching question renderings. Printed question numbers and whitespace in text are ignored. Differences in rendering, layout, or resolution may prevent otherwise identical questions from merging; this conservative mode protects different diagrams.
- `--dedupe text`: merge normalized text regardless of the diagrams. Use only when text sufficiently identifies your questions; identical text with different diagrams will merge.

The JSON contains `questions`, `summary`, and `errors`. Each question contains a stable content hash `id`, first occurrence `filename`, `question_number` and `order`, full extracted `text`, `stem`, `diagram_text`, `choices`, embedded PNG `images` (base64), and `sources` listing **every** occurrence with filename, printed question number, order, and pages. The first occurrence provides the canonical text and images; merged occurrences retain their provenance. Choice text may be empty for graphical choices; the image preserves them. PDF text ordering and crop limitations are the same as the web importer.

Duplicate question numbers across different PDFs are supported; numbering that restarts within a single PDF is currently rejected. Repeated runs rebuild the output from the folder rather than append to an old export. Output replacement is atomic. A bad PDF is reported under `errors`, other PDFs continue, and the command exits with status 1 to indicate a partial export. The default output is `questions.json` in the input folder.

## Gemini unit-classification extension

See [gemini-extension/README.md](gemini-extension/README.md) for Chrome/Edge installation and use. The extension submits question text to your signed-in Gemini tab, captures a matching unit classification, and stores the augmented JSON in `question_classifications` within `questions.sqlite3`. It supports single questions and an automatic queue with a random 0–3 second pause per query. Restart the Python app after updating to enable the classification endpoints.

When you select a question, its saved unit assignment and Gemini explanation appear above the question image. Unclassified questions display **Unit not assigned yet**. After classifying in the extension, select the question again (or refresh) to retrieve the latest assignment. Restart the Python app after updating to enable this display. Assignments are matched to the source filename, printed question number, and content so a changed question does not inherit an old label.

Questions can now have multiple unit assignments, shown together above the question image. JSON exports include `unit_numbers` and `unit_names`. Existing assignments are preserved as single-item lists. In the extension, choose **Reclassify all with multiple units** to revisit already-classified questions using the updated prompt.

## Download questions for one unit as a PDF

In the web app sidebar, enter a unit number (1–8) under **Export questions by unit**, then click **Download unit PDF**. The download is named `unit-8-questions.pdf`, for example.

The export uses the saved classifications across **all files**, independent of the currently selected file or search. A multi-unit question is included if the entered number is anywhere in its assignment list. Each deduplicated saved question appears once, in filename/question order. Original question crops preserve diagrams and answer choices. Each crop is placed on its own letter-size page with the source filename, printed question number, and assigned units; a question with multiple crops spans multiple pages. The output is image-based, so question text is not selectable. If nothing matches, the app displays a message rather than downloading an empty PDF.

Classify questions with the extension first. After updating, restart `python3 app.py` and refresh the webpage to see the export control. Export requires Pillow 10.1+ (already installed in this workspace).

## Scanned PDFs and OCR

If a PDF consists of page images, install OCR support and launch:

```sh
cd question-browser
./start.sh --with-ocr
```

On Fedora this installs `tesseract` and `tesseract-langpack-eng` through sudo. Once installed, the app and JSON exporter automatically try OCR when no numbered questions are detected. Tesseract adds a searchable text layer; the app then uses that layer for question boundaries while retaining the original page images for display. Originals are unchanged. Searchable copies are cached in `.ocr-cache` by file content and language so repeated imports do not repeat OCR. OCR progress appears in the terminal and can take several minutes for long PDFs.

Click **Import local PDFs** after installing, or restart the service. To regenerate the question JSON for the extension:

```sh
./.venv/bin/python pdf_to_json.py /path/to/scanned-pdfs -o questions.json
```

To create a searchable PDF explicitly:

```sh
./.venv/bin/python ocr_pdf.py /path/to/scan.pdf -o /path/to/searchable.pdf
```

English is the default. For other languages, install the corresponding Tesseract language data and set `QUESTION_OCR_LANGUAGE` (for example `QUESTION_OCR_LANGUAGE=eng+spa ./start.sh --with-ocr`). If Tesseract is already installed but English data is missing, install the English language package manually.

OCR is a fallback when the document has no recognized question numbers, not a complete layout recognizer. Use upright, clear scans with printed question numbers such as `1.` or `1)`. Review extracted text and crops, particularly equations. Mixed text/image documents with some recognized questions may require explicitly OCRing the scanned pages first. Automatic rotation, handwriting recognition, and multi-column question segmentation are not implemented. Tesseract is not installed in the development environment, so actual scan recognition requires installing it; fallback/cache behavior is tested.

## Splitting questions without printed numbers

The importer and JSON exporter now assign their own sequential numbers (1, 2, 3, …) per PDF, in extraction order. Printed numbers do not determine question IDs and may be absent, duplicated, or restart. For MCQs, boundaries are detected from repeated answer-choice groups `(A)`, `(B)`, `(C)` (and subsequent choices) and the question-text block preceding each group. Number markers are only a fallback hint for other formats. Original question images retain any printed labels, while extracted text and web buttons use generated numbers.

After updating, restart the app and import again. The changed parser automatically re-imports existing PDFs on startup. Regenerate `questions.json` for the extension using `python3 pdf_to_json.py /path/to/pdfs -o questions.json`. If generated numbering changes for a document, reclassify its new question entries.

This is a heuristic for single-column multiple-choice papers with recognizable choice labels. Scans still require OCR (`./start.sh --with-ocr`). Unnumbered free-response questions without answer-choice groups, multi-column layouts, and shared passages need a separate layout-specific splitting rule. Missing printed numbers alone no longer prevents MCQ parsing. On the supplied PDF, all 42 boundaries are detected even with printed numbers removed from extracted text.

## Portable database and custom database location

Choose where SQLite is stored:

```sh
./start.sh --database /path/to/library.sqlite3
# Or launch Python directly:
python3 app.py --database /path/to/library.sqlite3
```

The parent directory is created if missing. You may also set `QUESTION_DB_PATH=/path/to/library.sqlite3`; `--database` takes precedence. The default remains `questions.sqlite3` beside the app. Changing the path opens or creates that database; it does not move the old database automatically.

The database stores question text, source filename/order/page numbers, cropped PNG image bytes, complete question JSON objects in `question_archive`, unit assignments, explanations, and raw Gemini replies. The classification queue and classification writes read archived questions directly from SQLite. The original PDFs and external `questions.json` are no longer required to browse existing questions, continue classification, or generate unit PDFs. Older databases gain the archive automatically on startup, seeded from their stored images/text and available JSON export.

To move the library to another machine, update/start the app once to migrate the database, then make a consistent backup:

```sh
python3 db_tools.py backup --database /path/to/library.sqlite3 -o /path/to/portable.sqlite3
```

Copy the backup and application source to the new computer, install dependencies, and open only the saved library:

```sh
./start.sh --database /path/to/portable.sqlite3 --no-import
```

`--no-import` skips local PDFs and external JSON seeding, preventing unrelated local files from being imported into the moved database. The database path is printed at startup. If manually copying a database instead of using the backup command, stop the service first.

Recreate a complete question JSON export, including embedded PNGs and saved assignments:

```sh
python3 db_tools.py export-json --database /path/to/library.sqlite3 -o /path/to/restored-questions.json
```

Backup/export commands refuse to overwrite an existing output file. The portable database reconstructs extracted questions and their visual content; it does not contain the entire original source PDFs, their original vector graphics, or the application runtime itself. Keep originals separately if exact source-document recovery is needed.
