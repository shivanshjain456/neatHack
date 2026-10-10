"""Fee calculation engine for tiered merchant processing."""

from ledger.money import validate_cents


def calculate_tiered_fee(amount_cents: int, tier_bps: int, min_fee_cents: int = 50) -> int:
    """Calculate the processing fee in integer cents for a transaction.

    Contract required by downstream callers (settlement & invoicing):
    - Must accept (amount_cents: int, tier_bps: int, min_fee_cents: int = 50)
    - Must return an `int` representing integer cents.
    - For amount_cents == 0, fee must be 0.
    - Must use exact Decimal banker's rounding (ROUND_HALF_EVEN) on basis points
      (10,000 bps = 100%) before applying min_fee_cents, avoiding IEEE-754 float drift.
    """
    validate_cents(amount_cents)
    if amount_cents == 0:
        return 0
    # BUG: IEEE-754 float division + truncation `int(...)` loses precision on exact
    # basis-point boundaries (e.g., 33350 cents at 175 bps = 583.625 -> truncates to 583
    # instead of rounding to 584 cents, and 10050 cents at 250 bps = 251.25 -> 251).
    raw_fee = int(amount_cents * (tier_bps / 10000.0))
    return max(raw_fee, min_fee_cents)


def calculate_split_fees(total_amount_cents: int, splits_cents: list[int], tier_bps: int) -> dict:
    """Calculate fees across split sub-merchants and reconcile any rounding delta."""
    validate_cents(total_amount_cents)
    if sum(splits_cents) != total_amount_cents:
        raise ValueError("Sum of splits_cents must equal total_amount_cents")

    total_expected_fee = calculate_tiered_fee(total_amount_cents, tier_bps, min_fee_cents=0)
    allocated_fees = [calculate_tiered_fee(part, tier_bps, min_fee_cents=0) for part in splits_cents]
    # BUG: rounding residual (total_expected_fee - sum(allocated_fees)) is never applied
    # to the largest split leg, violating conservation of cents across split settlements!
    return {
        "total_fee_cents": sum(allocated_fees),
        "allocated_fees_cents": allocated_fees,
    }
