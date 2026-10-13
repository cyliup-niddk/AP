# Physics Question → Gemini Unit (Chrome / Chromium / Edge)

A Manifest V3 extension with a toolbar button that opens a classifier manager. It injects question text into a signed-in Gemini chat, reads the resulting unit classification, and saves the original question JSON plus unit number in the local SQLite database. No Gemini API key is used.

## Setup

1. Start the updated local app: `cd question-browser` then `python3 app.py`. If it is already running, press Ctrl+C and restart to load the new endpoints.
2. Ensure `question-browser/questions.json` exists. To regenerate it, run `python3 pdf_to_json.py . -o questions.json` from `question-browser`.
3. Open `chrome://extensions` (or `edge://extensions`), enable **Developer mode**, click **Load unpacked**, and select this `gemini-extension` directory (the directory containing `manifest.json`).
4. Open **https://gemini.google.com**, sign in, start a fresh chat, and leave it open. Refresh that tab if it was open before the extension was installed. The initial DOM selectors support the English Gemini interface.
5. Click the extension toolbar icon to open the manager. Set the local library URL if your port differs, then click **Load questions**.

## Use

- Choose a question and click **Classify selected question**. Or click **Use question open in library** to select the question currently displayed in the local question-browser tab, then classify it.
- Click **Automatically classify unassigned** to process all questions without saved unit numbers. The queue sends one question at a time and waits for the reply before continuing.
- Before each query, a random delay is sampled uniformly from **0–3 seconds**. Response time is additional; the extension never submits overlapping queries.
- Click **Stop after current question** to save an in-flight response and stop the queue. During a delay this prevents the next send. Closing or reloading the manager stops its loop; reopening and loading questions skips already saved results.
- If a database write fails, the captured response stays in extension storage. **Retry saving pending result** retries the write without asking Gemini again. New runs attempt this pending save first.
- **Download classified JSON** exports saved JSON objects with `unit_number`, `unit_name`, and `classification_reason`.

Keep the manager and Gemini tabs open and avoid manually chatting in the same Gemini conversation during a batch. Browser background timer throttling can make delays longer than the sampled 0–3 seconds. The extension does not bypass Gemini login, quotas, or rate limits; errors stop the queue. It does not automatically retry an unanswered query. A request times out after 120 seconds.

## Prompt and database

The prompt lists the eight AP Physics 1 units from [College Board's course framework](https://apcentral.collegeboard.org/courses/ap-physics-1), asks for every directly relevant unit, and requests JSON containing a unique request ID, question ID, array of integer unit numbers, and an explanation of each selected unit. Both IDs must match before a result can be saved, avoiding replies from an earlier question. Unit numbers outside 1–8 are rejected. These are AI classifications and can be reviewed or replaced by classifying the question again.

The request sends **question text only**, including extracted choice/diagram labels. It does not upload the PNG images, so visual-only questions may be classified less accurately.

SQLite table `question_classifications` in `question-browser/questions.sqlite3` contains:

- `question_id`: exported content hash (primary key, one current classification per unique question).
- `unit_number`, `reason`, `raw_response`, `classified_at`.
- `question_json`: the full original JSON object, including images and merged sources, augmented with the classification.

The original `questions.json` is not modified. The unit belongs to its deduplicated question, including all merged source occurrences. Later PDF re-imports do not delete classifications.

Local endpoints (provided by the updated Python app):

- `GET /api/classifier/questions`: text-only queue with saved unit numbers.
- `POST /api/classifier/result`: validated classification write.
- `GET /api/classifier/export`: classified question JSON objects.

Extension permissions are limited to Gemini and loopback hosts, storage for settings/pending responses, and scripting to read the current question in the local library. No broad access to other websites is requested. Implementation follows [Chrome content-script guidance](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts).

## Verification and limits

Backend tests cover unit validation, unknown question rejection, upsert behavior, JSON preservation, and resume queue state. Live Gemini injection must be checked in your signed-in browser; it cannot be verified in this workspace. If Gemini changes its DOM or your interface language differs, update editor, Send, response, and generation selectors in `gemini.js`. When a selector is unavailable, the queue stops rather than guessing or saving another response.

## Load questions says Not found

The server is an older process without the classifier endpoint. In the terminal running `app.py`, press Ctrl+C and run `python3 app.py` again from `question-browser`. Confirm `http://127.0.0.1:8001/api/classifier/questions` returns a JSON array. Reload this extension in `chrome://extensions`, close the old manager tab, and reopen it using the toolbar icon. Click Load questions. The updated manager displays a specific message for an outdated server.

## Classify button does not send a prompt

Reload the extension at `chrome://extensions`, then close its old manager tab and reopen it from the toolbar icon. Refresh the signed-in Gemini tab to load the latest helper. The updated manager automatically installs the helper if an existing tab has none, activates the Gemini tab, and reports connection, injection, and submission progress. Check the manager status if no prompt is submitted. Existing unsent Gemini drafts are preserved: clear or send them before classifying.

## Unit parser checks

The parser is `response-parser.js`. Open `../tests/extension-parser.html` in Chrome to run 30 checks covering units 1–8, fenced JSON, surrounding prose, braces in explanations, nested metadata, and rejection of invalid units or mismatched IDs. It requires the structured JSON requested by the prompt; plain text such as “Unit 8” alone is not saved.

## Multiple-unit assignments (version 1.1.0)

The prompt requests `unit_numbers`, a nonempty array such as `[2, 3, 8]`, and a reason explaining the concepts from each selected unit. It includes both central and supporting concepts required to understand or solve the question, and excludes incidental mentions. Returned numbers must be integers 1–8; duplicates are removed and numbers sorted.

The database and exported JSON now contain `unit_numbers` and `unit_names`. Existing assignments are migrated automatically to single-item lists without changing their original responses or timestamps. The legacy `unit_number`/`unit_name` fields remain as compatibility aliases for the first item; they do not indicate a primary unit.

Restart the Python app, reload the extension, close/reopen the manager, and refresh Gemini after updating. **Automatically classify unassigned** continues to skip saved questions. Use **Reclassify all with multiple units** to update existing assignments with the new prompt, or reclassify individual selected questions. No questions are submitted merely by installing this update. The web application displays all assigned units when the question is selected again.
