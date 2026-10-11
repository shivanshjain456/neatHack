#!/usr/bin/env python3
"""C9: pre-registered overfitting experiment (see docs/experiments/C9_PREREGISTRATION.md)."""

from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix.agent_harness import BENCHMARK_CATALOG  # noqa: E402
from verifix.assurance import dynamic_gates as dg  # noqa: E402
from verifix.assurance import static_gates as sg  # noqa: E402
from verifix.assurance.engine import load_spec, run_patch_assurance  # noqa: E402
from verifix.assurance.mutation import generate_mutants  # noqa: E402
from verifix.test_runner import SandboxedTestRunner  # noqa: E402

GROUND_TRUTH_SEED = 99
GROUND_TRUTH_INPUTS = 2000
GEN_SEED = 20261011
STATIC = {"scope", "api", "sast", "secrets", "symbols"}
GENERIC = STATIC | {"differential", "contracts", "determinism", "flaky", "performance", "coverage"}
FULL = GENERIC | {"relations"}


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def git_worktree(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=c9@verifix", "-c", "user.name=c9", "commit", "-q", "-m", "baseline"]):
        subprocess.run(cmd, cwd=dst, check=True, capture_output=True)
    return dst


def behaviour_jobs(case_id: str, target: str, ref_src: str, functions: list[str]):
    spec = load_spec(ROOT / "benchmarks" / "assurance_specs" / f"{case_id}.py")
    jobs, used = [], set()
    for q in functions:
        gen = getattr(spec, "INPUT_GENERATORS", {}).get(q) if spec else None
        drv = getattr(spec, "DRIVERS", {}).get(q) if spec else None
        if drv is not None and drv in used:
            continue
        if gen is not None:
            rng = random.Random(f"{GROUND_TRUTH_SEED}:{q}")
            inputs = [gen(rng) for _ in range(GROUND_TRUTH_INPUTS)]
        else:
            inputs, _why = dg.generic_inputs(ref_src, q, GROUND_TRUTH_INPUTS, GROUND_TRUTH_SEED)
            if inputs is None:
                continue
        job = {"mode": "call", "module": dg.module_name(target), "qualname": q, "inputs": inputs, "repeat": 1,
               "timeout_per_call": 1.0, "determinism_pass": False}
        if drv:
            job["driver_source"] = drv
            used.add(drv)
        jobs.append(job)
    return jobs


def observe(root: Path, jobs) -> list:
    out = []
    for job in jobs:
        r = dg.run_probe({**job, "root": str(root)}, timeout=300)
        if not r.get("probe_ok"):
            raise RuntimeError(f"ground-truth probe failed: {r.get('error')} {r.get('stderr', '')[:300]}")
        out.append([(x.get("ok"), x.get("value") if x.get("ok") else x.get("exc")) for x in r["results"]])
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "overfit_experiment.json"))
    ap.add_argument("--label", default="confirmatory")
    args = ap.parse_args()
    t0 = time.perf_counter()
    rows, per_case = [], {}
    for case_id, cat in BENCHMARK_CATALOG.items():
        target = cat["target_file"]
        tests = list(dict.fromkeys([cat["repro_test"], *cat["caller_tests"]]))
        original = (ROOT / cat["repo_subpath"] / target).read_text(encoding="utf-8")
        ref = (ROOT / "benchmarks" / "reference_fixes" / f"{case_id}.py").read_text(encoding="utf-8")
        changed_fns = sg.enclosing_functions(ref, sg.changed_line_numbers(original, ref))
        tree = __import__("ast").parse(ref)
        lines: set[int] = set()
        for q in changed_fns:
            node = dg._find_fn(tree, q)
            lines.update(range(node.lineno, node.end_lineno + 1))
        mutants, gen_stats = generate_mutants(ref, lines, filename=target, limit=10 ** 6, seed=GEN_SEED)
        tmp = Path(tempfile.mkdtemp(prefix="vfx_c9_"))
        try:
            wt = git_worktree(ROOT / cat["repo_subpath"], tmp / "wt")
            refwt = git_worktree(ROOT / cat["repo_subpath"], tmp / "ref")
            (refwt / target).write_text(ref, encoding="utf-8")
            jobs = behaviour_jobs(case_id, target, ref, changed_fns)
            ref_obs = observe(refwt, jobs)
            stats = {"mutants": len(mutants), "generation": gen_stats, "plausible": 0, "incorrect": 0, "equivalent": 0,
                     "functions": changed_fns, "ground_truth_jobs": len(jobs)}
            for m in mutants:
                (wt / target).write_text(m.source, encoding="utf-8")
                if not SandboxedTestRunner(wt).run_tests(tests, timeout=20)["passed"]:
                    continue
                stats["plausible"] += 1
                obs = observe(wt, jobs)
                diffs = sum(a != b for ja, jb in zip(ref_obs, obs) for a, b in zip(ja, jb))
                incorrect = diffs > 0
                stats["incorrect" if incorrect else "equivalent"] += 1
                rep = run_patch_assurance(wt, target, tests, SandboxedTestRunner,
                                          spec_file=ROOT / "benchmarks" / "assurance_specs" / f"{case_id}.py",
                                          mutation=False, minimality=False)
                blocking = set(rep["blocking_gates"])
                rows.append({"case_id": case_id, "mutant": m.mid, "operator": m.operator, "line": m.line,
                             "description": m.description, "incorrect": incorrect, "heldout_differences": diffs,
                             "blocking_gates": sorted(blocking),
                             "blocked": {"A_tests_only": False, "B_static": bool(blocking & STATIC),
                                         "C_generic": bool(blocking & GENERIC), "D_full": bool(blocking & FULL)}})
                print(f"{case_id} {m.mid} {m.operator:3} L{m.line:<3} {m.description[:28]:28} incorrect={incorrect!s:5} blocked_by={sorted(blocking)}", flush=True)
            per_case[case_id] = stats
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def arm_metrics(subset):
        res = {}
        for arm in ("A_tests_only", "B_static", "C_generic", "D_full"):
            inc = [r for r in subset if r["incorrect"]]
            eq = [r for r in subset if not r["incorrect"]]
            kd, kf = sum(r["blocked"][arm] for r in inc), sum(r["blocked"][arm] for r in eq)
            res[arm] = {"detected": kd, "incorrect": len(inc), "detection_rate": round(kd / len(inc), 4) if inc else None,
                        "detection_ci95": wilson(kd, len(inc)), "false_blocks": kf, "equivalent": len(eq),
                        "false_block_rate": round(kf / len(eq), 4) if eq else None, "false_block_ci95": wilson(kf, len(eq))}
        return res

    out = {
        "preregistration": "docs/experiments/C9_PREREGISTRATION.md",
        "label": args.label,
        "design": {"ground_truth_seed": GROUND_TRUTH_SEED, "ground_truth_inputs_per_function": GROUND_TRUTH_INPUTS,
                   "generator_seed": GEN_SEED, "arms": {"B_static": sorted(STATIC), "C_generic": sorted(GENERIC), "D_full": sorted(FULL)}},
        "per_case_counts": per_case,
        "pooled": arm_metrics(rows),
        "per_case": {c: arm_metrics([r for r in rows if r["case_id"] == c]) for c in per_case},
        "rows": rows,
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"pooled": out["pooled"], "counts": {c: {k: v for k, v in s.items() if k in ("mutants", "plausible", "incorrect", "equivalent")} for c, s in per_case.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
