"""Regression gates for repository-root resolution.

These exist because the root used to fall back to a hardcoded absolute path from the original
build sandbox. Any clone anywhere else silently got a non-existent root: ledger hydration was
skipped, /api/workspace served null evidence, the zero-tolerance audit crashed, and four release
tests failed. Nothing about that failure mode was visible in the build sandbox itself, so the
guard has to be explicit and location-independent.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from verifix.config import ROOT_MARKERS, looks_like_verifix_root, resolve_verifix_root_dir

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_contains_every_marker():
    root = resolve_verifix_root_dir()
    assert looks_like_verifix_root(root), f"{root} is missing one of {ROOT_MARKERS}"
    for marker in ROOT_MARKERS:
        assert (root / marker).exists()


def test_root_is_the_checkout_that_owns_this_test():
    """A judge cloning to an arbitrary path must get that path, not the original build path."""
    assert resolve_verifix_root_dir() == REPO_ROOT


def test_resolution_does_not_depend_on_the_working_directory(tmp_path):
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from verifix.config import resolve_verifix_root_dir;"
        "print(resolve_verifix_root_dir())"
    ) % str(REPO_ROOT / "src")
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "VERIFIX_ROOT_DIR"},
        check=True,
    )
    assert Path(out.stdout.strip()) == REPO_ROOT


def test_explicit_override_wins(tmp_path, monkeypatch):
    override = tmp_path / "elsewhere"
    override.mkdir()
    monkeypatch.setenv("VERIFIX_ROOT_DIR", str(override))
    assert resolve_verifix_root_dir() == override.resolve()


def test_lambda_task_dir_takes_precedence_over_the_checkout(tmp_path):
    """The deployed Lambda resolves /var/task; that ordering must not regress."""
    task = tmp_path / "var_task"
    (task / "benchmarks").mkdir(parents=True)
    assert resolve_verifix_root_dir(lambda_task_dir=task) == task.resolve()


def test_lambda_task_dir_without_benchmarks_is_not_used(tmp_path):
    empty_task = tmp_path / "var_task_empty"
    empty_task.mkdir()
    assert resolve_verifix_root_dir(lambda_task_dir=empty_task) == REPO_ROOT


def test_state_store_finds_the_tracked_run_ledger_from_any_clone(tmp_path):
    """Ledger hydration is what makes a fresh clone serve real run history.

    The store only hydrates a *default runtime* database, so the probe has to carry the
    runtime layout (`.../verifix_runtime/verifix_state.db`) for this to exercise hydration
    rather than merely opening an empty file.
    """
    from verifix.state_store import DEFAULT_ROOT_DIR, VeriFixStateStore

    assert DEFAULT_ROOT_DIR == REPO_ROOT
    ledger = DEFAULT_ROOT_DIR / "benchmarks" / "verified_runs_ledger.json"
    assert ledger.is_file(), "tracked run ledger is missing from the checkout"

    probe_db = tmp_path / "verifix_runtime" / "verifix_state.db"
    store = VeriFixStateStore(probe_db)
    assert store._is_default_runtime_db, "probe did not use the default-runtime layout"
    assert len(store.list_runs(limit=5)) > 0, "ledger did not hydrate into the runtime database"


def test_no_module_hardcodes_the_original_build_root():
    """The legacy path may appear only as the documented last-resort fallback in config.py."""
    offenders: list[str] = []
    scan_dirs = [REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "benchmarks",
                 REPO_ROOT / "video" / "scripts"]
    for directory in scan_dirs:
        for path in sorted(directory.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            hits = [ln for ln in text.splitlines() if "/home/user/verifix" in ln]
            if not hits:
                continue
            if path == REPO_ROOT / "src" / "verifix" / "config.py":
                # Exactly two sanctioned references: the docstring and the legacy_root fallback.
                if len(hits) == 2 and any("legacy_root = Path(" in ln for ln in hits):
                    continue
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {len(hits)} reference(s)")
    assert not offenders, "hardcoded build-sandbox root reappeared:\n  " + "\n  ".join(offenders)


def test_documented_audit_script_runs_from_a_fresh_clone():
    """scripts/verify_zero_tolerance.py is cited as a passing gate; it must not need the old path."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify_zero_tolerance.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ZERO-TOLERANCE AUDIT PASSED" in result.stdout


def test_workspace_serves_all_partner_evidence_sections():
    """The evidence a judge inspects must not arrive as null on a relocated checkout."""
    from fastapi.testclient import TestClient

    from verifix.server import app

    with TestClient(app) as client:
        body = client.get("/api/workspace").json()
    assert body["runs"], "run ledger did not hydrate"
    for section in ("entire", "plan_projection", "controlled_experiment", "cfo_model"):
        assert body[section] is not None, f"/api/workspace served null {section}"
