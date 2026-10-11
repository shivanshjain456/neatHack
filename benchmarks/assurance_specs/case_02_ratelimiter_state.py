"""Assurance spec for case_02 (token bucket); derived from the TokenBucket docstring and catalog goal."""


class _Reference:
    """Executable form of the documented contract: refill before check, rejection keeps tokens."""

    def __init__(self, capacity, rate, t0):
        self.capacity, self.rate, self.tokens, self.last = int(capacity), float(rate), float(capacity), float(t0)

    def consume(self, cost, now):
        if now > self.last:
            self.tokens = min(float(self.capacity), self.tokens + (now - self.last) * self.rate)
            self.last = float(now)
        if self.tokens >= cost:
            self.tokens -= cost
            return True, int(self.tokens), 0.0
        return False, int(self.tokens), round((cost - self.tokens) / self.rate, 4)


def _scenario(rng):
    cap = rng.randint(1, 20)
    rate = rng.choice([0.5, 1.0, 2.0, 4.0, 0.25])
    t = float(rng.randint(0, 1000))
    t0 = t
    ops = []
    for _ in range(rng.randint(1, 12)):
        t += rng.choice([0.0, 0.25, 0.5, 1.0, 1.5, 3.0])     # exact binary fractions: no float noise
        ops.append([rng.randint(1, cap + 3), t])
    return cap, rate, t0, ops


def contract_consume_matches_documented_model(rng):
    """Every consume() result equals the documented refill-then-check model."""
    from ratelimiter.bucket import TokenBucket
    cap, rate, t0, ops = _scenario(rng)
    b, ref = TokenBucket(cap, rate, initial_ts=t0), _Reference(cap, rate, t0)
    for cost, now in ops:
        got, want = b.consume(cost, now), ref.consume(cost, now)
        assert isinstance(got, tuple) and len(got) == 3, f"consume returned {got!r}"
        assert (got[0], got[1]) == (want[0], want[1]) and abs(got[2] - want[2]) < 1e-4, \
            f"TokenBucket({cap}, {rate}, {t0}) ops={ops}: at {(cost, now)} got {got}, contract requires {want}"


def mr_time_shift_invariance(rng):
    """Shifting every timestamp by the same offset leaves every decision unchanged."""
    from ratelimiter.bucket import TokenBucket
    cap, rate, t0, ops = _scenario(rng)
    shift = float(rng.choice([1, 64, 1024]))
    a, b = TokenBucket(cap, rate, initial_ts=t0), TokenBucket(cap, rate, initial_ts=t0 + shift)
    for cost, now in ops:
        ra, rb = a.consume(cost, now), b.consume(cost, now + shift)
        assert ra == rb, f"shift {shift}: {ra} vs {rb} for ops {ops}"


def contract_retry_after_semantics(rng):
    """Allowed requests return retry 0.0; rejected ones a positive wait; remaining never exceeds capacity."""
    from ratelimiter.bucket import TokenBucket
    cap, rate, t0, ops = _scenario(rng)
    b = TokenBucket(cap, rate, initial_ts=t0)
    for cost, now in ops:
        ok, rem, retry = b.consume(cost, now)
        assert type(ok) is bool and type(rem) is int and isinstance(retry, float), f"types {(ok, rem, retry)}"
        assert 0 <= rem <= cap, f"remaining {rem} outside [0, {cap}]"
        assert (retry == 0.0) if ok else (retry > 0), f"retry_after {retry} inconsistent with allowed={ok}"


DRIVE = '''
def drive(module, inp):
    b = module.TokenBucket(inp["capacity"], inp["rate"], initial_ts=inp["t0"])
    return [list(b.consume(cost, now)) for cost, now in inp["ops"]]
'''


def _drive_input(rng):
    cap, rate, t0, ops = _scenario(rng)
    return {"capacity": cap, "rate": rate, "t0": t0, "ops": ops}


INPUT_GENERATORS = {"TokenBucket.consume": _drive_input, "TokenBucket.__init__": _drive_input, "TokenBucket._refill": _drive_input}
DRIVERS = {"TokenBucket.consume": DRIVE, "TokenBucket.__init__": DRIVE, "TokenBucket._refill": DRIVE}
