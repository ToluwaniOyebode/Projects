# SignalDesk API

Base URL: `http://127.0.0.1:8104/api`.

Send JSON objects with `Content-Type: application/json`. Bodies over 1 MiB are rejected. Errors use `{"error":"message"}`: 400 invalid input, 403 cross-origin writes, 404 unknown resource, 409 conflict, 413 oversized request, 415 unsupported content type. Successful requests return 200, including creates. There is no authentication; this API is designed for local use.

| Method | Path after /api   | Contract                                                                     |
| ------ | ----------------- | ---------------------------------------------------------------------------- |
| GET    | `/health`         | `ok` and project name.                                                       |
| GET    | `/documents`      | Document metadata and chunk counts.                                          |
| POST   | `/documents`      | title and content strings; content limit 150,000 characters.                 |
| GET    | `/documents/{id}` | Full source text and version.                                                |
| PATCH  | `/documents/{id}` | title, content and expected version.                                         |
| DELETE | `/documents/{id}` | Deletes the source, chunks and postings.                                     |
| GET    | `/search`         | q, mode=any or all, limit=1..50. Up to 16 distinct non-stopword query terms. |
| GET    | `/stats`          | Document, passage, unique term and token counts.                             |

## Executable Python example

Works on Windows, macOS and Linux with Python 3.12+. Start the app first, then save/run this snippet:

```python
import json
import urllib.request

payload = {'title': 'My engineering notes', 'content': '# Transactions\nUse idempotency keys when retrying a reservation.'}
request = urllib.request.Request(
    "http://127.0.0.1:8104/api/documents",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.load(response))
```

This writes demonstration data to your local database. Repeat-key behavior is documented in the README where applicable.

Search result fields include document_id, title, section, start_line, end_line, snippet, score and explanation. Score is the sum of rounded term contributions. Chunk IDs are internal and can change after an edit; use document_id and source lines for navigation. Matching uses title, section and content terms; a title match can return a passage whose body snippet does not contain the term.
