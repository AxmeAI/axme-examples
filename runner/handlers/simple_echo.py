"""Simple echo handler — returns the payload as-is."""
from __future__ import annotations

from typing import Any


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "echoed": True}
