# AGENTS.md — building and testing this repository

<!-- entire-agent:begin -->
Read .entire/agent-guide.md for this repository's workflow, source inspection, and verification guidance.
@.entire/agent-guide.md
<!-- entire-agent:end -->

## Layout

- `src/verifix/` — the product: `server.py` (FastAPI mission control), `agent_harness.py`
  (guarded repair loop), `graph_engine.py` (Entire Graph caller context), `assurance/`
  (patch gates), `dashboard.py` + `web/` (single-source UI), `cli.py` (eleven subcommands).
- `tests/` — the offline deterministic suite (170 tests, no network, no keys).
- `benchmarks/` — versioned evidence: `verified_runs_ledger.json`, `receipts/` (one
  priced, sha256-hashed receipt per run), `cost_caps.json`, the controlled experiment,
  assurance corpus, security experiments, `test_suite.py` (the independent judge).
- `scripts/` — gates and generators: `verify_claims.py`, `verify_zero_tolerance.py`,
  `compute_plan_values.py`, `supply_chain.py`, `deploy_ui_release.py`, `jury_selftest.py`.
- `docs/` — GitHub Pages: `index.html` (generated), `agent.md`, `llms.txt`,
  `llms-full.txt`, `KNOWN_LIMITS.md`, `EVALUATION.md`, `SUPPLY_CHAIN.md`,
  `TECHNICAL_REFERENCE.md`, `comparison.md`, `experiments/`.
- `evidence/` — per-tool curated evidence index (neatlogs, Entire, cfo.ai).
- `video/` — v2 repo demo (2:18) and the v3 Remotion pipeline (submission cut 2:58).

## Setup

```bash
python3 -m pip install -r requirements-runtime.lock   # runtime deps, hash-checked
python3 -m pip install -r requirements-dev.lock       # + pytest, hypothesis
```

## Gates (run all three before every commit)

```bash
python3 -m pytest -q tests/                 # 170 passed; deterministic, offline
python3 scripts/verify_claims.py            # 43 claims recomputed from raw records; 0 failures
python3 scripts/verify_zero_tolerance.py    # forbidden patterns across src/ and benchmarks/*.py
```

CI re-runs these on every push (plus supply-chain and deploy gates). If a number in a
doc drifts from the raw run records, `verify_claims.py` fails — edit the records or the
prose together, never one alone.

## Invariants a coding agent must respect

1. **Single-source UI.** `docs/index.html` is generated. Edit `src/verifix/web/app.js`,
   `app.css`, `index.html`, then regenerate with `verifix.dashboard.build_dashboard()`
   (the deploy script does this too). `tests/test_web_release.py` fails if the committed
   HTML differs from the build, or if `app.js` has a syntax error.
2. **No secrets in the repo.** Keys live only in the operator env file; the deploy embeds
   them into the Lambda bundle, never into git. `verify_zero_tolerance.py` fails on
   hardcoded key patterns, TODOs, stubs and silent excepts.
3. **Receipts are append-only evidence.** A recorded run gets one receipt in
   `benchmarks/receipts/` whose `sha256` covers every other field; `index.json` carries
   the ledger hash. Do not edit historical receipts.
4. **Retired figures stay retired, labelled.** The handicapped 31,093→946 comparison and
   its wrong patch are history with a correction note, not headlines (README + EVALUATION).
5. **Deploys only through `scripts/deploy_ui_release.py`.** It verifies SLSA provenance,
   keeps a rollback package, and smoke-gates the live URL (HTML byte-match, workspace,
   anonymous-execution 403, health, judge-proof 7/7), rolling back automatically on failure.
6. **Public runs are capped.** The anonymous API offers four catalogued cases, refuses
   unknown `case_id` with HTTP 400, and caps each run at the configured model budget.

## Agent entry points

- `docs/agent.md` — preflight, install, commands with `--json`, statuses, safety rules.
- `docs/llms.txt` / `docs/llms-full.txt` — agent-readable index and full text.
- `skills/verifix/SKILL.md` — copyable Agent Skill folder.
- The dashboard `#verify` view maps every submission claim to an official judging weight
  and re-checks LIVE items on load.
