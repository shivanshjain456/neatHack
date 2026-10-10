"""Downstream caller regression tests for settlement batch processing and invoicing."""

from ledger.settlement import build_settlement_batch
from ledger.invoicing import render_tax_invoice


def test_settlement_batch_caller_contract():
    batch = build_settlement_batch(
        "batch_oct_10",
        [
            {"tx_id": "tx_1", "amount_cents": 33350, "tier_bps": 175},
            {"tx_id": "tx_2", "amount_cents": 10000, "tier_bps": 175},
            {"tx_id": "tx_3", "amount_cents": 0, "tier_bps": 175},
        ],
    )
    assert batch["gross_cents"] == 43350
    # 584 + 175 + 0 = 759
    assert batch["total_fee_cents"] == 759
    assert batch["net_payout_cents"] == 42591
    assert batch["formatted_net"] == "$425.91"
    assert isinstance(batch["integrity_checksum"], int)


def test_invoicing_caller_contract():
    inv = render_tax_invoice(
        "inv_2026_01",
        [
            {"amount_cents": 33350, "tier_bps": 175},
            {"amount_cents": 20000, "tier_bps": 200},
        ],
        tax_bps=1800,
    )
    # 584 + 400 = 984 subtotal; 984 * 0.18 = 177.12 -> 177 tax; total = 1161
    assert inv["subtotal_fee_cents"] == 984
    assert inv["tax_cents"] == 177
    assert inv["grand_total_cents"] == 1161
    assert inv["formatted_total"] == "$11.61"
