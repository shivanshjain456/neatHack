# neatHack 2026 — Companion Log (`hackathon.md`)

## Project
- **Name:** **VeriFix**
- **One-Sentence Purpose:** An autonomous software reliability and bug-remediation agent that takes a Git repository and a failing defect report, uses `entire-graph` to map the structural blast radius before editing code, reproduces the bug in an isolated Git worktree, synthesizes and verifies a surgical patch against both the reproduction test and all downstream caller contracts, and links every `neatlogs` trace to an `Entire` Git checkpoint and `cfo.ai` unit-economics model.

## Team
- **Shivansh Jain** — Solo Participant (Architecture, Agent Engineering, Partner Integrations, Financial Modeling, Demo & Public Build Log)

## Stack
- **Language & Runtime:** Python 3.13 (`FastAPI`, `Uvicorn`, `Pydantic`, `SQLite3` in `WAL` mode, `pytest`, `httpx`, `rich`)
- **LLM Inference (Card-Free Cascade):** Google GenAI SDK (`google-genai`) wrapped with `neatlogs.wrap()` and automatic multi-model cascade failover (`gemini-3.1-flash-lite-preview`, `gemini-3-flash-preview`, `gemini-3.6-flash`, `gemma-4-26b-a4b-it`, `gemini-2.5-flash`) + OpenAI/Groq compatibility
- **Observability & Evaluation (Partner Tool #1):** **Neatlogs** (`neatlogs v1.4.26`, regional ingest `https://ingest.neatlogs.com`, live Streamable HTTP MCP server `https://ingest.neatlogs.com/mcp`, Project ID `00201e50-a8c9-42cf-84bf-116568a49cd5`)
- **Code Context & Git Provenance (Partner Tool #2):** **Entire** (`entire v0.11.4` Checkpoints on `git-refs` strategy + `entire-graph v0.4.0` local tree-sitter code graph plugin)
- **Financial Planning & Unit Economics (Partner Tool #3):** **cfo.ai** (Deterministic 3-Scenario Financial Model & `https://api.cfo.ai/mcp` `edit_table_blocks` / `edit_scenarios` payload generator coupled to live Neatlogs trace telemetry)

## Build log
- **2026-10-10 (00:06 IST):** Initialized `/home/user/verifix` Git repository on `main`. Enabled `Entire CLI v0.11.4` (`entire enable --agent claude-code --project --absolute-git-hook-path --telemetry=false -y`) and initialized `entire-graph v0.4.0` (`entire graph init-agents --repo .`), generating `.entire/settings.json`, `.entire/graph-agent.md`, `AGENTS.md`, and `CLAUDE.md`. Verified `neatlogs doctor --local --json` and `neatlogs doctor --probe --json` (`status: "pass"`, 8/8 checks passing, `readback_trace_id: "a17e16d0b52ac53ffcab2c3b7dfe9bd0"`).
- **2026-10-10 (00:18 IST):** Built all 4 multi-file "Caller Trap" benchmark repositories (`case_01_ledger_rounding`, `case_02_ratelimiter_state`, `case_03_webhook_validator`, `case_04_dag_scheduler`) and verified `entire graph impact` + `entire graph neighbors` blast-radius resolution across direct and transitive callers.
- **2026-10-10 (00:25 IST):** Implemented the complete **VeriFix** production package (`src/verifix/config.py`, `state_store.py`, `graph_engine.py`, `worktree_manager.py`, `test_runner.py`, `neatlogs_mcp_client.py`, `cfo_economics.py`, `agent_harness.py`, `cli.py`, `server.py`).
- **2026-10-10 (00:32 IST):** Diagnosed two real production bottlenecks via **Neatlogs** traces:
  1. **Context & Caller-Blind Retry Bottleneck (`exp_0e3f5ca743`):** Run A (`baseline_naive`) consumed `12,216` prompt tokens (`14,395` total tokens) and `20,743.55 ms` across `2` attempts because it dumped all repo files and broke a downstream caller contract on Attempt #1. Run B (`graph_guarded` using `entire graph search` + `impact` + Blast-Radius Guardrail) reduced prompt tokens by **`65.05%`** (`4,269` prompt tokens, `5,222` total tokens, **`-63.72%`**) and latency by **`42.56%`** (`11,914.84 ms`), succeeding on Attempt #1.
  2. **Model Quota & Latency Stall (`503 UNAVAILABLE` / `429 RESOURCE_EXHAUSTED`):** Neatlogs spans revealed `gemini-2.5-flash` hitting 60s tenacity retry stalls on free-tier quota limits. Implemented `HttpOptions(timeout=15000, retry_options=HttpRetryOptions(attempts=1))` with automatic multi-model cascade failover (`gemini-3.1-flash-lite-preview` -> `gemini-3-flash-preview` -> `gemini-3.6-flash` -> `gemma-4-26b-a4b-it`), cutting per-call LLM latency from `~15s` to `~0.6s–1.2s`.
- **2026-10-10 (00:38 IST):** Verified all 4 benchmark repositories (`VERIFIED_COMPLETE`), Caller-Trap Guardrail Rollback & Self-Healing Recovery (`run_graph_case_01_le_44068`, `caller_regressions_caught: 1 -> VERIFIED_COMPLETE`), Stateful Interruption & Checkpoint Resumption (`run_graph_case_04_da_38526`, `resumed_from_checkpoint: 1 -> VERIFIED_COMPLETE`), 7/7 automated pytest checks (`benchmarks/test_suite.py`), Zero-Tolerance Policy audit (`31 source files verified with 0 violations`), and generated the telemetry-coupled `cfo.ai` financial model (`benchmarks/cfo_ai_verified_model.json`, demonstrating `79.83%` unit cost reduction and `81.92%` Q4 gross margin vs. `-42.33%` unoptimized).

## Demo
- **Live Mission Control Dashboard:** Served by `verifix serve --host 0.0.0.0 --port 8000` (`src/verifix/server.py`).
- **CLI Commands:** `verifix run`, `verifix experiment`, `verifix resume`, `verifix mcp-traces`, `verifix cfo-model`, `verifix serve`.
- **Demo Video (≤ 3 minutes):** Walkthrough covering (1) live autonomous bug remediation & blast-radius guardrail rollback on `case_01_ledger_rounding`, (2) `entire-graph` caller impact tree & `Entire` Git checkpoint trailer, (3) Neatlogs Before vs. After trace comparison (`-65.05%` prompt tokens, `-42.56%` latency) + live Neatlogs MCP query, and (4) `cfo.ai` unit economics & scenario model (`81.92%` Q4 gross margin vs. `-42.33%` unoptimized).

## Known limitations
- `entire-graph` (`v0.4.0`) provides deterministic static call/import/type relations via tree-sitter; highly dynamic runtime reflection (`getattr`/`eval`) in Python can require widening the source slice around the static graph hit.
- Sandboxed test execution currently targets Python `pytest` repositories in isolated local Git worktrees rather than multi-container Docker Compose clusters.
- Direct browser OAuth into `https://api.cfo.ai/mcp` requires workspace activation via the `cfo.ai` web UI or organizer-activated hackathon credits; our `CFOEconomicsEngine` computes the exact formula tables locally and emits ready-to-run `edit_table_blocks` and `edit_scenarios` MCP JSON-RPC payloads.

## Submission checklist
- [x] Agent works end-to-end on real multi-file defect repositories without stubs or mock data
- [x] `neatlogs` integrated (`doctor --local` & `--probe` pass; `WORKFLOW`, `AGENT`, `RETRIEVER`, `TOOL`, `GUARDRAIL`, `LLM`, `MCP_TOOL` spans recorded; real bottlenecks diagnosed and fixed with measured before/after comparison)
- [x] `Entire` integrated (`entire enable` active; `Entire-Checkpoint` commit trailers and `refs/entire/checkpoints/*` created; `entire-graph` `search`, `impact`, `neighbors`, `diff` powering agent context selection)
- [x] `cfo.ai` business model completed (`Pricing`, `Costs`, `Revenue`, `Runway`, `Main`/`Growth`/`Downside` Scenarios grounded in measured Neatlogs telemetry)
- [x] `hackathon.md` maintained at project root
- [ ] Build-in-public posts published on X/LinkedIn with `#neatHack` (ready-to-post copy prepared in `/home/user/planning/03_BUILD_IN_PUBLIC_AND_SUBMISSION_KIT.md`)
- [ ] Final ≤3-minute demo video recorded and submitted via X quote post of the official neatlogs submission tweet during the Monday, Oct 12, 7:00–11:55 PM IST window
