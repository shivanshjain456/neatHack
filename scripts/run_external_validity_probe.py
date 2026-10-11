"""Exploratory external-validity probe: a held-out case NOT in the headline 4-case catalog.

Runs the same three-arm controlled pipeline (identical model call, prompt, attempt limit and
rollback logic) on ``case_05_event_idempotency`` — a new failure class (at-least-once delivery /
dedup-key correctness) — and writes ``benchmarks/external_validity_probe.json``.

The case spec is injected into ``BENCHMARK_CATALOG`` *at runtime only*; the committed catalog,
the ``/api/workspace`` benchmark list and every deterministic test remain at four cases, so this
probe is strictly additive and cannot disturb the published experiment.

    PYTHONPATH=src python3 scripts/run_external_validity_probe.py --repeats 3
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "src"))

from verifix.ablation import ARMS, judge_full_suite, summarize  # noqa: E402
from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness  # noqa: E402
from verifix.config import TracedLLMClient  # noqa: E402

CASE_ID = "case_05_event_idempotency"

CASE_SPEC = {
    "case_id": CASE_ID,
    "title": "Event Ingestion Idempotency & Dedup-Key Correctness (held-out probe)",
    "repo_subpath": f"benchmarks/repos/{CASE_ID}",
    "target_file": "events/ingest.py",
    "target_symbol": "process_events",
    "repro_test": "tests/test_ingest.py",
    "caller_tests": ["tests/test_aggregate.py", "tests/test_reconcile.py"],
    "goal": (
        "At-least-once delivery redelivers events: a retry carries the same `event_id`. Fix "
        "`process_events` in `events/ingest.py` so each distinct `event_id` is counted exactly once "
        "(first occurrence wins), returning `{'total_cents', 'count', 'events'}` over the "
        "deduplicated list. Two different `event_id`s with an identical payload are distinct events "
        "and must BOTH be counted; deduplicate on `event_id` only, never on the payload."
    ),
    "caller_trap_patch": (
        '"""Caller-trap: dedups by payload instead of event_id; passes the repro but drops a distinct event."""\n'
        "from typing import Any\nimport json\n\n"
        "def process_events(events: list[dict[str, Any]]) -> dict[str, Any]:\n"
        "    seen: list[dict[str, Any]] = []\n    keys: set[str] = set()\n    total = 0\n"
        "    for ev in events:\n        key = json.dumps(ev['payload'], sort_keys=True)\n"
        "        if key in keys:\n            continue\n"
        "        keys.add(key); seen.append(ev); total += ev['amount_cents']\n"
        "    return {'total_cents': total, 'count': len(seen), 'events': seen}\n"
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--inject-fault", action="store_true",
                    help="plant the payload-dedup caller trap on attempt 1 in every arm")
    ap.add_argument("--output", default=str(ROOT / "benchmarks" / "external_validity_probe.json"))
    ap.add_argument("--seed", type=int, default=20261011)
    a = ap.parse_args()

    BENCHMARK_CATALOG[CASE_ID] = CASE_SPEC  # runtime-only injection

    out = Path(a.output)
    doc = json.loads(out.read_text()) if out.exists() else {"records": []}
    done = {(r["repeat"], r["arm"], r.get("injected_fault")) for r in doc["records"]}
    rng = random.Random(a.seed)
    harness = VeriFixAgentHarness(ROOT, llm_client=TracedLLMClient())
    repo = ROOT / CASE_SPEC["repo_subpath"]

    for repeat in range(1, a.repeats + 1):
        order = list(ARMS)
        rng.shuffle(order)
        for arm in order:
            if (repeat, arm, a.inject_fault) in done:
                continue
            t0 = time.perf_counter()
            run = harness.execute_case(case_id=CASE_ID, mode=arm,
                                       inject_caller_regression_on_attempt_1=a.inject_fault)
            judge = judge_full_suite(repo, run.get("final_diff") or "")
            rec = {
                "case_id": CASE_ID, "repeat": repeat, "arm": arm, "run_id": run.get("run_id"),
                "status": run.get("status"),
                "agent_success": run.get("status") in ("VERIFIED_COMPLETE", "REPRO_PASSED_CALLERS_UNCHECKED"),
                "attempts": run.get("current_attempt"), "rollbacks": run.get("rollbacks_executed"),
                "prompt_tokens": run.get("prompt_tokens"), "total_tokens": run.get("total_tokens"),
                "total_latency_ms": run.get("total_latency_ms") or round((time.perf_counter() - t0) * 1000, 1),
                "cost_usd": float(run.get("accumulated_cost_usd") or 0.0),
                "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
                "judge": judge, "judge_passed": judge["passed"],
                "injected_fault": a.inject_fault,
                "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            doc["records"].append(rec)
            doc["summary"] = summarize(doc["records"])
            doc["design"] = {
                "purpose": "held-out external-validity probe; new failure class (dedup-key correctness)",
                "arms": dict(ARMS_DESC), "repeats": a.repeats,
                "injected_fault": a.inject_fault,
                "judge": "final diff applied to a fresh copy; entire pytest suite",
                "note": "case injected at runtime; committed catalog stays at 4 cases",
            }
            out.write_text(json.dumps(doc, indent=1))
            print(json.dumps({k: rec[k] for k in ("repeat", "arm", "status", "total_tokens", "judge_passed")}),
                  flush=True)
    print(json.dumps(doc.get("summary", {}), indent=1))
    return 0


ARMS_DESC = {
    "target_only": "target file only; reproduction test only (caller-blind)",
    "baseline_naive": "all Python files; reproduction + caller tests",
    "graph_guarded": "target file + caller list; reproduction + caller tests",
}


if __name__ == "__main__":
    raise SystemExit(main())
