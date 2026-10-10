# VeriFix — Autonomous Blast-Radius-Aware Root-Cause & Verified-Patch Engineering Agent

> **Built for [neatHack 2026](https://neatlogs.com/hackathon) (October 10–12, 2026) — Single Track: *"Build an agent that works (literally)"***  
> **Team:** **HyperX** — **Shivansh Jain** (Solo Builder & Team Leader)  
> **Partner & Cloud Stack:** **Neatlogs** (`neatlogs v1.4.26` + Live MCP `https://ingest.neatlogs.com/mcp`) · **Entire** (`entire v0.11.4` Checkpoints + `entire-graph v0.4.0` Semantic Code Graph + `entire-brain v0.1.0` Continuous Memory) · **cfo.ai** (Telemetry-Coupled Unit Economics & Scenario Engine) · **AWS Lambda (`us-east-1`, Account `082229155652`)** (`verifix-hyperx-patch-verifier` Cryptographic & AST Patch Attestation)

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

## 3. Empirical Results: Controlled Before vs. After Experiment (Diagnosed via Neatlogs)

Executed on `case_01_ledger_rounding` (*Financial Ledger Tiered-Fee Precision & Split Conservation*, Experiment ID `exp_0e3f5ca743`, Neatlogs Project `00201e50-a8c9-42cf-84bf-116568a49cd5`):

| Metric | Run A — Before (`baseline_naive`: No `entire-graph`, Unpruned Repo Context, Caller-Blind) | Run B — After (`graph_guarded`: `entire-graph` `search`+`impact` + Blast-Radius Guardrail) | Measured Improvement |
|---|---|---|---|
| **Prompt Tokens** | `12,216` tokens | `4,269` tokens | **`-65.05%` prompt tokens** |
| **Total Tokens** | `14,395` tokens | `5,222` tokens | **`-63.72%` total tokens** |
| **End-to-End Latency** | `20,743.55 ms` | `11,914.84 ms` | **`-42.56%` latency** |
| **Patch Attempts Required** | `2` attempts (Attempt #1 broke downstream caller contract) | `1` attempt (1st-pass verified patch) | **`-1` retry cycle saved** |
| **Modeled Enterprise Direct COGS / Run** | `$0.8896 / run` | `$0.1794 / run` | **`-79.83%` unit cost reduction** |

### Second Bottleneck Diagnosed & Resolved via Neatlogs Traces
During initial benchmark execution, Neatlogs trace spans revealed `gemini-2.5-flash` suffering `503 UNAVAILABLE` tenacity retry stalls (`63.1s` wall-clock latency) followed by `429 RESOURCE_EXHAUSTED` (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit 20). We re-architected `TracedLLMClient` (`src/verifix/config.py`) with `HttpOptions(timeout=15000, retry_options=HttpRetryOptions(attempts=1))` and an automatic multi-model cascade (`gemini-3.1-flash-lite-preview` -> `gemini-3-flash-preview` -> `gemini-3.6-flash` -> `gemma-4-26b-a4b-it`) with persistent healthy-model promotion, cutting per-call LLM latency from `~15s` to `~0.6s–1.2s`.

---

## 4. Partner Tool Integrations (25% Rubric Weight)

### 4.1 Neatlogs (`neatlogs v1.4.26` + Live MCP `https://ingest.neatlogs.com/mcp`)
- Verified via `python3 -m neatlogs doctor --local --json` (`status: "pass"`) and `python3 -m neatlogs doctor --probe --json` (`status: "pass"`, 8/8 checks passing, `readback_trace_id: "a17e16d0b52ac53ffcab2c3b7dfe9bd0"`).
- Uses distinct workflow root spans (`defect-remediation` vs. `defect-remediation-naive-baseline`), `AGENT` (`hypothesis_planner`, `patch_synthesizer`), `RETRIEVER` (`entire_graph_retriever`), `TOOL` (`entire_graph_search`, `entire_graph_impact`, `run_pytest_target`, `apply_scoped_patch`, `rollback_worktree`), `GUARDRAIL` (`blast_radius_guardrail`), `LLM` (`SystemPromptTemplate` / `UserPromptTemplate`), and `MCP_TOOL` (`neatlogs_mcp_call`).
- Live Streamable HTTP JSON-RPC 2.0 MCP client (`src/verifix/neatlogs_mcp_client.py`) queries `whoami` and `search_traces` directly from `https://ingest.neatlogs.com/mcp` (44+ live traces verified in project `00201e50-a8c9-42cf-84bf-116568a49cd5`).

### 4.2 Entire (`entire v0.11.4` Checkpoints + `entire-graph v0.4.0` + `entire-brain v0.1.0`)
- Repository enabled via `entire enable --agent claude-code --project --absolute-git-hook-path --telemetry=false -y`, `entire graph init-agents --repo .`, `entire brain setup --no-backfill --no-daemon`, and `entire brain init-agents`.
- **Entire Graph (`v0.4.0`):** Uses `entire graph search --repo . --profile full --query ...`, `entire graph impact --repo . --symbol ...`, `entire graph neighbors --repo . --symbol ... --relation CALLS --direction both`, and `entire graph diff --repo . --base HEAD`.
- **Entire Brain (`v0.1.0` Continuous Memory):** Queries durable repository facts and invariants via `entire brain recall` inside the `RETRIEVER` span, and automatically records newly discovered caller-regression gotchas via `entire brain remember --kind gotcha --path workflow.verification.caller_trap` whenever the Guardrail rolls back a broken patch.
- **Entire Checkpoints (`v0.11.4`):** Every commit in `/home/user/verifix` is recorded through `Entire` session hooks (`entire hooks claude-code session-start | user-prompt-submit | stop`), creating `Entire-Checkpoint: <id>` commit trailers and `refs/entire/checkpoints/<shard>/<id>` Git refs.

### 4.4 AWS Lambda Cloud Patch Attestation (`us-east-1`, Account `082229155652`)
- Deployed `arn:aws:lambda:us-east-1:082229155652:function:verifix-hyperx-patch-verifier` in Team HyperX's official hackathon AWS account (`us-east-1`).
- Every patch that passes local `pytest` + `entire-graph` verification is attested in the cloud by `AWSLambdaPatchVerifier` (`src/verifix/aws_verifier.py`), embedding the signed `aws_request_id` and `sha256_attestation_digest` into the Verification Certificate.

### 4.3 cfo.ai (`src/verifix/cfo_economics.py` & `benchmarks/cfo_ai_verified_model.json`)
- Connects measured Neatlogs token/latency/retry telemetry directly into a 4-quarter unit-economic and financial forecast across three scenarios:
  - **Main (Graph-Optimized Base Plan):** `$0.1794` modeled enterprise direct COGS/run -> **79.89% Gross Margin in Q1** rising to **81.92% in Q4** (`$769,848` ARR, `$171,192.91` ending cash, **Infinite / Cash-Flow Positive Runway**).
  - **Growth (Ecosystem Attach Upside):** **84.36% Gross Margin in Q4** (`$1,278,306` ARR, `$367,432.22` ending cash).
  - **Downside (Unoptimized Grep + High Retry Burn):** `$0.8896` direct COGS/run + `2.1x` retry volume -> **-42.33% Gross Margin in Q1**, exhausting cash runway in **0.1 months**—demonstrating why `entire-graph` + `neatlogs` optimization is existential for unit economics.
- Generates ready-to-execute `https://api.cfo.ai/mcp` (`edit_scenarios` and `edit_table_blocks`) payloads.

---

## 5. Quickstart & Verification Commands

```bash
# 1. Load environment & install VeriFix in editable mode
export PATH="/home/user/bin:/home/user/.local/bin:$PATH"
source /home/user/.verifix_secrets.env
pip install -e .

# 2. Run Zero-Tolerance Policy Audit & Automated Pytest Suite (7/7 tests)
python3 scripts/verify_zero_tolerance.py
pytest benchmarks/test_suite.py -v

# 3. Run Controlled Before (Run A) vs. After (Run B) Experiment
verifix experiment --case case_01_ledger_rounding

# 4. Run Caller-Trap Guardrail Rollback & Self-Healing Recovery
verifix run --case case_01_ledger_rounding --mode graph_guarded --inject-caller-trap

# 5. Query Live Traces via Neatlogs MCP Server (https://ingest.neatlogs.com/mcp)
verifix mcp-traces --limit 10

# 6. Generate Telemetry-Coupled cfo.ai Financial Model
verifix cfo-model --output benchmarks/cfo_ai_verified_model.json

# 7. Launch Live Mission-Control FastAPI Dashboard on 0.0.0.0:8000
verifix serve --host 0.0.0.0 --port 8000
```
