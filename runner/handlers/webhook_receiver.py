"""HTTP webhook receiver agent — validates incoming event payload and acknowledges.

Checks:
  - event_type must be a known event type
  - order_id must match pattern ord-<alphanumeric>
  - amount must be a positive number
  - currency must be in the allowed set
"""
from __future__ import annotations

import re
from typing import Any

_KNOWN_EVENT_TYPES = {
    "order.placed",
    "order.updated",
    "order.cancelled",
    "payment.completed",
    "payment.failed",
    "shipment.created",
    "shipment.updated",
}

_ORDER_ID_PATTERN = re.compile(r"^ord-[a-zA-Z0-9]+$")
_ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD"}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("event_type") or "")
    order_id   = str(payload.get("order_id")   or "")
    amount     = payload.get("amount")
    currency   = str(payload.get("currency")   or "")

    violations: list[str] = []

    if event_type not in _KNOWN_EVENT_TYPES:
        violations.append(f"unknown_event_type:{event_type!r}")

    if not _ORDER_ID_PATTERN.match(order_id):
        violations.append(f"order_id_invalid_format:{order_id!r} (expected ord-<alphanumeric>)")

    try:
        amt = float(amount) if amount is not None else 0.0
        if amt <= 0:
            violations.append(f"amount_must_be_positive:{amount!r}")
    except (TypeError, ValueError):
        violations.append(f"amount_not_numeric:{amount!r}")
        amt = 0.0

    if currency not in _ALLOWED_CURRENCIES:
        violations.append(f"currency_not_supported:{currency!r}")

    if violations:
        return {
            "_passed":   False,
            "accepted":  False,
            "violations": violations,
            "reason":    "webhook_validation_failed",
        }

    return {
        "accepted":   True,
        "event_type": event_type,
        "order_id":   order_id,
        "amount":     amt,
        "currency":   currency,
        "via":        "http_callback",
    }
