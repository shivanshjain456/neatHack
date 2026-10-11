"""Ingest payment events.

Events may be delivered more than once (at-least-once delivery): a retry carries the same
``event_id``. Each distinct ``event_id`` must be counted exactly once (first occurrence wins).
Two different ``event_id``s that happen to carry an identical payload are distinct events and
must both be counted.
"""

from typing import Any


def process_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the deduplicated event list and the totals over it.

    BUG: retries are not deduplicated, so a redelivered ``event_id`` is counted (and summed)
    again, inflating ``total_cents`` and ``count`` and leaking duplicates into ``events``.
    """
    seen: list[dict[str, Any]] = []
    total = 0
    for ev in events:
        # Should skip events whose event_id was already seen; currently appends every record.
        seen.append(ev)
        total += ev["amount_cents"]
    return {"total_cents": total, "count": len(seen), "events": seen}
