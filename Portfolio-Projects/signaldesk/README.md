# SignalDesk

### Find the useful part

A local Markdown and text search engine with BM25 ranking, source line citations and term-by-term score explanations.

**Python 3.12+ · SQLite · Vanilla JavaScript · Zero third-party runtime dependencies**

## Run locally

Open this project folder in VS Code and use its integrated terminal:

```sh
python server.py
```

Open **http://127.0.0.1:8104**. No npm/pip installation is needed to run the application. On Windows, use `py server.py` if `python` is not on PATH.

The first run creates `data.sqlite3` and loads fictional sample data. Changes persist across restarts.

## What works

- Create, edit, delete and upload Markdown or text documents.
- Split documents into heading-aware passages with original line ranges.
- Search with any-word or all-word matching and inspect ranked excerpts.
- Explain term frequency, inverse document frequency and each score contribution.
- Rebuild an edited document index atomically and remove stale postings.

## Two-minute demo

1. Search for worker lease and open a source document.
2. Expand Why this result? to inspect individual term contributions.
3. Add a short Markdown document with a unique word and find it.
4. Edit the word; the old term disappears from search immediately.

## How it works

SQLite stores documents, chunks and a (chunk, term, frequency) postings index. The tokenizer case-folds Unicode words and removes a small English stopword set. BM25 uses k1=1.5 and b=0.75; N and average length are measured over chunks. Titles and section headings join each chunk before tokenization. Search sums per-term contributions, then orders by score and chunk ID. Updates use version checks and replace the affected chunks within one transaction.

## Tests

```sh
python -m unittest discover -s tests -v
```

8 domain tests cover business invariants and failures. The collection-level `python ../verify.py` runs every project plus live HTTP integration checks. Optional real-browser checks and responsive screenshots are produced by the [portfolio workflow](../../.github/workflows/portfolio-ci.yml).

## API

See [API.md](API.md) for endpoints and an executable request example. All API routes start with `/api`; `/api/health` reports readiness. Reads and successful writes return HTTP 200.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8104` | HTTP listen port |
| `HOST` | `127.0.0.1` | Local-only binding |
| `DB_PATH` | `data.sqlite3` in this folder | SQLite file |

The Python server also accepts `--port`, `--host` and `--db`. Example: `python server.py --port 9000 --db my-demo.sqlite3`.

## Docker (optional)

```sh
docker build -t signaldesk .
docker run --rm -p 127.0.0.1:8104:8104 -v signaldesk-data:/data signaldesk
```

Container recipes are provided; Docker execution is not part of the local validation record. The parent folder includes a Compose file for all six apps.

## Scope and tradeoffs

Lexical retrieval, not a chatbot or semantic search model. There is no stemming, OCR, PDF extraction or relevance benchmark. BM25 scores are ranking values, not confidence percentages. Headings without body text are not separate passages. Source excerpts may normalize whitespace; the source reader preserves the full document.

This is a complete local portfolio application, without public multi-user hosting or authentication. Keep it bound to loopback when working with personal data. To reset the demo, stop the server, back up your data, then remove its SQLite file and associated `-wal`/`-shm` files before restarting.

## Files to read first

- `service.py` — persistence, validation and business rules.
- `server.py and webcore.py` — HTTP boundary and startup.
- `static/app.js` — complete frontend interactions.
- `tests/` — concrete examples of correct behavior and rejected inputs.
- `search.py` — chunking, inverted index and BM25 scoring.

[MIT licensed](LICENSE). Built with AI assistance; implementation and tests are available for inspection. No experience, deployment or performance claims are implied.
