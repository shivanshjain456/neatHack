"""Unit tests for fee precision and split-fee conservation."""

from ledger.fees import calculate_tiered_fee, calculate_split_fees


def test_exact_basis_point_rounding():
    # 33350 cents * 175 / 10000 = 583.625 -> ROUND_HALF_EVEN must yield 584 cents (int)
    fee = calculate_tiered_fee(33350, 175)
    assert isinstance(fee, int)
    assert fee == 584

    # Half-way tie to even: 10000 * 125 / 10000 = 125
    # 200 * 125 / 10000 = 2.5 -> ROUND_HALF_EVEN rounds 2.5 to 2 (with min_fee_cents=0)
    assert calculate_tiered_fee(200, 125, min_fee_cents=0) == 2
    # 600 * 125 / 10000 = 7.5 -> ROUND_HALF_EVEN rounds 7.5 to 8 (with min_fee_cents=0)
    assert calculate_tiered_fee(600, 125, min_fee_cents=0) == 8


def test_split_fee_conservation():
    # Total: 10000 cents at 175 bps -> expected total fee = 175 cents
    # Splits: [3333, 3333, 3334] -> individual fees [58, 58, 58] = 174 cents without residual reconciliation!
    # The residual +1 cent must be allocated to the largest split leg (index 2: 3334) -> [58, 58, 59]
    res = calculate_split_fees(10000, [3333, 3333, 3334], 175)
    assert res["total_fee_cents"] == 175
    assert sum(res["allocated_fees_cents"]) == 175
    assert res["allocated_fees_cents"] == [58, 58, 59]
