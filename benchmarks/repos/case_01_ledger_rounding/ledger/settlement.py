"""Downstream settlement batch processor that consumes calculate_tiered_fee."""

from ledger.fees import calculate_tiered_fee
from ledger.money import validate_cents, format_usd


def build_settlement_batch(batch_id: str, transactions: list[dict]) -> dict:
    """Aggregate gross, fee, and net integer cents for a merchant payout batch.

    Caller contract: requires `calculate_tiered_fee` to return an `int` (cents)
    so bitwise checksum and validate_cents succeed.
    """
    gross_cents = 0
    total_fee_cents = 0
    processed_rows = []

    for tx in transactions:
        amt = validate_cents(tx["amount_cents"])
        bps = tx.get("tier_bps", 175)
        fee = calculate_tiered_fee(amt, bps)
        # Downstream caller strictly validates integer cents and uses bitwise XOR checksum
        validate_cents(fee)
        net = amt - fee
        gross_cents += amt
        total_fee_cents += fee
        processed_rows.append({
            "tx_id": tx["tx_id"],
            "gross_cents": amt,
            "fee_cents": fee,
            "net_cents": net,
        })

    net_payout_cents = gross_cents - total_fee_cents
    checksum = (gross_cents ^ total_fee_cents ^ net_payout_cents) & 0xFFFFFFFF
    return {
        "batch_id": batch_id,
        "gross_cents": gross_cents,
        "total_fee_cents": total_fee_cents,
        "net_payout_cents": net_payout_cents,
        "formatted_net": format_usd(net_payout_cents),
        "integrity_checksum": checksum,
        "rows": processed_rows,
    }
