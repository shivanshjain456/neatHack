"""Cryptographic webhook signature and replay-window validator."""

import hashlib
import hmac
from datetime import datetime, timezone


def parse_webhook_timestamp(ts_header: str | int | float) -> int:
    """Parse either Unix epoch seconds or ISO-8601 timestamp into integer UTC epoch seconds."""
    if isinstance(ts_header, (int, float)):
        return int(ts_header)
    raw = str(ts_header).strip()
    try:
        return int(raw)
    except ValueError:
        return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())


def verify_webhook_signature(
    payload_body: str,
    signature_header: str,
    timestamp_header: str | int,
    secret: str,
    now_epoch: int,
    tolerance_sec: int = 300,
) -> tuple[bool, str]:
    """Verify HMAC-SHA256 webhook signature and replay tolerance window."""
    try:
        epoch_ts = parse_webhook_timestamp(timestamp_header)
    except Exception:
        return False, "invalid_timestamp"

    if abs(now_epoch - epoch_ts) > tolerance_sec:
        return False, "timestamp_out_of_range"

    signed = f"{epoch_ts}.{payload_body}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    provided = signature_header.replace("sha256=", "")
    if not hmac.compare_digest(expected, provided):
        return False, "signature_mismatch"
    return True, "ok"
