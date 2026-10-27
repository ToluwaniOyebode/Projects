# Stockroom API

Base URL: `http://127.0.0.1:8103/api`.

Send JSON objects with `Content-Type: application/json`. Bodies over 1 MiB are rejected. Errors use `{"error":"message"}`: 400 invalid input, 403 cross-origin writes, 404 unknown resource, 409 conflict, 413 oversized request, 415 unsupported content type. Successful requests return 200, including creates. There is no authentication; this API is designed for local use.

| Method | Path after /api              | Contract                                                        |
| ------ | ---------------------------- | --------------------------------------------------------------- |
| GET    | `/health`                    | `ok` and project name.                                          |
| GET    | `/products`                  | Returns on_hand, reserved and available per SKU.                |
| POST   | `/products`                  | sku, name, on_hand, reorder_point, unit_price_cents (integers). |
| POST   | `/products/{sku}/adjust`     | Non-zero integer delta and a note; not an idempotent endpoint.  |
| GET    | `/reservations`              | Latest 100 reservations with product names.                     |
| POST   | `/reservations`              | sku, positive integer quantity, request_key.                    |
| POST   | `/reservations/{id}/ship`    | Empty object; safely repeats a shipped transition.              |
| POST   | `/reservations/{id}/release` | Empty object; safely repeats a released transition.             |
| GET    | `/movements`                 | Latest 50 movements.                                            |
| GET    | `/stats`                     | Availability, held units, low stock and on-hand value.          |

## Executable Python example

Works on Windows, macOS and Linux with Python 3.12+. Start the app first, then save/run this snippet:

```python
import json
import urllib.request

payload = {'sku': 'KEY-01', 'quantity': 2, 'request_key': 'demo-order-001'}
request = urllib.request.Request(
    "http://127.0.0.1:8103/api/reservations",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.load(response))
```

This writes demonstration data to your local database. Repeat-key behavior is documented in the README where applicable.
