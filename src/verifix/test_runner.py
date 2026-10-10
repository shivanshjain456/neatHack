"""Sandboxed pytest / Python test execution tool for defect reproduction and blast-radius regression checks."""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import neatlogs


_STDLIB_RUNNER_SCRIPT = """
import importlib.util, pathlib, sys, traceback

worktree = pathlib.Path(sys.argv[1]).resolve()
targets = sys.argv[2:]
sys.path.insert(0, str(worktree))

if not targets:
    targets = [str(p.relative_to(worktree)) for p in sorted(worktree.rglob("test_*.py"))]

passed_count = 0
failed_count = 0
failed_files = []
for raw_target in targets:
    if "::" in raw_target:
        rel, only_fn = raw_target.split("::", 1)
    else:
        rel, only_fn = raw_target, None
    p = (worktree / rel).resolve()
    spec = importlib.util.spec_from_file_location(f"{p.parent.name}_{p.stem}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    target_failed = False
    for attr in sorted(dir(mod)):
        if attr.startswith("test_") and callable(getattr(mod, attr)):
            if only_fn and attr != only_fn:
                continue
            fn = getattr(mod, attr)
            try:
                fn()
                print(f"{rel}::{attr} PASSED")
                passed_count += 1
            except Exception:
                print(f"{rel}::{attr} FAILED")
                traceback.print_exc()
                failed_count += 1
                target_failed = True
    if target_failed:
        failed_files.append(raw_target)
        if rel not in failed_files:
            failed_files.append(rel)

if failed_files:
    print(f"FAILED_FILES={','.join(failed_files)}")
print(f"=== {passed_count} passed, {failed_count} failed ===")
sys.exit(0 if failed_count == 0 else 1)
"""


class SandboxedTestRunner:
    """Runs pytest (or fast isolated `-S` Python test runner for zero-fixture suites) inside an isolated worktree."""

    def __init__(self, worktree_path: str | Path):
        self.worktree_path = Path(worktree_path).resolve()
        self._has_pytest = importlib.util.find_spec("pytest") is not None

    def _can_use_fast_stdlib_runner(self, test_targets: list[str] | None) -> bool:
        """Check via AST whether all target test files are pure zero-argument `def test_*()` suites without pytest fixtures."""
        targets = test_targets or [
            str(p.relative_to(self.worktree_path)) for p in sorted(self.worktree_path.rglob("test_*.py"))
        ]
        if not targets:
            return False
        for raw_rel in targets:
            rel = raw_rel.split("::", 1)[0]
            p = (self.worktree_path / rel).resolve()
            if not p.is_file():
                return False
            try:
                src = p.read_text(encoding="utf-8")
                if "pytest" in src:
                    return False
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                        if isinstance(node, ast.AsyncFunctionDef) or len(node.args.args) > 0:
                            return False
            except Exception:
                return False
        return True

    @neatlogs.span(
        kind="TOOL",
        tool_name="run_pytest_target",
        description="Execute pytest or fast isolated test runner on specific test files inside the isolated worktree.",
    )
    def run_tests(self, test_targets: list[str] | None = None, timeout: float = 25.0) -> dict[str, Any]:
        """Run tests on `test_targets` (or full test suite if None) and return structured pass/fail output."""
        use_fast = self._can_use_fast_stdlib_runner(test_targets)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if use_fast or not self._has_pytest:
            env["PYTHONPATH"] = str(self.worktree_path)
            cmd = [sys.executable, "-B", "-S", "-c", _STDLIB_RUNNER_SCRIPT, str(self.worktree_path)]
            if test_targets:
                cmd.extend(test_targets)
        else:
            extra_paths = [str(self.worktree_path)] + [p for p in sys.path if p]
            env["PYTHONPATH"] = os.pathsep.join(extra_paths)
            cmd = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "--tb=short",
                "--disable-warnings",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:doctest",
            ]
            if test_targets:
                cmd.extend(test_targets)

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.worktree_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            combined = (proc.stdout + "\n" + proc.stderr).strip()
            passed = proc.returncode == 0
            return {
                "passed": passed,
                "exit_code": proc.returncode,
                "targets": test_targets or ["all"],
                "latency_ms": latency_ms,
                "output": combined[-3000:],
            }
        except subprocess.TimeoutExpired as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return {
                "passed": False,
                "exit_code": -1,
                "targets": test_targets or ["all"],
                "latency_ms": latency_ms,
                "output": f"TimeoutExpired after {timeout}s: {exc}",
            }

    def run_combined_verification(
        self, repro_test: str, caller_targets: list[str], timeout: float = 25.0
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute reproduction test and downstream caller contract tests in a single pass when possible.
        If all pass, returns `(repro_check, caller_check)` from the single invocation; if any fail,
        attributes failure accurately between `repro_test` and `caller_targets`.
        """
        dedup_targets = list(dict.fromkeys([repro_test] + list(caller_targets)))
        if len(dedup_targets) == 1:
            single = self.run_tests(dedup_targets, timeout=timeout)
            return single, single

        combined_res = self.run_tests(dedup_targets, timeout=timeout)
        if combined_res["passed"]:
            half_lat = round(combined_res["latency_ms"] / 2.0, 2)
            repro_res = {**combined_res, "targets": [repro_test], "latency_ms": half_lat}
            caller_res = {**combined_res, "targets": caller_targets, "latency_ms": half_lat}
            return repro_res, caller_res

        # Combined run failed: determine whether repro_test or caller_targets failed
        out = combined_res.get("output", "")
        if "FAILED_FILES=" in out:
            failed_line = [ln for ln in out.splitlines() if ln.startswith("FAILED_FILES=")][-1]
            failed_set = set(failed_line.split("=", 1)[1].split(","))
            repro_passed = repro_test not in failed_set
            caller_passed = not any(ct in failed_set for ct in caller_targets)
            half_lat = round(combined_res["latency_ms"] / 2.0, 2)
            return (
                {
                    "passed": repro_passed,
                    "exit_code": 0 if repro_passed else 1,
                    "targets": [repro_test],
                    "latency_ms": half_lat,
                    "output": out,
                },
                {
                    "passed": caller_passed,
                    "exit_code": 0 if caller_passed else 1,
                    "targets": caller_targets,
                    "latency_ms": half_lat,
                    "output": out,
                },
            )

        repro_check = self.run_tests([repro_test], timeout=timeout)
        caller_check = self.run_tests(caller_targets, timeout=timeout)
        return repro_check, caller_check
