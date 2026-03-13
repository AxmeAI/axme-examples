"""Simple echo agent — reflects the message back with a timestamp.

The result depends on the input: different messages produce different echoes.
Used in Model A simple request-response scenario.
"""
from __future__ import annotations

import datetime
from typing import Any


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    message    = str(payload.get("message") or "")
    sender_id  = str(payload.get("sender_id") or "unknown")
    request_id = str(payload.get("request_id") or "")

    if not message.strip():
        return {
            "_passed": False,
            "reason":  "message_missing_or_empty",
        }

    return {
        "echo":           message,
        "echo_length":    len(message),
        "echo_upper":     message.upper(),
        "sender_id":      sender_id,
        "request_id":     request_id,
        "processed_at":   datetime.datetime.utcnow().isoformat() + "Z",
    }
