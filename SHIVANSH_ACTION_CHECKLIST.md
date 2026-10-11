# VeriFix (`Team HyperX`) — Complete Step-by-Step Operator Checklist for Shivansh Jain

> **Goal**: Maximize your score across **100% of the neatHack 2026 judging rubric** (`30% Agent + 25% Partner Tools + 20% Demo Video + 15% Building in Public + 10% Originality & Usefulness`) + **$500 Community Prize**.

> ⚠️ **Read this first (reconciled 2026-10-11):** Any figure in this doc that conflicts with
> [`README.md`](./README.md) is wrong — the README, [`docs/EVALUATION.md`](./docs/EVALUATION.md) and
> `scripts/verify_claims.py` (44 claims, 0 failures) are the source of truth. Current headline
> numbers: Entire Graph caller context **62% fewer tokens** than whole-repo (20/20 judged),
> C9 assurance **21/25** wrong-but-test-passing mutants caught, C10 **0/24** injected payloads
> shipped, cfo.ai plan **breaks even Month 11** (M12 ARR `$433,928`, M24 ARR `$2,264,709`). The
> first screen judges see is **"Verify in 2 minutes"**, not a 5-tab tour. Retired figures
> (`-65.1%` tokens, `-79.8%` COGS, `$298K` Q4 ARR, `Month 4`, `97%`) must never appear in a
> submission or post.

---

## 0. What Is Already 100% Done, Verified & Live in Production

Everything below is already built, verified, committed, and live:
- [x] **Public GitHub Repo (`shivanshjain456/neatHack`)**: Pushed and live at **`https://github.com/shivanshjain456/neatHack`** with `README.md`, `hackathon.md`, `BUSINESS_PLAN.md`, `plan.xlsx`, `REAL_OSS_BUG_REPORT_NEATLOGS.md`, `docs/verifix_architecture_proof_loop.png`, and `docs/screenshots/01..04_*.png`.
- [x] **Real Upstream Open-Source Bug Discovered, Fixed, Filed & PR Opened on `neatlogs/neatlogs` (`v1.4.26`)**:
  - **Live Issue**: **`https://github.com/neatlogs/neatlogs/issues/199`** (`neatlogs#199`)
  - **Live Pull Request**: **`https://github.com/neatlogs/neatlogs/pull/203`** (`neatlogs#203` — `30/30 -> 0/30` concurrent batch drops fixed, `530/530` unit tests + `black` + `isort` passing, AWS Lambda `us-east-1` SHA-256 attested).
- [x] **3 Published `#neatHack` Build-in-Public X Posts (`@sj909x`)**:
  - **Post 1 (`neatlogs#199` bug hunt)**: **`https://x.com/sj909x/status/2108813809792299255`**
  - **Post 2 (`shivanshjain456/neatHack` repo & partner proof)**: **`https://x.com/sj909x/status/2108814094514204930`**
  - **Post 3 (`neatlogs#203` fix PR opened — `530/530` unit tests + `black`/`isort` passing)**: Published by `@sj909x`.
- [x] **Entire (`entire v0.11.4` + `entire-graph v0.4.0` + `entire-brain v0.1.0` + `entire-agent-verifix`)**:
  - **`11` `Entire-Checkpoint` Git refs** pushed to `https://github.com/shivanshjain456/neatHack`.
  - `benchmarks/graph.ndjson` (`1,635` lines) + Interactive Obsidian-style SVG Graph Visualizer in Mission Control.
  - `Entire Brain` (`465` symbols, `1,666` relations, `6` durable architectural facts) active.
  - Native `entire-agent-verifix` External Agent Protocol v1 plugin implemented and registered (`entire status --json`).
