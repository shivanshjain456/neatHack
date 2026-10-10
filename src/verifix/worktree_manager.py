"""Isolated Git / Sandbox workspace and atomic rollback manager for VeriFix runs."""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import neatlogs


class WorktreeManager:
    """Manages an isolated working copy per agent run with atomic patch & rollback semantics.
    Uses Git when `/usr/bin/git` is available, with automatic stdlib baseline-snapshot & difflib
    support for serverless environments (e.g., AWS Lambda python3.12) where git is not pre-installed.
    """

    def __init__(self, source_repo_path: str | Path, run_id: str, base_dir: str | Path = "/tmp/verifix_worktrees"):
        self.source_repo_path = Path(source_repo_path).resolve()
        self.run_id = run_id
        self.worktree_path = (Path(base_dir) / run_id).resolve()
        self._baseline_dir = (Path(base_dir) / f"{run_id}__baseline").resolve()
        self._has_git = shutil.which("git") is not None

    @neatlogs.span(
        kind="TOOL",
        tool_name="prepare_isolated_worktree",
        description="Create an isolated repository workspace for safe defect reproduction and rollback.",
    )
    def prepare(self) -> Path:
        """Create or reuse an isolated workspace with a clean committed baseline."""
        if self.worktree_path.exists() and ((self.worktree_path / ".git").exists() or self._baseline_dir.exists()):
            return self.worktree_path

        if self.worktree_path.exists():
            shutil.rmtree(self.worktree_path)
        if self._baseline_dir.exists():
            shutil.rmtree(self._baseline_dir)

        self.worktree_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            self.source_repo_path,
            self.worktree_path,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"),
        )
        shutil.copytree(
            self.source_repo_path,
            self._baseline_dir,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.pyc"),
        )

        if self._has_git:
            tmpl_dir = Path("/tmp/verifix_git_templates") / self.source_repo_path.name
            if (tmpl_dir / ".git" / "HEAD").exists():
                shutil.copytree(tmpl_dir / ".git", self.worktree_path / ".git", dirs_exist_ok=True)
            else:
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
                tmpl_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(self.worktree_path / ".git", tmpl_dir / ".git", dirs_exist_ok=True)
        else:
            # Create .git marker directory so path-traversal & worktree checks behave identically
            (self.worktree_path / ".git").mkdir(exist_ok=True)
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

    def _compute_file_diff(self, relative_file_path: str) -> str:
        base_file = self._baseline_dir / relative_file_path
        curr_file = self.worktree_path / relative_file_path
        base_lines = base_file.read_text(encoding="utf-8").splitlines(keepends=True) if base_file.exists() else []
        curr_lines = curr_file.read_text(encoding="utf-8").splitlines(keepends=True) if curr_file.exists() else []
        return "".join(
            difflib.unified_diff(
                base_lines,
                curr_lines,
                fromfile=f"a/{relative_file_path}",
                tofile=f"b/{relative_file_path}",
            )
        ).strip()

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
        if self._has_git and (self.worktree_path / ".git" / "HEAD").exists():
            diff_proc = subprocess.run(
                ["git", "diff", "--", relative_file_path],
                cwd=str(self.worktree_path),
                capture_output=True,
                text=True,
                check=False,
            )
            diff_text = diff_proc.stdout.strip()
        else:
            diff_text = self._compute_file_diff(relative_file_path)
        return {
            "applied": True,
            "syntax_valid": True,
            "file_path": relative_file_path,
            "diff": diff_text,
        }

    @neatlogs.span(
        kind="TOOL",
        tool_name="rollback_worktree",
        description="Atomically revert all uncommitted modifications in the isolated worktree to baseline HEAD.",
    )
    def rollback_to_baseline(self, reason: str = "") -> dict[str, Any]:
        """Revert the isolated worktree back to clean HEAD after a failed test or caller regression."""
        if self._has_git and (self.worktree_path / ".git" / "HEAD").exists():
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
        elif self._baseline_dir.exists():
            for p in self.worktree_path.rglob("*"):
                if ".git" in p.parts:
                    continue
                if p.is_file():
                    p.unlink()
            shutil.copytree(self._baseline_dir, self.worktree_path, dirs_exist_ok=True)
        return {"rolled_back": True, "worktree": str(self.worktree_path), "reason": reason}

    def get_full_diff(self) -> str:
        if self._has_git and (self.worktree_path / ".git" / "HEAD").exists():
            proc = subprocess.run(
                ["git", "diff"],
                cwd=str(self.worktree_path),
                capture_output=True,
                text=True,
                check=False,
            )
            return proc.stdout.strip()
        diffs = []
        if self._baseline_dir.exists():
            for bf in sorted(self._baseline_dir.rglob("*.py")):
                rel = str(bf.relative_to(self._baseline_dir))
                d = self._compute_file_diff(rel)
                if d:
                    diffs.append(d)
        return "\n".join(diffs).strip()
