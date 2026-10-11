import re
from pathlib import Path

import pytest

from verifix.entire_intelligence import EntireIntelligenceEngine

ROOT = Path(__file__).resolve().parents[1]
STALE = ("0.8896", "0.1794", "79.83", "65.05", "exp_0e3f5ca743", "claude-sonnet", "01M4K6DVJVS5Z09X1PJ0MY8N3K", "8028b9a")


@pytest.fixture(scope="module")
def answer():
    return EntireIntelligenceEngine(ROOT).answer_onboarding_question()


def test_citation_line_ranges_point_at_the_named_definition(answer):
    for c in answer["code_graph_citations"]:
        m = re.fullmatch(r"(.+):(\d+)-(\d+)", c["location"])
        assert m, c
        lines = (ROOT / m.group(1)).read_text(encoding="utf-8").splitlines()
        start, end = int(m.group(2)), int(m.group(3))
        assert start <= end <= len(lines)
        assert re.match(rf"\s*(async\s+)?def {c['symbol'].split('.')[-1]}\(", lines[start - 1]), lines[start - 1]


def test_answer_uses_recorded_figures_and_no_stale_constants(answer):
    text = answer["answer_markdown"]
    import json
    vb = json.loads((ROOT / "benchmarks" / "ablation_experiment.json").read_text())["summary"]["comparisons"]["graph_guarded_vs_baseline_naive"]
    assert f"{round((1 - vb['token_ratio_geo_mean']) * 100)}% fewer tokens" in text
    assert "handicapped baseline" in text and "96.96%" not in text
    for stale in STALE:
        assert stale not in text, stale


def test_missing_checkpoint_is_stated_not_invented(monkeypatch):
    eng = EntireIntelligenceEngine(ROOT)
    monkeypatch.setattr(eng, "_load_telemetry_snapshot", lambda: {"recent_commits": [{"hash": "abc1234"}]})
    text = eng.answer_onboarding_question()["answer_markdown"]
    assert "records no Entire checkpoint" in text
    assert "entire.io" not in text


def test_line_ranges_survive_a_flat_package_layout(tmp_path):
    """Lambda ships modules at <root>/verifix/, not <root>/src/verifix/; locations must still resolve."""
    (tmp_path / "benchmarks").symlink_to(ROOT / "benchmarks")  # Lambda ships benchmarks/ but not src/
    eng = EntireIntelligenceEngine(tmp_path)
    eng._load_telemetry_snapshot = lambda: {}
    cites = eng.answer_onboarding_question()["code_graph_citations"]
    assert all(re.fullmatch(r"src/verifix/\w+\.py:\d+-\d+", c["location"]) for c in cites), cites
