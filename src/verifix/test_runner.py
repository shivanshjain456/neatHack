"""Sandboxed pytest / Python test execution tool for defect reproduction and blast-radius regression checks."""

from __future__ import annotations

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
for rel in targets:
    p = (worktree / rel).resolve()
    spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in sorted(dir(mod)):
        if attr.startswith("test_") and callable(getattr(mod, attr)):
            fn = getattr(mod, attr)
            try:
                fn()
                print(f"{rel}::{attr} PASSED")
                passed_count += 1
            except Exception:
                print(f"{rel}::{attr} FAILED")
                traceback.print_exc()
                failed_count += 1

print(f"=== {passed_count} passed, {failed_count} failed ===")
sys.exit(0 if failed_count == 0 else 1)
"""


class SandboxedTestRunner:
    """Runs pytest (or stdlib test runner in minimal serverless environments) inside an isolated worktree."""

    def __init__(self, worktree_path: str | Path):
        self.worktree_path = Path(worktree_path).resolve()
        self._has_pytest = importlib.util.find_spec("pytest") is not None

    @neatlogs.span(
        kind="TOOL",
        tool_name="run_pytest_target",
        description="Execute pytest on specific test files or node IDs inside the isolated worktree.",
    )
    def run_tests(self, test_targets: list[str] | None = None, timeout: float = 25.0) -> dict[str, Any]:
        """Run pytest on `test_targets` (or full test suite if None) and return structured pass/fail output."""
        env = os.environ.copy()
        extra_paths = [str(self.worktree_path)] + [p for p in sys.path if p]
        env["PYTHONPATH"] = os.pathsep.join(extra_paths)
        if self._has_pytest:
            cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
            if test_targets:
                cmd.extend(test_targets)
        else:
            cmd = [sys.executable, "-c", _STDLIB_RUNNER_SCRIPT, str(self.worktree_path)]
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
