"""Run the controlled three-arm ablation and write benchmarks/ablation_experiment.json.

    PYTHONPATH=src python3 scripts/run_ablation.py --repeats 5

Resumable: pairs already in the output file are skipped. Arm order is shuffled per (case, repeat)
with a fixed seed so no arm always runs first. Every model call's model name is recorded.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix.ablation import ARMS, judge_full_suite, summarize  # noqa: E402
from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness  # noqa: E402
from verifix.config import TracedLLMClient  # noqa: E402


class RecordingLLM:
    """Delegates to the real client and remembers which model answered each call."""

    def __init__(self) -> None:
        self.inner = TracedLLMClient()
        self.calls: list[dict] = []

    def generate(self, *args, **kwargs):
        res = self.inner.generate(*args, **kwargs)
        self.calls.append({"model": res.model, "provider": res.provider, "prompt_tokens": res.prompt_tokens,
                           "completion_tokens": res.completion_tokens, "failover_count": res.failover_count})
        return res

    def __getattr__(self, name):
        return getattr(self.inner, name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--cases", default=",".join(BENCHMARK_CATALOG))
    ap.add_argument("--output", default=str(ROOT / "benchmarks" / "ablation_experiment.json"))
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--inject-fault", action="store_true",
                    help="inject the case's known caller-breaking patch on attempt 1 in every arm (fault-injection study)")
    a = ap.parse_args()
    out = Path(a.output)
    doc = json.loads(out.read_text()) if out.exists() else {"records": []}
    done = {(r["case_id"], r["repeat"], r["arm"]) for r in doc["records"]}
    rng = random.Random(a.seed)
    llm = RecordingLLM()
    harness = VeriFixAgentHarness(ROOT, llm_client=llm)
    for repeat in range(1, a.repeats + 1):
        for case_id in a.cases.split(","):
            order = list(ARMS)
            rng.shuffle(order)
            for arm in order:
                if (case_id, repeat, arm) in done:
                    continue
                llm.calls.clear()
                t0 = time.perf_counter()
                run = harness.execute_case(case_id=case_id, mode=arm,
                                           inject_caller_regression_on_attempt_1=a.inject_fault)
                wall = round((time.perf_counter() - t0) * 1000, 1)
                spec = BENCHMARK_CATALOG[case_id]
                judge = judge_full_suite(ROOT / spec["repo_subpath"], run.get("final_diff") or "")
                rec = {
                    "case_id": case_id, "repeat": repeat, "arm": arm, "run_id": run["run_id"],
                    "status": run.get("status"),
                    "agent_success": run.get("status") in ("VERIFIED_COMPLETE", "REPRO_PASSED_CALLERS_UNCHECKED"),
                    "attempts": run.get("current_attempt"), "rollbacks": run.get("rollbacks_executed"),
                    "prompt_tokens": run.get("prompt_tokens"), "completion_tokens": run.get("completion_tokens"),
                    "total_tokens": run.get("total_tokens"), "total_latency_ms": run.get("total_latency_ms"),
                    "wall_ms": wall, "cost_usd": float(run.get("accumulated_cost_usd") or 0.0),
                    "models": [c["model"] for c in llm.calls], "llm_calls": list(llm.calls),
                    "judge": judge, "injected_fault": a.inject_fault, "position_in_block": order.index(arm),
                    "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                doc["records"].append(rec)
                doc["summary"] = summarize(doc["records"])
                doc["design"] = {
                    "arms": {"target_only": "target file only; reproduction test only (caller-blind)",
                             "baseline_naive": "all Python files of the case repo; reproduction + caller tests",
                             "graph_guarded": "target file + Entire Graph caller list; reproduction + caller tests"},
                    "shared": "same single model call per attempt, prompt template, max 3 attempts, rollback on failure",
                    "injected_fault": ("attempt 1 uses the case's known caller-breaking patch in every arm" if a.inject_fault
                                       else "none"),
                    "judge": "final diff applied to a fresh copy of the case repo; entire pytest suite",
                    "order": f"arm order shuffled per (case, repeat) with seed {a.seed}",
                    "repeats": a.repeats,
                }
                out.write_text(json.dumps(doc, indent=1))
                print(json.dumps({k: rec[k] for k in ("case_id", "repeat", "arm", "status", "total_tokens", "attempts")}
                                 | {"judge": rec["judge"]["passed"], "models": rec["models"]}), flush=True)
    print(json.dumps(doc.get("summary", {}), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
