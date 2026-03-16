"""Fulfillment service agent — processes an order and returns a tracking ID.

Checks:
  - order_id must be a non-empty string
  - customer_id must be a non-empty string
  - items must be a non-empty list, each with sku and quantity
  - shipping must be one of: standard, express, overnight

tracking_id is deterministic: derived from order_id (same input -> same tracking ID).
estimated_delivery_days depends on the shipping tier from the payload.
"""
from __future__ import annotations

from typing import Any

_SHIPPING_DAYS: dict[str, int] = {
    "standard": 5,
    "express": 2,
    "overnight": 1,
}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    order_id = str(payload.get("order_id") or "")
    customer_id = str(payload.get("customer_id") or "")
    items = payload.get("items")
    shipping = str(payload.get("shipping") or "").lower()

    violations: list[str] = []

    if not order_id.strip():
        violations.append("order_id_missing")

    if not customer_id.strip():
        violations.append("customer_id_missing")

    if not items or not isinstance(items, list) or len(items) == 0:
        violations.append("items_empty_or_missing")
    else:
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                violations.append(f"items[{i}]_not_an_object")
                continue
            if not item.get("sku"):
                violations.append(f"items[{i}].sku_missing")
            qty = item.get("quantity")
            if qty is None or not isinstance(qty, (int, float)) or qty <= 0:
                violations.append(f"items[{i}].quantity_invalid:{qty!r}")

    if shipping not in _SHIPPING_DAYS:
        violations.append(
            f"shipping_tier_unknown:{shipping!r} (allowed: {', '.join(sorted(_SHIPPING_DAYS))})"
        )

    if violations:
        return {
            "_passed": False,
            "fulfilled": False,
            "violations": violations,
            "reason": "fulfillment_validation_failed",
        }

    # Deterministic tracking ID from order_id
    suffix = abs(hash(order_id)) % 90000 + 10000
    tracking_id = f"TRK-{order_id.upper().replace('-', '')}-{suffix}"

    delivery_days = _SHIPPING_DAYS[shipping]
    item_count = sum(
        int(item.get("quantity", 1))
        for item in (items or [])
        if isinstance(item, dict)
    )

    return {
        "fulfilled": True,
        "tracking_id": tracking_id,
        "estimated_delivery_days": delivery_days,
        "shipping_tier": shipping,
        "items_count": item_count,
        "order_id": order_id,
    }
