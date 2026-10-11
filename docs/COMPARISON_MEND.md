# VeriFix and Mend: an evidence-only comparison

Written 11 Oct 2026. Mend is [thegoodengineers/mend](https://github.com/thegoodengineers/mend), inspected at commit `a70b509`.
VeriFix is this repository, at the commit that adds this file.

**Rules:**
- Every cell is something we ran, read in source, or fetched from a public API.
- Nothing is inferred from names, marketing copy or missing docs.
- Where we could not check something, the cell says **unverified** or **insufficient evidence**, and any conclusion that
  depends on it is qualified.

## How each project was examined

**Mend:**
- Cloned at `a70b509` into a fresh virtualenv.
- `pytest`: 22 passed.
- `python -m mend.verify`: 44 README numbers recomputed, all OK.
- Read `README.md`, `mend/verify.py`, `mend/stats.py`, `docs/GATE.md`, `.github/workflows/ci.yml`, the `evidence/` and
  `runs/` directories, and `tasks/*.json`.
- GitHub API: CI and Pages succeeded on `a70b509`, `b5e4132` and `094d4b4`. The repo was created 2026-10-10T08:09Z and
  has 128 commits.

**VeriFix:**
- `tests/` and `benchmarks/test_suite.py`: 100 passed.
- `scripts/verify_claims.py`: 28 claims, 0 failures.
- Three-browser checks against the live Lambda: 33/33.
- Live judge-proof: 7 verified, 0 attention, 0 unavailable.
- Controlled experiment: 60 runs plus 15 fault-injection runs (see [`EVALUATION.md`](EVALUATION.md)).

## Comparison

| Dimension | Mend (evidence) | VeriFix (evidence) |
|---|---|---|
| **What it does** | A supervisor (Opus) reads neatlogs traces over MCP and has Claude Code edit a worker agent's prompt and code. A gate keeps a change only if more tasks pass, or the same tasks pass with ≥15% fewer tokens; otherwise it reverts. | A repair agent fixes a failing test. Entire Graph supplies the target's callers, and a patch is kept only if the reproduction test and the caller tests pass; otherwise the worktree is rolled back and the agent retries. |
| **Unit of improvement** | The agent itself (self-improvement loop over rounds) | Each code patch (verification and rollback per repair) |
| **Workload** | Haiku 4.5 worker on an invoicing sandbox: 29 tasks, 37 tests; 10 held-out tasks; 8 tasks in a real-world `inflection` repo | 4 benchmark bugs written for this project (ledger, rate limiter, webhooks, scheduler) plus custom repairs; one real upstream investigation (neatlogs PR #203, open) |
| **Headline effectiveness** | 8 rounds, 5 kept. Kept rounds cut tokens by 8.8–30.8%. Bootstrap CIs: R3 [0.609, 0.788], R4 [0.642, 0.764], R5 [0.702, 0.824]. | Graph context: 62% fewer tokens than whole-repo context (95% CI by case 58–68%), 7% more than target-file-only, same fix rate (20/20 in every arm) |
| **Fix-rate evidence** | Repeats 27, 26, 27 → 28, 28, 28 of 29. R1/R2 solve gains are single-task flips (p = 1.0, stated in its README). Held-out 9/10 → 10/10. Real-world 2–3/8 → 8/8. | No fix-rate difference measured: all arms solved all 4 bugs. A planted caller-breaking patch was shipped 5/5 by the caller-blind arm, and rolled back and fixed 5/5 by both guarded arms (one scripted fault, one case). |
| **Statistical method** | Paired sign test and bootstrap CI (`mend/stats.py`). Its CI resamples tasks; repeats are reported separately. | Paired geometric-mean ratio, seeded bootstrap by pair and by case, exact sign test (`src/verifix/ablation.py`). The headline CI resamples cases. |
| **Independent check** | Task tests run by the harness; held-out and real-world sets are separate from the training tasks | A separate judge applies each final diff to a fresh repo copy and runs the whole test suite |
| **Known evaluation limits** | Trains and scores on the same 29 tasks (held-out set is 10). Its CI resamples tasks, not runs. | 4 small cases (only 256 possible case-level resamples); near-deterministic repeats; judge suites of 4 tests; no real-world benchmark |
| **Claim checking in CI** | `mend.verify` recomputes 44 README numbers; CI runs pytest, `mend.tasks --check` and `mend.verify` | `scripts/verify_claims.py` recomputes 28 figures across 6 files; CI runs it and the experiment tests. The live `/api/judge-proof` recomputes the experiment summary and rejects edited files. |
| **Live, runnable demo** | Static GitHub Pages site; videos 2:42 / 1:55 (per its README, not timed by us) | Public AWS Lambda workspace: anyone can run a benchmark repair and watch the rollback; the Verify screen checks 7 claims (4 live, 3 recorded) |
| **neatlogs use** | Supervisor reads traces over MCP; every gate verdict is also sent as a `mend-gate` trace (HEAD commit message). Its own evidence notes ingestion failures since about 04:40 UTC on 11 Oct. | Every run is a trace with typed spans and `neatlogs.workflow.*` attributes; MCP read-back in the workspace. Ingestion failures observed on the same date. |
| **Entire use** | Checkpoint links in `evidence/entire-checkpoint.md`. Contents **unverified**: entire.io returns 404 to non-browser requests. | Entire Graph at runtime (caller list); checkpoint `01M4KFYKQXFHME1HRZJVXJ7YT8` as development provenance. Our live judge-proof checks the checkpoint refs on GitHub (`refs/entire/checkpoints`). The entire.io page body is **unverified** by us: it returns 404 to curl as well. |
| **cfo.ai use** | `docs/business-plan-cfo-ai.xlsx`. cfo.ai origin **unverified**: the file has no creator metadata. | `plan.xlsx` and `BUSINESS_PLAN.md` in the cfo.ai format, recalculated by `scripts/compute_plan_values.py`. Labelled projections. The workbook layout was first generated by a script (now `scripts/archive/generate_cfo_ai_workbook.py`) and has since been edited directly; use of the cfo.ai service itself is **unverified** from repository evidence. |
| **Precedent / memory** | Precedent path shown only by a unit test: **insufficient evidence** of use in a kept round | Entire Brain facts recalled with the graph context; no controlled measurement of their effect: **insufficient evidence** of benefit |
| **Maturity (age, commits, CI)** | Created 10 Oct; 128 commits; CI and Pages green on the last 3 commits | First commit 2026-10-10 (IST); 35 commits before this comparison; CI gates on source, scripts and claims. Docs-only commits do not trigger UI CI. |
| **Reliability** | CI green on inspected commits; **insufficient evidence** on runtime reliability (no hosted runtime) | 100/100 tests, 123/123 local release checks, 33/33 live browser checks. Lambda run storage is instance-local, not durable. |
| **License** | None declared (GitHub API) | Not compared: outside the scope of this evaluation |

## What this does and does not show

- **Different things.** The projects improve different things. Mend makes the *agent* better over rounds; VeriFix makes each
  *patch* safer. Neither result is evidence about the other's task.
- **Mend's breadth.** Mend's effectiveness evidence is broader: it has a held-out set and a real-world repository, and its
  token reductions hold across several gated rounds. VeriFix's workload is smaller.
- **VeriFix's strongest result** is the mechanism under fault injection. The caller-blind agent shipped the planted
  regression every time; the guarded agent never did. That is one scripted fault, not a rate estimate.
- **Partner-tool rows.** Several rows depend on things neither team's evidence settles (entire.io checkpoint pages, xlsx
  provenance). Conclusions in those rows are qualified accordingly.

## Ideas adopted from Mend, and how they were adapted

| Mend practice | Adopted in VeriFix | Adaptation |
|---|---|---|
| README numbers recomputed in CI (`mend/verify.py`) | `scripts/verify_claims.py` | Also checks the evaluation doc, business plan, technical reference, MCP notes, video narration and on-screen card |
| Paired sign test and bootstrap CI (`mend/stats.py`) | `src/verifix/ablation.py` | Geometric-mean ratio; the headline CI resamples cases rather than runs, because our repeats are near-deterministic |
| Reporting single-task flips as non-significant | Fix-rate parity stated as "no difference measured" | Same principle: no claim beyond the data |
| Ablation of what drives the gain | 3-arm controlled experiment plus fault-injection study | Isolates context (target / whole repo / graph) and the caller check |

What we kept distinct:
- per-patch verification with rollback;
- caller context from Entire Graph;
- an independent full-suite judge;
- a public runtime where judges can trigger a real repair.

We did not copy Mend's supervisor loop or its gate.
