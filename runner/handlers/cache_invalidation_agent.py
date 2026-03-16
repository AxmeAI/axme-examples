"""Cache invalidation agent — validates and accepts cache invalidation requests."""
from __future__ import annotations

from typing import Any

_ALLOWED_OPERATIONS = {"invalidate", "invalidate_and_reload", "reload"}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []

    service = str(payload.get("service") or "")
    operation = str(payload.get("operation") or "")
    cache_keys = payload.get("cache_keys", [])

    if operation not in _ALLOWED_OPERATIONS:
        violations.append(f"operation_unknown:{operation!r}")

    if not cache_keys or not isinstance(cache_keys, list) or len(cache_keys) == 0:
        violations.append("cache_keys_empty_or_missing")

    if violations:
        return {
            "_passed": False,
            "operation_accepted": False,
            "violations": violations,
            "reason": "cache_invalidation_validation_failed",
        }

    return {
        "operation_accepted": True,
        "service": service,
        "operation": operation,
        "keys_count": len(cache_keys),
        "cache_keys": cache_keys,
    }
