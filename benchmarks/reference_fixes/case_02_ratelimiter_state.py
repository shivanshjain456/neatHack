"""Distributed token-bucket rate limiter core."""


class TokenBucket:
    """Token bucket with continuous fractional refill."""

    def __init__(self, capacity: int, refill_rate_per_sec: float, initial_ts: float = 0.0):
        self.capacity = int(capacity)
        self.refill_rate_per_sec = float(refill_rate_per_sec)
        self.tokens = float(capacity)
        self.last_refill_ts = float(initial_ts)

    def _refill(self, now: float) -> None:
        if now > self.last_refill_ts:
            elapsed = now - self.last_refill_ts
            self.tokens = min(float(self.capacity), self.tokens + elapsed * self.refill_rate_per_sec)
            self.last_refill_ts = float(now)

    def consume(self, cost: int, now: float) -> tuple[bool, int, float]:
        """Attempt to consume `cost` tokens at timestamp `now`."""
        if cost <= 0:
            raise ValueError("cost must be positive")
        self._refill(now)
        if self.tokens >= cost:
            self.tokens -= cost
            return True, int(self.tokens), 0.0
        retry_after = round((cost - self.tokens) / self.refill_rate_per_sec, 4)
        return False, int(self.tokens), retry_after
