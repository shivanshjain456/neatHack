# VeriFix — Creative Brief, Claim-to-Evidence Map, Storyboard & Narration Script

- **Project**: **VeriFix — Autonomous Blast-Radius-Aware Root-Cause & Verified-Patch Engineering Agent**
- **Hackathon**: **neatHack 2026** (`https://neatlogs.com/hackathon`)
- **Participant / Team**: **Shivansh Jain (`Team HyperX`)**
- **Final Video Artifact**: `/home/user/verifix/video/out/verifix_neathack_2026_demo.mp4` (and `/home/user/verifix/verifix_neathack_2026_demo.mp4`)
- **Format & Runtime**: `1920x1080` (`16:9`), `30.00 fps`, `H.264 (yuv420p)` + `AAC (48 kHz Stereo, -15.1 LUFS)`, **`170.00 seconds` (`2:50.00`)** — strictly under the 3:00 (`180s`) neatHack ceiling.
- **Rendering Architecture**:
  - **Master Composition & Assembly**: **Remotion (`v4.0.534`)** (`src/index.ts`, `src/Root.tsx`, `src/VeriFixDemo.tsx`, `scripts/render_master_video.mjs`)
  - **Authored Motion Scene (`0:00 – 0:08`)**: **HyperFrames (`v0.8.145`)** (`hyperframes-scene/index.html` → `public/captures/hyperframes_caller_trap_intro.mp4`)
  - **Voiceover & Procedural Sound Engine**: Registered narrator voice **`voice-00`** (`public/audio/scene_01_hook.mp3` .. `scene_06_oss_and_close.mp3`) + FFmpeg C-filtergraph procedural harmonic pad & transition chimes (`scripts/build_master_audio.py`).

---

## 1. Creative Brief

- **Target Audience**: neatHack 2026 Jury (evaluating **The Agent 30%**, **Tool Usage & Improvement 25%**, **Demo Video 20%**, **Business Plan 15%**, **Open-Source Bug Found 10%**) and developer viewers on X (`@sj909x`).
- **Core Problem**: Standard AI coding agents optimize exclusively for making the failing target unit test pass—frequently introducing silent breaking changes into downstream callers (`settlement.py`, `invoicing.py`) or stuffing the entire repository into prompt context.
- **Core Solution (VeriFix)**: Before editing a single line of code, VeriFix maps the repository's 1-hop and transitive blast radius via `entire-graph` (`v0.4.0`) and recalls durable architectural invariants from `Entire Brain` (`v0.1.0`). Every patch executes inside an isolated Git worktree, is gated by `blast_radius_guardrail` (atomically rolling back any patch that breaks a downstream caller), is traced end-to-end in `Neatlogs` (`v1.4.26` SDK + MCP), feeds measured token savings into a 4-sheet `cfo.ai` Excel model (`plan.xlsx`), and is cryptographically attested by a live AWS Lambda verifier in `us-east-1`.

---

## 2. Claim-to-Evidence Map (100% Checkable in Repository)

