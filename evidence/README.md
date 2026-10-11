# Evidence index

Curated, dated evidence for the three required tools, one file each. Every claim is
numbered and links to a source a judge can open or a command a judge can run. Nothing
here is a live feed: where a figure is a capture, its date is stated.

| File | Covers |
| :--- | :--- |
| [neatlogs.md](./neatlogs.md) | Tracing every run, the SDK bug found by tracing, dated analytics captures |
| [entire.md](./entire.md) | Checkpoints in the public history, Entire Graph as the runtime caller source |
| [cfo.md](./cfo.md) | The measured-token business model, cost caps, drift-tested recomputation |

Cross-cutting evidence lives elsewhere by design:

- `benchmarks/` — the versioned raw records: run ledger, receipts, controlled
  experiment, assurance corpus, security experiments, cost caps.
- `docs/EVALUATION.md` — method and data; `docs/comparison.md` — the same numbers
  against the obvious alternatives.
- `scripts/verify_claims.py` — recomputes every public number from the raw records;
  CI fails on drift.
- The dashboard `#verify` view re-checks LIVE items (GitHub, neatlogs, this
  deployment) each time it loads, and shows `source unavailable` rather than a fake
  pass when a source cannot be reached.
