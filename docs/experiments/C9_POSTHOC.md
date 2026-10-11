# C9 post-hoc follow-up (exploratory)

> **Exploratory, not confirmatory.** These changes were made *after* seeing the confirmatory misses
> in [`C9_RESULTS.md`](C9_RESULTS.md). The corpus, ground truth and seeds are identical, but the gates
> were improved with knowledge of what they missed. Read these numbers as "the gaps are fixable",
> not as an unbiased detection rate. The confirmatory figure remains **84% (21/25)**.

## Changes (all committed alongside this file)

1. **Generic, needs no spec: call-site-aware API rule.** A changed parameter default is now
   *breaking* when any call site in the repository omits that argument
   (`static_gates.callers_relying_on_default`). Before, it was always only a warning.
   Tests: `test_caller_trap_default_change_is_blocked_by_api_gate_and_declared_contract`,
   `test_default_change_without_dependent_callers_stays_a_warning`.
2. **Spec additions, each traced to a documented contract:**
   * case_01 `contract_rejects_invalid_amounts`: from `ledger.money.validate_cents` (no negative or non-integer cents).
   * case_03 `contract_invalid_timestamp_rejected`: from the `(False, "invalid_timestamp")` reason documented in the verifier.
   * case_03 `mr_float_header_equals_int_header`: from the `str | int | float` signature.
   * case_03 `contract_default_window_is_300s`: `WebhookDispatcher.dispatch` omits `tolerance_sec`.

## Result (same 43 plausible mutants, same ground truth)

| Arm | Confirmatory | Post-hoc (exploratory) | False blocks (both runs) |
| --- | ---: | ---: | ---: |
| A — tests only | 0/25 | 0/25 | 0/18 |
| B — static gates | 0/25 | 5/25 (20%) | 0/18 |
| C — generic gates (no hand-written oracle) | 4/25 (16%) | **9/25 (36%)** | 0/18 |
| D — full gates with declared specs | 21/25 (84%) | **25/25 (100%, Wilson 87–100%)** | 0/18 |

The generic-arm gain (+5) comes entirely from change 1, which applies to any repository. The rest of
the arm-D gain comes from the four spec additions.

Raw data: `benchmarks/overfit_experiment_posthoc.json` (`"label": "posthoc-exploratory"`).
