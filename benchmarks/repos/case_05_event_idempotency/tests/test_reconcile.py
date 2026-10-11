"""Caller tests: reconciliation depends on a retry-free total."""

from events.reconcile import reconcile


def _ev(eid, amount, region="APAC"):
    return {"event_id": eid, "amount_cents": amount, "payload": {"region": region}}


def test_reconcile_matches_ledger_when_deduped():
    events = [_ev("e1", 1000), _ev("e1", 1000), _ev("e2", 500)]
    res = reconcile(events, 1500)
    assert res["matched"] is True
    assert res["discrepancy_cents"] == 0
    assert res["processed_count"] == 2


def test_reconcile_flags_real_discrepancy():
    events = [_ev("e1", 1000), _ev("e2", 500)]
    res = reconcile(events, 1400)
    assert res["matched"] is False
    assert res["discrepancy_cents"] == 100
