"""Webhook receiver agent — validates and accepts webhook events."""
from __future__ import annotations

from typing import Any

_ALLOWED_EVENT_TYPES = {
    "order.placed", "order.shipped", "order.delivered", "order.cancelled",
    "payment.received", "payment.refunded",
}
_ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY"}
_ORDER_ID_PREFIX = "ord-"


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []

    event_type = str(payload.get("event_type") or "")
    order_id = str(payload.get("order_id") or "")
    amount = payload.get("amount", 0)
    currency = str(payload.get("currency") or "")

    if event_type not in _ALLOWED_EVENT_TYPES:
        violations.append(f"event_type_unknown:{event_type!r}")

    if not order_id.startswith(_ORDER_ID_PREFIX):
        violations.append(f"order_id_invalid_format:{order_id!r}")

    if not isinstance(amount, (int, float)) or amount < 0:
        violations.append(f"amount_invalid:{amount!r}")

    if currency not in _ALLOWED_CURRENCIES:
        violations.append(f"currency_unsupported:{currency!r}")

    if violations:
        return {
            "_passed": False,
            "accepted": False,
            "violations": violations,
            "reason": "webhook_validation_failed",
        }

    return {
        "accepted": True,
        "event_type": event_type,
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "via": "http_callback",
    }
