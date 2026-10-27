# Validation record

Initial validation: 27 October 2026.

| Check                   | Measured result                                                                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Applyboard domain tests | 6 passed                                                                                                                                         |
| LedgerLens domain tests | 8 passed                                                                                                                                         |
| Stockroom domain tests  | 7 passed, including competing worker threads with separate database connections                                                                  |
| SignalDesk domain tests | 8 passed                                                                                                                                         |
| Pitchside domain tests  | 6 passed                                                                                                                                         |
| QueueCraft domain tests | 10 passed, including concurrent claims and stale lease rejection                                                                                 |
| JavaScript syntax       | All frontend modules and Stockroom server/store passed node --check                                                                              |
| HTTP integration        | All six apps started with isolated databases and passed health, static asset, JSON, cross-origin, traversal and project-specific behavior checks |
| Real browser acceptance | All six passed: desktop 1440×1000, mobile 390×844, no page or console errors; see docs/browser-report.json                                       |
| Docker execution        | Not run in the initial workspace                                                                                                                 |

Local runtime: Python 3.12.14, Node.js 24.22.1. No third-party packages were needed for domain or HTTP validation.

Real-browser checks exercised application creation and stage changes, expense entry and budgets, stock reservation and fulfillment, document indexing and search explanations, football team/time filters and shot views, and failed queue inspection/retry. The mobile check verifies that page content does not overflow the viewport; intended table and board scrolling stays inside its container.

[Browser report](docs/browser-report.json) · [Screenshot gallery](docs/portfolio-overview.webp)

No application-load benchmark, trained ML model, public deployment, security audit or real-user study was performed. Tests cover the documented local scope, not all possible failure modes.
