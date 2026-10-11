# Skill: VeriFix

Use when asked to repair a defect without breaking its dependents, to verify a
patch against caller contracts, or to inspect VeriFix evidence.

## Setup

```bash
pip install git+https://github.com/shivanshjain456/neatHack
```

Live model commands need `GEMINI_API_KEY` or `LITELLM_API_KEY`+`LITELLM_BASE_URL`;
`mcp-traces` needs `NEATLOGS_API_KEY`+`NEATLOGS_ENDPOINT`. Offline commands need none.

## Workflow

1. `verifix run --case <case> --mode graph_guarded --json` — guarded repair.
2. Read the JSON: `status`, `rollbacks_executed`, `caller_regressions_caught`.
3. If `INTERRUPTED_CHECKPOINTED`, continue with `verifix resume --run-id <id> --json`.
4. Cite evidence from `benchmarks/receipts/index.json` (hashed receipts) and
   `benchmarks/cost_caps.json` (measured caps), never from memory.

## Guardrails

- Public runs are capped at $0.25 model budget; attempts are explicit, never auto-retried.
- Only the four catalogued cases are public; custom targets are operator-only.
- A passing test is half the story: verified = reproduction + caller contracts.
- Honest limits: read `docs/KNOWN_LIMITS.md` before claiming coverage.
