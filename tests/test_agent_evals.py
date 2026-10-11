"""Agent evals-as-code, flaky quarantine, sandbox boundary, and minimal-reproducer discipline."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix.agent_evals import cost_regression, evaluate_trajectory, hallucination_rate, load_json  # noqa: E402
from verifix.quality_registry import FlakyRegistry  # noqa: E402
from verifix.test_runner import SandboxedTestRunner  # noqa: E402


def steps(*phases):
    return [{"phase": p, "span_kind": "X", "status": "COMPLETED"} for p in phases]


GOOD = steps("LOCALIZING", "REPRODUCING", "PLANNING_ATTEMPT_1", "PATCHING_ATTEMPT_1", "ASSURANCE_ATTEMPT_1",
             "RECOVERY_ROLLBACK_1", "PLANNING_ATTEMPT_2", "PATCHING_ATTEMPT_2", "ASSURANCE_ATTEMPT_2", "VERIFYING_ATTEMPT_2")


# ── trajectory evaluation ────────────────────────────────────────────────────────────────────
def test_valid_trajectory_passes():
    r = evaluate_trajectory(GOOD, "VERIFIED_COMPLETE", "graph_guarded")
    assert r["ok"], r["violations"]
    assert r["attempts"] == 2 and r["accepted_attempt"] == 2 and r["rollbacks"] == 1


def test_patch_before_reproduction_is_flagged():
    bad = steps("LOCALIZING", "PLANNING_ATTEMPT_1", "REPRODUCING", "PATCHING_ATTEMPT_1", "VERIFYING_ATTEMPT_1")
    assert any(v.startswith("R1") for v in evaluate_trajectory(bad, "VERIFIED_COMPLETE", "graph_guarded")["violations"])


def test_attempt_with_two_verdicts_and_accept_after_rollback_are_flagged():
    bad = steps("LOCALIZING", "REPRODUCING", "PLANNING_ATTEMPT_1", "PATCHING_ATTEMPT_1", "RECOVERY_ROLLBACK_1", "VERIFYING_ATTEMPT_1")
    v = evaluate_trajectory(bad, "VERIFIED_COMPLETE", "graph_guarded")["violations"]
    assert any(x.startswith("R3") for x in v) and any(x.startswith("R6") for x in v)


def test_verified_run_whose_last_attempt_was_rolled_back_is_flagged():
    bad = steps("LOCALIZING", "REPRODUCING", "PLANNING_ATTEMPT_1", "PATCHING_ATTEMPT_1", "RECOVERY_ROLLBACK_1")
    assert any(v.startswith("R5") for v in evaluate_trajectory(bad, "VERIFIED_COMPLETE", "graph_guarded")["violations"])


def test_accepted_attempt_without_assurance_is_flagged_once_assurance_is_active():
    bad = steps("LOCALIZING", "REPRODUCING", "PLANNING_ATTEMPT_1", "PATCHING_ATTEMPT_1", "ASSURANCE_ATTEMPT_1", "RECOVERY_ROLLBACK_1",
                "PLANNING_ATTEMPT_2", "PATCHING_ATTEMPT_2", "VERIFYING_ATTEMPT_2")
    assert any(v.startswith("R7") for v in evaluate_trajectory(bad, "VERIFIED_COMPLETE", "graph_guarded")["violations"])


def test_attempt_gap_is_flagged():
    bad = steps("LOCALIZING", "REPRODUCING", "PLANNING_ATTEMPT_1", "PATCHING_ATTEMPT_1", "RECOVERY_ROLLBACK_1",
                "PLANNING_ATTEMPT_3", "PATCHING_ATTEMPT_3", "VERIFYING_ATTEMPT_3")
    assert any(v.startswith("R2") for v in evaluate_trajectory(bad, "VERIFIED_COMPLETE", "graph_guarded")["violations"])


def test_committed_trajectory_snapshot_is_all_valid():
    snap = load_json(ROOT / "benchmarks" / "trajectory_eval.json")
    assert snap["runs"] >= 40 and snap["trajectory_valid"] == snap["runs"]


# ── cost regression + hallucination rate ─────────────────────────────────────────────────────
def test_measured_costs_are_within_committed_budgets():
    res = cost_regression(load_json(ROOT / "benchmarks" / "ablation_experiment.json"), load_json(ROOT / "quality" / "budgets.json"))
    assert res["ok"], res


def test_cost_regression_detects_an_over_budget_arm():
    budgets = load_json(ROOT / "quality" / "budgets.json")
    budgets["arms"]["graph_guarded"]["max_mean_total_tokens"] = 800
    res = cost_regression(load_json(ROOT / "benchmarks" / "ablation_experiment.json"), budgets)
    assert res["regressions"] == ["graph_guarded"]


def test_hallucination_rate_is_computed_from_the_replayed_corpus():
    corpus = load_json(ROOT / "benchmarks" / "assurance_corpus.json")
    res = hallucination_rate(corpus)
    assert res["patches"] == corpus["summary"]["replayed"]
    planted = {"records": corpus["records"][:3] + [{"assurance": {"gates": {"symbols": "fail"}}}]}
    first3 = sum(r["assurance"]["gates"].get("symbols") == "fail" for r in corpus["records"][:3])
    assert hallucination_rate(planted)["with_hallucinated_reference"] == first3 + 1
    assert hallucination_rate(planted)["patches"] == 4


# ── flaky quarantine ─────────────────────────────────────────────────────────────────────────
def test_flaky_quarantine_after_two_and_release_after_five(tmp_path):
    reg = FlakyRegistry(tmp_path / "q.db", quarantine_after=2, release_after=5)
    assert reg.record("t::a", [True, False, True])["quarantined"] is False
    assert reg.record("t::a", [True, True, True])["quarantined"] is False
    st = reg.record("t::a", [False, True, True])
    assert st["quarantined"] and st["transition"] == "quarantined"
    for i in range(4):
        assert reg.record("t::a", [True, True, True])["quarantined"] is True, i
    assert reg.record("t::a", [True, True, True])["transition"] == "released"
    assert not reg.is_quarantined("t::a")
    rate = reg.flaky_rate()
    assert rate["observations"] == 8 and rate["flaky_observations"] == 2 and rate["flaky_rate"] == 0.25


# ── sandbox / permission boundary ────────────────────────────────────────────────────────────
def test_sandboxed_tests_cannot_read_secrets_or_open_sockets(tmp_path, monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "sk-should-never-leak")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_never_leak")
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_evil.py").write_text(
        "import os, socket, pytest\n"
        "def test_no_secrets():\n"
        "    assert 'LITELLM_API_KEY' not in os.environ and 'GITHUB_TOKEN' not in os.environ\n"
        "def test_no_network():\n"
        "    with pytest.raises(PermissionError):\n"
        "        socket.create_connection(('1.1.1.1', 443), timeout=2)\n",
        encoding="utf-8")
    res = SandboxedTestRunner(repo).run_tests(["tests/test_evil.py"], timeout=60)
    assert res["passed"], res["output"][-800:]


# ── minimal-reproducer discipline ────────────────────────────────────────────────────────────
def test_harness_refuses_to_patch_when_the_defect_does_not_reproduce(tmp_path):
    from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness
    from verifix.state_store import VeriFixStateStore

    case = BENCHMARK_CATALOG["case_01_ledger_rounding"]
    repo = tmp_path / "already_fixed"
    shutil.copytree(ROOT / case["repo_subpath"], repo, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "benchmarks" / "reference_fixes" / "case_01_ledger_rounding.py", repo / case["target_file"])
    spec = {**case, "case_id": "custom_already_fixed", "repo_path": str(repo)}
    harness = VeriFixAgentHarness(root_dir=ROOT, state_store=VeriFixStateStore(tmp_path / "s.db"))
    run = harness.execute_case("custom_already_fixed", mode="graph_guarded", custom_spec=spec)
    assert run["status"] == "NOT_REPRODUCED", run.get("error_reason")
    assert "already passes" in run["error_reason"]
    assert int(run.get("total_tokens") or 0) == 0
