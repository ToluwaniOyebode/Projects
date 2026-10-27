# Applyboard API

Base URL: `http://127.0.0.1:8101/api`.

Send JSON objects with `Content-Type: application/json`. Bodies over 1 MiB are rejected. Errors use `{"error":"message"}`: 400 invalid input, 403 cross-origin writes, 404 unknown resource, 409 conflict, 413 oversized request, 415 unsupported content type. Successful requests return 200, including creates. There is no authentication; this API is designed for local use.

| Method | Path after /api | Contract |
| --- | --- | --- |
| GET | `/health` | `ok` and project name. |
| GET | `/applications` | Optional q and stage filters; returns matching applications. |
| POST | `/applications` | company, role, stage required; applied_on, followup_on, url, notes optional. |
| PATCH | `/applications/{id}` | version required, plus fields to change; returns the incremented version. |
| DELETE | `/applications/{id}` | Deletes the application and records the deletion in activity. |
| GET | `/stats` | Stage counts, active opportunities and due follow-ups. |
| GET | `/activity` | Latest 20 changes. |
| GET | `/export.csv` | CSV export; accepts q and stage. |

## Executable Python example

Works on Windows, macOS and Linux with Python 3.12+. Start the app first, then save/run this snippet:

```python
import json
import urllib.request

payload = {'company': 'Example Co', 'role': 'Backend Engineer', 'stage': 'applied', 'applied_on': '2026-10-27', 'followup_on': '2026-10-30'}
request = urllib.request.Request(
    "http://127.0.0.1:8101/api/applications",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.load(response))
```

This writes demonstration data to your local database. Repeat-key behavior is documented in the README where applicable.
