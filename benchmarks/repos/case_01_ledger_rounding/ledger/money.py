"""Monetary representation and validation helpers for the settlement ledger."""

from decimal import Decimal, ROUND_HALF_EVEN


def validate_cents(amount_cents: int) -> int:
    """Ensure monetary amounts are represented as non-negative integer cents."""
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise TypeError(f"amount_cents must be an integer, got {type(amount_cents).__name__}")
    if amount_cents < 0:
        raise ValueError(f"amount_cents cannot be negative: {amount_cents}")
    return amount_cents


def format_usd(amount_cents: int) -> str:
    """Format integer cents into a standard USD string."""
    validate_cents(amount_cents)
    dollars = Decimal(amount_cents) / Decimal(100)
    return f"${dollars.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN):,.2f}"
