"""Distributed token-bucket rate limiter core."""


class TokenBucket:
    """Token bucket with continuous fractional refill.

    Downstream callers (`APIGatewayMiddleware` and `QuotaSynchronizer`) depend on:
    - `consume(cost: int, now: float) -> tuple[bool, int, float]`
      returning `(allowed: bool, remaining_whole_tokens: int, retry_after_sec: float)`
    - `self.tokens` storing exact float tokens and `self.last_refill_ts` only advancing
      by the time actually accounted for in `self.tokens`.
    """

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
        # BUG 1: Refill is NOT called before checking `self.tokens >= cost`, AND
        # `self.last_refill_ts = now` is overwritten at the end without adding elapsed refill
        # when a request is rejected, wiping out accumulated refill time!
        # BUG 2: retry_after_sec returns 0.0 even when rejected instead of
        # round((cost - self.tokens) / self.refill_rate_per_sec, 4).
        if self.tokens >= cost:
            self.tokens -= cost
            self.last_refill_ts = float(now)
            return True, int(self.tokens), 0.0

        self.last_refill_ts = float(now)
        return False, int(self.tokens), 0.0
