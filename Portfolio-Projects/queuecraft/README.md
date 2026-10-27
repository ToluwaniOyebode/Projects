# QueueCraft

### Make background work visible

A persistent background job queue with retries, crash recovery, fencing tokens and an operations dashboard.

**Python 3.12+ · SQLite · Vanilla JavaScript · Zero third-party runtime dependencies**

## Run locally

Open this project folder in VS Code and use its integrated terminal:

```sh
python server.py
```

Open **http://127.0.0.1:8106**. No npm/pip installation is needed to run the application. On Windows, use `py server.py` if `python` is not on PATH.

The first run creates `data.sqlite3` and loads fictional sample data. Changes persist across restarts. The server starts an embedded worker automatically.

## What works

- Run safe built-in sum, word-count and simulated-transient-failure jobs.
- Prioritize ready jobs and store their payloads, outcomes and complete event history.
- Retry failures with exponential backoff; inspect and retry dead-letter jobs.
- Recover expired worker leases and reject stale worker results.
- Run the embedded worker or additional separate worker processes on one SQLite file.

## Two-minute demo

1. Enqueue a sum job and inspect its persisted result.
2. Choose Demonstrate retries with fail_until=2 and max attempts=3; inspect the history after completion.
3. Use max attempts=1 to send a failing task to dead-letter. Inspect it, then retry manually.
4. Run a separate worker with the same --db path to demonstrate competing claims.

## How it works

A short BEGIN IMMEDIATE transaction claims one eligible job, increments attempts and assigns a UUID token plus a 15-second lease. Higher priorities run first, then creation time and ID. Expired jobs return to queued or enter dead-letter if attempts are exhausted. A completion checks status, token and lease time in the same transaction. Failures wait min(60, 2**(attempts-1)) seconds. Manual retry resets attempts while retaining the full history. Built-in tasks are bounded and fast; no arbitrary code is executed.

## Tests

```sh
python -m unittest discover -s tests -v
```

10 domain tests cover business invariants and failures. The collection-level `python ../verify.py` runs every project plus live HTTP integration checks. Optional real-browser checks and responsive screenshots are produced by the [portfolio workflow](../../.github/workflows/portfolio-ci.yml).

## API

See [API.md](API.md) for endpoints and an executable request example. All API routes start with `/api`; `/api/health` reports readiness. Reads and successful writes return HTTP 200.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8106` | HTTP listen port |
| `HOST` | `127.0.0.1` | Local-only binding |
| `DB_PATH` | `data.sqlite3` in this folder | SQLite file |

The Python server also accepts `--port`, `--host` and `--db`. Example: `python server.py --port 9000 --db my-demo.sqlite3`.

For an additional worker, use `python worker.py --db data.sqlite3` from this folder. Use the same absolute database path if starting from another directory. The separate worker shares claims safely with the embedded worker.

## Docker (optional)

```sh
docker build -t queuecraft .
docker run --rm -p 127.0.0.1:8106:8106 -v queuecraft-data:/data queuecraft
```

Container recipes are provided; Docker execution is not part of the local validation record. The parent folder includes a Compose file for all six apps.

## Scope and tradeoffs

At-least-once execution, not exactly-once side effects. External effects need their own idempotency keys. The queue has no broker cluster, distributed filesystem support, heartbeat extension or arbitrary task plugin loader. Built-in tasks fit within the 15-second lease; longer handlers would require a heartbeat API. Local SQLite writers serialize.

This is a complete local portfolio application, without public multi-user hosting or authentication. Keep it bound to loopback when working with personal data. To reset the demo, stop the server, back up your data, then remove its SQLite file and associated `-wal`/`-shm` files before restarting.

## Files to read first

- `service.py` — persistence, validation and business rules.
- `server.py and webcore.py` — HTTP boundary and startup.
- `static/app.js` — complete frontend interactions.
- `tests/` — concrete examples of correct behavior and rejected inputs.
- `worker.py` — bounded task execution and polling.

[MIT licensed](LICENSE). Built with AI assistance; implementation and tests are available for inspection. No experience, deployment or performance claims are implied.
