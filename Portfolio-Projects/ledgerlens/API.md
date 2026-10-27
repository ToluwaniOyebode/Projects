# LedgerLens API

Base URL: `http://127.0.0.1:8102/api`.

Send JSON objects with `Content-Type: application/json`. Bodies over 1 MiB are rejected. Errors use `{"error":"message"}`: 400 invalid input, 403 cross-origin writes, 404 unknown resource, 409 conflict, 413 oversized request, 415 unsupported content type. Successful requests return 200, including creates. There is no authentication; this API is designed for local use.

| Method | Path after /api      | Contract                                                        |
| ------ | -------------------- | --------------------------------------------------------------- |
| GET    | `/health`            | `ok` and project name.                                          |
| GET    | `/transactions`      | month=YYYY-MM; defaults to the current month.                   |
| POST   | `/transactions`      | date, description and amount decimal string; optional category. |
| PATCH  | `/transactions/{id}` | category required; updates categorization.                      |
| DELETE | `/transactions/{id}` | Removes a transaction.                                          |
| POST   | `/import`            | csv string; returns inserted, duplicates and rows.              |
| POST   | `/budgets`           | month, category and positive amount decimal string.             |
| GET    | `/summary`           | month=YYYY-MM; net/gross/refund totals, budgets and trend.      |
| GET    | `/export.csv`        | month=YYYY-MM; exports the selected month.                      |

## Executable Python example

Works on Windows, macOS and Linux with Python 3.12+. Start the app first, then save/run this snippet:

```python
import json
import urllib.request

payload = {'date': '2026-10-27', 'description': 'Bus ride', 'amount': '500.00', 'category': 'transport'}
request = urllib.request.Request(
    "http://127.0.0.1:8102/api/transactions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.load(response))
```

This writes demonstration data to your local database. Repeat-key behavior is documented in the README where applicable.

Categories: `food`, `groceries`, `transport`, `bills`, `shopping`, `health`, `learning`, `other`. Amounts must be decimal strings, for example `"500.00"`; positive means expense, negative means refund. Refunds are signed numeric CSV values; text descriptions beginning with spreadsheet formula characters are prefixed with an apostrophe on export.
