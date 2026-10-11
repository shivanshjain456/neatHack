# C9 pre-registration: do assurance gates catch plausible but wrong patches?

**Status:** registered before any result was produced. The analysis script, specs, reference fixes and
this document are committed together, and results are committed afterwards. The git history is the
ordering evidence. The metrics and analysis below must not be changed after results exist. Any
deviation will be reported as a deviation in the results file.

## Question

A patch is *plausible* when it passes the tests the agent was told to satisfy (repro + caller tests).
Automated program repair research has shown repeatedly that plausible patches are often incorrect
(patch overfitting: Smith et al., FSE 2015; Qi et al., ISSTA 2015). Test-only acceptance accepts every
plausible patch by construction. How many plausible-but-incorrect patches do VeriFix's assurance gates
block, and how many correct ones do they block by mistake?

## Corpus (generated, deterministic)

For each of the 4 benchmark cases:

1. Start from the hand-written reference fix (`benchmarks/reference_fixes/<case>.py`). Each one
   transcribes the catalog goal and passes the case tests.
2. Generate **all** first-order mutants (operators AOR, ROR, LCR, UOI/UOD, CRP, RVR, SDL, BCR in
   `verifix.assurance.mutation`) on every line of the functions the reference fix changes relative
   to the buggy original. Syntactic duplicates and TCE-equivalent mutants are removed. No cap is
   applied, and the generator seed is 20261011.
3. Keep only **plausible** mutants: those that pass the case's repro + caller tests in the sandbox.

These are synthetic near-miss patches, not LLM output. The LLM-output complement is the corpus replay
in `benchmarks/assurance_corpus.json`.

## Ground truth (independent of the gates)

A plausible mutant is labelled **incorrect** if, on a held-out set of 2,000 inputs per changed
function (or per driver), its observable behaviour differs from the reference fix on at least one
input. Observable behaviour means the return value, the exception type, or a timeout.
- Input generators: the spec `INPUT_GENERATORS`, or annotation-based generation when no spec
  generator exists.
- Seed: **99**. The gates use seed 20261011, so the gates never see the ground-truth inputs.

Otherwise the mutant is labelled **equivalent-on-held-out**. Such mutants may still differ outside
the sample, so the false-block rate reported on them is an upper bound on the true false-block rate.

## Arms

| Arm | Accepts a plausible patch when |
| --- | --- |
| A — tests only (VeriFix before C8) | always (by construction) |
| B — static gates | scope, API, SAST, secrets, symbols do not block |
| C — generic gates | B, plus differential fuzzing vs the original, contracts, determinism, flaky, performance, diff coverage (blocks below 50%). **No spec relations.** |
| D — full gates | C, plus the declared metamorphic relations and contracts of the case spec |

Mutation testing and minimality are reported but never block, so they do not change any arm. Each arm is evaluated from the same single gate run per mutant: arm B counts only blocking static gates, arm C adds the generic dynamic gates, and arm D adds `relations`.

## Metrics

* **Detection rate** = blocked incorrect / incorrect, per arm. Reported pooled and per case, with a
  Wilson 95% interval.
* **False-block rate** = blocked equivalent-on-held-out / equivalent-on-held-out, per arm.
  Reported with a Wilson 95% interval.
* Counts of plausible, incorrect and equivalent mutants per case.

## Known limitations, declared in advance

* The spec relations (arm D) were written by the same team as the reference fixes. Both come from the
  same documented contracts. Arm C contains no hand-written oracle and is the conservative figure.
* Four small cases, clustered. Pooled rates will be reported next to the per-case rates, and no
  generalisation beyond these cases is claimed.
* First-order mutants approximate, but are not identical to, the mistakes LLMs make.
