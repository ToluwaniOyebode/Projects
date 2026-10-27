# Pitchside

### Read the game in numbers

A football event-analysis dashboard with passing networks, shot maps, player summaries and CSV import/export.

**Python 3.12+ · SQLite · Vanilla JavaScript · Zero third-party runtime dependencies**

## Run locally

Open this project folder in VS Code and use its integrated terminal:

```sh
python server.py
```

Open **http://127.0.0.1:8105**. No npm/pip installation is needed to run the application. On Windows, use `py server.py` if `python` is not on PATH.

The first run creates `data.sqlite3` and loads fictional sample data. Changes persist across restarts.

## What works

- Explore 420 explicitly synthetic events from a deterministic demo match.
- Filter by team, player and minute range.
- Visualize aggregated pass connections and recorded shot locations.
- Measure pass completion, progressive passes, final-third entries and player contributions.
- Import a validated event CSV and replace the current match atomically.

## Two-minute demo

1. Filter Harbor FC to the first 45 minutes and inspect its pass network.
2. Switch to Shots; hover over a shot to inspect its outcome.
3. Export the selected events or import the documented synthetic example.

## How it works

All coordinates are in [0,100], normalized so both teams attack toward increasing x. A progressive pass is a completed pass with end_x-x >= 15. A final-third entry is a completed pass/carry crossing x=66.666…. Network nodes average pass starts and receptions; edges count completed passes with a named receiver. Team and player together identify a network node, avoiding cross-team name collisions. Metrics describe the filtered selection.

## Tests

```sh
python -m unittest discover -s tests -v
```

6 domain tests cover business invariants and failures. The collection-level `python ../verify.py` runs every project plus live HTTP integration checks. Optional real-browser checks and responsive screenshots are produced by the [portfolio workflow](../../.github/workflows/portfolio-ci.yml).

## API

See [API.md](API.md) for endpoints and an executable request example. All API routes start with `/api`; `/api/health` reports readiness. Reads and successful writes return HTTP 200.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8105` | HTTP listen port |
| `HOST` | `127.0.0.1` | Local-only binding |
| `DB_PATH` | `data.sqlite3` in this folder | SQLite file |

The Python server also accepts `--port`, `--host` and `--db`. Example: `python server.py --port 9000 --db my-demo.sqlite3`.

## Docker (optional)

```sh
docker build -t pitchside .
docker run --rm -p 127.0.0.1:8105:8105 -v pitchside-data:/data pitchside
```

Container recipes are provided; Docker execution is not part of the local validation record. The parent folder includes a Compose file for all six apps.

## Scope and tradeoffs

This is event analytics, not video detection or next-action prediction. Demo events are synthetic and are not a benchmark. Shot circle size uses an illustrative hand-written location score, not trained or validated xG. No model accuracy is claimed. The match import expects normalized, already-labeled events and does not detect replays.

This is a complete local portfolio application, without public multi-user hosting or authentication. Keep it bound to loopback when working with personal data. To reset the demo, stop the server, back up your data, then remove its SQLite file and associated `-wal`/`-shm` files before restarting.

## Files to read first

- `service.py` — persistence, validation and business rules.
- `server.py and webcore.py` — HTTP boundary and startup.
- `static/app.js` — complete frontend interactions.
- `tests/` — concrete examples of correct behavior and rejected inputs.
- `analytics.py` — event validation and descriptive metrics.

[MIT licensed](LICENSE). Built with AI assistance; implementation and tests are available for inspection. No experience, deployment or performance claims are implied.
