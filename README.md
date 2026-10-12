# VeriFix

**A coding agent that is not allowed to say "fixed" until it has proved it did not break anything else.**

VeriFix takes a failing test, finds the code responsible, and writes a patch. Before accepting the patch it also runs every
caller of the changed function. If the patch breaks one of them, VeriFix rolls the change back, feeds the failure to the
planner and tries again. Every step is traced in neatlogs.

Built for [neatHack 2026](https://neatlogs.com/hackathon) by Team **HyperX** (Shivansh Jain, solo).

[![Tests](https://img.shields.io/badge/tests-175%20offline-1B8A3A?style=for-the-badge)](./tests)
[![Claims](https://img.shields.io/badge/claims-43%20recomputed%20in%20CI-1B8A3A?style=for-the-badge)](./scripts/verify_claims.py)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge)](./pyproject.toml)
[![Site](https://img.shields.io/badge/site-GitHub%20Pages-0A66D6?style=for-the-badge)](https://shivanshjain456.github.io/neatHack/)

## For judges — verify in 60 seconds

```bash
git clone https://github.com/shivanshjain456/neatHack && cd neatHack
git log --reverse --date=iso --format='%h %ad %s' | head -3        # first commit 2026-10-10, inside the code window
git log --no-merges --format='%(trailers:key=Entire-Checkpoint,valueonly=true)' | grep -c .   # 24 checkpoints
python3 -m pip install -r requirements-runtime.lock && python3 -m pytest -q tests/            # 175 passed
python3 scripts/verify_claims.py && python3 scripts/verify_zero_tolerance.py                  # 43 claims 0 failures · 68 files 0 violations
```

The [Verify screen](https://shivanshjain456.github.io/neatHack/#verify) maps every claim to an official judging weight and
re-checks LIVE items on load; [comparison.md](./docs/comparison.md) puts the numbers against the obvious alternatives;
[evidence/](./evidence/README.md) curates the neatlogs / Entire / cfo.ai proof per tool.

| | |
| :--- | :--- |
| **Verify every claim in two minutes** | **[Open the Verify screen →](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/#verify)** (checks GitHub, neatlogs and this deployment live) |
| Live workspace | [AWS Lambda](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/) · [GitHub Pages mirror](https://shivanshjain456.github.io/neatHack/) |
| Demo video (2:18) | [download](https://gofile.io/d/eipSA3Zd) · [measured metadata](./verifix_neathack_2026_demo.meta.json) · [how it was made](./video/v2/README.md) |
| Full video (3:12, 1080p30) | [download](https://gofile.io/d/Io92bIuk) · [Remotion pipeline](./video/v3/README.md) |
| **Submission cut (2:58, narrated, ≤ 3:00)** | [download](https://gofile.io/d/lajq8oNU) · voiceover over the problem → live caller-trap run → controlled experiment → neatlogs critical incidents → Entire/cfo.ai assurance story; prior un-narrated cut: [gofile](https://gofile.io/d/yNMt8IBw) |
| Highlight video (0:30, HyperFrames) | [download](https://gofile.io/d/PyixHf0U) · alternate Remotion cut: [download](https://gofile.io/d/hAPT6bAb) |
| Entire checkpoint | [`10c7406`](https://github.com/shivanshjain456/neatHack/commit/10c7406723f285cc778b729863365713735e9191) · checkpoint `01M4KFYKQXFHME1HRZJVXJ7YT8` |
| Business plan (cfo.ai) | [`BUSINESS_PLAN.md`](./BUSINESS_PLAN.md) · [`plan.xlsx`](./plan.xlsx) · [cfo.ai](https://cfo.ai/) · **pricing** $49/$249/$999 per mo + metered overage; **costs** measured mean $0.005176 per receipt vs $0.25 cap; **revenue** month-24 $188,726 (ARR $2.26M, projections labelled); **runway** first positive EBITDA month 11 |
| Neatlogs traces & incidents | [traces](https://app.neatlogs.com/traces) · [critical incidents](https://app.neatlogs.com/incidents) · [analytics](https://app.neatlogs.com/analytics) · MCP `https://ingest.neatlogs.com/mcp` · exported trace `25c8f74e7cc8dd6260b36019dc8a6dfe` (run `run_graph_case_01_le_24584`, [live trace read-back](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/api/neatlogs-trace-readback) · [public share of the run](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/runs/run_graph_case_01_le_24584/share)) · [public trace screenshot](https://shivanshjain456.github.io/neatHack/screenshots/03_neatlogs_trace_comparison.png) · [public orphan-trace audit](https://shivanshjain456.github.io/neatHack/screenshots/08_neatlogs_trace_comparison_orphan_audit.png) · [public incidents screenshot](https://shivanshjain456.github.io/neatHack/screenshots/01_neatlogs_error_and_detection_analysis.png) |
| Upstream contribution | Found and fixed an exporter race in neatlogs: issue [#199](https://github.com/neatlogs/neatlogs/issues/199), PR [#203](https://github.com/neatlogs/neatlogs/pull/203) (open) |
| Build in public (#neatHack) | [Post 1](https://x.com/sj909x/status/2108813809792299255) · [Post 2](https://x.com/sj909x/status/2108814094514204930) · #neatHack |

### Neatlogs — publicly viewable trace & incident screenshots

![neatlogs trace comparison screenshot](https://shivanshjain456.github.io/neatHack/screenshots/03_neatlogs_trace_comparison.png)
![neatlogs orphan-trace audit screenshot](https://shivanshjain456.github.io/neatHack/screenshots/08_neatlogs_trace_comparison_orphan_audit.png)
![neatlogs critical incidents screenshot](https://shivanshjain456.github.io/neatHack/screenshots/01_neatlogs_error_and_detection_analysis.png)

## The result

A controlled experiment ([method and data](./docs/EVALUATION.md)): 4 benchmark bugs × 5 repeats × 3 arms. Every arm uses the
same model routing, prompt and attempt limit; only the context and the check differ. An independent judge applies each final
diff to a fresh copy of the repo and runs its whole test suite.

| | Target file only (caller-blind) | Whole repository | **Entire Graph callers (VeriFix)** |
| :--- | ---: | ---: | ---: |
| Passed the independent judge | 20/20 | 20/20 | **20/20** |
| Mean tokens per fix | 789 | 2,383 | **871** |
| Planted caller-breaking patch | shipped it 5/5 | rolled back, fixed 5/5 | **rolled back, fixed 5/5** |

- Graph context used **62% fewer tokens** than reading the whole repository: 871 vs 2,383 tokens, with a 95% CI by case of
  58–68%. It was cheaper in 19 of 20 paired runs.
- It costs 7% more than the target file alone. What that buys is the caller check: when the ledger case's known bad patch is
  planted on attempt 1, the caller-blind arm ships it, and VeriFix rolls it back and recovers.
- Fix rates were identical, since all three arms fixed all 4 bugs. These are small bugs written for this project; see the
  limitations in [EVALUATION.md](./docs/EVALUATION.md).
- `scripts/verify_claims.py` recomputes every number here from the raw run records, and CI fails if one drifts.

**Before / after, measured on the same bugs.** *Before* (caller-blind, target file only):
ships the planted caller-breaking patch 5/5, reads 789 tokens but never checks a caller.
*Before* (whole repository): 2,383 mean tokens per fix for the same 20/20. *After*
(VeriFix, Entire Graph callers): 871 mean tokens — 62% fewer than whole-repo — the same
20/20 independent-judge pass rate, and the planted regression rolled back and fixed 5/5.

**Retired figure:** the earlier headline, 31,093 → 946 tokens (`exp_24aa3f2776`), compared one run against a handicapped
baseline. That baseline had a forced bad first patch, an extra model call and unrelated docs in its prompt. Both runs remain in
[`benchmarks/verified_runs_ledger.json`](./benchmarks/verified_runs_ledger.json) as history, not as a claim.
**Correction:** the patch that run accepted (`patch_1c244a1e99`) passes its tests but is wrong. `if residual > 0:` drops negative rounding residuals, so split fees can sum to a cent more than the fee on the total. The assurance gates added later block it (`contract_split_conserves_cents`, recorded in [`benchmarks/assurance_corpus.json`](./benchmarks/assurance_corpus.json)).

## Passing tests is not proof

Tests passing is where VeriFix starts checking, not where it stops. Every candidate patch then goes through
[patch assurance](./src/verifix/assurance/):
- static gates: scope, API break, SAST, secrets, complexity;
- dynamic gates: differential fuzzing against the original, declared contracts and metamorphic relations, mutation score,
  determinism, performance, flakiness;
- a pre-write security policy.

| Experiment | Tests alone | **VeriFix** |
| :--- | ---: | ---: |
| [C9, pre-registered](./docs/experiments/C9_RESULTS.md): 43 mutants that pass every test, 25 of them wrong on held-out tests | caught 0/25 | **caught 21/25** (84%, 95% CI 65–94%), 0/18 false blocks |
| [Replay of 21 real LLM patches](./docs/EVALUATION.md) the earlier agent had accepted | accepted all 21 | **blocked 5/21** with concrete counterexamples |
| [C10, prompt injection](./docs/experiments/C10_AGENT_SECURITY.md): 24 attacks hidden in source strings and test messages | payload shipped 7/24 (29.2%), backdoor 4/4 | **shipped 0/24** (Fisher p = 0.0094) |

In C10, the undefended pipeline reported 24/24 fixes. Replayed through assurance, 23 of those 24 patches were either compromised
or wrong (C10 replay). An [exploratory follow-up](./docs/experiments/C9_POSTHOC.md) to C9 reaches 25/25, but it was tuned after
seeing the misses, so 84% remains the headline.

VeriFix's own releases get the same treatment ([supply chain](./docs/SUPPLY_CHAIN.md)):
- digest-locked dependencies, 1,754 SHA-256 hashes, installed with `--require-hashes`;
- an OSV vulnerability gate, currently 0 findings;
- a CycloneDX SBOM;
- byte-reproducible bundles;
- Sigstore-signed SLSA provenance, verified before every deploy;
- SHA-pinned CI actions;
- a hash-chained audit ledger of every agent run.

## Recovery from failure

Run `run_graph_case_01_le_24584` (open it from the Verify screen; its exported trace ID is `25c8f74e7cc8dd6260b36019dc8a6dfe`, and neatlogs ingestion was still processing recent traces when this was written) uses the built-in *caller trap*. Attempt 1 makes the
failing test pass but breaks a downstream caller. The guardrail catches it, the worktree is rolled back, the traceback goes to
the planner, and attempt 2 is verified: 2 attempts, 1 rollback, 2,195 tokens. Anyone can reproduce this on the live
workspace (*Run a benchmark* → enable *caller trap*).

## How each partner tool is used

| Tool | Role in VeriFix |
| :--- | :--- |
| **neatlogs** | Every run is a trace with WORKFLOW, AGENT, TOOL, RETRIEVER and GUARDRAIL spans. Root spans carry `neatlogs.workflow.*` attributes (case, mode, agent version, outcome, attempts, rollbacks, tokens), so runs can be filtered. The workspace reads traces back through the neatlogs MCP server (`verifix mcp-traces`, `/api/neatlogs-mcp`); the agent loop itself does not query MCP. Every run in the experiment above was traced the same way. |
| **Entire** | *Runtime:* Entire Graph finds the callers of the function being patched; that caller list is what the guardrail tests. *Development:* the build sessions are recorded as Entire checkpoints pushed with the repo. Checkpoints are provenance, not a runtime dependency. |
| **cfo.ai** | Planning. Measured per-run token cost feeds the unit economics in `plan.xlsx`. All plan figures are **projections**; `scripts/compute_plan_values.py` recalculates the workbook and a test fails if `BUSINESS_PLAN.md` drifts from it. |

## Any coding agent can start from agent.md

Give Claude Code, Cursor, Codex or your own agent this one line:

```text
Read https://shivanshjain456.github.io/neatHack/agent.md and follow it.
```

- Open **Agent Ready** in the dashboard topbar to copy the prompt and the install command.
- `pip install git+https://github.com/shivanshjain456/neatHack` installs the `verifix` CLI; every subcommand speaks `--json`.
- `docs/llms.txt` indexes the agent-readable surface; `docs/llms-full.txt` bundles it; `skills/verifix/SKILL.md` copies into `.claude/skills/`.
- Each recorded run ships as a priced, sha256-hashed receipt in `benchmarks/receipts/`; `benchmarks/cost_caps.json` states how the $0.25 public cap relates to measured costs.

## Run it

```bash
pip install -r requirements-runtime.lock -r requirements-dev.lock
export LITELLM_API_KEY=...  NEATLOGS_API_KEY=...      # neatlogs is optional; runs still work without it
PYTHONPATH=src python -m uvicorn verifix.server:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/#verify
```

The repository root is discovered from the checkout itself, so **any** clone location works —
there is no fixed build path to edit. On first start, the tracked runs in
[`benchmarks/verified_runs_ledger.json`](./benchmarks/verified_runs_ledger.json) hydrate the local
SQLite store, so a fresh clone serves real run history and all four partner evidence sections
instead of an empty workspace.

### Checks a judge can run in about a minute

| Check | Command | Measured on a fresh clone |
| :--- | :--- | :--- |
| Deterministic gates | `pytest tests/` | **175 passed**, 0 failed, ~19 s |
| Zero-tolerance source audit | `python scripts/verify_zero_tolerance.py` | **68 files, 0 violations** |
| Claim drift against raw run records | `python scripts/verify_claims.py` | **43 claims checked, 0 failures** |
| Integration, real agent runs | `pytest benchmarks/test_suite.py` | **18/18** when `LITELLM_API_KEY` is present; spends model budget, so not a default gate |
| Held-out external-validity probe | `python scripts/run_external_validity_probe.py` | **9/9** judge-pass on a new failure class (see below); exploratory, needs the same key |

The integration row is deliberately gated on credentials: it spends model credits. Its recorded
result (and the probe's) are in [`QUALITY_REPORT.md`](./QUALITY_REPORT.md) and
[`docs/experiments/EXTERNAL_VALIDITY_PROBE.md`](./docs/experiments/EXTERNAL_VALIDITY_PROBE.md).

**External validity, honestly:** the headline controlled experiment uses four small, purpose-built
repositories. To probe generalisation, [`scripts/run_external_validity_probe.py`](./scripts/run_external_validity_probe.py)
runs the same three-arm pipeline on a held-out case in a failure class the agent had not seen
(at-least-once delivery / dedup-key correctness). It is injected at runtime so the four-case catalog
and every published figure are untouched: 9/9 no-fault runs judge-pass on the first attempt, and
`graph_guarded` used 0.34× the tokens of whole-repo context at an equal pass rate. It is reported as
exploratory, not as a headline claim.

## Limits

- Four fixed benchmark repositories are public. Running arbitrary repositories or code is operator-only.
- The live Lambda keeps run history in `/tmp`, which is recycled. Recorded runs are preserved in the release ledger.
- The quality evidence in [`QUALITY_REPORT.md`](./QUALITY_REPORT.md) separates what was executed from what was not (no
  penetration test and no production load test were performed).

Long-form technical reference: [`docs/TECHNICAL_REFERENCE.md`](./docs/TECHNICAL_REFERENCE.md).
