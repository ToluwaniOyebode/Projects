# QueueCraft API

Base URL: `http://127.0.0.1:8106/api`.

Send JSON objects with `Content-Type: application/json`. Bodies over 1 MiB are rejected. Errors use `{"error":"message"}`: 400 invalid input, 403 cross-origin writes, 404 unknown resource, 409 conflict, 413 oversized request, 415 unsupported content type. Successful requests return 200, including creates. There is no authentication; this API is designed for local use.

| Method | Path after /api | Contract |
| --- | --- | --- |
| GET | `/health` | `ok` and project name. |
| GET | `/jobs` | Optional status=queued or running or succeeded or dead; latest 100. |
| POST | `/jobs` | kind, payload; optional max_attempts 1..8, priority 0..9 and request_key. |
| GET | `/jobs/{id}` | Job payload, result, error and event history; lease token is not exposed. |
| POST | `/jobs/{id}/retry` | Empty object; only dead-letter jobs may be retried. |
| GET | `/stats` | State counts, current attempt count and worker mode. |

## Executable Python example

Works on Windows, macOS and Linux with Python 3.12+. Start the app first, then save/run this snippet:

```python
import json
import urllib.request

payload = {'kind': 'flaky', 'payload': {'fail_until': 2}, 'max_attempts': 3, 'priority': 5, 'request_key': 'my-retry-demo'}
request = urllib.request.Request(
    "http://127.0.0.1:8106/api/jobs",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.load(response))
```

This writes demonstration data to your local database. Repeat-key behavior is documented in the README where applicable.
