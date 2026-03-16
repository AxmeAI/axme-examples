"""Order validator handler — validates order structure."""
from __future__ import annotations

from typing import Any


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []

    order_id = str(payload.get("order_id") or "")
    items = payload.get("items", [])

    if not order_id.strip():
        violations.append("order_id_missing")

    if not items or not isinstance(items, list):
        violations.append("items_missing")

    passed = len(violations) == 0
    result = {
        "_passed": passed,
        "validation_passed": passed,
        "violations": violations,
        "order_id": order_id,
    }
    if not passed:
        result["reason"] = "order_validation_failed"
    return result
