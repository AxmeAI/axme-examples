"""Order executor agent — executes an order based on validated input.

Used in Model A manual multi-step scenario (step 2/2).
Receives the validation result from step 1 (embedded in payload by the initiator)
and executes the order if the score is sufficient.

The execution result depends on: order_id, validation_score, and amount.
"""
from __future__ import annotations

import datetime
from typing import Any

_MIN_SCORE_TO_EXECUTE = 70


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    order_id         = str(payload.get("order_id")         or "")
    validation_score = int(payload.get("validation_score") or 0)
    amount           = float(payload.get("amount")         or 0.0)
    currency         = str(payload.get("currency")         or "USD")

    if validation_score < _MIN_SCORE_TO_EXECUTE:
        return {
            "_passed":  False,
            "executed": False,
            "reason":   f"validation_score_too_low:{validation_score} < {_MIN_SCORE_TO_EXECUTE}",
            "order_id": order_id,
        }

    if not order_id.strip():
        return {
            "_passed":  False,
            "executed": False,
            "reason":   "order_id_missing",
        }

    # Execution reference number: deterministic from order_id + amount
    ref_number = f"EXE-{abs(hash(order_id + str(amount))) % 900000 + 100000}"

    return {
        "executed":        True,
        "execution_ref":   ref_number,
        "order_id":        order_id,
        "amount_charged":  amount,
        "currency":        currency,
        "validation_score": validation_score,
        "executed_at":     datetime.datetime.utcnow().isoformat() + "Z",
    }