| Video Claim (Spoken / On-Screen) | Source Artifact / Verifiable Evidence in `/home/user/verifix` |
|---|---|
| **Run `run_graph_case_01_le_3061` blocks Attempt #1 caller regression, rolls back worktree (`1 Rollback`), and self-heals on Attempt #2** | `.verifix_runtime/verifix_state.db` (`runs`, `steps`, `patches` tables) & `benchmarks/verified_runs_ledger.json` |
| **6 verified runs across 4 multi-file Python repos (`case_01`..`case_04`) & `10/10` automated pytest suite passing** | `benchmarks/repos/case_01_ledger_rounding`..`case_04_dag_scheduler`, `benchmarks/test_suite.py` (`pytest benchmarks/test_suite.py`) |
| **Live AWS Lambda verifier (`verifix-hyperx-patch-verifier`) in `us-east-1` (`Account 082229155652`), `17+` traced calls at `0.0%` error rate (`449ms` P50)** | `src/verifix/aws_verifier.py`, Function URL `https://kmljtgaph5gaato6sysdjypw3a0vctrh.lambda-url.us-east-1.on.aws/`, `docs/screenshots/02_neatlogs_tool_performance_p50_p95.png` |
| **Entire Partner Proof: `1,635` AST graph records (`benchmarks/graph.ndjson`), `Entire Brain v0.1.0` (`465` symbols, `1,666` relations, `6` facts), `entire-agent-verifix` Protocol v1 (`token_calculator: true`), `13` Git Checkpoints (`99.7k` / `182.7k` tokens, `100% AI` line attribution)** | `benchmarks/graph.ndjson`, `src/verifix/graph_engine.py`, `src/verifix/entire_agent_plugin.py`, `git for-each-ref refs/entire/`, `entire checkpoint explain HEAD` (`01M4JKQ2R6CX0NGKZMMMT588WR`), `entire why src/verifix/aws_verifier.py` |
| **Neatlogs Partner Proof: `275` production traces, `556+` tool calls (`0.0%` error rate), `11` Active Detections (`992` 7d hits), controlled experiment `exp_0e3f5ca743` (`-65.05%` prompt tokens `12,216 → 4,269`, `-63.72%` total tokens `14,395 → 5,222`, `-42.56%` latency `20.74s → 11.91s`, `Execution Failed 27 → 0`)** | `benchmarks/neatlogs_live_traces.json`, `src/verifix/neatlogs_mcp_client.py`, `docs/screenshots/01..04_neatlogs_*.png` |
| **`cfo.ai` Partner Proof: Modeled enterprise direct COGS cut `-79.83%` (`$0.8896 → $0.1794/run`), projected `94.67%` Q4 Gross Margin (incl. Dodo Payments `3.9% + $0.40` MoR fee), projected `$298,050` Q4 ARR (`$1.19M` M24 ARR), projected Infinite Cash-Flow Positive Runway from Month 4 (`$17,372` Q4 Ending Cash)** | `plan.xlsx` (`Board_Overview`, `Assumptions`, `24M_Main_Model`, `4Q_Scenario_Comparison`), `BUSINESS_PLAN.md`, `benchmarks/cfo_ai_verified_model.json`, `src/verifix/cfo_economics.py` (all forecasts explicitly labeled as modeled projections) |
| **Real Upstream Open-Source Bug Fixed in `neatlogs/neatlogs` (`v1.4.26`): `_MaskWorkerPool` thread-pool starvation in `neatlogs/core/masking_exporter.py` (`30/30 → 0/30` dropped batches, `530/530` unit tests passing), upstream Issue `#199` & PR `#203`** | `REAL_OSS_BUG_REPORT_NEATLOGS.md`, `benchmarks/real_oss_bug_hunt_neatlogs_sdk.json`, `benchmarks/neatlogs_pr_199_patch.diff`, `https://github.com/neatlogs/neatlogs/issues/199`, `https://github.com/neatlogs/neatlogs/pull/203` |

---

## 3. Timed 6-Scene Storyboard & Spoken Narration Script (`170.00s` Total)

### Scene 1 (`0:00.00 – 0:28.00` · `28.0s` · `Frames 0 – 840`) — The Silent Caller Trap & Live Autonomous Recovery
- **Visuals**:
  - `0:00.00 – 0:08.00`: Authored **HyperFrames (`v0.8.145`)** kinetic architecture diagram (`public/captures/hyperframes_caller_trap_intro.mp4`) illustrating Attempt #1 passing `tests/test_fees.py` while breaking `ledger/settlement.py`, blocked by `blast_radius_guardrail` and healed on Attempt #2.
  - `0:08.00 – 0:28.00`: Live captured **VeriFix Mission Control Tab 1 (`01_tab1_run3061_recovery.png`)** inspecting `run_graph_case_01_le_3061` (`Attempts: 2`, `Rollbacks: 1`, `VERIFIED_COMPLETE`).
- **Spoken Narration (`scene_01_hook.mp3`, `voice-00`)**:
  > "Most coding agents make a failing unit test pass while silently breaking downstream callers. VeriFix is an autonomous bug-remediation agent that maps your repository's call graph before editing a single line of code. Watch run 3061 on our live Mission Control dashboard: Attempt 1 passes the target test, but breaks a downstream settlement caller. VeriFix's guardrail blocks the commit, rolls back the worktree, and self-heals on Attempt 2."

### Scene 2 (`0:28.00 – 0:57.50` · `29.5s` · `Frames 840 – 1725`) — Deterministic State Machine, 4 Multi-File Repos & AWS Lambda Verifier
- **Visuals**:
  - `0:28.00 – 0:43.00`: Live captured **Mission Control Tab 1 (`02_tab1_steps_and_diff.png`)** showing the 8-span execution ledger, unified Git diff, and all 4 multi-file Python repositories (`case_01`..`case_04`).
  - `0:43.00 – 0:57.50`: **VeriFix 3-Row Architecture Proof-Loop (`verifix_architecture_proof_loop.png`)** + AWS Lambda (`us-east-1`, `verifix-hyperx-patch-verifier`) attestation metrics.
- **Spoken Narration (`scene_02_workflow.mp3`, `voice-00`)**:
  > "Every run executes a deterministic state machine across isolated Git worktrees and a transactional SQLite write-ahead ledger. Across 4 multi-file Python repositories—covering ledger rounding, rate limiters, webhook HMAC validation, and DAG schedulers—VeriFix localizes the defect, plans a testable hypothesis, verifies every caller contract, and signs each patch with our live AWS Lambda verifier in us-east-1."

