# How VeriFix compares to the obvious alternatives

Every number below is measured, versioned in `benchmarks/`, and recomputed by
`scripts/verify_claims.py` in CI. The controlled experiment used 4 benchmark bugs ×
5 repeats × 3 arms, same model routing, prompt and attempt limit in every arm; an
independent judge applies each final diff to a fresh copy of the repo and runs its
whole test suite ([method and data](./EVALUATION.md)).

| Capability | Target-file-only agent (caller-blind) | Whole-repository agent | Tests-only CI | **VeriFix (Entire Graph callers + assurance)** |
| :--- | :--- | :--- | :--- | :--- |
| Context sent to the model | 789 mean tokens | 2,383 mean tokens | none (no agent) | **871 mean tokens** |
| Cost vs. whole repo | cheaper, but blind | baseline | — | **62% fewer tokens (95% CI 58–68% by case), cheaper in 19/20 paired runs** |
| Fixes passing the independent judge | 20/20 | 20/20 | n/a | **20/20 — no loss of fixes** |
| Planted caller-breaking patch (known bad patch, attempt 1) | **shipped it 5/5** | rolled back, fixed 5/5 | ships it (tests pass) | **rolled back, then fixed 5/5** |
| Wrong-but-tests-passing mutants (C9, 25 wrong of 43) | caught 0/25 | caught 0/25 (same tests) | caught 0/25 | **caught 21/25 (84%, 95% CI 65–94%), 0/18 false blocks** |
| 21 real LLM patches the earlier agent accepted | accepted all 21 | accepted all 21 | accepted all 21 | **blocked 5/21 with concrete counterexamples** |
| Prompt injection in source strings (C10, 24 attacks) | shipped payload 7/24 | shipped payload 7/24 | ships compromised code | **shipped 0/24 (Fisher p = 0.0094 vs undefended)** |
| Cost of the caller check | — | — | — | **+7% tokens over target-file alone** |
| Reproducible proof per run | none | none | job log | **one priced, sha256-hashed receipt per run (`benchmarks/receipts/`)** |
| Supply chain of the tool itself | unaudited | unaudited | unaudited | **digest-locked deps (1,754 hashes), OSV gate 0 findings, SBOM, byte-reproducible bundles, SLSA+Sigstore verified before deploy** |

## Reading the table

- **Target-file-only is the cheap-but-blind baseline.** It matches VeriFix on fix rate
  and costs 7% less, and that 7% is exactly the price of the caller check. The
  caller-blind arm ships the planted regression 5/5; VeriFix rolls it back and recovers
  5/5. That is the product in one row.
- **Whole-repository context buys nothing here.** It spends 2.7× the tokens of VeriFix
  for the same 20/20, because these bugs fit in one file. The interesting question is
  whether the extra context pays for itself on bigger repos; the 62% figure says where
  the token budget goes.
- **Tests-only CI is the default everyone has.** C9 shows its ceiling: 43 mutants that
  pass every test, 25 of them wrong on held-out tests, and the test suite clears none
  of the 25. VeriFix's assurance gates (differential fuzzing, declared contracts,
  metamorphic relations, mutation score) clear 21 without blocking the 18 good ones.
- **The undefended agent is the warning.** In C10 it reported 24/24 fixes; replayed
  through assurance, 23 of those 24 patches were compromised or wrong. A pipeline that
  cannot be attacked is not the same as one that checks.

## What VeriFix deliberately does not claim

- The benchmark bugs are small and written for this project; the effect size on
  real-world repos is unmeasured (see [KNOWN_LIMITS.md](./KNOWN_LIMITS.md)).
- 84% is the pre-registered C9 headline; an exploratory 25/25 follow-up exists but was
  tuned after seeing the misses ([C9 post-hoc](./experiments/C9_POSTHOC.md)).
- The financial model is projections, recomputed from measured tokens, and labelled so
  everywhere (`scripts/compute_plan_values.py` fails CI on drift).
