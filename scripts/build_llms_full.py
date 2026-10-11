"""Assemble docs/llms-full.txt from the agent quickstart, limits and receipt format.

Single source: the committed llms-full.txt must equal this builder's output,
enforced by tests/test_release_artifacts.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

RECEIPT_FIELDS = [
    ("receipt_id", "VF-<utc stamp>-<case>, stable per run"),
    ("run_id / case_id / mode", "identity of the recorded run"),
    ("status", "the proof outcome, verbatim from the ledger"),
    ("attempts / rollbacks", "how many tries, how many guardrail rollbacks"),
    ("total_tokens / latency_ms", "measured usage"),
    ("priced_usd / cap_usd / cap_used_pct", "the receipt: cost, configured cap, share used"),
    ("sha256", "sha256 of the canonical JSON of every other field"),
]


def build() -> str:
    agent = (ROOT / "docs" / "agent.md").read_text(encoding="utf-8")
    limits = (ROOT / "docs" / "KNOWN_LIMITS.md").read_text(encoding="utf-8")
    fields = "\n".join(f"- `{k}` — {v}" for k, v in RECEIPT_FIELDS)
    return (
        "# VeriFix llms-full\n\n"
        "agent.md, the known limits and the receipt format in one file.\n\n"
        + agent.strip()
        + "\n\n"
        + limits.strip()
        + "\n\n## Receipt and caps format\n\n"
        "Every recorded run has one receipt in benchmarks/receipts/; the index is\n"
        "benchmarks/receipts/index.json and the measured caps are benchmarks/cost_caps.json.\n\n"
        + fields
        + "\n"
    )


def main() -> int:
    (ROOT / "docs" / "llms-full.txt").write_text(build(), encoding="utf-8")
    print("wrote docs/llms-full.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
