"""Assurance spec for case_01 (ledger fees); derived from the fees.py docstring contract."""

from fractions import Fraction


def _oracle_fee(amount, bps, min_fee):
    if amount == 0:
        return 0
    return max(round(Fraction(amount * bps, 10000)), min_fee)   # round(Fraction) is half-to-even


def contract_tiered_fee_exact_half_even(rng):
    """calculate_tiered_fee == max(half-even(amount*bps/10000), min_fee), 0 for 0, always int."""
    from ledger.fees import calculate_tiered_fee
    amount = rng.choice([0, rng.randint(1, 200), rng.randint(1, 10 ** 7), rng.randrange(0, 10 ** 6, 2) * 100])
    bps = rng.choice([0, 1, 25, 125, 175, 250, 299, 10000, rng.randint(0, 10000)])
    min_fee = rng.choice([0, 1, 50, rng.randint(0, 500)])
    got = calculate_tiered_fee(amount, bps, min_fee)
    want = _oracle_fee(amount, bps, min_fee)
    assert type(got) is int, f"calculate_tiered_fee({amount}, {bps}, {min_fee}) returned {type(got).__name__}"
    assert got == want, f"calculate_tiered_fee({amount}, {bps}, {min_fee}) = {got}, contract requires {want}"


def contract_default_min_fee_is_50(rng):
    """The default min_fee_cents stays 50 (settlement and invoicing callers rely on it)."""
    from ledger.fees import calculate_tiered_fee
    amount = rng.randint(1, 2000)
    bps = rng.randint(1, 100)
    assert calculate_tiered_fee(amount, bps) == _oracle_fee(amount, bps, 50), f"default min fee changed for ({amount}, {bps})"


def mr_fee_monotonic_in_amount(rng):
    """Raising the amount never lowers the fee (same tier, same minimum)."""
    from ledger.fees import calculate_tiered_fee
    a = rng.randint(0, 10 ** 6)
    b = a + rng.randint(0, 10 ** 4)
    bps = rng.randint(0, 10000)
    fa, fb = calculate_tiered_fee(a, bps, 0), calculate_tiered_fee(b, bps, 0)
    assert fa <= fb, f"fee({a})={fa} > fee({b})={fb} at {bps} bps"


def _split(rng):
    legs = [rng.randint(0, 50000) for _ in range(rng.randint(1, 6))]
    return sum(legs), legs, rng.choice([1, 99, 125, 175, 250, 333, rng.randint(0, 10000)])


def contract_split_conserves_cents(rng):
    """Split fees sum exactly to the fee on the total; total_fee_cents equals that sum."""
    from ledger.fees import calculate_split_fees
    total, legs, bps = _split(rng)
    res = calculate_split_fees(total, legs, bps)
    want = _oracle_fee(total, bps, 0)
    assert sum(res["allocated_fees_cents"]) == want, f"split {legs} at {bps}: legs sum {sum(res['allocated_fees_cents'])} != {want}"
    assert res["total_fee_cents"] == want, f"split {legs} at {bps}: total_fee_cents {res['total_fee_cents']} != {want}"


def contract_split_residual_to_largest_leg(rng):
    """Only the largest leg (ties: highest index) absorbs the rounding residual."""
    from ledger.fees import calculate_split_fees
    total, legs, bps = _split(rng)
    res = calculate_split_fees(total, legs, bps)["allocated_fees_cents"]
    big = max(range(len(legs)), key=lambda i: (legs[i], i))
    for i, leg in enumerate(legs):
        if i != big:
            assert res[i] == _oracle_fee(leg, bps, 0), f"split {legs} at {bps}: leg {i} got {res[i]}, expected {_oracle_fee(leg, bps, 0)}"


def mr_single_leg_split_equals_direct_fee(rng):
    """A one-leg split charges exactly the direct fee on that amount."""
    from ledger.fees import calculate_split_fees
    amount, bps = rng.randint(0, 10 ** 6), rng.randint(0, 10000)
    res = calculate_split_fees(amount, [amount], bps)
    assert res["allocated_fees_cents"] == [_oracle_fee(amount, bps, 0)], f"single leg {amount} at {bps}: {res}"


def _split_input(rng):
    total, legs, bps = _split(rng)
    return {"args": [total, legs, bps], "kwargs": {}}


INPUT_GENERATORS = {"calculate_split_fees": _split_input}
