"""Cryptographic webhook signature and replay-window validator."""

import hashlib
import hmac
from datetime import datetime, timezone


def parse_webhook_timestamp(ts_header: str | int | float) -> int:
    """Parse either Unix epoch seconds or ISO-8601 timestamp into integer UTC epoch seconds."""
    if isinstance(ts_header, (int, float)):
        return int(ts_header)
    raw = str(ts_header).strip()
    # BUG: Only handles pure digit strings; raises ValueError when upstream sends
    # ISO-8601 strings like "2026-10-10T07:00:00Z" or "2026-10-10T12:30:00+05:30"!
    return int(raw)


def verify_webhook_signature(
    payload_body: str,
    signature_header: str,
    timestamp_header: str | int,
    secret: str,
    now_epoch: int,
    tolerance_sec: int = 300,
) -> tuple[bool, str]:
    """Verify HMAC-SHA256 webhook signature and replay tolerance window.

    Downstream caller `WebhookDispatcher.dispatch` requires `(is_valid: bool, reason: str)`
    where valid returns `(True, "ok")`, expired returns `(False, "timestamp_out_of_range")`,
    and bad signature returns `(False, "signature_mismatch")`.
    Canonical signing string is `f"{epoch_ts}.{payload_body}"`.
    """
    try:
        epoch_ts = parse_webhook_timestamp(timestamp_header)
    except Exception:
        return False, "invalid_timestamp"

    if abs(now_epoch - epoch_ts) > tolerance_sec:
        return False, "timestamp_out_of_range"

    # BUG: Signs `payload_body` alone instead of canonical `f"{epoch_ts}.{payload_body}"`
    # and strips "sha256=" prefix Case-Sensitively without handling leading/trailing whitespace.
    expected = hmac.new(secret.encode("utf-8"), payload_body.encode("utf-8"), hashlib.sha256).hexdigest()
    provided = signature_header.replace("sha256=", "")
    if not hmac.compare_digest(expected, provided):
        return False, "signature_mismatch"
    return True, "ok"