### Scene 3 (`0:57.50 – 1:25.00` · `27.5s` · `Frames 1725 – 2550`) — Partner #1 Deep Dive: Entire (`entire v0.11.4`)
- **Visuals**:
  - `0:57.50 – 1:11.50`: Live captured **Mission Control Tab 3 (`03_tab3_entire_graph_and_brain.png`)** showing the Obsidian-style interactive SVG Blast-Radius Graph (`1,635` NDJSON records) and live `entire graph impact --symbol calculate_tiered_fee`.
  - `1:11.50 – 1:25.00`: Live captured **Mission Control Tab 3 (`04_tab3_entire_checkpoints_and_why.png`)** showing `entire checkpoint explain HEAD` (`01M4JKQ2R6CX0NGKZMMMT588WR`, `99.7k` tokens), `entire why` (`100% AI`), `Entire Brain v0.1.0` (`465` symbols, `1,666` relations), and `entire-agent-verifix` External Agent Protocol v1 plugin.
- **Spoken Narration (`scene_03_entire.mp3`, `voice-00`)**:
  > "Entire powers both our runtime context and development provenance. At runtime, Entire Graph queries 1,635 AST records to isolate exact symbol slices and direct callers, while Entire Brain recalls durable architectural invariants across 465 symbols. For provenance, we built a native Entire External Agent plugin and recorded 13 Git Checkpoints with full token and line attribution."

### Scene 4 (`1:25.00 – 1:56.50` · `31.5s` · `Frames 2550 – 3495`) — Partner #2 Deep Dive: Neatlogs (`neatlogs v1.4.26` SDK + Live MCP)
- **Visuals**:
  - `1:25.00 – 1:41.00`: Live captured **Mission Control Tab 2 (`05_tab2_neatlogs_experiment_and_mcp.png`)** + controlled experiment `exp_0e3f5ca743` (`-65.05%` prompt tokens, `-63.72%` total tokens, `-42.56%` latency).
  - `1:41.00 – 1:56.50`: 2x2 gallery of our **4 real production `app.neatlogs.com/analytics` screenshots** (`275` traces, `556+` tool calls at `0.0%` error rate, `11` Active Detections with `992` 7d occurrences, `Execution Failed 27 → 0`).
- **Spoken Narration (`scene_04_neatlogs.mp3`, `voice-00`)**:
  > "Neatlogs traces every workflow, retriever, tool, guardrail, and model span—and connects back to the agent through the live Neatlogs MCP server. Across 275 production traces and 556+ tool calls with a 0.0% tool error rate, Neatlogs revealed severe context bloat in our naive baseline. Switching to graph-guarded retrieval cut prompt tokens by 65.05% and reduced latency by 42.56%, eliminating unguarded execution failures across 11 active Neatlogs detections."

### Scene 5 (`1:56.50 – 2:23.00` · `26.5s` · `Frames 3495 – 4290`) — Partner #3 Deep Dive: `cfo.ai` (`plan.xlsx` & `BUSINESS_PLAN.md`)
- **Visuals**:
  - Live captured **Mission Control Tab 4 (`06_tab4_cfo_ai_simulator_and_plan_xlsx.png`)** + Telemetry-to-Unit-Economics callout card (`-79.83%` modeled enterprise COGS `$0.8896 → $0.1794/run`, projected `94.67%` Q4 Gross Margin after Dodo Payments `3.9% + $0.40` MoR fee, projected `$298,050` Q4 ARR, projected Cash-Flow Positive Infinite Runway from Month 4).
- **Spoken Narration (`scene_05_cfo.mp3`, `voice-00`)**:
  > "Those measured Neatlogs token savings flow directly into our cfo.ai business model and 4-sheet formula workbook, plan.xlsx. Cutting modeled enterprise inference cost by 79.83%—down to $0.1794 per verified run—transforms our projected unit economics: delivering a projected 94.67% Q4 gross margin after Dodo Payments fees, and projected cash-flow positive infinite runway by Month 4."

### Scene 6 (`2:23.00 – 2:50.00` · `27.0s` · `Frames 4290 – 5100`) — Real Upstream Open-Source Bug Fixed (`neatlogs#199` & `PR #203`) & Finale
- **Visuals**:
  - `2:23.00 – 2:41.00`: Live captured **Mission Control Tab 5 (`07_tab5_oss_bug_hunt_and_selftest.png`)** showing the `neatlogs/core/masking_exporter.py` concurrency bug (`30/30 → 0/30` drops, `530/530` unit tests passing, `Issue #199`, `PR #203`) and `6/6` Jury Self-Test (`PASSED`).
  - `2:41.00 – 2:50.00`: Closing summary card with checkable URLs (`github.com/shivanshjain456/neatHack` & `github.com/neatlogs/neatlogs/pull/203`).
- **Spoken Narration (`scene_06_oss_and_close.mp3`, `voice-00`)**:
  > "To prove VeriFix beyond benchmarks, we pointed it at the official Neatlogs Python SDK itself. VeriFix uncovered a real thread-pool starvation bug in masking_exporter.py that dropped concurrent span batches, synthesized a deadline-bounded fix passing all 530 unit tests, and we opened Issue #199 and Pull Request #203 upstream. VeriFix: autonomous patches you can trust to ship."
