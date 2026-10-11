# How VeriFix is evaluated

This page explains the controlled experiment behind the numbers on the VeriFix overview. Every figure below comes from
[`benchmarks/ablation_experiment.json`](../benchmarks/ablation_experiment.json) and
[`benchmarks/ablation_fault_injection.json`](../benchmarks/ablation_fault_injection.json). `scripts/verify_claims.py` recomputes
the figures from those raw run records in CI, and fails the build if this page, the README or the stored summaries disagree with
the data.

## The question

Does giving the agent Entire Graph caller context make it cheaper or safer than the obvious alternatives? Earlier versions of this
README quoted one comparison: 31,093 tokens before and 946 after. That comparison was not a fair test (see
[Retired figure](#retired-figure)). So we re-ran the question as a controlled experiment.

## Design

Three arms share one pipeline: the same single model call per attempt, the same prompt template, at most 3 attempts, and a
rollback whenever a check fails. No faults are injected. Only the context and the check differ:

| Arm | What the agent sees | What must pass before the patch is kept |
|---|---|---|
| `target_only` | The target file | Reproduction test only (caller-blind) |
| `baseline_naive` | Every Python file of the case repository | Reproduction test and caller tests |
| `graph_guarded` | The target file and the Entire Graph caller list | Reproduction test and caller tests |

- **Workload:** the 4 benchmark bugs in `benchmarks/repos/`, run 5 times each in every arm, for 60 runs in total.
- **Order:** arm order is shuffled within each (case, repeat) block, with seed 20261011.
- **Model routing:** routing is identical in every arm. Attempt 1 goes to the fast tier (`nova-2-lite` in every run) and retries
  escalate to `claude-sonnet-4.6`. The model that answered each call is recorded per run.
- **Independent judge:** each run's final diff is applied to a fresh copy of the case repository, and the case's *whole* test
  suite runs there. The agent never sees this judge.
- **Statistics:** each run is paired with the other arms' runs in the same (case, repeat) block, and we report the following.
  - The geometric mean of the per-pair token ratios.
  - A seeded bootstrap 95% interval. The headline interval resamples cases, not runs, because repeats of one case are not
    independent evidence.
  - An exact two-sided sign test.
- **Code:** `src/verifix/ablation.py` holds the judge and statistics, `scripts/run_ablation.py` the runner, and
  `tests/test_ablation.py` the tests.

## Results (60 runs, 11 Oct 2026)

| Arm | Passed the independent judge | Shipped a regression | Mean tokens per fix | Mean attempts | Mean latency |
|---|---|---|---|---|---|
| `target_only` | 20/20 | 0 | 789 | 1.0 | 1.31 s |
| `baseline_naive` | 20/20 | 0 | 2,383 | 1.1 | 1.66 s |
| `graph_guarded` | 20/20 | 0 | 871 | 1.05 | 1.54 s |

**Graph context vs. reading the whole repository:**
- Token ratio: 0.376, i.e. 62% fewer tokens (95% CI by case 58–68%; by pair 56–68%).
- The graph arm was cheaper in 19 of 20 pairs (sign test p = 0.00004) and in all 4 cases.
- Per-case token ratios:

| Case | Token ratio |
|---|---|
| Ledger | 0.303 |
| Rate limiter | 0.394 |
| Webhooks | 0.378 |
| Scheduler | 0.442 |

**Graph context vs. the target file alone:**
- Graph context costs 7% more tokens (ratio 1.073; 95% CI by case 1.008–1.179).
- It was more expensive in 15 of 20 pairs (p = 0.041).
- That cost is the price of the caller list and the caller check.

**Fix rate:** identical. Every arm fixed every bug on these 4 cases, so this experiment shows no fix-rate advantage for any arm.

## Fault injection: what the caller check is for

The natural runs never produced a caller-breaking patch, so they cannot show whether the check matters. A second, separately
labelled study plants one. On attempt 1, every arm receives the ledger case's known bad patch (`caller_trap_patch`). That patch
passes the reproduction test but breaks the settlement caller. 15 runs: 5 per arm.

| Arm | Agent's own verdict | Independent judge | Mean tokens |
|---|---|---|---|
| `target_only` | Accepted the bad patch 5/5 | Failed 5/5 (2 of 4 tests fail) | 896 |
| `baseline_naive` | Rolled back, then fixed 5/5 | Passed 5/5 | 6,944 |
| `graph_guarded` | Rolled back, then fixed 5/5 | Passed 5/5 | 2,193 |

This shows the mechanism works on one scripted fault in one case. It is not an estimate of how often a real model writes
caller-breaking patches.

## Patch assurance: replay of real LLM patches

`scripts/assurance_corpus.py` replays every distinct patch the agent ever produced (23) through the assurance engine. Each patch
is replayed against a pristine copy of its case.

* **21** patches pass the repro and caller tests. **5 of those 21 (23.8%)** are BLOCKED, all in case_01 and all by a declared
  relation (`contract_split_conserves_cents`). Each block comes with a concrete counterexample. For example, splits
  [42798, 38465, 28909, 37328] at 99 bps give legs summing to 1461 against a fee of 1460.
* The other 16 grade **strong 11, moderate 5**. Strong means mutation score ≥ 0.80 and diff coverage ≥ 0.80.
* The median assurance time is 3.08 s per patch. Raw records are in `benchmarks/assurance_corpus.json`.

The same gate fired live in `run_graph_case_01_le_26893`. Attempt 1 was blocked; attempt 2 passed with a strong grade, a
mutation score of 0.8065 and diff coverage of 0.80 (`benchmarks/assurance_live_catch.json`).

Controlled follow-ups:
* [C9](./experiments/C9_RESULTS.md) is a pre-registered study of overfitting detection on test-passing mutants.
* [C10](./experiments/C10_AGENT_SECURITY.md) measures the attack success rate of indirect prompt injection.

## Limitations

- **Small sample:** 4 small benchmark bugs, written for this project. A bootstrap over 4 cases has only 256 possible resamples,
  so treat its interval as rough.
- **Correlated repeats:** temperature is 0.1, so repeats are close to identical. 20 pairs are not 20 independent observations.
- **Small judge suites:** each case's full suite has 4 tests.
- **Estimated cost:** the runs' total cost of $0.19 is estimated from token counts and list prices, not read from an invoice.
- **No real-world evidence yet:** none of these results show performance on real-world repositories.

## Retired figure

The earlier headline, 31,093 → 946 tokens (−96.96%, experiment `exp_24aa3f2776`), is kept in the run ledger as history but is
no longer a claim.

**Correction:** the patch that run accepted (`patch_1c244a1e99`) passes its tests but is wrong. `if residual > 0:` drops negative rounding residuals, so split fees can sum to a cent more than the fee on the total. The assurance gates added later block it (`contract_split_conserves_cents`, recorded in [`benchmarks/assurance_corpus.json`](../benchmarks/assurance_corpus.json)).
 Its baseline was handicapped:

- A known bad patch was forced on its first attempt, and that attempt's model call was still billed.
- It made two model calls per attempt instead of one.
- Its prompt asked for a detailed analysis of every file.
- Its context included unrelated VeriFix docs.

It was also a single run of a single case. The recorded runs themselves are genuine; the comparison between them is not a fair
measure of what graph context does.

## Reproduce

```bash
PYTHONPATH=src python3 scripts/run_ablation.py --repeats 5 --output /tmp/ablation.json
PYTHONPATH=src python3 scripts/run_ablation.py --repeats 5 --cases case_01_ledger_rounding --inject-fault --output /tmp/fault.json
python3 scripts/verify_claims.py
```

A rerun needs model access, which costs about $0.20 at the recorded routing. Token counts will vary slightly between runs.
