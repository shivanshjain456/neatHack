# Known limits

What VeriFix does not do, found while testing the edge cases. Dated 12 Oct 2026;
every item below is also stated where the feature appears in the dashboard.

- Run storage and rate limits are local to a Lambda execution environment.
  Warm-instance run records can disappear at recycle; the versioned ledger in
  `benchmarks/verified_runs_ledger.json` is the durable evidence, not a
  production history.
- Public benchmark execution is serialized per server instance and
  rate-limited. These are not account-wide spending controls; the per-run
  model budget ($0.25) is the hard stop a run is refused past.
- Arbitrary repository paths and uploaded Python execution are operator-only,
  because a temporary folder is not a security sandbox. The public surface
  offers the four catalogued benchmark repositories only.
- Entire Graph context is a release-time snapshot; token totals in imported
  transcripts are not independently audited usage.
- The neatlogs analytics aggregates are dated captures; global trace averages
  and a single benchmark measure different workloads and are never compared as
  equivalent samples. When remote trace readback stalls, VeriFix exposes its
  locally recorded steps; that does not finalize a remote trace.
- A clean caller graph can yield `REPRO_PASSED_CALLERS_UNCHECKED` rather than
  full caller verification; the receipt states exactly which checks ran.
- Fault injection (`--inject-caller-trap`) deliberately breaks a caller
  contract in attempt 1. It is a controlled test, never presented as a
  production failure.
- The financial model is projections, recomputed by
  `scripts/compute_plan_values.py` with a drift test; the dashboard labels
  them projections, not realized revenue.
- The submission video's numbers are true at recording time; live figures are
  shown separately with dates (Evidence library, "Current usage, dated").
- SQLite WAL checkpoints resume on the same instance only; a recycled
  instance cannot resume another's interrupted run.
