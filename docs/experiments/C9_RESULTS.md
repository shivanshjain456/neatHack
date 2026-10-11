# C9 results: plausible-but-wrong patches vs assurance gates

**Pre-registration:** [`C9_PREREGISTRATION.md`](C9_PREREGISTRATION.md), committed in `0674a9d` before
this run.
**Raw data:** `benchmarks/overfit_experiment.json`, one row per plausible mutant.
**Script:** `scripts/overfit_experiment.py`. Wall time 72.4 s.
**Deviations from the registration:** none.

## Corpus

| Case | First-order mutants of the reference fix | Plausible (pass all case tests) | Incorrect on held-out inputs | Equivalent on held-out inputs |
| --- | ---: | ---: | ---: | ---: |
| case_01 ledger | 48 | 14 | 6 | 8 |
| case_02 rate limiter | 28 | 10 | 3 | 7 |
| case_03 webhooks | 41 | 19 | 16 | 3 |
| case_04 DAG | 2 | 0 | 0 | 0 |
| **Total** | **119** | **43** | **25** | **18** |

43 of the 119 mutants pass every test the agent is asked to satisfy, and 25 of those 43 are
behaviourally wrong. Test-only acceptance would ship all 25. The case_04 fix is a single line, and
neither of its two mutants passes the tests.

## Confirmatory result (pooled)

| Arm | Incorrect blocked | Detection rate (Wilson 95%) | Equivalent blocked | False-block rate (Wilson 95%) |
| --- | ---: | ---: | ---: | ---: |
| A — tests only (VeriFix before C8) | 0 / 25 | 0% (0–13%) | 0 / 18 | 0% (0–18%) |
| B — static gates | 0 / 25 | 0% (0–13%) | 0 / 18 | 0% (0–18%) |
| C — generic gates, no hand-written oracle | 4 / 25 | 16% (6–35%) | 0 / 18 | 0% (0–18%) |
| D — full gates with declared specs | **21 / 25** | **84% (65–94%)** | **0 / 18** | **0% (0–18%)** |

Per case, arm D: case_01 5/6, case_02 3/3, case_03 13/16.

## Interpretation

* Static analysis catches nothing here. That is expected: these near-misses introduce no
  security, API or symbol problem. Static gates exist for a different class of agent failure, and
  `tests/test_assurance.py` covers that class with planted defects.
* The generic dynamic gates (arm C) need no hand-written oracle. They caught only the four
  `return None` mutants, through the runtime return-type contract. Differential fuzzing against the
  *buggy original* cannot tell a correct behaviour change from a wrong one.
* Most of the gain comes from declared contracts (arm D). This is the honest headline: in these
  cases, **an executable contract of a few dozen lines turns a 0% detection rate into 84%**.
  Arm D's oracle was written by the same team as the reference fixes, from the same documented
  contracts. This is the limitation declared in the pre-registration.
* No arm falsely blocked a patch that matched the reference on the held-out inputs.

## The four misses (arm D)

| Mutant | Change | Why the declared spec missed it |
| --- | --- | --- |
| case_01 M002 | deletes `validate_cents(amount_cents)` | the spec never generates negative amounts, so lost input validation is invisible to it |
| case_03 M002 | deletes the `int`/`float` fast path | float timestamp headers now raise; no relation used float headers |
| case_03 M021 | default `tolerance_sec` 300 → 301 | the API gate classifies a changed default as *dangerous* (a warning, not a block), and the replay-window contract always passes `tolerance_sec` explicitly |
| case_03 M023 | `return False, "invalid_timestamp"` → `return True, …` | **an authentication bypass on unparseable timestamps**. `contract_return_shape` checked the reason string but not the boolean |

## Post-hoc follow-up (exploratory, not confirmatory)

The misses point at concrete spec gaps. Closing them and re-running is an **exploratory** analysis:
the spec was changed after seeing the data, so its numbers must not be read as a confirmatory
detection rate. It is reported in [`C9_POSTHOC.md`](C9_POSTHOC.md).
