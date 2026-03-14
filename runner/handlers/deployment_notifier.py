"""Deployment notifier agent — validates a deployment event before notification step.

Used in the notification scenario (before and after the internal notification step).

Checks:
  - deployment_id must be a non-empty string
  - service must be a non-empty string
  - environment must be in the allowed set
  - triggered_by must be a non-empty string
"""
from __future__ import annotations

from typing import Any

_ALLOWED_ENVIRONMENTS = {"dev", "staging", "prod", "prod-cluster-eu", "prod-cluster-us"}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    deployment_id = str(payload.get("deployment_id") or "")
    service       = str(payload.get("service")       or "")
    environment   = str(payload.get("environment")   or "")
    triggered_by  = str(payload.get("triggered_by")  or "")

    violations: list[str] = []

    if not deployment_id.strip():
        violations.append("deployment_id_missing")

    if not service.strip():
        violations.append("service_missing")

    if environment not in _ALLOWED_ENVIRONMENTS:
        violations.append(f"environment_not_allowed:{environment!r}")

    if not triggered_by.strip():
        violations.append("triggered_by_missing")

    if violations:
        return {
            "_passed":            False,
            "deployment_accepted": False,
            "violations":         violations,
            "reason":             "deployment_validation_failed",
        }

    return {
        "deployment_accepted": True,
        "deployment_id":       deployment_id,
        "service":             service,
        "environment":         environment,
    }
