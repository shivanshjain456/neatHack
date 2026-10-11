# VeriFix agent quickstart

VeriFix is a blast-radius-aware repair agent: it maps downstream callers before
patching, checks the patch against the bug and the caller contracts, and rolls
back when a contract breaks. This page is the agent entry point. A human
quickstart lives in the README; the honest limits live in KNOWN_LIMITS.md.

## Preflight

1. Python 3.10–3.13, git, and disk for a clone.
2. Offline commands (`cfo-model`, `--help`, report inspection) need no keys.
3. Live model commands need one provider key: `GEMINI_API_KEY` or
   `LITELLM_API_KEY` + `LITELLM_BASE_URL`. `mcp-traces` needs
   `NEATLOGS_API_KEY` + `NEATLOGS_ENDPOINT`. `selftest` additionally needs the
   AWS + Entire environment. Missing keys fail with a clear error; nothing is
   silently skipped.

## Install

```bash
pip install git+https://github.com/shivanshjain456/neatHack
verifix --help
```

The package installs the `verifix` CLI with eleven subcommands:
`run, resume, experiment, mcp-traces, cfo-model, serve, selftest,
fix-custom, auto-fix, entire-intelligence, dispatch-incident`
(see `verifix --help` for the live list).

## Commands (all emit JSON with `--json`)

```bash
# A guarded repair run on a catalogued benchmark case (billable; capped).
verifix run --case case_01_ledger_rounding --mode graph_guarded --json

# Stress the guardrail: attempt 1 ships a caller-breaking patch on purpose.
verifix run --case case_02_ratelimiter_state --inject-caller-trap --json

# Pause after reproduction to inspect the SQLite WAL checkpoint, then resume.
verifix run --case case_03_webhook_validator --interrupt-after REPRODUCING --json
verifix resume --run-id <run_id> --json

# The controlled before/after telemetry experiment (billable).
verifix experiment --case case_01_ledger_rounding --json

# Read live traces back over the neatlogs MCP (read-only).
verifix mcp-traces --limit 10 --json

# Recompute the cfo.ai model offline from versioned telemetry.
verifix cfo-model --output model.json

# Mission-control API server (the public deployment runs this on Lambda).
verifix serve --host 0.0.0.0 --port 8000
```

## Statuses you will see

- `VERIFIED_COMPLETE` — patch passed reproduction and caller-contract checks.
- `REPRO_PASSED_CALLERS_UNCHECKED` — fixed and reproduced; caller graph empty or unchecked.
- `INTERRUPTED_CHECKPOINTED` — paused; resumable with `verifix resume`.
- HTTP 400 `Unknown case_id` — the public API only accepts the four catalogued cases.

## Safety rules

1. Public runs are capped at the configured model budget ($0.25 per run on the
   live deployment); a run is refused past it. Every run ends with a receipt:
   priced, cap, cap used, proof status (`benchmarks/receipts/index.json`).
2. Arbitrary repositories and uploaded code are operator-only (bearer token).
   A temp folder is not a security sandbox, so the public surface offers only
   the four catalogued benchmark repositories.
3. Requests are never automatically retried; attempts are explicit and counted.
4. Fault injection (`--inject-caller-trap`) is a controlled test, not a
   production failure; reports say so.
5. A passing test is only half the story: verified means reproduction plus
   caller contracts, with the evidence kept.

## Where the evidence lives

- `benchmarks/receipts/index.json` — one priced, hashed receipt per recorded run.
- `benchmarks/cost_caps.json` — how the cap relates to measured run costs.
- `docs/llms.txt` and `docs/llms-full.txt` — agent-readable index and full text.
- `docs/comparison.md` — the measured numbers against target-file-only,
  whole-repository and tests-only approaches, with the deliberate non-claims.
- `evidence/README.md` — numbered, linked evidence per required tool
  (neatlogs, Entire, cfo.ai).
- `skills/verifix/SKILL.md` — copyable agent skill folder.
- The dashboard's `#verify` view maps every claim to an official judging weight.
