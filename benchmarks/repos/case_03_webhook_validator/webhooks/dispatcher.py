"""Downstream webhook dispatcher caller."""

from webhooks.signature import verify_webhook_signature


class WebhookDispatcher:
    def __init__(self, secret: str):
        self.secret = secret
        self.delivered_events: list[str] = []

    def dispatch(self, event_id: str, payload: str, sig_header: str, ts_header: str | int, now_epoch: int) -> dict:
        ok, reason = verify_webhook_signature(
            payload_body=payload,
            signature_header=sig_header,
            timestamp_header=ts_header,
            secret=self.secret,
            now_epoch=now_epoch,
        )
        if ok and event_id not in self.delivered_events:
            self.delivered_events.append(event_id)
        return {"event_id": event_id, "accepted": ok, "reason": reason}
