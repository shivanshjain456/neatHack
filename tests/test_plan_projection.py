import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from verifix.server import app, plan_projection

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = json.loads((ROOT / "benchmarks" / "plan_xlsx_computed.json").read_text(encoding="utf-8"))


def test_projection_matches_recalculated_workbook_and_business_plan():
    plan = plan_projection(SNAPSHOT)
    months = {m["month"]: m for m in plan["milestones"]}
    assert sorted(months) == [1, 6, 12, 24]
    business = (ROOT / "BUSINESS_PLAN.md").read_text(encoding="utf-8")
    for m in months.values():
        assert f"${m['arr']:,.0f}" in business
    assert plan["first_positive_ebitda_month"] == SNAPSHOT["first_positive_ebitda_month"]
    assert f"Month {plan['first_positive_ebitda_month']}" in business


@pytest.mark.parametrize("bad", [None, {}, {"months": []}, {"months": "x"},
                                 dict(SNAPSHOT, lowest_cash=None),
                                 dict(SNAPSHOT, months=[m for m in SNAPSHOT["months"] if m["month"] != 12])])
def test_missing_or_malformed_snapshot_yields_none(bad):
    assert plan_projection(bad) is None


def test_non_finite_values_are_rejected():
    months = [dict(m, arr=math.inf) if m["month"] == 24 else m for m in SNAPSHOT["months"]]
    assert plan_projection(dict(SNAPSHOT, months=months)) is None


def test_workspace_exposes_projection():
    with TestClient(app) as client:
        body = client.get("/api/workspace").json()
    assert body["plan_projection"] == plan_projection(SNAPSHOT)
