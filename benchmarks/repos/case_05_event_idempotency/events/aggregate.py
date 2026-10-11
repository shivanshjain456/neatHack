"""Aggregate deduplicated events by region."""

from typing import Any

from events.ingest import process_events


def total_by_region(events: list[dict[str, Any]]) -> dict[str, int]:
    """Sum ``amount_cents`` per ``payload['region']`` over the deduplicated events.

    Relies on ``process_events`` returning each distinct ``event_id`` exactly once. Two distinct
    event ids with an identical payload are separate events and must both contribute.
    """
    out: dict[str, int] = {}
    for ev in process_events(events)["events"]:
        region = ev["payload"]["region"]
        out[region] = out.get(region, 0) + ev["amount_cents"]
    return out


def region_event_count(events: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ev in process_events(events)["events"]:
        region = ev["payload"]["region"]
        out[region] = out.get(region, 0) + 1
    return out
