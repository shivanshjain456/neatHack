"""Reproduction tests: retries must be deduplicated by event_id."""

from events.ingest import process_events


def _ev(eid, amount, region="APAC"):
    return {"event_id": eid, "amount_cents": amount, "payload": {"region": region}}


def test_retry_is_counted_once():
    events = [_ev("e1", 1000), _ev("e1", 1000), _ev("e2", 500)]
    res = process_events(events)
    assert res["count"] == 2
    assert res["total_cents"] == 1500


def test_first_occurrence_wins():
    # A retry with a corrupted amount must not override or add to the first delivery.
    events = [_ev("e1", 1000), {"event_id": "e1", "amount_cents": 999999, "payload": {"region": "APAC"}}]
    res = process_events(events)
    assert res["count"] == 1
    assert res["total_cents"] == 1000
    assert res["events"][0]["amount_cents"] == 1000
