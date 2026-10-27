# Project demonstrations and technical discussions

Choose two or three projects that match a role, run them and learn the code before including them in an application. Describe your own review and modifications accurately. These projects were built with AI assistance; they do not establish professional work experience or independent authorship.

| Role focus | Start with | Demonstrate | Be ready to explain |
| --- | --- | --- | --- |
| Full-stack / software engineering | Applyboard, Stockroom | Add an application, cause a version conflict, reserve and ship inventory | Request validation, persistence, UI state and transaction boundaries |
| Backend / platform | Stockroom, QueueCraft | Competing reservations; a crashed lease and stale completion | Idempotency vs transactions, at-least-once delivery, retries and fencing |
| Data / analytics | LedgerLens, Pitchside | Bad CSV rollback, exact sums, team/time event filters | Data quality, deduplication assumptions, clear metric definitions and synthetic-data limits |
| Search / applied AI infrastructure | SignalDesk, QueueCraft | Term score breakdown; atomic index update | Inverted indexes, BM25 length normalization, lexical vs semantic search, background indexing |

## Concrete code paths

1. **Applyboard:** `App.update` matches `id + version` and records activity in the same transaction. Explain what would be lost without the version check.
2. **LedgerLens:** `parse_transaction` converts decimals to integer kobo and creates a normalized fingerprint. Explain why identical legitimate purchases can collide under this deduplication policy.
3. **Stockroom:** `Store.reserve` checks availability under `BEGIN IMMEDIATE`. Explain why a read followed by an unrelated insert can oversell.
4. **SignalDesk:** `search` computes BM25 contributions per passage. Explain why the same numeric score cannot be treated as a probability or compared as confidence across queries.
5. **Pitchside:** `analyze` builds pass connections from successful events. Explain that broadcast video, event labels and predictions are three different inputs/outputs.
6. **QueueCraft:** `claim` assigns a lease token; `finish` rejects stale tokens. Explain why this prevents stale writes but cannot undo an external action already performed by a worker.

## Evidence you can use

Use the actual domain tests, HTTP checks and browser reports. Do not invent percentages, traffic volumes, latency improvements, cloud deployments or user counts. The football score is a custom illustrative heuristic with no trained-model accuracy. Docker packaging is provided separately from measured local execution.

## A useful interview exercise

Pick one small enhancement and implement it yourself, then add one meaningful test. Examples: allow an optional external transaction ID for CSV deduplication, add a historical interview transition metric, or add a lease heartbeat for longer queue tasks. Explain the design and review the diff rather than memorizing a README.
