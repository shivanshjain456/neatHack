"""Controlled ablation of VeriFix's context and verification strategy.

Three arms share one pipeline (the same single model call, prompt template, attempt limit and
rollback logic) and differ only in what the agent sees and how a patch is checked:

* ``target_only``    target file only; only the reproduction test is run (caller-blind)
* ``baseline_naive`` every Python file of the case repository; reproduction + caller tests
* ``graph_guarded``  target file + Entire Graph caller list; reproduction + caller tests

Each finished run is judged independently: the run's final diff is applied to a fresh copy of the
case repository and the case's *entire* test suite is run. The agent never sees this judge.
"""
from __future__ import annotations

import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ARMS = ("target_only", "baseline_naive", "graph_guarded")


def judge_full_suite(case_repo: Path, final_diff: str, timeout_s: int = 180) -> dict[str, Any]:
    """Apply ``final_diff`` to a fresh copy of ``case_repo`` and run its whole test suite."""
    with tempfile.TemporaryDirectory(prefix="verifix_judge_") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(case_repo, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        applied = False
        if final_diff.strip():
            patch = Path(tmp) / "final.diff"
            patch.write_text(final_diff if final_diff.endswith("\n") else final_diff + "\n", encoding="utf-8")
            proc = subprocess.run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=work,
                                  capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return {"passed": False, "patch_applied": False, "summary": f"git apply failed: {proc.stderr.strip()[:300]}"}
            applied = True
        try:
            proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=work,
                                  capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return {"passed": False, "patch_applied": applied, "summary": f"test suite timed out after {timeout_s}s"}
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
        return {"passed": proc.returncode == 0, "patch_applied": applied, "summary": lines[-1] if lines else ""}


def sign_test_p(wins: int, losses: int) -> float:
    """Exact two-sided binomial sign test (ties excluded)."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * tail), 6)


def geo_mean(values: Iterable[float]) -> float:
    vals = [v for v in values]
    if not vals or any(v <= 0 for v in vals):
        raise ValueError("geometric mean needs positive values")
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def bootstrap_ratio_ci(ratios: list[float], resamples: int = 10000, seed: int = 7) -> tuple[float, float]:
    """95% percentile interval for the geometric-mean ratio, resampling pairs with a fixed seed."""
    if not ratios:
        raise ValueError("no ratios")
    rng = random.Random(seed)
    logs = [math.log(r) for r in ratios]
    n = len(logs)
    means = sorted(math.exp(sum(logs[rng.randrange(n)] for _ in range(n)) / n) for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def cluster_bootstrap_ci(per_case_logs: dict[str, list[float]], resamples: int = 10000, seed: int = 7) -> tuple[float, float]:
    """95% interval resampling whole cases (repeats of one case are not independent evidence)."""
    case_means = [sum(v) / len(v) for v in per_case_logs.values() if v]
    if not case_means:
        raise ValueError("no cases")
    rng = random.Random(seed)
    n = len(case_means)
    means = sorted(math.exp(sum(case_means[rng.randrange(n)] for _ in range(n)) / n) for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-arm outcomes and paired comparisons of ``graph_guarded`` against each other arm."""
    by_key: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for r in records:
        by_key.setdefault((r["case_id"], r["repeat"]), {})[r["arm"]] = r
    arms: dict[str, Any] = {}
    for arm in ARMS:
        rs = [r for r in records if r["arm"] == arm]
        if not rs:
            continue
        arms[arm] = {
            "runs": len(rs),
            "judge_passed": sum(r["judge"]["passed"] for r in rs),
            "agent_reported_success": sum(r["agent_success"] for r in rs),
            "shipped_regressions": sum(r["agent_success"] and not r["judge"]["passed"] for r in rs),
            "mean_total_tokens": round(sum(r["total_tokens"] for r in rs) / len(rs), 1),
            "mean_latency_ms": round(sum(r["total_latency_ms"] for r in rs) / len(rs), 1),
            "mean_attempts": round(sum(r["attempts"] for r in rs) / len(rs), 2),
            "total_cost_usd": round(sum(r["cost_usd"] for r in rs), 6),
        }
    comparisons: dict[str, Any] = {}
    for other in ("baseline_naive", "target_only"):
        pairs = [(v["graph_guarded"], v[other]) for v in by_key.values() if "graph_guarded" in v and other in v]
        pairs = [(g, o) for g, o in pairs if g["total_tokens"] > 0 and o["total_tokens"] > 0]
        if not pairs:
            continue
        ratios = [g["total_tokens"] / o["total_tokens"] for g, o in pairs]
        lo, hi = bootstrap_ratio_ci(ratios)
        fewer = sum(g["total_tokens"] < o["total_tokens"] for g, o in pairs)
        more = sum(g["total_tokens"] > o["total_tokens"] for g, o in pairs)
        g_only = sum(g["judge"]["passed"] and not o["judge"]["passed"] for g, o in pairs)
        o_only = sum(o["judge"]["passed"] and not g["judge"]["passed"] for g, o in pairs)
        per_case: dict[str, list[float]] = {}
        for g, o in pairs:
            per_case.setdefault(g["case_id"], []).append(math.log(g["total_tokens"] / o["total_tokens"]))
        clo, chi = cluster_bootstrap_ci(per_case)
        case_level = [math.exp(sum(v) / len(v)) for v in per_case.values()]
        comparisons[f"graph_guarded_vs_{other}"] = {
            "pairs": len(pairs),
            "cases": len(per_case),
            "token_ratio_geo_mean": round(geo_mean(ratios), 4),
            "token_ratio_ci95_pairs": [round(lo, 4), round(hi, 4)],
            "token_ratio_ci95_cases": [round(clo, 4), round(chi, 4)],
            "token_ratio_by_case": {c: round(math.exp(sum(v) / len(v)), 4) for c, v in sorted(per_case.items())},
            "cases_graph_cheaper": sum(r < 1 for r in case_level),
            "cases_graph_costlier": sum(r > 1 for r in case_level),
            "graph_fewer_tokens_pairs": fewer,
            "graph_more_tokens_pairs": more,
            "token_sign_test_p": sign_test_p(fewer, more),
            "judge_pass_only_graph": g_only,
            "judge_pass_only_other": o_only,
            "judge_sign_test_p": sign_test_p(g_only, o_only),
        }
    return {"arms": arms, "comparisons": comparisons}
