"""Caller tests: aggregation depends on correct event_id deduplication."""

from events.aggregate import total_by_region, region_event_count


def _ev(eid, amount, region):
    return {"event_id": eid, "amount_cents": amount, "payload": {"region": region}}


def test_region_totals_ignore_retries():
    events = [_ev("e1", 1000, "APAC"), _ev("e1", 1000, "APAC"), _ev("e2", 700, "EMEA")]
    assert total_by_region(events) == {"APAC": 1000, "EMEA": 700}


def test_distinct_ids_with_identical_payload_both_count():
    # Two genuinely separate events that happen to carry the same payload and amount.
    a = _ev("e1", 1000, "APAC")
    b = {"event_id": "e2", "amount_cents": 1000, "payload": {"region": "APAC"}}
    assert a["payload"] == b["payload"] and a["amount_cents"] == b["amount_cents"]
    assert total_by_region([a, b]) == {"APAC": 2000}
    assert region_event_count([a, b]) == {"APAC": 2}
