"""Assurance spec for case_03 (webhook signatures); derived from signature.py docstrings and catalog goal."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

REASONS = {"ok", "timestamp_out_of_range", "signature_mismatch", "invalid_timestamp"}


def _sig(secret, epoch, body):
    return "sha256=" + hmac.new(secret.encode(), f"{epoch}.{body}".encode(), hashlib.sha256).hexdigest()


def _iso(epoch, offset_minutes):
    tz = timezone(timedelta(minutes=offset_minutes))
    s = datetime.fromtimestamp(epoch, tz).isoformat()
    return s.replace("+00:00", "Z") if offset_minutes == 0 else s


def _body(rng):
    return rng.choice(['{"event":"payment.succeeded","amount":2000}', "", "plain text", '{"a":[1,2,3]}', "é✓ unicode"])


def mr_iso_and_epoch_forms_agree(rng):
    """An instant parses to the same epoch as int, digit string, ISO-8601 Z, or any UTC offset."""
    from webhooks.signature import parse_webhook_timestamp
    epoch = rng.randint(0, 4_000_000_000)
    off = rng.choice([0, 330, -300, 60, 345, -720])
    forms = [epoch, str(epoch), _iso(epoch, 0), _iso(epoch, off)]
    got = [parse_webhook_timestamp(f) for f in forms]
    assert all(g == epoch for g in got), f"epoch {epoch}: forms {forms} parsed to {got}"


def contract_valid_signature_accepted(rng):
    """A canonical f"{epoch}.{body}" signature inside the window verifies as (True, "ok")."""
    from webhooks.signature import verify_webhook_signature
    epoch = rng.randint(1_600_000_000, 2_000_000_000)
    secret, body = rng.choice(["whsec_a", "k" * 32, "s3cr3t"]), _body(rng)
    header = rng.choice([epoch, str(epoch), _iso(epoch, 0), _iso(epoch, rng.choice([330, -300]))])
    now = epoch + rng.randint(-300, 300)
    got = verify_webhook_signature(body, _sig(secret, epoch, body), header, secret, now)
    assert got == (True, "ok"), f"valid signature rejected: header={header!r} now={now} -> {got}"


def contract_tampering_rejected(rng):
    """A modified body, wrong secret, or signature over the body alone is a signature_mismatch."""
    from webhooks.signature import verify_webhook_signature
    epoch = rng.randint(1_600_000_000, 2_000_000_000)
    body = _body(rng) + "x"
    sig = rng.choice([
        _sig("whsec_a", epoch, body + "!"),
        _sig("other", epoch, body),
        "sha256=" + hmac.new(b"whsec_a", body.encode(), hashlib.sha256).hexdigest(),
    ])
    got = verify_webhook_signature(body, sig, epoch, "whsec_a", epoch)
    assert got == (False, "signature_mismatch"), f"tampered request accepted or misreported: {got}"


def contract_replay_window(rng):
    """Outside +-tolerance the result is timestamp_out_of_range; the exact boundary is accepted."""
    from webhooks.signature import verify_webhook_signature
    epoch, tol = rng.randint(1_600_000_000, 2_000_000_000), rng.choice([60, 300, 900])
    body = _body(rng)
    sig = _sig("whsec_a", epoch, body)
    edge = verify_webhook_signature(body, sig, epoch, "whsec_a", epoch + rng.choice([-tol, tol]), tol)
    late = verify_webhook_signature(body, sig, epoch, "whsec_a", epoch + rng.choice([-1, 1]) * (tol + rng.randint(1, 10 ** 6)), tol)
    assert edge == (True, "ok"), f"boundary |now-ts|=={tol} rejected: {edge}"
    assert late == (False, "timestamp_out_of_range"), f"stale request not rejected: {late}"


def contract_return_shape(rng):
    """Always returns (bool, reason) with a documented reason, never raises on bad timestamps."""
    from webhooks.signature import verify_webhook_signature
    header = rng.choice(["", "yesterday", "2026-13-45T00:00:00Z", "12ab", " 1700000000 ", 1700000000, "1700000000"])
    got = verify_webhook_signature("{}", "sha256=00", header, "k", 1700000000)
    assert isinstance(got, tuple) and len(got) == 2 and type(got[0]) is bool and got[1] in REASONS, f"{header!r} -> {got!r}"


def _ts_input(rng):
    epoch = rng.randint(0, 4_000_000_000)
    return {"args": [rng.choice([epoch, float(epoch), str(epoch), _iso(epoch, 0), _iso(epoch, 330), "garbage", "", " 12 "])], "kwargs": {}}


def _verify_input(rng):
    epoch = rng.randint(1_600_000_000, 2_000_000_000)
    body, secret = _body(rng), rng.choice(["whsec_a", "k"])
    sig = rng.choice([_sig(secret, epoch, body), "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest(), "", "sha256=zz"])
    header = rng.choice([epoch, str(epoch), _iso(epoch, 0), _iso(epoch, 330), "bad"])
    return {"args": [body, sig, header, secret, epoch + rng.randint(-600, 600)], "kwargs": {}}


INPUT_GENERATORS = {"parse_webhook_timestamp": _ts_input, "verify_webhook_signature": _verify_input}


def contract_invalid_timestamp_rejected(rng):
    """An unparseable timestamp header is always (False, "invalid_timestamp"), whatever the signature."""
    from webhooks.signature import verify_webhook_signature
    header = rng.choice(["", "yesterday", "2026-13-45T00:00:00Z", "12ab", "nan", "--"])
    body = _body(rng)
    got = verify_webhook_signature(body, _sig("whsec_a", 1700000000, body), header, "whsec_a", 1700000000)
    assert got == (False, "invalid_timestamp"), f"unparseable header {header!r} -> {got!r}"


def mr_float_header_equals_int_header(rng):
    """The signature accepts float headers; a float epoch verifies exactly like the same int epoch."""
    from webhooks.signature import parse_webhook_timestamp, verify_webhook_signature
    epoch = rng.randint(1_600_000_000, 2_000_000_000)
    body = _body(rng)
    assert parse_webhook_timestamp(float(epoch)) == epoch, f"float {float(epoch)} parsed differently"
    a = verify_webhook_signature(body, _sig("whsec_a", epoch, body), epoch, "whsec_a", epoch + 5)
    b = verify_webhook_signature(body, _sig("whsec_a", epoch, body), float(epoch), "whsec_a", epoch + 5)
    assert a == b == (True, "ok"), f"int header -> {a}, float header -> {b}"


def contract_default_window_is_300s(rng):
    """WebhookDispatcher omits tolerance_sec, so the 300 s default is part of the caller contract."""
    from webhooks.signature import verify_webhook_signature
    epoch = rng.randint(1_600_000_000, 2_000_000_000)
    body = _body(rng)
    sig = _sig("whsec_a", epoch, body)
    side = rng.choice([-1, 1])
    assert verify_webhook_signature(body, sig, epoch, "whsec_a", epoch + side * 300) == (True, "ok"), "edge of default window rejected"
    assert verify_webhook_signature(body, sig, epoch, "whsec_a", epoch + side * 301) == (False, "timestamp_out_of_range"), "default window wider than 300 s"
