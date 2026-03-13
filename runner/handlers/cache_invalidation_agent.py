"""Cache invalidation agent — validates and acknowledges a cache invalidation request.

Used in the delay scenario (before and after the delay step).
Both the pre-delay and post-delay workflow steps are assigned to this agent.

Checks:
  - operation must be a known operation type
  - cache_keys must be a non-empty list
  - each cache_key must be a non-empty string
"""
from __future__ import annotations

from typing import Any

_ALLOWED_OPERATIONS = {
    "invalidate",
    "invalidate_and_reload",
    "reload",
    "flush",
    "warm",
}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    service    = str(payload.get("service")    or "")
    operation  = str(payload.get("operation")  or "")
    cache_keys = payload.get("cache_keys")

    violations: list[str] = []

    if operation not in _ALLOWED_OPERATIONS:
        violations.append(
            f"operation_unknown:{operation!r} "
            f"(allowed: {', '.join(sorted(_ALLOWED_OPERATIONS))})"
        )

    if not cache_keys or not isinstance(cache_keys, list):
        violations.append("cache_keys_missing_or_empty")
    else:
        for i, key in enumerate(cache_keys):
            if not isinstance(key, str) or not key.strip():
                violations.append(f"cache_keys[{i}]_invalid:{key!r}")

    if violations:
        return {
            "_passed":           False,
            "operation_accepted": False,
            "violations":        violations,
            "reason":            "cache_validation_failed",
        }

    return {
        "operation_accepted": True,
        "operation":          operation,
        "service":            service,
        "keys_count":         len(cache_keys),
    }
