"""Downstream tax invoice generator that calls calculate_tiered_fee."""

from ledger.fees import calculate_tiered_fee
from ledger.money import format_usd, validate_cents


def render_tax_invoice(invoice_id: str, line_items: list[dict], tax_bps: int = 1800) -> dict:
    """Build a merchant fee tax invoice from transaction line items."""
    subtotal_fee_cents = 0
    for item in line_items:
        fee = calculate_tiered_fee(item["amount_cents"], item["tier_bps"])
        validate_cents(fee)
        subtotal_fee_cents += fee

    tax_cents = calculate_tiered_fee(subtotal_fee_cents, tax_bps, min_fee_cents=0)
    validate_cents(tax_cents)
    grand_total_cents = subtotal_fee_cents + tax_cents
    return {
        "invoice_id": invoice_id,
        "subtotal_fee_cents": subtotal_fee_cents,
        "tax_cents": tax_cents,
        "grand_total_cents": grand_total_cents,
        "formatted_total": format_usd(grand_total_cents),
    }
