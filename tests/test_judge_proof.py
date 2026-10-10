"""Tests for the judge verification report: live checks are mocked at the HTTP layer only."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix import judge_proof as jp  # noqa: E402

LEDGER = json.loads((ROOT / "benchmarks" / "verified_runs_ledger.json").read_text(encoding="utf-8"))


def github_handler(commit_dates: list[str], refs: list[str], pr_state: str = "open", fail: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("network down", request=request)
        path = request.url.path
        if path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": f"s{i}", "commit": {"author": {"date": d}}}
                                             for i, d in enumerate(commit_dates)])
        if "/git/matching-refs/entire/checkpoints" in path:
            return httpx.Response(200, json=[{"ref": f"refs/entire/checkpoints/v1/{r}"} for r in refs])
        if "/pulls/" in path:
            return httpx.Response(200, json={"state": pr_state, "merged_at": None, "title": "Fix exporter"})
        return httpx.Response(404, json={"message": "not found"})
    return handler


def build(handler, search=None):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        return jp.build_judge_proof(ROOT, LEDGER, search, client=client, use_cache=False)
    finally:
        client.close()


def by_id(report):
    return {item["id"]: item for item in report["items"]}


def test_all_sources_healthy_reports_verified_items():
    report = build(github_handler(["2026-10-10T08:00:00Z", "2026-10-11T09:00:00Z"], [jp.CHECKPOINT_ID, "01ABC"]),
                   search=lambda: {"total": 12, "results": [{"trace_id": "t1", "created_at": "2026-10-10T10:00:00Z"}]})
    items = by_id(report)
    assert [i["id"] for i in report["items"]] == ["improvement", "neatlogs", "entire", "cfo", "recovery", "public", "commits"]
    assert items["commits"]["verdict"] == "verified"
    assert items["entire"]["facts"]["checkpoint_refs"] == 2
    assert items["neatlogs"]["facts"]["matching_traces"] == 12
    assert items["public"]["facts"]["upstream_pr_state"] == "open"
    assert sum(report["summary"].values()) == len(report["items"])


def test_commits_before_official_start_are_flagged_not_hidden():
    report = build(github_handler(["2026-10-10T04:08:59Z", "2026-10-10T09:00:00Z"], [jp.CHECKPOINT_ID]))
    commits = by_id(report)["commits"]
    assert commits["verdict"] == "attention"
    assert commits["facts"]["dated_before_official_start"] == 1
    assert "2026-10-10T04:08:59Z" in commits["detail"]


def test_missing_submission_checkpoint_needs_attention():
    entire = by_id(build(github_handler(["2026-10-10T08:00:00Z"], ["01OTHER"])))["entire"]
    assert entire["verdict"] == "attention" and "missing" in entire["detail"]


def test_network_failure_is_reported_unavailable_never_verified():
    report = build(github_handler([], [], fail=True), search=None)
    items = by_id(report)
    for key in ("commits", "entire", "public", "neatlogs"):
        assert items[key]["verdict"] == "unavailable", key
        assert items[key]["detail"], key
    assert report["summary"]["unavailable"] == 4


def test_rate_limit_message_is_surfaced():
    def handler(request):
        return httpx.Response(403, text="API rate limit exceeded for 1.2.3.4")
    items = by_id(build(handler))
    assert items["commits"]["verdict"] == "unavailable"
    assert "rate limit" in items["commits"]["detail"].lower()


@pytest.mark.parametrize("payload", [None, [], {"unexpected": 1}])
def test_malformed_neatlogs_response_is_unavailable(payload):
    result = jp.check_neatlogs(lambda: payload)
    assert result["verdict"] == "unavailable"


def test_neatlogs_exception_is_unavailable():
    def boom():
        raise TimeoutError("mcp timed out")
    result = jp.check_neatlogs(boom)
    assert result["verdict"] == "unavailable" and "timed out" in result["detail"]


def test_recorded_improvement_comes_from_ledger():
    item = jp.check_improvement(LEDGER)
    assert item["method"] == "RECORDED"
    assert item["verdict"] == "verified"


def test_recovery_run_is_inspectable():
    item = jp.check_recovery(LEDGER)
    assert item["verdict"] == "verified"
    assert any(link["url"] == f"#run/{jp.RECOVERY_RUN_ID}" for link in item["links"])


def test_empty_ledger_does_not_claim_improvement_or_recovery():
    assert jp.check_improvement({"runs": []})["verdict"] != "verified"
    assert jp.check_recovery({"runs": []})["verdict"] != "verified"


def test_cfo_figures_match_recalculated_workbook():
    item = jp.check_cfo(ROOT)
    assert item["verdict"] == "verified"
    assert item["facts"]["plan_figures_match_workbook"] is True


def test_cfo_detects_plan_drift(tmp_path):
    for name in ("plan.xlsx", "BUSINESS_PLAN.md"):
        shutil.copy2(ROOT / name, tmp_path / name)
    (tmp_path / "benchmarks").mkdir()
    shutil.copy2(ROOT / "benchmarks" / "plan_xlsx_computed.json", tmp_path / "benchmarks")
    plan = tmp_path / "BUSINESS_PLAN.md"
    snapshot = json.loads((tmp_path / "benchmarks" / "plan_xlsx_computed.json").read_text())
    arr = f"${snapshot['months'][11]['arr']:,.0f}"
    plan.write_text(plan.read_text().replace(arr, "$1"))
    item = jp.check_cfo(tmp_path)
    assert item["verdict"] == "attention"
    assert arr in item["facts"]["figures_missing_from_plan"]


def test_cfo_without_snapshot_is_not_verified(tmp_path):
    for name in ("plan.xlsx", "BUSINESS_PLAN.md"):
        shutil.copy2(ROOT / name, tmp_path / name)
    assert jp.check_cfo(tmp_path)["verdict"] == "attention"


def test_cache_returns_age_and_same_items(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return github_handler(["2026-10-10T08:00:00Z"], [jp.CHECKPOINT_ID])(request)
    monkeypatch.setattr(jp, "_cache", {"at": 0.0, "value": None})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    first = jp.build_judge_proof(ROOT, LEDGER, None, client=client, use_cache=True)
    used = calls["n"]
    second = jp.build_judge_proof(ROOT, LEDGER, None, client=client, use_cache=True)
    client.close()
    assert calls["n"] == used
    assert second["items"] == first["items"]
    assert second["cache_age_s"] >= 0


def test_business_plan_quotes_workbook_projection_label():
    text = (ROOT / "BUSINESS_PLAN.md").read_text(encoding="utf-8")
    assert "Projection, not realised results" in text
    for stale in ("never drops below $112k", "$298,050", "Month 4 (Cash-Flow Break-Even)"):
        assert stale not in text
