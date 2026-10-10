"""API Gateway middleware caller for TokenBucket."""

from ratelimiter.bucket import TokenBucket


class APIGatewayMiddleware:
    """Enforces per-tenant rate limits using TokenBucket."""

    def __init__(self, capacity: int = 10, refill_rate: float = 2.0):
        self.buckets: dict[str, TokenBucket] = {}
        self.capacity = capacity
        self.refill_rate = refill_rate

    def handle_request(self, tenant_id: str, cost: int, timestamp: float) -> dict:
        if tenant_id not in self.buckets:
            self.buckets[tenant_id] = TokenBucket(self.capacity, self.refill_rate, initial_ts=timestamp)
        bucket = self.buckets[tenant_id]
        allowed, remaining, retry_after = bucket.consume(cost, timestamp)
        return {
            "status_code": 200 if allowed else 429,
            "allowed": allowed,
            "remaining_tokens": remaining,
            "retry_after_sec": retry_after,
        }
