"""Sandboxed pytest execution tool for defect reproduction and blast-radius regression checks."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import neatlogs


class SandboxedTestRunner:
    """Runs pytest inside an isolated worktree with strict timeouts and structured failure parsing."""

    def __init__(self, worktree_path: str | Path):
        self.worktree_path = Path(worktree_path).resolve()

    @neatlogs.span(
        kind="TOOL",
        tool_name="run_pytest_target",
        description="Execute pytest on specific test files or node IDs inside the isolated worktree.",
    )
    def run_tests(self, test_targets: list[str] | None = None, timeout: float = 25.0) -> dict[str, Any]:
        """Run pytest on `test_targets` (or full test suite if None) and return structured pass/fail output."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.worktree_path)
        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
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
