"""Tests for webhook signature verification and dispatcher caller."""

import hashlib
import hmac
from webhooks.signature import verify_webhook_signature, parse_webhook_timestamp
from webhooks.dispatcher import WebhookDispatcher


def _make_sig(secret: str, epoch_ts: int, body: str) -> str:
    msg = f"{epoch_ts}.{body}".encode("utf-8")
    return "sha256=" + hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def test_iso8601_and_epoch_timestamp_parsing():
    # 2026-10-10T07:00:00Z == 1791615600
    ts_utc = parse_webhook_timestamp("2026-10-10T07:00:00Z")
    ts_ist = parse_webhook_timestamp("2026-10-10T12:30:00+05:30")
    assert ts_utc == ts_ist
    assert parse_webhook_timestamp(str(ts_utc)) == ts_utc


def test_canonical_hmac_and_dispatcher_caller():
    secret = "whsec_neathack_2026"
    epoch = parse_webhook_timestamp("2026-10-10T07:00:00Z")
    body = '{"event":"payment.succeeded","amount":2000}'
    sig = _make_sig(secret, epoch, body)

    ok, reason = verify_webhook_signature(body, sig, "2026-10-10T12:30:00+05:30", secret, now_epoch=epoch + 15)
    assert (ok, reason) == (True, "ok")

    dispatcher = WebhookDispatcher(secret)
    res = dispatcher.dispatch("evt_01", body, sig, "2026-10-10T07:00:00Z", now_epoch=epoch + 30)
    assert res == {"event_id": "evt_01", "accepted": True, "reason": "ok"}
    assert dispatcher.delivered_events == ["evt_01"]
