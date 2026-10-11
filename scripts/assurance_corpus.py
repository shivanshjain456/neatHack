#!/usr/bin/env python3
"""Replay every distinct LLM-generated patch in the VeriFix run store through the assurance engine.

The run store (``.verifix_runtime/verifix_state.db``) records each patch attempt the agent made, and
whether the harness's repro + caller tests passed. This script asks a narrower question: of the
patches the harness accepted, how many would the assurance gates have blocked, and why? It is
measurement only. Nothing in the store is modified.

Output: ``benchmarks/assurance_corpus.json`` (per-patch verdicts plus summary).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix.agent_harness import BENCHMARK_CATALOG  # noqa: E402
from verifix.assurance.engine import run_patch_assurance  # noqa: E402
from verifix.test_runner import SandboxedTestRunner  # noqa: E402


def load_patches(db: Path) -> list[dict]:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT p.patch_id, p.run_id, p.attempt_num, p.target_file, p.unified_diff, p.repro_test_passed,
                  p.caller_tests_passed, p.rolled_back, p.rollback_reason, p.created_at, r.case_id, r.mode
           FROM patches p JOIN runs r USING(run_id) ORDER BY p.created_at"""
    ).fetchall()
    out, seen = [], set()
    for r in rows:
        diff = (r["unified_diff"] or "").strip()
        if r["case_id"] not in BENCHMARK_CATALOG or not diff:
            continue
        key = (r["case_id"], hashlib.sha256(diff.encode()).hexdigest())
        if key in seen:
            continue
        seen.add(key)
        out.append({**dict(r), "unified_diff": diff + "\n", "diff_sha256": key[1]})
    return out


def worktree_for(case_id: str, tmp: Path) -> Path:
    cat = BENCHMARK_CATALOG[case_id]
    wt = tmp / "wt"
    shutil.copytree(ROOT / cat["repo_subpath"], wt, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=corpus@verifix", "-c", "user.name=corpus", "commit", "-q", "-m", "baseline"]):
        subprocess.run(cmd, cwd=wt, check=True, capture_output=True)
    return wt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / ".verifix_runtime" / "verifix_state.db"))
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "assurance_corpus.json"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    patches = load_patches(Path(args.db))
    if args.limit:
        patches = patches[: args.limit]
    records = []
    t0 = time.perf_counter()
    for i, p in enumerate(patches, 1):
        cat = BENCHMARK_CATALOG[p["case_id"]]
        tmp = Path(tempfile.mkdtemp(prefix="vfx_corpus_"))
        try:
            wt = worktree_for(p["case_id"], tmp)
            ap_res = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], input=p["unified_diff"], text=True,
                                    cwd=wt, capture_output=True)
            if ap_res.returncode != 0:
                records.append({"patch_id": p["patch_id"], "case_id": p["case_id"], "apply_error": ap_res.stderr.strip()[:300]})
                continue
            tests = list(dict.fromkeys([cat["repro_test"], *cat["caller_tests"]]))
            runner = SandboxedTestRunner(wt)
            tests_now = runner.run_tests(tests, timeout=60)
            spec = ROOT / "benchmarks" / "assurance_specs" / f"{p['case_id']}.py"
            rep = run_patch_assurance(wt, cat["target_file"], tests, SandboxedTestRunner, spec_file=spec)
            records.append({
                "patch_id": p["patch_id"], "run_id": p["run_id"], "attempt": p["attempt_num"], "case_id": p["case_id"],
                "mode": p["mode"], "created_at": p["created_at"], "diff_sha256": p["diff_sha256"],
                "harness_recorded": {"repro_passed": bool(p["repro_test_passed"]), "callers_passed": bool(p["caller_tests_passed"]),
                                     "rolled_back": bool(p["rolled_back"]), "reason": p["rollback_reason"]},
                "tests_now_pass": bool(tests_now["passed"]),
                "assurance": {"verdict": rep["verdict"], "blocking_gates": rep["blocking_gates"], "strength": rep["strength"],
                              "duration_ms": rep["duration_ms"],
                              "gates": {g["gate"]: g["status"] for g in rep["gates"]},
                              "blocking_findings": [{"gate": g["gate"], **f} for g in rep["gates"] if g["blocking"] for f in g["findings"][:2]]},
            })
            print(f"[{i}/{len(patches)}] {p['case_id']} {p['patch_id'][:10]} tests={tests_now['passed']} -> {rep['verdict']} "
                  f"{rep['blocking_gates']} {rep['strength']['grade']} {rep['duration_ms']:.0f}ms", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    ok = [r for r in records if "assurance" in r]
    accepted = [r for r in ok if r["tests_now_pass"]]
    blocked_after_tests = [r for r in accepted if r["assurance"]["verdict"] == "BLOCKED"]
    rejected = [r for r in ok if not r["tests_now_pass"]]
    summary = {
        "distinct_patches": len(records), "replayed": len(ok), "apply_errors": len(records) - len(ok),
        "test_passing_patches": len(accepted),
        "test_passing_but_blocked": len(blocked_after_tests),
        "blocked_share_of_test_passing": round(len(blocked_after_tests) / len(accepted), 4) if accepted else None,
        "blocking_gate_counts": dict(Counter(g for r in blocked_after_tests for g in r["assurance"]["blocking_gates"])),
        "test_failing_patches": len(rejected),
        "test_failing_also_blocked": sum(r["assurance"]["verdict"] == "BLOCKED" for r in rejected),
        "strength_of_passed": dict(Counter(r["assurance"]["strength"]["grade"] for r in accepted if r["assurance"]["verdict"] == "PASSED")),
        "per_case": {c: {"test_passing": sum(r["case_id"] == c for r in accepted),
                         "blocked": sum(r["case_id"] == c for r in blocked_after_tests)} for c in sorted({r["case_id"] for r in ok})},
        "median_assurance_ms": sorted(r["assurance"]["duration_ms"] for r in ok)[len(ok) // 2] if ok else None,
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    out = {"generated_by": "scripts/assurance_corpus.py", "source": "patches table of the VeriFix run store (LLM-generated attempts)",
           "note": "Measurement only; tests_now_pass re-runs the case's repro + caller tests on the replayed patch.",
           "summary": summary, "records": records}
    Path(args.out).write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
