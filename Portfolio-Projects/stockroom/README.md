# Stockroom

### Stock you can count on

An inventory operations dashboard and REST API with atomic reservations, safe retries, fulfillment and stock movement history.

**Node.js 24.x · SQLite · Vanilla JavaScript · Zero third-party runtime dependencies**

## Run locally

Open this project folder in VS Code and use its integrated terminal:

```sh
npm start
```

Open **http://127.0.0.1:8103**. No npm/pip installation is needed to run the application. Node 24 is required for its built-in SQLite module.

The first run creates `data.sqlite3` and loads fictional sample data. Changes persist across restarts.

## What works

- Maintain products, opening stock, prices and low-stock thresholds.
- Reserve units without overselling, even across competing processes.
- Use request keys to safely retry reservation requests.
- Ship or release reservations; record stock adjustments with a reason.
- Inspect current availability, on-hand stock value and an append-only movement log.

## Two-minute demo

1. Reserve two mechanical keyboards and watch available stock decrease.
2. Ship the reservation: on-hand stock decreases and held units return to zero.
3. Reserve another item, release it, and inspect the movement log.
4. Try a negative adjustment that would consume held stock; the API rejects it.

## How it works

Available stock equals physical on-hand stock minus active holds. BEGIN IMMEDIATE serializes competing writers. Reservation request keys are unique: a replay with identical SKU and quantity returns the original reservation; a different payload returns 409. Shipping and releasing are idempotent terminal transitions. Stock adjustments cannot reduce on-hand stock below active holds. SQL values are bound parameters.

## Tests

```sh
npm test
```

7 domain tests cover business invariants and failures. The collection-level `python ../verify.py` runs every project plus live HTTP integration checks. Optional real-browser checks and responsive screenshots are produced by the [portfolio workflow](../../.github/workflows/portfolio-ci.yml).

## API

See [API.md](API.md) for endpoints and an executable request example. All API routes start with `/api`; `/api/health` reports readiness. Reads and successful writes return HTTP 200.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8103` | HTTP listen port |
| `HOST` | `127.0.0.1` | Local-only binding |
| `DB_PATH` | `data.sqlite3` in this folder | SQLite file |

## Docker (optional)

```sh
docker build -t stockroom .
docker run --rm -p 127.0.0.1:8103:8103 -v stockroom-data:/data stockroom
```

Container recipes are provided; Docker execution is not part of the local validation record. The parent folder includes a Compose file for all six apps.

## Scope and tradeoffs

A single-location local inventory service. Holds do not expire automatically. Request-key protection covers reservations; adjustments must not be blindly retried after an ambiguous network failure. No payment gateway, warehouse barcode scanner, authentication or distributed database. Node SQLite uses synchronous calls, appropriate here for short local transactions.

This is a complete local portfolio application, without public multi-user hosting or authentication. Keep it bound to loopback when working with personal data. To reset the demo, stop the server, back up your data, then remove its SQLite file and associated `-wal`/`-shm` files before restarting.

## Files to read first

- `store.js` — persistence, validation and business rules.
- `server.js` — HTTP boundary and startup.
- `static/app.js` — complete frontend interactions.
- `tests/` — concrete examples of correct behavior and rejected inputs.


[MIT licensed](LICENSE). Built with AI assistance; implementation and tests are available for inspection. No experience, deployment or performance claims are implied.
