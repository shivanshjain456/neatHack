# External-validity probe: a held-out case in a new failure class (11 Oct 2026)

**Status:** exploratory, additive. It does **not** alter the headline controlled experiment in
[`../EVALUATION.md`](../EVALUATION.md) (4 cases × 5 repeats × 3 arms) and is not used as a headline
claim. The case spec is injected at runtime by
[`scripts/run_external_validity_probe.py`](../../scripts/run_external_validity_probe.py); the
committed `BENCHMARK_CATALOG` and the `/api/workspace` benchmark list remain at four cases, so no
deterministic test or published figure is affected.

## Why

The strongest skeptical critique of the headline experiment is that its four benchmark
repositories are small and self-authored. This probe asks whether the same three-arm pipeline
generalises to a **new failure class** the agent has not seen: at-least-once delivery /
dedup-key correctness (`case_05_event_idempotency`). The crux is subtle: retries must be deduped by
`event_id`, while two *distinct* event ids carrying an identical payload are separate events and
must both count — a payload-based dedup is wrong.

## Method

Identical to the headline experiment: three arms share one model call, prompt template, attempt
limit and rollback logic; they differ only in context (`target_only`, `baseline_naive` = whole
repo, `graph_guarded` = target + caller list). An independent judge applies each final diff to a
fresh copy and runs the case's whole pytest suite. 3 repeats (no fault) + 2 repeats with a planted
subtly-wrong patch (dedup by payload).

## Results (recorded in `benchmarks/external_validity_probe.json`)

| Arm | Judge passed | Mean total tokens |
| :--- | :---: | :---: |
| target_only (caller-blind) | 3/3 | 540 |
| baseline_naive (whole repo) | 3/3 | 1,972 |
| graph_guarded | 3/3 | 679 |

- The agent solved the new failure class on the first attempt in **all 9 no-fault runs**.
- `graph_guarded` used a geometric-mean **0.34×** the tokens of whole-repo context (679 vs 1,972),
  with an identical judge pass rate — the headline token advantage replicates on a held-out class.
  It cost ~1.26× target-only, again matching the headline trade-off (the caller check is the price).
- **Fault injection:** planting the payload-dedup patch (passes the reproduction test, drops a
  distinct same-payload event) did not survive to the judge in any arm: each arm rolled back once
  and shipped a judge-passing fix in 2 attempts. On this case the dynamic differential/contract
  gates — in addition to caller tests in the guarded arms — contributed to catching the wrong patch.
  We therefore do **not** claim a caller-blind-ships-it contrast for this case; the honest reading
  is that the wrong patch was caught and recovered everywhere.

## Honest limits

One new case, small repository, 3+2 repeats: this is a probe of generalisation, not a replacement
for the headline experiment. On a repository this small, whole-repo context is cheap in absolute
terms; the token advantage of graph context grows with repository size, which is exactly the
regime the headline experiment's whole-repo arm (2,383 tokens) begins to explore.
