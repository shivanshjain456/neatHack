"""Fee calculation engine for tiered merchant processing."""

from decimal import Decimal, ROUND_HALF_EVEN

from ledger.money import validate_cents


def calculate_tiered_fee(amount_cents: int, tier_bps: int, min_fee_cents: int = 50) -> int:
    """Calculate the processing fee in integer cents for a transaction."""
    validate_cents(amount_cents)
    if amount_cents == 0:
        return 0
    raw_fee = int((Decimal(amount_cents) * Decimal(tier_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    return max(raw_fee, min_fee_cents)


def calculate_split_fees(total_amount_cents: int, splits_cents: list[int], tier_bps: int) -> dict:
    """Calculate fees across split sub-merchants and reconcile any rounding delta."""
    validate_cents(total_amount_cents)
    if sum(splits_cents) != total_amount_cents:
        raise ValueError("Sum of splits_cents must equal total_amount_cents")

    total_expected_fee = calculate_tiered_fee(total_amount_cents, tier_bps, min_fee_cents=0)
    allocated_fees = [calculate_tiered_fee(part, tier_bps, min_fee_cents=0) for part in splits_cents]
    residual = total_expected_fee - sum(allocated_fees)
    if residual and allocated_fees:
        largest = max(range(len(splits_cents)), key=lambda i: (splits_cents[i], i))
        allocated_fees[largest] += residual
    return {
        "total_fee_cents": sum(allocated_fees),
        "allocated_fees_cents": allocated_fees,
    }
