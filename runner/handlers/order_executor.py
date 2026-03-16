"""Order executor handler — executes an order after validation."""
from __future__ import annotations

from typing import Any


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    order_id = str(payload.get("order_id") or "")

    if not order_id.strip():
        return {
            "_passed": False,
            "executed": False,
            "reason": "order_id_missing",
        }

    execution_id = f"exec-{abs(hash(order_id)) % 90000 + 10000}"
    return {
        "executed": True,
        "order_id": order_id,
        "execution_id": execution_id,
    }
