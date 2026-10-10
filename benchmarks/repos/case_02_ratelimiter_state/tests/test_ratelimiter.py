"""Tests for TokenBucket and downstream APIGatewayMiddleware."""

from ratelimiter.bucket import TokenBucket
from ratelimiter.middleware import APIGatewayMiddleware


def test_refill_preserved_across_rejected_burst():
    bucket = TokenBucket(capacity=10, refill_rate_per_sec=2.0, initial_ts=0.0)
    # Consume 9 tokens at t=0 -> 1.0 remaining
    allowed, rem, retry = bucket.consume(9, now=0.0)
    assert (allowed, rem, retry) == (True, 1, 0.0)

    # At t=1.5s, +3.0 tokens have refilled -> 4.0 tokens available.
    # Requesting 6 tokens at t=1.5s must be rejected with retry_after = (6 - 4) / 2.0 = 1.0s,
    # AND the 4.0 accumulated tokens must NOT be lost!
    allowed2, rem2, retry2 = bucket.consume(6, now=1.5)
    assert allowed2 is False
    assert rem2 == 4
    assert abs(retry2 - 1.0) < 1e-4

    # At t=2.0s (+0.5s later -> +1.0 token -> 5.0 tokens available), requesting 5 tokens must succeed!
    allowed3, rem3, retry3 = bucket.consume(5, now=2.0)
    assert allowed3 is True
    assert rem3 == 0
    assert retry3 == 0.0


def test_gateway_middleware_caller_contract():
    gw = APIGatewayMiddleware(capacity=10, refill_rate=2.0)
    r1 = gw.handle_request("tenant_a", cost=8, timestamp=100.0)
    assert r1["status_code"] == 200
    assert r1["remaining_tokens"] == 2

    # At t=101.0s (+2 tokens -> 4 available), burst of 6 gets 429 with retry_after = 1.0s
    r2 = gw.handle_request("tenant_a", cost=6, timestamp=101.0)
    assert r2["status_code"] == 429
    assert r2["remaining_tokens"] == 4
    assert abs(r2["retry_after_sec"] - 1.0) < 1e-4

    # At t=102.0s (+2 tokens -> 6 available), burst of 6 succeeds
    r3 = gw.handle_request("tenant_a", cost=6, timestamp=102.0)
    assert r3["status_code"] == 200
    assert r3["remaining_tokens"] == 0
