import math
from pathlib import Path

import pytest

from verifix.ablation import bootstrap_ratio_ci, geo_mean, judge_full_suite, sign_test_p, summarize
from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness
from verifix.config import LLMCallResult
from verifix.state_store import VeriFixStateStore

ROOT = Path(__file__).resolve().parents[1]
CASE = "case_01_ledger_rounding"
SPEC = BENCHMARK_CATALOG[CASE]
ORIGINAL = (ROOT / SPEC["repo_subpath"] / SPEC["target_file"]).read_text(encoding="utf-8")


class FakeLLM:
    """Returns the unchanged target module, so no attempt can pass on its own. Records prompts."""

    def __init__(self):
        self.prompts = []

    def generate(self, system_prompt, user_prompt, **kwargs):
        self.prompts.append(user_prompt)
        return LLMCallResult(content=f"```python\n# HYPOTHESIS: unchanged\n{ORIGINAL}```", model="fake", provider="test",
                             prompt_tokens=len(user_prompt) // 4, completion_tokens=50,
                             total_tokens=len(user_prompt) // 4 + 50, latency_ms=1.0, estimated_cost_usd=0.0)


def harness(tmp_path, llm):
    return VeriFixAgentHarness(ROOT, state_store=VeriFixStateStore(tmp_path / "state.db"), llm_client=llm)


def test_baseline_is_not_forced_to_fail_and_sees_only_the_case_repository(tmp_path):
    llm = FakeLLM()
    run = harness(tmp_path, llm).execute_case(CASE, mode="baseline_naive")
    assert run["status"] != "VERIFIED_COMPLETE"
    assert all("min_fee_cents: int = 500" not in (p.get("unified_diff") or "") for p in run["patches"])
    assert llm.prompts and all("REPOSITORY:" in p for p in llm.prompts)
    assert not any("REPO DOC" in p or "BUSINESS_PLAN" in p for p in llm.prompts)
    assert "settlement.py" in llm.prompts[0]


def test_target_only_prompt_has_no_repository_context(tmp_path):
    llm = FakeLLM()
    harness(tmp_path, llm).execute_case(CASE, mode="target_only")
    assert llm.prompts and not any("REPOSITORY:" in p for p in llm.prompts)


def test_caller_blind_arm_ships_the_regression_and_the_independent_judge_catches_it(tmp_path):
    run = harness(tmp_path, FakeLLM()).execute_case(CASE, mode="target_only", inject_caller_regression_on_attempt_1=True)
    assert run["status"] == "REPRO_PASSED_CALLERS_UNCHECKED"
    assert run["verification_certificate"]["caller_tests_run"] is False
    verdict = judge_full_suite(ROOT / SPEC["repo_subpath"], run["final_diff"])
    assert verdict["patch_applied"] is True and verdict["passed"] is False


def test_guarded_arm_rejects_the_same_injected_patch(tmp_path):
    run = harness(tmp_path, FakeLLM()).execute_case(CASE, mode="baseline_naive", inject_caller_regression_on_attempt_1=True)
    assert run["status"] != "VERIFIED_COMPLETE"
    assert run["rollbacks_executed"] >= 1


def test_unknown_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        harness(tmp_path, FakeLLM()).execute_case(CASE, mode="nonsense")


def test_judge_on_unpatched_repository_fails_and_bad_diff_is_reported():
    assert judge_full_suite(ROOT / SPEC["repo_subpath"], "")["passed"] is False
    bad = judge_full_suite(ROOT / SPEC["repo_subpath"], "--- a/nope.py\n+++ b/nope.py\n@@ -1 +1 @@\n-x\n+y\n")
    assert bad["passed"] is False and bad["patch_applied"] is False


def test_statistics():
    assert sign_test_p(0, 0) == 1.0
    assert sign_test_p(10, 0) == pytest.approx(2 / 1024, abs=1e-6)
    assert sign_test_p(5, 5) == 1.0
    assert geo_mean([0.5, 2.0]) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        geo_mean([0.0, 1.0])
    lo, hi = bootstrap_ratio_ci([0.5] * 12)
    assert lo == pytest.approx(0.5) and hi == pytest.approx(0.5)
    lo, hi = bootstrap_ratio_ci([0.4, 0.5, 0.6, 0.45, 0.55])
    assert 0.4 <= lo <= hi <= 0.6
    assert bootstrap_ratio_ci([0.4, 0.5, 0.6]) == bootstrap_ratio_ci([0.4, 0.5, 0.6])


def test_summary_pairs_by_case_and_repeat():
    def rec(arm, rep, tokens, judged, success=True):
        return {"case_id": "c", "repeat": rep, "arm": arm, "total_tokens": tokens, "total_latency_ms": 1.0,
                "attempts": 1, "cost_usd": 0.0, "agent_success": success, "judge": {"passed": judged}}
    rs = [rec("graph_guarded", 1, 100, True), rec("baseline_naive", 1, 400, True), rec("target_only", 1, 80, False),
          rec("graph_guarded", 2, 120, True), rec("baseline_naive", 2, 300, True), rec("target_only", 2, 90, True)]
    s = summarize(rs)
    assert s["arms"]["target_only"]["shipped_regressions"] == 1
    c = s["comparisons"]["graph_guarded_vs_baseline_naive"]
    assert c["pairs"] == 2 and c["graph_fewer_tokens_pairs"] == 2
    assert c["token_ratio_geo_mean"] == pytest.approx(math.sqrt(0.25 * 0.4), rel=1e-3)
    assert s["comparisons"]["graph_guarded_vs_target_only"]["judge_pass_only_graph"] == 1
    assert c["cases"] == 1 and c["token_ratio_by_case"]["c"] == pytest.approx(math.sqrt(0.1), rel=1e-3)
    assert c["token_ratio_ci95_cases"][0] == pytest.approx(c["token_ratio_ci95_cases"][1])


def test_cluster_bootstrap_resamples_cases_not_runs():
    from verifix.ablation import cluster_bootstrap_ci
    lo, hi = cluster_bootstrap_ci({"a": [math.log(0.5)] * 50, "b": [math.log(1.0)] * 2})
    assert lo == pytest.approx(0.5) and hi == pytest.approx(1.0)
