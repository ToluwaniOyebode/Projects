# Validation record

Initial validation: 27 October 2026.

| Check | Measured result |
| --- | --- |
| Applyboard domain tests | 6 passed |
| LedgerLens domain tests | 8 passed |
| Stockroom domain tests | 7 passed, including competing worker threads with separate database connections |
| SignalDesk domain tests | 8 passed |
| Pitchside domain tests | 6 passed |
| QueueCraft domain tests | 10 passed, including concurrent claims and stale lease rejection |
| JavaScript syntax | All frontend modules and Stockroom server/store passed node --check |
| HTTP integration | All six apps started with isolated databases and passed health, static asset, JSON, cross-origin, traversal and project-specific behavior checks |
| Real browser acceptance | Configured in GitHub Actions; see the workflow run and uploaded report for its result |
| Docker execution | Not run in the initial workspace |

Local runtime: Python 3.12.14, Node.js 24.22.1. No third-party packages were needed for domain or HTTP validation.

The browser binary was unavailable in the authoring workspace and its download failed; the remote preview browser could not reach the local servers. Browser checks are not represented as locally executed. GitHub Actions installs Chromium and records the actual browser result independently.

No application-load benchmark, trained ML model, public deployment, security audit or real-user study was performed. Tests cover the documented local scope, not all possible failure modes.
