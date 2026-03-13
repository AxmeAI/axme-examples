"""Order validator agent — validates an order and returns a validation score.

Used in Model A manual multi-step scenario (step 1/2).
The result (validation_score) depends on the actual order fields.
"""
from __future__ import annotations

import re
from typing import Any

_ORDER_ID_PATTERN = re.compile(r"^ORD-\d+$")
_ALLOWED_CURRENCIES = {"USD", "EUR", "GBP"}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    order_id   = str(payload.get("order_id")   or "")
    customer   = str(payload.get("customer")   or "")
    amount     = payload.get("amount")
    currency   = str(payload.get("currency")   or "")
    items      = payload.get("items")

    violations: list[str] = []
    score = 100

    if not _ORDER_ID_PATTERN.match(order_id):
        violations.append(f"order_id_format_invalid:{order_id!r}")
        score -= 30

    if not customer.strip():
        violations.append("customer_missing")
        score -= 20

    try:
        amt = float(amount) if amount is not None else 0.0
        if amt <= 0:
            violations.append(f"amount_not_positive:{amount!r}")
            score -= 20
        elif amt > 100_000:
            violations.append(f"amount_exceeds_limit:{amt}")
            score -= 15
    except (TypeError, ValueError):
        violations.append(f"amount_not_numeric:{amount!r}")
        score -= 20
        amt = 0.0

    if currency not in _ALLOWED_CURRENCIES:
        violations.append(f"currency_not_supported:{currency!r}")
        score -= 10

    if not items or not isinstance(items, list):
        violations.append("items_missing_or_empty")
        score -= 20

    score = max(0, score)
    passed = len(violations) == 0

    return {
        "_passed":          passed,
        "validation_score": score,
        "violations":       violations,
        "order_id":         order_id,
        "validated":        passed,
        **({"reason": "order_validation_failed"} if not passed else {}),
    }
