"""Reconcile ingested totals against an expected ledger total."""

from typing import Any

from events.ingest import process_events


def reconcile(events: list[dict[str, Any]], expected_total_cents: int) -> dict[str, Any]:
    """Compare the deduplicated total to ``expected_total_cents``.

    A retry-inflated total will disagree with the ledger and report a spurious discrepancy.
    """
    res = process_events(events)
    diff = res["total_cents"] - expected_total_cents
    return {"matched": diff == 0, "discrepancy_cents": diff, "processed_count": res["count"]}
