# VeriFix UI release — verification report

**Release scope:** task-oriented interface redesign, request-boundary hardening,
read-only workspace API, browser error handling and reproducible quality gates.
**Date:** 11 October 2026, India time. All results below refer to checks actually executed.

## Live product
- [Cloud workspace](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/)
- [GitHub Pages](https://shivanshjain456.github.io/neatHack/)
- [Desktop screenshot](artifacts/ui-release/after-desktop.png)
- [Mobile screenshot](artifacts/ui-release/after-mobile.png)
- [Live verified benchmark screenshot](artifacts/ui-release/live-run-verified.png)

## Verified results
| Gate | Observed result | Evidence |
|---|---|---|
| Hosted CI | Deterministic gates and Pages deployment both **completed successfully** for code revision `8b6ff99` | `artifacts/ui-release/hosted-ci.json` |
| Unit, API, security-boundary, database & property tests | **37 passed**; includes 200 generated property/fuzz examples across two tests | `artifacts/ui-release/unit-api.xml` |
| Existing integration/regression suite | **18 passed**; real model, Entire and AWS integrations, interruption/resume, caller-trap rollback | `artifacts/ui-release/legacy-integration.xml` |
| Browser suite, local service | **138 assertions passed** across Chromium, Firefox, WebKit and explicitly labeled fault fixtures | `artifacts/ui-release/browser-local.json` |
| Live Lambda browser suite | **42 assertions passed**, including an actual billable benchmark and inspection of its nonempty diff | `artifacts/ui-release/browser-live-lambda.json` |
| Live GitHub Pages browser suite | **41 assertions passed**, including cross-origin data loading and run evidence | `artifacts/ui-release/browser-live-pages.json` |
| Automated accessibility | No axe WCAG A/AA violations in the audited screens/dialogs across all three engines | `axe_results` in browser report |
| Responsive layouts | No document-level overflow at 320, 390, 768, 1280 and 1440 CSS px, all five routes, all three engines | browser report |
| Script errors | Zero uncaught page errors in the browser suites | browser reports |
| Deployed actions | Graph: 8 callers; intelligence: 8 modules; concurrency reproduction: 0 patched drops out of 30; selftest: 6/6 | `artifacts/ui-release/live-actions.json` |
| Runtime dependency vulnerability audit | No known vulnerabilities reported for the resolved runtime lock or actual Lambda dependency directory | `runtime-dependency-audit.json`, `lambda-dependency-audit.json` |
| New HTTP boundary & dashboard-builder static scan | Zero Bandit findings in those two modules | `bandit-boundary.json` |
| Source pattern audit | Existing zero-tolerance script passed; narrow pattern scan, not a security certification | `scripts/verify_zero_tolerance.py` |
| Deployment | Live HTML SHA-256 matched generated source byte-for-byte; data/health returned; anonymous code execution rejected | `artifacts/ui-release/deployment.json` |

### Fresh end-to-end model execution
The deployed browser completed `run_graph_case_01_le_78940`:
- Outcome: `VERIFIED_COMPLETE`, one attempt, zero rollbacks.
- 981 total tokens; recorded run latency **1.89 seconds** (not browser/page-load latency).
- Actual patch, execution steps and certificate saved in
  [`live-run-record.json`](artifacts/ui-release/live-run-record.json).
- This fresh result is deliberately **not** substituted for the historical 946-token,
  1.48-second experiment. Model executions vary.
- The genuine live record was then imported into the release ledger and verified readable after a Lambda redeploy, preserving this specific proof without claiming globally durable run storage.

### Read-only load, spike and recovery probe — local only
- Sequential: 10/10 HTTP 200; accepted median 7.7 ms.
- Concurrency 8: 30/30 HTTP 200; accepted median 49.23 ms.
- Concurrency 32 spike: 160 requests → 81 HTTP 200 and **79 expected HTTP 429**;
  no HTTP 5xx. Accepted maximum 654.32 ms.
- Thirty-second recovery/soak: 30/30 HTTP 200, maximum 32.33 ms.
- These measurements are from this sandbox, not AWS capacity or multi-hour endurance results.
- Raw results: [`local-load.json`](artifacts/ui-release/local-load.json).

## Failure and boundary scenarios exercised
- HTTP 503, 429, invalid JSON, malformed response schema and network failure, each followed by recovery.
- Empty data without invented measurements; a 1,000-record **test fixture** with pagination/search.
- Stored-XSS input rendered as text, missing/invalid run IDs, unknown cases/modes/fields,
  malformed JSON, oversized and chunked request bodies.
- Public custom-code routes denied without an operator token; wrong tokens denied;
  valid test credentials proceed to validation rather than unconditional success.
- Completed runs cannot be resumed; one execution per server instance; lock releases after injected failure.
- Token bucket concurrent accounting, replenishment and bounded LRU memory.
- SQL update identifiers checked against schema; values parameterized; database backup/restore integrity probe.
- Keyboard dialog focus containment, Escape/focus restoration, scrollable code focus,
  reduced-motion context, German numeric formatting and no-JavaScript guidance.
- All fault/volume fixtures are test-only; production never serves a fixture as a real response.

## Security and reliability findings — not hidden
The full source Bandit scan reports **74 findings: 64 low and 10 medium, no high**.
Most are existing subprocess usage, bind-to-all-interfaces or predictable `/tmp`
locations. Its dynamic-SQL finding now has an explicit schema allowlist and regression
test, but the static pattern still flags dynamic query assembly. See
[`bandit-full.json`](artifacts/ui-release/bandit-full.json). These findings are not
silently waived or presented as a clean full-product penetration test.

A scan of the general development sandbox also found vulnerable non-runtime packages
(Jupyter, NLTK, Tornado) and an older urllib3. The runtime urllib3 was upgraded and the
actual deployable dependency tree separately audited. The sandbox-wide report remains
in `dependency-audit.json`; it must not be confused with the deployment audit.

Implemented protections include hash-based script CSP, no frontend secrets, request
body limits, operator authentication for arbitrary code, bounded per-client throttles,
execution serialization, explicit schema validation, and package/HTML integrity checks.
Credentials bundled privately for Lambda are restricted to runtime use; no GitHub token
or long-lived AWS keys are included in the new deployment package.

**Remaining production blockers:**
1. SQLite and rate limits are per execution environment, not globally durable/shared.
   A Lambda recycle may discard fresh run records. Release-time ledger evidence persists in Git.
2. A separate process/worktree is not hostile-code isolation. Trusted operator operations
   still need a hardened, network/credential-isolated sandbox before multi-tenant release.
3. Model-cost limits and per-instance throttles are not an account-wide spend quota.
4. Legacy checkpoint transcripts and partner snapshots are inherited artifacts, not
   independently audited usage. No new synthetic checkpoint transcript was created for this release.
5. Local trace reconstruction does not resolve Neatlogs' remote finalization queue or
   recover another team's unrecorded spans.

## Test taxonomy: scope honestly applied
**Executed:** unit, API integration, system/browser acceptance, functional, smoke,
san­ity/regression, E2E, bounded performance/load/spike/recovery, input fuzz/property,
security-boundary, static/dynamic checks, accessibility, three-engine compatibility,
visual review, database integrity/restore, packaging and configuration checks.

**Partial:** automated usability evaluation (not human UAT), internationalization
(numbers/dates only), bounded volume/soak (not large-scale endurance), deployment
rollback implementation (not an intentionally destructive live failure drill),
limited failure injection (not infrastructure chaos).

**Not claimed:** human UAT, formal penetration test/red team, statistical A/B testing,
alpha/beta user program, mutation-score coverage, multi-hour endurance, distributed
scalability/SLO proof, Chaos Mesh/Chaos Monkey, cross-region disaster recovery or
host-infrastructure hardening. These require additional environments, authorization,
representative traffic and/or human participants. No shared cloud account was subjected
to destructive load tests.

## Reproduce
```sh
python -m pip install -r requirements-runtime.lock
python -m pip install --no-deps -e .
python -m pip install pytest hypothesis playwright bandit pip-audit
node --check src/verifix/web/app.js
pytest tests/test_web_release.py -q
# Integration suite uses real credentials, model budget and Entire runtime:
pytest benchmarks/test_suite.py -q
python -m playwright install --with-deps chromium firefox webkit
# Download axe-core 4.10.3 into /tmp/axe.min.js (test tool only).
# Start uvicorn in another terminal, then:
python scripts/browser_release_checks.py --faults
python scripts/local_load_probe.py  # strictly localhost
# A billable fresh model run is opt-in:
python scripts/browser_release_checks.py --base <deployment-url> --engines chromium --live-run
```

The GitHub Actions workflow runs deterministic gates only and does not consume model
credits or deploy. The first hosted run exposed premature provider initialization for
invalid resume requests (local credentials had masked it). That defect was fixed,
with a dedicated regression test. Hosted run evidence is in `hosted-ci.json`; consult
its conclusion rather than inferring success from the workflow file.
The deployment script retains a private rollback zip and restores it if post-deployment
HTTP/hash checks fail. Private deployment packages must never be uploaded publicly.

## Archived raw traces
Large Firefox/WebKit traces are available in the [complete backup](https://gofile.io/d/UVEhxwoT) and Git history; see `artifacts/ui-release/ARCHIVED_TRACES.md`. They were archived to respect the persisted-workspace size cap.

---

## Release: judge Verify screen, plan reconciliation and hardening (11 Oct 2026, IST)

**What changed**
- New first screen, **Verify in 2 minutes** (`#verify`, backed by `GET /api/judge-proof`). It maps each item of the official evidence checklist to a LIVE check (GitHub commits, Entire checkpoint refs, upstream PR state, neatlogs MCP search) or a RECORDED one (run ledger, business plan). Unreachable sources are shown as *unavailable*; nothing is hard-coded as a pass.
- `BUSINESS_PLAN.md` did not match `plan.xlsx`: it quoted Q4 ARR $298,050 and "break-even in Month 4", while the workbook formulas compute first positive EBITDA in Month 11 and a lowest cash balance of $50,734 in Month 10. The workbook was recalculated (`scripts/compute_plan_values.py` → `benchmarks/plan_xlsx_computed.json`), and §4–5 of the plan and two Board_Overview labels were corrected. A test now fails on drift.
- 16 silent `except …: pass` blocks were replaced with logged warnings. The `cfo-model` CLI no longer falls back to hard-coded token numbers. The onboarding guide reports `answer_source` when the live LLM fails.
- neatlogs: root spans set `neatlogs.workflow.*` attributes. Each run's certificate records its neatlogs trace ID. The workflow root now flushes *after* the root span ends: previously, short-lived processes could lose the root span.

**Executed checks (this release)**
| Gate | Result |
| :--- | :--- |
| Deterministic tests (`pytest tests/`, incl. 17 new judge-proof tests with mocked HTTP failure, rate-limit and drift cases) | 54/54 |
| Integration tests with real agent runs (`benchmarks/test_suite.py`) | 18/18 |
| Verify-screen browser gates, local, Chromium + Firefox + WebKit (axe WCAG 2.1 AA, 320–1024 px overflow, fault-fixture error state + retry, inspector, links) | 30/30 |
| Existing release browser gates incl. fault fixtures, local, 3 engines | 138/138 |
| Verify-screen browser gates against live Lambda, 3 engines | 30/30 (re-run after the commit-history change) |
| Existing release browser gates against live Lambda, 3 engines | 123/123 |
| Deploy smoke gates (byte-identical HTML, workspace, operator-only execution denied, judge-proof 7 items, health) | 5/5; live judge-proof summary recorded in `artifacts/ui-release/deployment.json` |
| Verify-screen browser gates against live GitHub Pages (API on Lambda, cross-origin), 3 engines | 30/30 |
| Hosted CI and Pages for `b3f7a3e` | [CI success](https://github.com/shivanshjain456/neatHack/actions/runs/38088999868) · [Pages success](https://github.com/shivanshjain456/neatHack/actions/runs/38088999620) |
| Live failure-recovery run on Lambda (`run_graph_case_01_le_34401`) | VERIFIED_COMPLETE, 2 attempts, 1 rollback, 1 caller regression caught, 2,274 tokens, 11.5 s |

**Not verified**
- The neatlogs ingest endpoint accepted the new spans (HTTP 200), but at the time of writing the neatlogs backend still showed recent traces as *processing*. Visibility of the new `neatlogs.workflow.*` attributes in the neatlogs UI was therefore not yet confirmed.
- No penetration test, production load test or human usability study was performed.

## Release: financial view from the recalculated workbook (11 Oct 2026, IST)

**Problem found:** the in-app financial view showed one Q4 margin, a cost per run and a raw JSON dump. A newcomer could not see the plan's headline figures (break-even month, ARR, lowest cash) without opening `plan.xlsx`.

**Change:**
- `/api/workspace` now returns `plan_projection`: the Month 1/6/12/24 figures, the first month with positive EBITDA and the lowest cash balance, all from `benchmarks/plan_xlsx_computed.json` (the recalculated `plan.xlsx`). Missing, malformed or non-finite data returns `null`, and the view then says the figures are unavailable rather than showing defaults.
- The view shows that table plus the workbook's separate scenario sheet, labelled as using its own static assumptions. Negative values are formatted as −$.
- The Verify screen's commit item is now a neutral check of the public commit history, and the generic failure label reads "Not met".

| Gate | Result |
| :--- | :--- |
| `tests/` (adds `tests/test_plan_projection.py`: matches BUSINESS_PLAN.md, malformed input, non-finite input, API contract) | 64/64 |
| `benchmarks/test_suite.py` (re-run after the trace-flush change) | 18/18 |
| Verify and financial browser checks, local, 3 engines | 33/33 |
| Release browser checks with fault injection, local, 3 engines | 138/138 |
| Lambda deploy smoke checks | deployed_and_smoke_verified; judge proof 7 verified / 0 not met / 0 unavailable |
| Verify and financial browser checks, live Lambda, 3 engines | 33/33 |
| Release browser checks, live Lambda, 3 engines | 123/123 |

## Release: demo video v2 (11 Oct 2026, IST)

**Problem found:** the 2:50 demo showed the earlier interface in text too small to read at 1080p. It also quoted plan figures that the workbook reconciliation had already corrected ("Q4 ARR $298,050", "cash-flow month 4").

**Change:** a new 2:20 cut recorded with Playwright against the live Lambda deployment. The live run inside it is `run_graph_case_01_le_93931`: attempt 1 is an injected bad patch (labelled on screen as a controlled failure test), it is caught and rolled back, and attempt 2 is verified with 2,270 tokens and neatlogs trace `a84d1896…`. Every spoken figure matches its source; the token caption states the experiment ID. Pipeline and captions are in `video/v2/`.

| Check | Result |
| :--- | :--- |
| Duration | 140.0 s (limit 180 s) |
| Streams | H.264 1920×1080 30 fps; AAC 48 kHz stereo; durations match within 0.01 s |
| Loudness | −16.2 LUFS integrated |
| Gaps | no silence longer than 1.2 s except the final fade |
| Visual review | 20-frame contact sheet (`video/v2/qa_contact_sheet.png`); every scene shows its intended screen |
| Captions | 35 cues, last ends at 138.8 s |

**Not verified:** no human viewer has watched the full cut yet, and the narration is synthesised speech.

## Release: onboarding answer computed from source (11 Oct 2026, IST)

**Problem found:** the Entire onboarding answer (`/api/entire-onboarding-qa`, operator-only) had five problems. Its file:line citations were hardcoded and out of date (`execute_case` was cited at line 306; it is at 357). It named a model that is no longer fixed. It quoted v2-era figures (79.83%, $0.8896 → $0.1794) as the headline. It fell back to a hardcoded checkpoint and commit when none was recorded. Two docs also still quoted superseded plan figures.

**Change:**
- Line ranges are now read from the current source with `ast`, also inside the Lambda package layout.
- Caller names come from the Entire Graph result.
- Figures come from `benchmarks/cfo_ai_verified_model.json`.
- A missing checkpoint is stated as missing.
- `docs/TECHNICAL_REFERENCE.md` and `SHIVANSH_ACTION_CHECKLIST.md` now cite the recalculated figures, and the v1 storyboard is marked superseded.

| Gate | Result |
| :--- | :--- |
| `tests/` (adds `tests/test_onboarding_answer.py`: ranges land on the named `def`, no stale constants, missing checkpoint stated, flat package layout) | 68/68 |
| `benchmarks/test_suite.py` | 18/18 |
| Live Lambda onboarding answer (operator token) | ranges `agent_harness.py:357-885`, `graph_engine.py:656-762`, `worktree_manager.py:149-171`, `aws_verifier.py:57-117`; no stale figures |
| Lambda deploy smoke checks | deployed_and_smoke_verified, judge proof 7 / 0 / 0 |
| Verify and financial browser checks, live Lambda, 3 engines | 33/33 |
| Release browser checks, live Lambda, 3 engines (before the line-range follow-up) | 123/123 |
| Verify and financial browser checks, Pages with the Lambda API, 3 engines | 33/33 |

## Release: controlled experiment replaces the single handicapped comparison (11 Oct 2026, IST)

**Problem found:** the headline result, 31,093 → 946 tokens (−96.96%), was a single run per side on one case, and the
baseline was handicapped by construction:
- a known bad patch was forced on its first attempt, and that attempt's model call was still billed;
- it made two model calls per attempt instead of one;
- its prompt asked for an analysis of every file;
- its context included unrelated VeriFix docs.

The comparison could not support a causal claim about graph context.

**Change:**
- **Harness:** the baseline is no longer forced to fail; fault injection happens only when requested, in any arm. All arms
  use one single-call pipeline.
- **New arm:** a caller-blind `target_only` arm reports `REPRO_PASSED_CALLERS_UNCHECKED` rather than claiming verification.
- **Latency:** step latency is the real call latency, replacing an earlier 35/65 split of one call across two steps.
- **`src/verifix/ablation.py`:** an independent full-suite judge on a fresh repo copy, paired geometric-mean token ratios,
  seeded bootstrap CIs (by pair and by case), and an exact sign test.
- **New data:** a 60-run experiment and a 15-run fault-injection study (`benchmarks/ablation_*.json`; method in
  `docs/EVALUATION.md`).
- **Claim gates:**
  - `scripts/verify_claims.py` recomputes every published figure from the raw records, and CI runs it.
  - The judge-proof improvement check recomputes the summary and rejects edited files.
- **Relabelling:** UI, README, business plan, technical reference, hackathon notes, onboarding answer, MCP notes and the demo
  video now cite the controlled result and mark the old figure as historical.
- **Ledger bug fixed:** `state_store` export used to overwrite the tracked ledger with the local database, which dropped two
  live Lambda runs. It now merges by primary key.

**Result:**

| Measure | Value |
|---|---|
| Graph vs whole-repo tokens | 0.376× (62% fewer); 95% CI by case 58–68%; 19/20 pairs; p = 0.00004 |
| Graph vs target-only tokens | 1.073× (7% more) |
| Independent judge passes, per arm | 20/20 |
| Planted caller-breaking patch, caller-blind arm | Shipped 5/5 |
| Planted caller-breaking patch, both guarded arms | Rolled back and fixed 5/5 |

| Gate | Result |
| :--- | :--- |
| `tests/` (adds `test_ablation.py` and `test_ledger_merge.py`; judge-proof tamper test) | 82/82 |
| `benchmarks/test_suite.py` | 18/18 |
| `scripts/verify_claims.py` | 28 claims, 0 failures |
| Lambda deploy smoke checks | deployed_and_smoke_verified, judge proof 7 / 0 / 0 |
| Release browser checks, local and live Lambda, 3 engines (axe WCAG 2.1 AA) | 123/123 each |
| Verify and financial browser checks, live Lambda, 3 engines | 33/33 |
| Verify and financial browser checks, Pages with the Lambda API, 3 engines | 33/33 |
| Demo video | 146.98 s, H.264 1080p30 + AAC 48 kHz, −16.0 LUFS, 34 caption cues; 9-frame QA sheet reviewed |

**Limitations:**
- The evidence comes from 4 small benchmark cases with near-deterministic repeats.
- The fault injection is one scripted patch.
- Cost figures are estimates from token counts.
- See `docs/EVALUATION.md`.

## Cycle 6 (11 Oct 2026): demo fits X without Premium

**Problem:** the 2:27 cut (146.98 s) was over X's 140-second upload limit for accounts without Premium, and the submission account has no Premium.

**Change:** shortened narration n5 and n7 only; scenes, recordings and cards are unchanged. Added `video/v2/loudnorm.py` (two-pass EBU R128) and `tests/test_demo_video.py`, which reads the MP4 header duration and fails above 139.5 s or if the captions drift from `narration.json`. The guard failed on the 2:27 cut before the fix.

| Check | Result |
| :--- | :--- |
| Demo video | 138.40 s, H.264 1080p30 + AAC 48 kHz, −16.1 LUFS, true peak −1.3 dBTP, 19.2 MB, 32 caption cues (last ends 137.27 s); 9-frame QA sheet reviewed |
| pytest `tests/` | 85 passed |
| `scripts/verify_claims.py` | 28 claims, 0 failures |
