"""Integrity gates for the agent-facing release artifacts.

Receipts must re-verify their hashes, the caps file must match the ledger, and
the committed llms-full.txt must equal its builder (single source).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_llms_full
import make_receipts


def test_receipts_reverify_and_match_ledger():
    ledger = json.loads(make_receipts.LEDGER.read_text())
    index = json.loads((ROOT / "benchmarks" / "receipts" / "index.json").read_text())
    assert index["count"] == len(ledger["runs"])
    assert len(index["rows"]) == len(ledger["runs"])
    for row in index["rows"]:
        rec = json.loads((ROOT / "benchmarks" / "receipts" / f"{row['run_id']}.json").read_text())
        payload = {k: v for k, v in rec.items() if k != "sha256"}
        assert make_receipts.sha_obj(payload) == rec["sha256"] == row["sha256"]
        assert 0 <= rec["cap_used_pct"] <= 100


def test_cost_caps_match_ledger():
    ledger = json.loads(make_receipts.LEDGER.read_text())
    committed = json.loads(make_receipts.CAPS_FILE.read_text())
    fresh = make_receipts.build_caps(ledger["runs"])
    assert committed == fresh
    assert committed["measured_usd"]["p90"] < committed["configured_public_cap_usd"]


def test_receipts_rebuild_is_stable():
    assert make_receipts.build() == {
        rel: (ROOT / rel).read_text() for rel in make_receipts.build()
    }


def test_llms_full_single_source():
    assert (ROOT / "docs" / "llms-full.txt").read_text() == build_llms_full.build()
    text = (ROOT / "docs" / "llms-full.txt").read_text()
    assert "verifix run" in text and "Known limits" in text and "sha256" in text
