# neatlogs evidence

1. **Every VeriFix run is traced.** The agent harness exports each step (model calls,
   tool calls, tokens, latency) to neatlogs. At submission-video recording time,
   1,400+ traces had been read back over the neatlogs MCP; the video states that
   figure at recording time. Source: `video/v3/src/FullVideo.tsx` (scene 08),
   `benchmarks/neatlogs_live_traces.json`.
2. **Current usage, dated capture.** The neatlogs Analytics dashboard showed 3,592
   traces in the last-14-day window on 2026-10-12: $0.1548 total model cost, 0.6%
   error rate, 84.7% detection rate; the caller-contract detector fired 8,764 times
   and the quota-429 failover detector 111. Source:
   `benchmarks/neatlogs_analytics_2026-10-12.json` (capture, not a live feed).
3. **Tracing paid for itself upstream.** Traced telemetry under load surfaced spans
   being dropped in the neatlogs SDK itself: reproduced, filed as issue #199, fix
   proposed in PR #203 (deadline-bounded semaphore acquisition instead of dropping
   work). Sources: [issue #199](https://github.com/neatlogs/neatlogs/issues/199),
   [PR #203](https://github.com/neatlogs/neatlogs/pull/203),
   `REAL_OSS_BUG_REPORT_NEATLOGS.md`, `benchmarks/real_oss_bug_hunt_neatlogs_sdk.json`.
   A contribution is a contribution, not a claim that it merged.
4. **Live read-back is a product feature, not a screenshot.** `verifix mcp-traces
   --json` and the dashboard Evidence library read traces back over the neatlogs MCP
   at request time; the Lambda endpoint `/api/neatlogs-trace-readback` does the same.
   When remote read-back stalls, VeriFix exposes its locally recorded steps and says
   so (`docs/KNOWN_LIMITS.md`).
5. **The recovery run is inspectable.** `run_graph_case_01_le_24584` shows attempt 1
   breaking a downstream caller, the rollback, and attempt 2 verified; its exported
   trace id is `25c8f74e7cc8dd6260b36019dc8a6dfe`. Open it from the dashboard Run
   history or `benchmarks/verified_runs_ledger.json`.
6. **Second capture, submission day (2026-10-12).** Home Needs Attention:
   *traces stopped flowing* (critical) — the gap the submission-day traced runs close.
   Daily Digest Oct 11–12: 1,727 recorded requests, 0.0% recorded errors, **0 incidents
   created or updated, 0 marked resolved** (board populates after the first Issue
   snapshot publishes; recorded as-is). Traces list shows live detection chips per run;
   detections page lists 11 active detectors plus 4 platform-suggested from our recent
   traces (OAuth Bypass Attempt, Test Failure, Stale Git Locus, Call Dependency Impact).
   Analytics: 3,594 traces, $0.1548, 0.6% error rate, 84.7% detection rate.
   Screenshots: `docs/screenshots/10_…`–`14_neatlogs_*_2026-10-12.png`.
