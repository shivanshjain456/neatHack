# Receipts

One file per recorded run, plus `index.json`. A receipt is the run's proof-of-work:

- `receipt_id` — `VF-<utc stamp>-<case>`, stable per run.
- `run_id / case_id / mode` — identity of the recorded run in
  `../verified_runs_ledger.json`.
- `status` — the proof outcome, verbatim from the ledger (e.g. `VERIFIED_COMPLETE`).
- `attempts / rollbacks` — how many tries, how many guardrail rollbacks.
- `total_tokens / latency_ms` — measured usage.
- `priced_usd / cap_usd / cap_used_pct` — what the run cost, the configured cap, the
  share of it used.
- `sha256` — sha256 of the canonical JSON of every other field in this file.

`index.json` lists every receipt with its `sha256` and carries `ledger_sha256`, the
hash of `../verified_runs_ledger.json` at receipt time. To verify: recompute the
canonical-JSON hash of any receipt's fields and compare; recompute the ledger hash
and compare. Receipts are append-only evidence — historical receipts are never
edited (see `AGENTS.md` invariant 3). Measured cap statistics over all priced runs
live in `../cost_caps.json`.
