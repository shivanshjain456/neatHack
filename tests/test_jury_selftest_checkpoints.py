"""Offline regression gates for the Entire-checkpoint source fallback in the jury self-test.

The self-test used to read checkpoint refs only from the local repository whenever ``.git``
existed, so a fresh clone (which never fetches ``refs/entire/checkpoints/*``) reported 0 and
failed. ``count_entire_checkpoint_refs`` now tries local -> origin -> the tracked snapshot and
reports the source. These tests exercise every branch that can run without a network.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("jury_selftest", REPO_ROOT / "scripts" / "jury_selftest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_no_git_no_snapshot_reports_none(tmp_path):
    count, source, trailer = _load().count_entire_checkpoint_refs(tmp_path)
    assert (count, source, trailer) == (0, "none", False)


def test_no_git_uses_tracked_snapshot(tmp_path):
    bench = tmp_path / "benchmarks"
    bench.mkdir()
    (bench / "entire_telemetry_snapshot.json").write_text(
        json.dumps({"entire_refs": [f"ref-{i}" for i in range(12)]}), encoding="utf-8")
    count, source, trailer = _load().count_entire_checkpoint_refs(tmp_path)
    assert count == 12 and source == "tracked snapshot" and trailer is False


def test_git_with_local_refs_wins(tmp_path):
    _git("init", "-q", cwd=tmp_path)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "c1", cwd=tmp_path)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                         capture_output=True, text=True).stdout.strip()
    _git("update-ref", "refs/entire/checkpoints/c1", sha, cwd=tmp_path)
    _git("update-ref", "refs/entire/checkpoints/c2", sha, cwd=tmp_path)
    count, source, trailer = _load().count_entire_checkpoint_refs(tmp_path)
    assert count == 2 and source == "local"


def test_git_without_local_or_remote_falls_back_to_snapshot(tmp_path):
    _git("init", "-q", cwd=tmp_path)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "c1", cwd=tmp_path)
    bench = tmp_path / "benchmarks"
    bench.mkdir()
    (bench / "entire_telemetry_snapshot.json").write_text(
        json.dumps({"entire_refs": ["a", "b", "c"]}), encoding="utf-8")
    # No local checkpoint refs and no `origin` remote: ls-remote errors and the snapshot is used.
    count, source, trailer = _load().count_entire_checkpoint_refs(tmp_path)
    assert count == 3 and source == "tracked snapshot"


def test_real_repo_resolves_checkpoints_from_local_refs():
    count, source, trailer = _load().count_entire_checkpoint_refs(REPO_ROOT)
    # The working clone fetches the custom refs; it must not report zero.
    assert count >= 1
    assert source in ("local", "origin", "tracked snapshot")
