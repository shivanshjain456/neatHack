"""Isolated Git workspace and atomic rollback manager for VeriFix runs."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import neatlogs


class WorktreeManager:
    """Manages an isolated Git working copy per agent run with atomic patch & rollback semantics."""

    def __init__(self, source_repo_path: str | Path, run_id: str, base_dir: str | Path = "/tmp/verifix_worktrees"):
        self.source_repo_path = Path(source_repo_path).resolve()
        self.run_id = run_id
        self.worktree_path = (Path(base_dir) / run_id).resolve()

    @neatlogs.span(
        kind="TOOL",
        tool_name="prepare_isolated_worktree",
        description="Create an isolated Git repository workspace for safe defect reproduction and rollback.",
    )
    def prepare(self) -> Path:
        """Create or reuse an isolated Git workspace with a clean committed HEAD baseline."""
        if self.worktree_path.exists() and (self.worktree_path / ".git").exists():
            return self.worktree_path

        if self.worktree_path.exists():
            shutil.rmtree(self.worktree_path)
        self.worktree_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            self.source_repo_path,
            self.worktree_path,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"),
        )

        env = os.environ.copy()
        env["TZ"] = "Asia/Kolkata"
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.worktree_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "VeriFix Agent"], cwd=str(self.worktree_path), env=env, check=True)
        subprocess.run(["git", "config", "user.email", "verifix@neathack.dev"], cwd=str(self.worktree_path), env=env, check=True)
        subprocess.run(["git", "add", "."], cwd=str(self.worktree_path), env=env, check=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline: unpatched target repository state"],
            cwd=str(self.worktree_path),
            env=env,
            check=True,
            capture_output=True,
        )
        return self.worktree_path

    def resolve_safe_path(self, relative_file_path: str) -> Path:
        """Enforce strict path-traversal containment inside the isolated worktree."""
        cleaned = relative_file_path.lstrip("/").strip()
        if ".." in Path(cleaned).parts or cleaned.startswith(".git") or cleaned.endswith(".env"):
            raise PermissionError(f"Unsafe or forbidden path blocked by VeriFix security policy: {relative_file_path}")
        full_path = (self.worktree_path / cleaned).resolve()
        if not str(full_path).startswith(str(self.worktree_path)):
            raise PermissionError(f"Path traversal outside isolated worktree blocked: {relative_file_path}")
        return full_path

    @neatlogs.span(
        kind="TOOL",
        tool_name="apply_scoped_patch",
        description="Write candidate code fix into the isolated worktree and validate Python syntax.",
    )
    def apply_file_content(self, relative_file_path: str, new_source_code: str) -> dict[str, Any]:
        """Apply new source code to `relative_file_path`, validate AST syntax, and return unified diff."""
        target = self.resolve_safe_path(relative_file_path)
        if not target.exists():
            raise FileNotFoundError(f"Target file does not exist in worktree: {relative_file_path}")

        # Validate Python syntax before writing or check immediately
        try:
            compile(new_source_code, str(target), "exec")
        except SyntaxError as exc:
            return {
                "applied": False,
                "syntax_valid": False,
                "error": f"SyntaxError at line {exc.lineno}: {exc.msg}",
                "diff": "",
            }

        target.write_text(new_source_code, encoding="utf-8")
        diff_proc = subprocess.run(
            ["git", "diff", "--", relative_file_path],
            cwd=str(self.worktree_path),
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "applied": True,
            "syntax_valid": True,
            "file_path": relative_file_path,
            "diff": diff_proc.stdout.strip(),
        }

    @neatlogs.span(
        kind="TOOL",
        tool_name="rollback_worktree",
        description="Atomically revert all uncommitted modifications in the isolated worktree to baseline HEAD.",
    )
    def rollback_to_baseline(self, reason: str = "") -> dict[str, Any]:
        """Revert the isolated worktree back to clean HEAD after a failed test or caller regression."""
        subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=str(self.worktree_path),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=str(self.worktree_path),
            check=True,
            capture_output=True,
        )
        return {"rolled_back": True, "worktree": str(self.worktree_path), "reason": reason}

    def get_full_diff(self) -> str:
        proc = subprocess.run(
            ["git", "diff"],
            cwd=str(self.worktree_path),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip()
