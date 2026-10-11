"""Patch assurance: run every gate on a candidate patch and produce one auditable report.

Verdict
    ``BLOCKED`` if any gate reports a blocking failure (the harness rolls the patch back and feeds
    the findings to the next attempt), otherwise ``PASSED``.

Verification strength (reported, never used to fake a pass)
    ``strong``    mutation score >= 0.80 and diff coverage >= 0.80
    ``moderate``  mutation score >= 0.50 and diff coverage >= 0.50
    ``weak``      otherwise, or when mutation testing could not run
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from verifix.assurance import dynamic_gates as dg
from verifix.assurance import static_gates as sg

ENGINE_VERSION = "1.0.0"


def _git(worktree: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=worktree, capture_output=True, text=True, timeout=30, check=True).stdout


def changed_files(worktree: Path) -> list[str]:
    out = set(_git(worktree, "diff", "--name-only", "HEAD").split())
    for line in _git(worktree, "status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].strip()
        if path and "__pycache__" not in path and not path.endswith(".pyc"):
            out.add(path)
    return sorted(out)


IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", ".verifix_runtime"}


def _tree_files(root: Path) -> dict[str, str]:
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and not (IGNORED_PARTS & set(p.relative_to(root).parts)) and p.suffix != ".pyc":
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def changed_files_vs_baseline(baseline: Path, worktree: Path) -> list[str]:
    """Files added, removed or modified relative to a pristine baseline copy (no git needed)."""
    a, b = _tree_files(baseline), _tree_files(worktree)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def original_source(worktree: Path, rel: str) -> str:
    try:
        return _git(worktree, "show", f"HEAD:{rel}")
    except subprocess.CalledProcessError:
        return ""


def load_spec(spec_file: Path | None):
    if spec_file is None or not spec_file.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"vfx_spec_{spec_file.stem}", spec_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_runner(test_runner_cls):
    def run(root: Path, targets: list[str], timeout: float, hash_seed: str = "0") -> dict[str, Any]:
        r = test_runner_cls(root)
        r.hash_seed = hash_seed
        return r.run_tests(targets, timeout=timeout)
    return run


def strength(mutation: dict[str, Any] | None, coverage: dict[str, Any] | None) -> dict[str, Any]:
    ms = (mutation or {}).get("score")
    dc = (coverage or {}).get("diff_coverage")
    if ms is None or dc is None:
        grade = "weak"
    elif ms >= 0.8 and dc >= 0.8:
        grade = "strong"
    elif ms >= 0.5 and dc >= 0.5:
        grade = "moderate"
    else:
        grade = "weak"
    return {"grade": grade, "mutation_score": ms, "diff_coverage": dc,
            "rule": "strong: mutation>=0.80 and diff coverage>=0.80; moderate: both>=0.50; otherwise weak"}


def run_patch_assurance(worktree: Path, target_file: str, tests: list[str], test_runner_cls,
                        spec_file: Path | None = None, allowed_files: list[str] | None = None,
                        mutation_limit: int = 40, fuzz_inputs: int = 300, minimality: bool = True,
                        mutation: bool = True, baseline_dir: Path | None = None,
                        flaky_registry: Any = None) -> dict[str, Any]:
    """Run all gates on the patch currently applied in ``worktree``.

    The unpatched state comes from ``baseline_dir`` (a pristine copy, as kept by WorktreeManager)
    when given, otherwise from the worktree's git HEAD.
    """
    t0 = time.perf_counter()
    worktree = Path(worktree).resolve()
    run_tests = make_runner(test_runner_cls)
    if baseline_dir is not None and Path(baseline_dir).is_dir():
        files = changed_files_vs_baseline(Path(baseline_dir), worktree)
        base_file = Path(baseline_dir) / target_file
        original = base_file.read_text(encoding="utf-8") if base_file.is_file() else ""
    else:
        files = changed_files(worktree)
        original = original_source(worktree, target_file)
    patched = (worktree / target_file).read_text(encoding="utf-8")
    changed = sg.changed_line_numbers(original, patched)
    functions = sg.enclosing_functions(patched, changed)
    spec = load_spec(spec_file)

    gates: list[sg.GateResult] = []

    def timed(fn, *a, **k):
        s = time.perf_counter()
        g = fn(*a, **k)
        if isinstance(g, sg.GateResult) and not g.duration_ms:
            g.duration_ms = round((time.perf_counter() - s) * 1000, 1)
        return g

    scope = timed(sg.gate_scope, files, allowed_files or [target_file])
    if not changed:
        scope.status, scope.blocking = "fail", True
        scope.summary = f"The patch makes no change to {target_file}; there is nothing to verify."
        scope.findings.append({"rule": "EMPTY_PATCH", "severity": "high", "message": "no lines changed in the target file",
                               "line": None, "snippet": target_file})
    gates.append(scope)
    gates.append(timed(sg.gate_api, original, patched, worktree, target_file))
    gates.append(timed(sg.gate_sast, original, patched))
    gates.append(timed(sg.gate_secrets, original, patched))
    gates.append(timed(sg.gate_symbols, original, patched, worktree))
    gates.append(timed(sg.gate_complexity, original, patched))
    static_block = any(g.blocking for g in gates)

    coverage_metrics: dict[str, Any] | None = None
    mutation_metrics: dict[str, Any] | None = None
    if not static_block:
        tmp = Path(tempfile.mkdtemp(prefix="vfx_base_"))
        try:
            baseline = dg.copy_tree(worktree, tmp / "baseline")
            (baseline / target_file).write_text(original, encoding="utf-8")
            gates.extend(dg.gate_differential(baseline, worktree, target_file, functions, spec, n_inputs=fuzz_inputs))
            cov_gate, _raw = dg.gate_coverage(worktree, target_file, tests, changed)
            gates.append(cov_gate)
            coverage_metrics = cov_gate.metrics
            gates.append(dg.gate_flaky(worktree, tests, run_tests, flaky_registry))
            if mutation:
                mg = dg.gate_mutation(worktree, target_file, tests, changed, run_tests, limit=mutation_limit)
                gates.append(mg)
                mutation_metrics = mg.metrics if mg.status != "skipped" else None
            if minimality:
                gates.append(dg.gate_minimality(worktree, target_file, original, tests, run_tests))
            if spec is not None and getattr(spec, "__file__", None):
                gates.append(gate_relations(worktree, Path(spec.__file__)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    blocking = [g for g in gates if g.blocking]
    report = {
        "engine": "verifix-assurance", "engine_version": ENGINE_VERSION,
        "verdict": "BLOCKED" if blocking else "PASSED",
        "blocking_gates": [g.gate for g in blocking],
        "strength": strength(mutation_metrics, coverage_metrics),
        "target_file": target_file, "changed_files": files, "changed_lines": sorted(changed),
        "changed_functions": functions, "verifying_tests": tests,
        "patch_sha256": hashlib.sha256(patched.encode()).hexdigest(),
        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "gates": [g.as_dict() for g in gates],
        "terms_exercised": sorted({t for g in gates if g.status != "skipped" for t in g.terms}),
        "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    return report


def gate_relations(worktree: Path, spec_file: Path, trials: int = 200, seed: int = 20261011) -> sg.GateResult:
    """Metamorphic relations and contracts declared in the case's assurance spec."""
    t0 = time.perf_counter()
    res = dg.run_probe({"mode": "relations", "root": str(worktree), "spec_file": str(spec_file), "trials": trials, "seed": seed}, timeout=180)
    terms = ["metamorphic-testing", "property-based-testing", "design-by-contract"]
    if not res.get("probe_ok"):
        return sg.GateResult("relations", "Declared metamorphic relations and contracts", terms, "skipped", False,
                             f"Relation probe failed: {res.get('error')}", {})
    rels = res["relations"]
    failed = [r for r in rels if r["status"] != "pass"]
    findings = [{"rule": "RELATION_VIOLATED", "severity": "high", "message": f"{r['name']}: {r.get('doc','')}",
                 "line": None, "snippet": r.get("counterexample", "")[:240]} for r in failed]
    return sg.GateResult("relations", "Declared metamorphic relations and contracts", terms,
                         "fail" if failed else "pass", bool(failed),
                         (f"{len(failed)} of {len(rels)} declared relation(s) violated." if failed else
                          f"All {len(rels)} declared relation(s) held over {sum(r['trials'] for r in rels)} generated trials."),
                         {"relations": rels, "seed": seed}, findings, round((time.perf_counter() - t0) * 1000, 1))


def summarize(report: dict[str, Any]) -> str:
    """One-paragraph feedback for the next agent attempt when a patch is blocked."""
    lines = [f"ASSURANCE_GATES_BLOCKED: {', '.join(report['blocking_gates'])}"]
    for g in report["gates"]:
        if g["blocking"]:
            lines.append(f"- {g['title']}: {g['summary']}")
            for f in g["findings"][:3]:
                lines.append(f"  * {f['rule']}: {f['message']}" + (f" [{f['snippet']}]" if f.get("snippet") else ""))
    return "\n".join(lines)


def report_digest(report: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(report, sort_keys=True, default=str).encode()).hexdigest()
