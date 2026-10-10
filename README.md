# VeriFix — Autonomous Blast-Radius-Aware Root-Cause & Verified-Patch Engineering Agent

> **Built for [neatHack 2026](https://neatlogs.com/hackathon) (October 10–12, 2026) — Single Track: *"Build an agent that works (literally)"***  
> **Team:** **HyperX** — **Shivansh Jain** (Solo Builder & Team Leader)  
> **Live 24/7 Interactive Cloud Mission Control (Audit, Edit Code & Run Live `claude-sonnet-4.6` Fixes in Browser):** [**AWS Lambda Live Cloud URL (`us-east-1`)**](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/) · [**GitHub Pages Live Portal**](https://shivanshjain456.github.io/neatHack/) · [**Live `6/6` Jury Self-Test JSON**](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/api/selftest) · [**Live Shareable PR & Trace Evidence Sample**](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/runs/run_graph_case_01_le_3061/share)  
> **Inference & Partner Stack:** **Official neatHack LiteLLM Gateway** (`https://litellm.vision.aivar.app/v1` — **`claude-sonnet-4.6`** primary Tier-1 model with cascade failover to `claude-haiku`, `nova-pro`, Gemini, TokenHarbor & OpenRouter) · **Neatlogs** (`neatlogs v1.4.26` SDK + Live MCP `https://mcp.neatlogs.com/mcp` + **275+ Traces** + **11 Active Detections / 992 7-Day Occurrences** + **3 Deployed `v1`/`v2` Prompts**) · **Entire** (`entire-graph v0.4.0` Semantic Code Graph + `Entire Brain v0.1.0` Continuous Memory at runtime; `entire v0.11.4` Checkpoints + `entire why` + `entire-agent-verifix` plugin for development provenance) · **cfo.ai** ([`plan.xlsx`](./plan.xlsx) 4-Sheet Formula Model + [`BUSINESS_PLAN.md`](./BUSINESS_PLAN.md) + Interactive Ari Simulator for modeled financial projections) · **AWS Lambda (`us-east-1`, Account `082229155652`)** ([Live Interactive Mission Control](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/) + [Live Public Verifier URL](https://kmljtgaph5gaato6sysdjypw3a0vctrh.lambda-url.us-east-1.on.aws/) — `verifix-hyperx-patch-verifier` Cryptographic & AST Patch Attestation)  
> **Submission Demo Video (`2:50.00` / `170.00s` <= `3:00` cap):** [`verifix_neathack_2026_demo.mp4`](./verifix_neathack_2026_demo.mp4) (`1920x1080`, `30fps`, `H.264` + `AAC 48kHz stereo`, `-15.1 LUFS`, `0` black frames, captions in [`video/out/verifix_neathack_2026_demo.srt`](./video/out/verifix_neathack_2026_demo.srt), visual QA in [`video/out/qa_contact_sheet.png`](./video/out/qa_contact_sheet.png)) · **Competitive Audit & Evidence Register:** [`COMPETITIVE_AUDIT_AND_MINDMAP.md`](./COMPETITIVE_AUDIT_AND_MINDMAP.md)  
> **Real Open-Source Bug Fixed:** Caught, reproduced & patched a 100%-reproducible concurrency race in [`neatlogs/neatlogs#199`](https://github.com/neatlogs/neatlogs/issues/199) · **Live Fix PR:** [`neatlogs/neatlogs#203`](https://github.com/neatlogs/neatlogs/pull/203) ([`REAL_OSS_BUG_REPORT_NEATLOGS.md`](./REAL_OSS_BUG_REPORT_NEATLOGS.md) — `30/30 -> 0/30` dropped batches, `530/530` unit tests + `black`/`isort` CI passing)  
> **Live `#neatHack` Build-in-Public Thread (`@sj909x`):** [Post 1 — OSS Bug Hunt (`neatlogs#199`)](https://x.com/sj909x/status/2108813809792299255) · [Post 2 — Full Repo, Checkpoints, Detections & `plan.xlsx`](https://x.com/sj909x/status/2108814094514204930) · **Post 3 — Live Fix PR [`neatlogs/neatlogs#203`](https://github.com/neatlogs/neatlogs/pull/203) (`530/530` unit tests + `black` + `isort` passing)** · [`@neatlogs` Thread Engagement](https://x.com/neatlogs/status/2108855688026042598)

![VeriFix Architecture Proof Loop](./docs/verifix_architecture_proof_loop.svg)

---

## 1. The Thesis: Why Most Coding Agents Fail in Production (and How VeriFix Fixes Both Technical & Financial Failure Modes)

Standard autonomous coding agents fail in real codebases for two coupled reasons:
1. **Unbounded Grep & Full-File Context Bloat:** Without a structural code graph, agents read entire directories into the prompt window, burning 2.5x–3.5x more tokens and latency per attempt.
2. **The "Caller Trap" (Downstream Contract Regressions):** Agents optimize strictly to make the *single failing reproduction test* pass, inadvertently breaking default parameters, return types, or invariants expected by downstream callers across other files.

**VeriFix** solves both problems—and proves the business impact in **cfo.ai** using live telemetry from **Neatlogs**:
- **Structural Localization & Blast-Radius Mapping (`entire-graph`):** Before reading source files or synthesizing a patch, VeriFix executes `entire graph search --profile full` and `entire graph impact` + `neighbors` inside a Neatlogs `RETRIEVER` span to identify the exact symbol line range, its helper callees, and every direct and transitive caller.
- **Sandboxed Reproduction & Blast-Radius Guardrail (`GUARDRAIL` span):** Candidate patches are applied in an isolated Git worktree and must pass **both** the target reproduction test **and** all downstream caller contract tests discovered by `entire-graph`.
- **Self-Healing Atomic Rollback & Stateful Resume (`SQLite WAL` + `Entire Checkpoints`):** When a candidate patch triggers a downstream caller regression or syntax error, VeriFix's Guardrail blocks the commit, atomically rolls back the worktree (`git checkout -- .`), records the refuted hypothesis in its durable SQLite WAL ledger, and iterates to a verified caller-safe fix. If a run is interrupted mid-flight, `verifix resume --run-id <id>` resumes from the exact SQLite WAL checkpoint without re-running completed phases.

---

## 2. How VeriFix Exercises All 8 neatHack Focus Areas

| Focus Area | Concrete Implementation in VeriFix | Code Location |
|---|---|---|
| **1. Planning** | `hypothesis_planner` (`@neatlogs.span(kind="AGENT")`) decomposes a defect report, failing pytest output, and `entire-graph` caller invariants into a 3-bullet testable hypothesis before any code edit. | `src/verifix/agent_harness.py` (`_plan_hypothesis`) |
| **2. Tool Use** | Strictly typed, path-traversal-guarded tools (`entire_graph_search`, `entire_graph_impact`, `prepare_isolated_worktree`, `run_pytest_target`, `apply_scoped_patch`, `rollback_worktree`, `entire_graph_diff`, `neatlogs_mcp_call`). | `src/verifix/graph_engine.py`, `worktree_manager.py`, `test_runner.py`, `neatlogs_mcp_client.py` |
| **3. State** | Transactional SQLite WAL store (`VeriFixStateStore`) tracking `runs`, `steps`, `hypotheses`, `patches`, and `experiments`, paired with `Entire` CLI Git checkpoints (`refs/entire/checkpoints/*`). | `src/verifix/state_store.py` |
| **4. Context** | `EntireGraphEngine.retrieve_focused_context` (`RETRIEVER` span) replaces full-repository file dumps with targeted AST symbol slices (`file:start_line-end_line`), callee helpers, and direct caller contract slices. | `src/verifix/graph_engine.py` |
| **5. Execution** | Multi-step state machine (`INITIALIZED -> LOCALIZING -> REPRODUCING -> PLANNING -> PATCHING -> VERIFYING -> VERIFIED_COMPLETE`) executing inside isolated Git worktrees (`/tmp/verifix_worktrees/<run_id>`). | `src/verifix/agent_harness.py` (`execute_case`) |
| **6. Recovery** | Dual-layer recovery: (a) Worktree atomic rollback + traceback feedback loop when a patch fails a caller contract; (b) Automatic multi-model LLM cascade failover (`gemini-3.1-flash-lite-preview` -> `gemini-3-flash-preview` -> `gemini-3.6-flash` -> `gemma-4-26b-a4b-it`) on HTTP `429`/`503`/`504`; (c) Stateful checkpoint resumption (`verifix resume`). | `src/verifix/config.py`, `src/verifix/agent_harness.py` |
| **7. Verification** | `blast_radius_guardrail` (`GUARDRAIL` span) verifies both the target defect reproduction test and all downstream caller tests, followed by `entire graph diff --base HEAD` semantic verification and certificate issuance. | `src/verifix/agent_harness.py`, `benchmarks/test_suite.py` |
| **8. Iteration** | Controlled Before (`baseline_naive`) vs. After (`graph_guarded`) experiment harness (`verifix experiment`) measuring exact token, latency, retry, and unit-cost deltas in Neatlogs. | `src/verifix/agent_harness.py` (`run_before_after_experiment`) |

---

## 3. Empirical Results: Two-Stage Iterative Optimization Diagnosed via Neatlogs (`v1 -> v2 -> v3`)

Executed on `case_01_ledger_rounding` (*Financial Ledger Tiered-Fee Precision & Split Conservation*, Neatlogs Project `00201e50-a8c9-42cf-84bf-116568a49cd5` across **350+ production traces**, Experiments `exp_0e3f5ca743` & `exp_bd53a0e4a4`):

| Metric | Run A — Before (`v1 baseline_naive`: No `entire-graph`, Unpruned Repo Context, Caller-Blind) | Iteration 1 (`v2 graph_guarded`: 2-Call `entire-graph` + Guardrail, `exp_0e3f5ca743`) | **Iteration 2 (`v3 Coalesced Graph-Brain Turbo`, `exp_bd53a0e4a4`)** | **`v3` Improvement vs `v1` Naive** | **`v3` Improvement vs `v2` Graph** |
|---|---:|---:|---:|---:|---:|
| **Prompt Tokens / Run** | `26,743` (`12,216` in `v2` exp) | `4,269` (`-65.05%`) | **`1,533` tokens** | **`-94.27%` prompt tokens** | **`-64.09%` fewer than `v2`** |
| **Total Tokens / Run** | `31,093` (`14,395` in `v2` exp) | `5,222` (`-63.72%`) | **`2,218` tokens** | **`-92.87%` total tokens** | **`-57.53%` fewer than `v2`** |
| **End-to-End Run Latency** | `41,381.72 ms` (`20,743.55 ms` in `v2` exp) | `11,914.84 ms` (`-42.56%`) | **`4,682.46 ms` (`4.68s`)** | **`-88.68%` latency** | **`-60.70%` faster than `v2`** |
| **Direct API Cost / Run (`claude-sonnet-4.6`)** | `$0.145479` | `$0.027057` | **`$0.014874`** | **`-89.78%` LLM cost** | **`-45.03%` lower than `v2`** |
| **Patch Attempts Required** | `2` attempts (Attempt #1 broke downstream caller contract) | `1` attempt (1st-pass verified patch) | **`1` attempt (`1` Coalesced LLM call)** | **`-1` retry cycle (`4 -> 1` LLM calls)** | **`-50%` LLM round-trips (`2 -> 1`)** |
| **`run_pytest_target` Verification Latency** | `339ms P50 / 847ms P95` (`2` calls) | `339ms P50 / 847ms P95` | **`36.8ms` (`1` combined `-S` pass)** | **`-89.1% P50 / -95.7% P95`** | **`9.2x` faster verification** |
| **`entire_graph_impact` / Context Retrieval** | N/A | `254ms P50 / 4,400ms P95` | **`2.7ms` warm / `577ms` cold** | N/A | **`-99.9%` warm / `-86.9%` P95** |
| **Modeled Enterprise Direct COGS / Run** | `$1.8626` (`$0.8896` in `v2` exp) | `$0.1794 / run` (`-79.83%`) | **`$0.0946 / run`** | **`-94.92%` unit cost reduction** | **`-47.27%` lower than `v2`** |

### Bottlenecks Diagnosed & Resolved Across 350+ Neatlogs Traces (`app.neatlogs.com/analytics`)
1. **Cold Worktree Graph Re-Indexing Tail Latency (`entire_graph_impact` `P95 = 4.4s` & `analyze_blast_radius` `P95 = 3.8s` in `docs/screenshots/07_neatlogs_tool_performance_21_tools.png`):** Neatlogs Tool Performance revealed that running `entire graph` against freshly created `/tmp/verifix_worktrees/<run_id>` directories forced cold tree-sitter index rebuilds on disk. We added SHA-256 content-addressed repository digest caching + canonical index resolution + concurrent `ThreadPoolExecutor` execution for `impact` + `neighbors`, cutting `retrieve_focused_context` to **`577ms` cold / `2.7ms` warm (`-99.9%`)**.
2. **Subprocess Test Startup & Dual-Invocation Overhead (`run_pytest_target` `244` calls, `P50 = 339ms`, `P95 = 847ms`):** Built an AST-inspected hybrid `-S` runner for zero-fixture test suites (`36.8ms` vs `1,252.9ms` full `pytest -v`, **34x faster**) and `run_combined_verification(repro_test, caller_targets)` (1 subprocess instead of 2 in `VERIFYING`), plus parallel execution of `entire graph diff` and AWS Lambda attestation.
3. **Redundant 2-Call LLM Context Duplication & `504`/`429` Provider Spikes:** Replaced sequential `_plan_hypothesis` + `_synthesize_patch` calls in `graph_guarded` mode with `_plan_and_synthesize_unified` (Coalesced Single-Pass Graph-Brain Planner & Surgical Patch Synthesizer using `# HYPOTHESIS:` comment headers inside a single ` ```python ... ``` ` block), deduplicated `target_symbol_definition` from the prompt context, and added persistent HTTP keep-alive connection pooling + a 300s Circuit-Breaker Cooldown (`_MODEL_COOLDOWN_UNTIL`).
4. **AWS Lambda Attestation `boto3` Fallback & Content-Addressed Caching:** Eliminated the `2.4%` (`1/42`) `No module named 'boto3'` tool error by checking `importlib.util.find_spec("boto3")` before fallback to pooled HTTPS Function URL with SHA-256 attestation caching (`0.0%` error rate, `<1ms` on cached diffs).

---

## 4. Partner Tool Integrations & Truthful Tool Role Matrix (25% Rubric Weight)

To maintain complete engineering transparency, VeriFix explicitly separates **production runtime dependencies** (invoked inside `VeriFixAgentHarness.execute_case` during live bug remediation) from **development-workflow provenance**, **diagnostic evaluation**, and **business-planning projections**:

| Layer / Role | Tools & Artifacts | How VeriFix Uses It | Required at Agent Runtime? |
| :--- | :--- | :--- | :---: |
| **1. Production Runtime Dependencies** | `entire-graph v0.4.0`, `Entire Brain v0.1.0`, `neatlogs v1.4.26` SDK, LiteLLM `claude-sonnet-4.6` (`https://litellm.vision.aivar.app/v1`), AWS Lambda (`verifix-hyperx-patch-verifier`, `us-east-1`) | Invoked live during every `verifix run` and `verifix fix-custom` execution to localize symbols/callers (`search`, `impact`, `neighbors`, `diff`), recall/store durable repository memory (`brain recall`/`remember`), emit structured spans/guardrails, synthesize patches, and cryptographically attest verified diffs. | **Yes (Core Runtime)** |
| **2. Development-Workflow Provenance** | `Entire Checkpoints v0.11.4` (`refs/entire/checkpoints/v1`), `entire why`, custom `entire-agent-verifix` Go plugin (`token_calculator: true`) | Captures development sessions, commit trailers (`Entire-Checkpoint`), token accounting, and line-level AI attribution (`100% AI` on `aws_verifier.py`) across the repository's build history. | **No (Dev Provenance)** |
| **3. Diagnostic & Evaluation Layer** | `Neatlogs MCP` (`https://mcp.neatlogs.com/mcp`), 11 active failure detections (`992` 7d hits), controlled `v1` vs `v2` experiments (`exp_0e3f5ca743`) | Queries historical trace spans (`whoami`, `search_traces`), scores failure patterns across runs, and quantifies before/after token (`-63.72%`) and latency (`-42.56%`) improvements. | **Diagnostic / Eval** |
| **4. Business-Planning & Financial Model** | `cfo.ai` 4-tab `plan.xlsx` (`39` dynamic formulas), `BUSINESS_PLAN.md`, Interactive Ari Scenario Simulator (`Main` / `Upside` / `Downside`) | Translates measured Neatlogs unit telemetry (`$0.8896 -> $0.1794/run` modeled COGS, `-79.83%`) into 24-month financial **projections** (ARR, gross margin, Dodo Payments MoR fees, and cash runway). Never represented as a code-fixing runtime dependency. | **No (Business Planning)** |

### 4.0 Remediating Any Arbitrary Local Python Repository (`verifix auto-fix` & `verifix fix-custom`)
In addition to the 4 built-in multi-file benchmark repositories (`case_01`–`case_04`), VeriFix supports both **Zero-Config Autonomous Discovery & Healing** (`verifix auto-fix` / `POST /api/auto-fix` — pass ONLY `--repo-path` and VeriFix runs `pytest` + AST + `entire-graph` to auto-discover the failing test, root-cause file/symbol, and caller test suite) and explicit custom target remediation (`verifix fix-custom` / `POST /api/run-custom`):
```bash
# 1. Zero-Config Auto-Discovery & Healing (requires ONLY --repo-path)
verifix auto-fix --repo-path /path/to/your/python/repo

# 2. Explicit Custom Target Remediation
verifix fix-custom \
  --repo-path /path/to/your/python/repo \
  --target-file billing/discount.py \
  --target-symbol compute_loyalty_discount_cents \
  --repro-test tests/test_discount.py \
  --caller-tests tests/test_invoice_callers.py \
  --goal "Fix half-to-even rounding in compute_loyalty_discount_cents while preserving caller contracts."
```

### 4.1 Neatlogs (`neatlogs v1.4.26` + Live MCP `https://ingest.neatlogs.com/mcp` + 11 Active Detections + 3 Deployed Prompts)
- Verified via `python3 -m neatlogs doctor --local --json` (`status: "pass"`) and `python3 -m neatlogs doctor --probe --json` (`status: "pass"`, 8/8 checks passing, `readback_trace_id: "a17e16d0b52ac53ffcab2c3b7dfe9bd0"`).
- **275+ Production Traces Analyzed in Neatlogs (`app.neatlogs.com/analytics`, Project `00201e50-a8c9-42cf-84bf-116568a49cd5`):**
  - Uses distinct workflow root spans (`defect-remediation` vs. `defect-remediation-naive-baseline`) tagged with `verifix.version = "v2"` vs `"v1"`, `AGENT` (`hypothesis_planner`, `patch_synthesizer`), `RETRIEVER` (`entire_graph_retriever`), `TOOL` (`entire_graph_search`, `entire_graph_impact`, `run_pytest_target`, `apply_scoped_patch`, `rollback_worktree`), `GUARDRAIL` (`blast_radius_guardrail`, `budget_and_loop_guardrail` enforcing **`3 tries, 20 tool calls, $0.25 max cost`**), `LLM` (`SystemPromptTemplate` / `UserPromptTemplate`), and `MCP_TOOL` (`neatlogs_mcp_call`).
  - **Tool Performance (`0.0%` Error Rate across 20 Traced Tools / `556+` Tool Calls):** `run_pytest_target` (`151` calls, P50 `337ms`, P95 `500ms`), `call_tool.tool` (`123` calls, P50 `139ms`, P95 `526ms`), `prepare_isolated_worktree` (`54` calls, P50 `15ms`, P95 `19ms`), `apply_scoped_patch` (`53` calls, P50 `4ms`, P95 `5ms`), `entire_graph_impact` (`44` calls, P50 `107ms`, P95 `284ms`), `entire_graph_search` (`40` calls, P50 `136ms`, P95 `200ms`), `entire_graph_diff` (`37` calls, P50 `45ms`, P95 `65ms`), `entire_brain_recall` (`19` calls, P50 `104ms`, P95 `182ms`), `analyze_blast_radius` (`18` calls, P50 `267ms`), `aws_lambda_patch_attestation` (`17` calls, P50 `449ms`, P95 `733ms`).
- **3 Deployed Neatlogs Prompts (`app.neatlogs.com/prompts`, Auto-Extracted & Versioned `v1` vs `v2`):**
  1. `defect-remediation/llm_patch_synthesizer_prompt` (`v2`, Variables: `attempt_no`, `blast_radius`, `bug_description`, `focused_context`, `hypothesis`, `previous_failure_context`, `pytest_repro_output`)
  2. `defect-remediation/llm_planner_graph_guarded_prompt` (`v2`, Variables: `blast_radius`, `bug_description`, `focused_context`, `pytest_repro_output`)
  3. `defect-remediation/llm_planner_baseline_naive_prompt` (`v1`, Variables: `bug_description`, `full_repo_context`, `pytest_repro_output`)
- **11 Active Neatlogs Detections (`992` 7-Day Scored Occurrences on `ingest.neatlogs.com`, including 4 Copilot-Suggested Detections):**
  1. `Floating Point Error Detector` (`Negative` · Copilot Suggested & Activated, `455` occurrences)
  2. `Downstream Caller Contract Regression Blocked` (`Negative` · VeriFix Guardrail, `140` occurrences)
  3. `Attestation Verification Tracker` (`Positive` · Copilot Suggested & Activated, `125` occurrences)
  4. `v2 Graph-Guarded Zero-Regression Patch Verified` (`Positive` · VeriFix Verification, `108` occurrences)
  5. `v1 Unbounded Full-Repo Context Bloat` (`Negative` · VeriFix Context Guard, `49 -> 0` occurrences after `v2` upgrade)
  6. `Execution Failed` (`Negative` · Built-in, **`47 -> 0` occurrences (`-100%` failure elimination on Oct 10)**)
  7. `LLM Provider Quota 429 Cascade Failover` (`Neutral` · VeriFix Recovery, `43 -> 1` occurrences after active model persistence)
  8. `Performance Metric Tracker` (`Neutral` · Copilot Suggested & Activated, `17` occurrences)
  9. `Slow LLM Response` (`Negative` · Built-in, `6` occurrences)
  10. `System Integrity Error Detector` (`Negative` · Copilot Suggested & Activated, `2` occurrences)
  11. `Expensive LLM Call` (`Negative` · Built-in, `0` occurrences)
- **GitHub OAuth Connected to Neatlogs Copilot (via Composio):** Connected at `app.neatlogs.com/integrations` so Neatlogs Copilot can read repository files and open pull requests directly.
- **Real Open-Source Bug Discovered, Fixed, Reported & PR Opened in `neatlogs/neatlogs` (`v1.4.26`, [`neatlogs#199`](https://github.com/neatlogs/neatlogs/issues/199) & [`neatlogs#203`](https://github.com/neatlogs/neatlogs/pull/203)):** Using `entire-graph`, VeriFix identified and patched a real concurrency race in `neatlogs/core/masking_exporter.py` (`_MaskWorkerPool.submit` / `_MaskRunner.apply_many`) where concurrent `MaskingSpanExporter` and `MaskingLogExporter` flushes dropped `30/30` batches under `blocking=False`. After VeriFix's patch: `0/30` drops, `530/530` unit tests in `neatlogs/tests/unit` + `black` + `isort` pass, and the patch is attested by AWS Lambda (`us-east-1`, `SHA-256: 58857f2d68ce1d5dfb40ac9dbe069772475bcb4880e24cc1ea24805d26d7523b`) — see [**Issue #199**](https://github.com/neatlogs/neatlogs/issues/199), [**Pull Request #203**](https://github.com/neatlogs/neatlogs/pull/203), and [`REAL_OSS_BUG_REPORT_NEATLOGS.md`](./REAL_OSS_BUG_REPORT_NEATLOGS.md).

#### Live Neatlogs Production Analytics Screenshots (`app.neatlogs.com/analytics`)

| 1. Error & Detection Analysis (`Downstream Caller Contract Regression Blocked 34%`, `v2 Graph-Guarded Verified 28%`) | 2. Tool Performance (`0.0%` Error Rate across all 10 Traced Tools, P50/P95 Latency) |
|---|---|
| ![Neatlogs Error and Detection Analysis](./docs/screenshots/01_neatlogs_error_and_detection_analysis.png) | ![Neatlogs Tool Performance](./docs/screenshots/02_neatlogs_tool_performance_p50_p95.png) |
| **3. Side-by-Side Trace Comparison (`app.neatlogs.com/analytics`)** | **4. Arc Patterns Sankey Flow (`WORKFLOW -> analyze_blast_radius -> rollback_to_baseline -> apply_file_content`)** |
| ![Neatlogs Trace Comparison](./docs/screenshots/03_neatlogs_trace_comparison.png) | ![Neatlogs Arc Patterns Sankey](./docs/screenshots/04_neatlogs_arc_patterns_sankey.png) |

### 4.2 Entire (`entire v0.11.4` Checkpoints + `entire-graph v0.4.0` + `entire-brain v0.1.0` + `entire-agent-verifix` External Agent Plugin)
- Repository enabled via `entire enable --agent claude-code --project --absolute-git-hook-path --telemetry=false -y`, `entire enable --agent verifix --project --telemetry=false -y`, `entire graph init-agents --repo .`, `entire brain setup --no-backfill --no-daemon`, and `entire brain init-agents`.
- **Native External Agent Plugin (`entire-agent-verifix`, `src/verifix/entire_agent_plugin.py`):** Implements the official **`entireio/external-agents` Protocol v1** (`info`, `detect`, `get-session-id`, `get-session-dir`, `resolve-session-file`, `read-session`, `write-session`, `read-transcript`, `chunk-transcript`, `reassemble-transcript`, `compact-transcript`, `format-resume-command`, `install-hooks`, `uninstall-hooks`, `are-hooks-installed`, `parse-hook`, `get-transcript-position`, `extract-modified-files`, `extract-prompts`, `extract-summary`) so `entire status --json` natively registers `"agent": "VeriFix Autonomous Remediation Agent"`.
- **Entire Graph (`v0.4.0` + `benchmarks/graph.ndjson` + Obsidian SVG Visualizer):** Uses `entire graph search --repo . --profile full --query ...`, `entire graph impact --repo . --symbol ...`, `entire graph neighbors --repo . --symbol ... --relation CALLS --direction both`, `entire graph diff --repo . --base HEAD`, and exports `benchmarks/graph.ndjson` (`1,635` NDJSON records) paired with an interactive **Obsidian-style Force-Directed SVG Blast-Radius Visualizer** in Mission Control.
- **Entire Brain (`v0.1.0` Continuous Memory):** Queries durable repository facts and invariants via `entire brain recall` inside the `RETRIEVER` span, and automatically records newly discovered caller-regression gotchas via `entire brain remember --kind gotcha --path workflow.verification.caller_trap` whenever the Guardrail rolls back a broken patch.
- **Entire Checkpoints (`v0.11.4`):** Every commit in `/home/user/verifix` is recorded through `Entire` session hooks (`entire hooks claude-code session-start | user-prompt-submit | stop`), creating `Entire-Checkpoint: <id>` commit trailers and `refs/entire/checkpoints/<shard>/<id>` Git refs.

### 4.4 AWS Lambda Cloud Patch Attestation (`us-east-1`, Account `082229155652`)
- Deployed `arn:aws:lambda:us-east-1:082229155652:function:verifix-hyperx-patch-verifier` in Team HyperX's official `$25` hackathon AWS account (`us-east-1`), exposed via both IAM SDK (`boto3`) and a live **Public HTTPS Function URL**: [**`https://kmljtgaph5gaato6sysdjypw3a0vctrh.lambda-url.us-east-1.on.aws/`**](https://kmljtgaph5gaato6sysdjypw3a0vctrh.lambda-url.us-east-1.on.aws/).
- Every patch that passes local `pytest` + `entire-graph` verification is attested in the cloud by `AWSLambdaPatchVerifier` (`src/verifix/aws_verifier.py` — `17+` live invocations with `0.0%` error rate in Neatlogs), embedding the signed `aws_request_id` and `sha256_attestation_digest` into the Verification Certificate. Even judges cloning the repo without AWS IAM keys automatically hit the live public `us-east-1` Function URL.

### 4.3 cfo.ai (`plan.xlsx`, `BUSINESS_PLAN.md`, `src/verifix/cfo_economics.py` & Interactive Ari Simulator)
- **In-Repo Formula Workbook (`plan.xlsx`) & Board Memo (`BUSINESS_PLAN.md`):** 100% Excel formula-driven 4-sheet workbook (`Board_Overview`, `Assumptions`, `24M_Main_Model`, `4Q_Scenario_Comparison`) + interactive **Ari Game-Engine Simulation Controls** in Mission Control (real-time sliders for Customer Growth, LLM Inference Cost, Retries/Run, and `v1` vs `v2` architecture mode) + **Dodo Payments Merchant-of-Record (`3.9% + $0.40`)** global billing model.
- Connects measured Neatlogs token/latency/retry telemetry directly into a 4-quarter and 24-month unit-economic and financial forecast across three scenarios:
  - **Main (Graph-Optimized Base Plan):** `$0.1794` modeled enterprise direct COGS/run -> **94.67% Q4 Gross Margin** (`$298,050` Q4 ARR, **`$1.19M` M24 ARR** in `24M_Main_Model`, **Infinite / Cash-Flow Positive Runway** starting Month 4).
  - **Growth (Ecosystem Attach Upside):** **94.68% Q4 Gross Margin** (`$547,423` Q4 ARR, `$248,690` Q4 ending cash).
  - **Downside (Unoptimized Grep + High Retry Burn):** Demonstrates why `entire-graph` + `neatlogs` optimization is existential for unit economics.
- Generates ready-to-execute `https://api.cfo.ai/mcp` (`edit_scenarios` and `edit_table_blocks`) payloads.

---

## 5. Quickstart & One-Command Jury Self-Test

```bash
# 1. Load environment & install VeriFix in editable mode
export PATH="/home/user/bin:/home/user/.local/bin:$PATH"
source /home/user/.verifix_secrets.env
pip install -e .

# 2. Run One-Command 6-Point Jury Self-Test (Entire + Neatlogs + cfo.ai + AWS Lambda)
verifix selftest

# 3. Run Zero-Tolerance Policy Audit & Automated Pytest Suite (16/16 tests)
python3 scripts/verify_zero_tolerance.py
pytest benchmarks/test_suite.py -v

# 4. Run Controlled Before (Run A) vs. After (Run B) Experiment
verifix experiment --case case_01_ledger_rounding

# 5. Run Caller-Trap Guardrail Rollback & Self-Healing Recovery
verifix run --case case_01_ledger_rounding --mode graph_guarded --inject-caller-trap

# 6. Run All 8/8 Entire Continuous Memory Intelligence Modules (#01-#08) & Neatlogs Incident Dispatcher
verifix entire-intelligence --symbol calculate_tiered_fee --case case_01_ledger_rounding
verifix dispatch-incident --detection "Downstream Caller Contract Regression Blocked"

# 7. Query Live Traces & 11 Active Detections via Neatlogs MCP Server
verifix mcp-traces --limit 10

# 8. Regenerate Telemetry-Coupled cfo.ai Workbook (plan.xlsx) & BUSINESS_PLAN.md
python3 scripts/generate_cfo_ai_workbook.py

# 9. Launch Live Mission-Control FastAPI Dashboard on 0.0.0.0:8000
verifix serve --host 0.0.0.0 --port 8000
```

---

## 6. Entire at Neathacks 2026 — Official Submission Checklist & Checkpoint Links

Per the official [Entire at Neathacks 2026 Guide](https://hack.entire.io/neathacks-2026/#submission):

- **Project:** **VeriFix** — Autonomous Blast-Radius-Aware Root-Cause & Verified-Patch Engineering Agent that maps caller blast radius via `entire-graph` + `Entire Brain` before editing code, enforces downstream caller contract tests in an isolated Git worktree, attests verified patches on AWS Lambda (`us-east-1`), and links every `neatlogs` trace to an `Entire` checkpoint and `cfo.ai` financial projection.
- **Implements ALL 8 of 8 Official "Ideas to Build" (`https://hack.entire.io/neathacks-2026/#ideas` in `src/verifix/entire_intelligence.py` & `POST /api/entire-intelligence`):**
  1. **#01 Debugger for Agent Mistakes:** Forensically compares rolled-back Attempt #1 patches against downstream caller contracts (`calculate_split_fees`, `build_settlement_batch`, `render_tax_invoice`).
  2. **#02 Reviewer That Checks Intent:** Audits the original defect goal against the verified Git diff, caller blast radius, pytest evidence, and AWS Lambda (`us-east-1`) cryptographic attestation.
  3. **#03 "Before You Build" Assistant:** Queries `Entire Brain`, historical rejected approaches in SQLite WAL, and `entire-graph` caller invariants before a single line of code is edited.
  4. **#04 Architecture Drift Detector:** Compares `entire graph diff --base HEAD~1` and `benchmarks/graph.ndjson` across commits with attached `Entire-Checkpoint` explanations.
  5. **#05 An Onboarding Guide You Can Question (`POST /api/entire-onboarding-qa`):** Interactive Q&A combining live `entire-graph` caller/callee edges, `Entire Brain` decisions, `Entire Checkpoints` commit links, and `file:start_line-end_line` citations.
  6. **#06 Regression Test Scout:** Inspects `entire graph impact` caller edges to generate targeted regression test recommendations.
  7. **#07 Checkpoint-to-Demo Generator:** Turns any verified run + `Entire-Checkpoint` into a one-click Shareable PR & Trace Evidence walkthrough (`/runs/<run_id>/share`).
  8. **#08 Integration for an External Agent (`entire-agent-verifix`):** Complete External Agent Protocol v1 plugin (`src/verifix/entire_agent_plugin.py`) with lifecycle hooks, `token_calculator`, and `neatlogs.wrap()`-traced `text_generator` (`entire checkpoint explain --generate`).
- **Entire Features Used (All 5 Core Features + Trails Runners):**
  1. **Entire Graph (`v0.4.0`):** `entire graph init-agents --repo .` (`.entire/graph-agent.md`, `AGENTS.md`, `CLAUDE.md`), `entire graph search --profile full`, `entire graph impact`, `entire graph neighbors --relation CALLS --direction both`, `entire graph diff --base HEAD`, and **`entire graph stats --repo .`** (**`100%` graph-first rate, `~39,216` tokens saved / `~81.53%` of billed session tokens** across `10/10` credited graph calls, plus `-65.05%` prompt token reduction in controlled experiment `exp_0e3f5ca743`).
  2. **Entire Brain (`v0.1.0`):** `entire brain setup`, **`entire brain init-agents`** (`.entire/agent-guide.md`, `AGENTS.md`, `CLAUDE.md`), **`entire brain mcp --print-config`**, `entire brain recall` (retrieved inside Neatlogs `RETRIEVER` span before planning), and `entire brain remember` (persists newly discovered caller-trap gotchas into `.entire/brain` when a patch is rolled back).
  3. **Entire Checkpoints (`v0.11.4`):** `git-refs` strategy (`21+` pushed `refs/entire/checkpoints/*`), `entire checkpoint list`, `entire checkpoint explain HEAD`, `entire checkpoint explain --generate`, `entire checkpoint tokens HEAD`, and `entire why src/verifix/aws_verifier.py` (`71 lines · 100% AI · 0% human`).
  4. **Agent Integration Protocol v1 (`entire-agent-verifix`):** Custom external agent plugin (`src/verifix/entire_agent_plugin.py`) implementing all lifecycle hooks (`agent-spawn`, `user-prompt-submit`, `stop`), `"token_calculator": true` (`calculate-tokens` / `calculate-total-tokens`), and `"text_generator": true` (`generate-text` powered by `claude-sonnet-4.6` and wrapped in `neatlogs.wrap()`).
  5. **Entire Trail Runners (`entire runner setup -y`):** Generated and tuned all 6 `.entire/runners/trail-*.json` evaluators (`trail-confidence.json`, `trail-drift.json`, `trail-review.json`, `trail-risk.json`, `trail-security.json`, `trail-summary.json`) using `entire-agent-verifix` + `claude-sonnet-4.6`.
- **Demo Links:**
  - **Live 24/7 Cloud Mission Control (AWS Lambda `us-east-1`):** [`https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/`](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/)
  - **GitHub Pages Live Portal:** [`https://shivanshjain456.github.io/neatHack/`](https://shivanshjain456.github.io/neatHack/)
  - **2:50 Submission Demo Video (`1080p@30fps`):** [`verifix_neathack_2026_demo.mp4`](./verifix_neathack_2026_demo.mp4) ([Gofile Mirror](https://gofile.io/d/yjUjZnu1))
- **Accessible Entire Checkpoint Links (`https://entire.io/gh/OWNER/REPO/commit/FULL_COMMIT_SHA`):**
  - **All 8/8 Official Entire Neathacks Ideas + AI-Generated Summary (`01M4K6PXDKWZK3090X4DH1TEDJ`, `169.4k` tokens):**  
    [`https://entire.io/gh/shivanshjain456/neatHack/commit/627aad4c7cd8b77b09810b04f439e7d5bab90584`](https://entire.io/gh/shivanshjain456/neatHack/commit/627aad4c7cd8b77b09810b04f439e7d5bab90584)
  - **Entire Intelligence Engine & OAuth-Independent Neatlogs Incident Dispatcher (`01M4K6DVJVS5Z09X1PJ0MY8N3K`, `156.8k` tokens):**  
    [`https://entire.io/gh/shivanshjain456/neatHack/commit/8028b9aac2cc51c0518f6e9e74e972950d39f489`](https://entire.io/gh/shivanshjain456/neatHack/commit/8028b9aac2cc51c0518f6e9e74e972950d39f489)
  - **Entire Graph Stats, Brain Init-Agents & Tuned Trail Runners (`01M4K41GVKXT2F117M4MTRMMBM`):**  
    [`https://entire.io/gh/shivanshjain456/neatHack/commit/4cf4d43fbe173b7d17004f260d10cb8a390b3e85`](https://entire.io/gh/shivanshjain456/neatHack/commit/4cf4d43fbe173b7d17004f260d10cb8a390b3e85)
  - **Shareable PR & Trace Evidence Checkpoint (`01M4K1AQSHJ30Q7V39F0TDK8PS`, `104.4k` tokens):**  
    [`https://entire.io/gh/shivanshjain456/neatHack/commit/decf6f7c225f8b3fa6fb69ab86801836773f3374`](https://entire.io/gh/shivanshjain456/neatHack/commit/decf6f7c225f8b3fa6fb69ab86801836773f3374)
  - **Zero-Config Auto-Discovery & Healing Checkpoint (`01M4JVR803V53S44V3NBAPWN86`):**  
    [`https://entire.io/gh/shivanshjain456/neatHack/commit/9e9d04c5be49fd6bf8e6dfca0efbd1ab3d60b810`](https://entire.io/gh/shivanshjain456/neatHack/commit/9e9d04c5be49fd6bf8e6dfca0efbd1ab3d60b810)
  - **External Agent Protocol v1 Plugin (`entire-agent-verifix`) Checkpoint (`01M4J98Q5S510JRH4W3356YNXK`):**  
    [`https://entire.io/gh/shivanshjain456/neatHack/commit/42227d95fd1c197fc3c94879f504a3365a8ec5ef`](https://entire.io/gh/shivanshjain456/neatHack/commit/42227d95fd1c197fc3c94879f504a3365a8ec5ef)

