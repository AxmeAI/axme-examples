"""Change management validator — validates a change request before approval routing.

Checks:
  - change_id must match pattern CHG-<digits>
  - rollback_plan must be present and non-empty
  - environment must be in the allowed set
  - service must be a non-empty string
"""
from __future__ import annotations

import re
from typing import Any

_CHANGE_ID_PATTERN = re.compile(r"^CHG-\d+$")
_ALLOWED_ENVIRONMENTS = {"staging", "prod-cluster-us", "prod", "dev", "prod-cluster-eu"}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    change_id = str(payload.get("change_id") or "")
    environment = str(payload.get("environment") or "")
    service = str(payload.get("service") or "")
    rollback_plan = str(payload.get("rollback_plan") or "")

    # change_id format
    if _CHANGE_ID_PATTERN.match(change_id):
        checks_passed.append("change_id_format")
    else:
        checks_failed.append(f"change_id_invalid_format:{change_id!r} (expected CHG-<digits>)")

    # environment
    if environment in _ALLOWED_ENVIRONMENTS:
        checks_passed.append("environment_allowed")
    else:
        checks_failed.append(f"environment_not_allowed:{environment!r}")

    # service
    if service.strip():
        checks_passed.append("service_present")
    else:
        checks_failed.append("service_missing")

    # rollback_plan
    if rollback_plan.strip():
        checks_passed.append("rollback_plan_present")
    else:
        checks_failed.append("rollback_plan_missing")

    passed = len(checks_failed) == 0

    result = {
        "_passed": passed,
        "validation_passed": passed,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "change_id": change_id,
        "service": service,
    }
    if not passed:
        result["reason"] = "validation_failed"
        result["violations"] = checks_failed
    return result
