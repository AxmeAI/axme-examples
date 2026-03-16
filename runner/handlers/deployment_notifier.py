"""Deployment notifier agent — validates and accepts deployment notifications."""
from __future__ import annotations

from typing import Any

_ALLOWED_ENVIRONMENTS = {"staging", "prod-cluster-us", "prod-cluster-eu", "dev", "prod"}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []

    deployment_id = str(payload.get("deployment_id") or "")
    service = str(payload.get("service") or "")
    environment = str(payload.get("environment") or "")
    triggered_by = str(payload.get("triggered_by") or "")

    if not deployment_id.strip():
        violations.append("deployment_id_missing")

    if environment not in _ALLOWED_ENVIRONMENTS:
        violations.append(f"environment_not_allowed:{environment!r}")

    if not triggered_by.strip():
        violations.append("triggered_by_missing")

    passed = len(violations) == 0

    result = {
        "_passed": passed,
        "deployment_accepted": passed,
        "violations": violations,
        "deployment_id": deployment_id,
        "service": service,
        "environment": environment,
    }
    if not passed:
        result["reason"] = "deployment_notification_failed"
    return result