- [x] **Neatlogs (`neatlogs v1.4.26` SDK + Live MCP Server + `11` Active Detections + `3` Deployed Prompts + `4` Production Analytics Screenshots)**:
  - **`188+` traces** analyzed with **`0.0%` tool error rate across all 10 tools** (`app.neatlogs.com/analytics`).
  - **`11` Active Detections (`992` 7-day flagged occurrences)** including all 4 Neatlogs Copilot Suggested Detections (`Floating Point Error Detector`, `Attestation Verification Tracker`, `System Integrity Error Detector`, `Performance Metric Tracker`).
  - **`3` Deployed Neatlogs Prompts (`v1` vs `v2`)**: `defect-remediation/llm_patch_synthesizer_prompt` (`v2`), `defect-remediation/llm_planner_graph_guarded_prompt` (`v2`), `defect-remediation/llm_planner_baseline_naive_prompt` (`v1`).
  - **GitHub OAuth Connected** to Neatlogs Copilot via Composio (`app.neatlogs.com/integrations`).
  - **4 Production `app.neatlogs.com/analytics` Screenshots** committed (`docs/screenshots/01..04_*.png`) and rendered inside Mission Control Tab 2, `README.md`, and `hackathon.md`.
- [x] **All 4 Multi-File Benchmark Repositories (`case_01` through `case_04`) Executed & Persisted (`benchmarks/verified_runs_ledger.json`)**:
  - `case_01_ledger_rounding` (Controlled `v1` vs `v2` Experiment + Caller-Trap Guardrail Rollback & Self-Healing Recovery)
  - `case_02_ratelimiter_state` (`VERIFIED_COMPLETE`)
  - `case_03_webhook_validator` (`VERIFIED_COMPLETE`)
  - `case_04_dag_scheduler` (`VERIFIED_COMPLETE`)
  - Automatically hydrates `.verifix_runtime/verifix_state.db` on any fresh `git clone`!
- [x] **cfo.ai Business Plan (`plan.xlsx` + `BUSINESS_PLAN.md` + Interactive Ari Sliders)**:
  - 4-tab formula-driven Excel workbook (`plan.xlsx`) + interactive Board Overview simulator in Mission Control (recalculated projections: M12 ARR `$433,928`, M24 ARR `$2,264,709`, first positive EBITDA in Month 11, lowest cash `$50,734` in Month 10; see `BUSINESS_PLAN.md`).
- [x] **Built-In 5-Act Jury Guided Tour & Demo Director (`▶ Start 3-Min Jury Tour (5 Acts)`)**:
  - Built directly into the header of **VeriFix Mission Control** (`0.0.0.0:8000`) with automatic tab switching, live benchmark triggers, and on-screen voiceover teleprompter cues!

---

## 1. How to Record Your ≤ 3-Minute Demo Video in One Take (`20%` of Total Score)

We built a **1-Click Demo Director & Voiceover Teleprompter (`▶ Start 3-Min Jury Tour (5 Acts)`)** directly into **VeriFix Mission Control** so you can record a crisp `2:45` video in a single take:

