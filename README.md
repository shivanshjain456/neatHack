# VeriFix

**A coding agent that is not allowed to say "fixed" until it has proved it did not break anything else.**

VeriFix takes a failing test, finds the code responsible, and writes a patch. Before accepting the patch it also runs every
caller of the changed function. If the patch breaks one of them, VeriFix rolls the change back, feeds the failure to the
planner and tries again. Every step is traced in neatlogs.

Built for [neatHack 2026](https://neatlogs.com/hackathon) by Team **HyperX** (Shivansh Jain, solo).

| | |
| :--- | :--- |
| **Verify every claim in two minutes** | **[Open the Verify screen →](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/#verify)** (checks GitHub, neatlogs and this deployment live) |
| Live workspace | [AWS Lambda](https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws/) · [GitHub Pages mirror](https://shivanshjain456.github.io/neatHack/) |
| Demo video (2:50) | [`verifix_neathack_2026_demo.mp4`](./verifix_neathack_2026_demo.mp4) |
| Entire checkpoint | [`10c7406`](https://entire.io/gh/shivanshjain456/neatHack/commit/10c7406723f285cc778b729863365713735e9191) · checkpoint `01M4KFYKQXFHME1HRZJVXJ7YT8` |
| Business plan (cfo.ai) | [`BUSINESS_PLAN.md`](./BUSINESS_PLAN.md) · [`plan.xlsx`](./plan.xlsx) |
| Upstream contribution | Found and fixed an exporter race in neatlogs: issue [#199](https://github.com/neatlogs/neatlogs/issues/199), PR [#203](https://github.com/neatlogs/neatlogs/pull/203) (open) |
| Build in public | [Post 1](https://x.com/sj909x/status/2108813809792299255) · [Post 2](https://x.com/sj909x/status/2108814094514204930) |

## The result

Same benchmark (`case_01_ledger_rounding`), same verifier, one recorded run before and one after the change. Both runs are in
[`benchmarks/verified_runs_ledger.json`](./benchmarks/verified_runs_ledger.json).

| | Before: v1 baseline | After: v4 graph-guarded |
| :--- | ---: | ---: |
| Run | `run_basel_case_01_le_948` | `run_graph_case_01_le_56698` |
| Total tokens | 31,093 | **946** |
| Attempts | 2 | **1** |
| Latency | 41,382 ms | **1,483 ms** |
| Model cost | $0.145479 | **$0.000298** |
| Outcome | verified | verified |

What changed: v1 reads whole files and guesses. v4 asks Entire Graph for the target symbol, its callers and the narrowest test,
and sends only those slices to a smaller model. This is one recorded comparison in which model routing and context strategy both
changed, not a statistical benchmark. Cases 02–04 have also been verified by v4; every run is listed in the ledger.

## Recovery from failure

Run `run_graph_case_01_le_24584` (open it from the Verify screen; its exported trace ID is `25c8f74e7cc8dd6260b36019dc8a6dfe`, and neatlogs ingestion was still processing recent traces when this was written) uses the built-in *caller trap*. Attempt 1 makes the
failing test pass but breaks a downstream caller. The guardrail catches it, the worktree is rolled back, the traceback goes to
the planner, and attempt 2 is verified: 2 attempts, 1 rollback, 2,195 tokens. Anyone can reproduce this on the live
workspace (*Run a benchmark* → enable *caller trap*).

## How each partner tool is used

| Tool | Role in VeriFix |
| :--- | :--- |
| **neatlogs** | Every run is a trace with WORKFLOW, AGENT, TOOL, RETRIEVER and GUARDRAIL spans. Root spans carry `neatlogs.workflow.*` attributes (case, mode, agent version, outcome, attempts, rollbacks, tokens), so runs can be filtered. The workspace reads traces back through the neatlogs MCP server (`verifix mcp-traces`, `/api/neatlogs-mcp`); the agent loop itself does not query MCP. The token and latency numbers above are recorded in these traces. |
| **Entire** | *Runtime:* Entire Graph finds the callers of the function being patched; that caller list is what the guardrail tests. *Development:* the build sessions are recorded as Entire checkpoints pushed with the repo. Checkpoints are provenance, not a runtime dependency. |
| **cfo.ai** | Planning. Measured per-run token cost feeds the unit economics in `plan.xlsx`. All plan figures are **projections**; `scripts/compute_plan_values.py` recalculates the workbook and a test fails if `BUSINESS_PLAN.md` drifts from it. |

## Timing disclosure

The repository's first five commits are timestamped **09:38–12:21 IST on 10 October**, before the official 12:30 PM IST start,
and one neatlogs trace dates from 00:25 IST that day. The history has not been rewritten. The Verify screen reports this live
from the GitHub API, flagged for judges to assess.

## Run it

```bash
pip install -r requirements-runtime.lock
export LITELLM_API_KEY=...  NEATLOGS_API_KEY=...      # neatlogs is optional; runs still work without it
PYTHONPATH=src python -m uvicorn verifix.server:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/#verify
```

Tests: `pytest tests/` (54 deterministic tests, including the judge-verification checks) and
`pytest benchmarks/test_suite.py` (18 integration tests that execute real agent runs).

## Limits

- Four fixed benchmark repositories are public. Running arbitrary repositories or code is operator-only.
- The live Lambda keeps run history in `/tmp`, which is recycled. Recorded runs are preserved in the release ledger.
- The quality evidence in [`QUALITY_REPORT.md`](./QUALITY_REPORT.md) separates what was executed from what was not (no
  penetration test and no production load test were performed).

Long-form technical reference: [`docs/TECHNICAL_REFERENCE.md`](./docs/TECHNICAL_REFERENCE.md).