1. Open **VeriFix Mission Control** (`port 8000` live preview) in your browser.
2. Start your screen + mic recorder (**Loom**, **OBS Studio**, **macOS `Cmd+Shift+5`**, or **Windows `Win+G`**).
3. Click the blue **`▶ Start 3-Min Jury Tour (5 Acts)`** button in the top-right header of Mission Control:
   - **Act 1 (`0:00–0:35` · Tab 1 — The Agent `30%`)**: Automatically selects the Caller-Trap Guardrail Rollback run (`Rollbacks: 1 -> VERIFIED_COMPLETE`) showing Attempt #1 blocked by `blast_radius_guardrail` and Attempt #2 attested by AWS Lambda (`us-east-1`). Read the voiceover cue on the bottom dock, then click **`Next Act →`**.
   - **Act 2 (`0:35–1:15` · Tab 2 — Neatlogs Partner Proof)**: Automatically switches to Tab 2, showing the controlled 3-arm experiment (**Entire Graph context uses 62% fewer tokens than reading the whole repository, 20/20 through the independent judge; the earlier `-65.05%` single-run figure is superseded**), the `11` Active Detections, deployed `v1`/`v2` prompts, and triggers a live Neatlogs MCP query. Read the voiceover cue, then click **`Next Act →`**.
   - **Act 3 (`1:15–1:55` · Tab 3 — Entire Partner Proof)**: Automatically switches to Tab 3, highlights `calculate_tiered_fee` in the Obsidian-style interactive `entire-graph` SVG visualizer (`1,635` NDJSON records), and shows the `11` `Entire` Checkpoints, `Entire Brain` (`465` symbols, `1,666` relations), and `entire-agent-verifix` External Agent Protocol v1 plugin. Read the voiceover cue, then click **`Next Act →`**.
   - **Act 4 (`1:55–2:30` · Tab 4 — `cfo.ai` Partner Proof)**: Automatically switches to Tab 4 (`Ari Board Overview` simulator + `plan.xlsx` 4-sheet formula model). Show the recalculated projections: **Month-12 ARR `$433,928`, Month-24 ARR `$2,264,709`, first positive EBITDA in Month 11, lowest cash `$50,734` in Month 10** (all projections, recomputed by `scripts/compute_plan_values.py`). The old `$298K Q4 ARR / Infinite Runway from Month 4` figures did not match the workbook and were retired. Read the voiceover cue, then click **`Next Act →`**.
   - **Act 5 (`2:30–3:00` · Tab 5 — Real OSS Bug Hunt `neatlogs#199` & `PR #203`)**: Automatically switches to Tab 5, runs the live **6-Point Jury Self-Test (`6/6 PASSED`)**, and runs the live **30-Batch Concurrency Stress Benchmark (`neatlogs#199` `80%+` dropped -> `PR #203` `0%` dropped, `530/530` unit tests passing)**. Read the closing voiceover cue and stop recording!

---

## 2. Optional Extra Build-in-Public X Posts (`<= 280` Characters Each)

### Current-figure posts (prefer these; reconcile 2026-10-11)

**Post A — the reproducibility fix as a honesty story (248 raw / ≈228 X chars).** The brand is
"prove it", so shipping a bug-fix story is a strength:
```text
Our repo passed CI, but a judge cloning it elsewhere got an empty workspace.
Bug: root path hardcoded to our build sandbox.
Fix: resolve from the checkout + a test that fails if it ever returns.
https://github.com/shivanshjain456/neatHack #neatHack
```

**Post B — the controlled experiment (250 chars):**
```text
VeriFix: a coding agent not allowed to say "fixed" until it proves it.
3-arm controlled test, 60 runs: Entire Graph callers = 62% fewer tokens than whole-repo, 20/20 judged, and it rolls back a planted caller regression.
#neatHack @neatlogs @entirehq
```

### Optional Post 4 (Analytics Sankey, 11 Detections & 0.0% Tool Error Rate — `263 / 280` chars)
Attach `docs/screenshots/04_neatlogs_arc_patterns_sankey.png` or `01_neatlogs_error_and_detection_analysis.png`:
```text
1,400+ traces & 992 detection hits on @neatlogs for VeriFix:
• 0.0% error rate across 20 tools
• 11 active detections (incl. 4 Copilot rules)
• 3 v1/v2 prompts + GitHub OAuth
• 11 @entireio Checkpoints + @arithecfo model
https://github.com/shivanshjain456/neatHack #neatHack
```

---

## 3. Official Final Submission Window (Monday, Oct 12, 7:00 PM – 11:55 PM IST)

Between **7:00 PM IST and 11:55 PM IST on Monday, Oct 12, 2026**, go to `@neatlogs` on X, find their official **Submission Post**, click **Quote Post**, attach your **≤ 3-minute Demo Video**, and paste (`266 / 280` chars):

```text
Official #neatHack submission — VeriFix!
An agent not allowed to say "fixed" until it proves it.
• @entireio Graph: 62% fewer tokens, 20/20 judged
• @neatlogs: upstream PR #203, every run traced
• @arithecfo plan: breaks even month 11

https://github.com/shivanshjain456/neatHack
```
> 278 raw characters / ≈258 under X's URL counting — under the 280 limit. **Numbers above are the
> current, judge-verified figures** (3-arm controlled experiment, 60 runs). Earlier drafts of this
> doc quoted `-65.1%` tokens and `-79.8%` COGS — those belong to a superseded single-run
> comparison and a retired headline, and must not be posted.
