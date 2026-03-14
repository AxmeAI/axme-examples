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
_ALLOWED_ENVIRONMENTS = {"dev", "staging", "prod", "prod-cluster-eu", "prod-cluster-us"}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    change_id    = str(payload.get("change_id")    or "")
    environment  = str(payload.get("environment")  or "")
    service      = str(payload.get("service")      or "")
    rollback_plan = payload.get("rollback_plan")

    if _CHANGE_ID_PATTERN.match(change_id):
        checks_passed.append("change_id_format")
    else:
        checks_failed.append(f"change_id_invalid_format:{change_id!r} (expected CHG-<digits>)")

    if environment in _ALLOWED_ENVIRONMENTS:
        checks_passed.append("environment_allowed")
    else:
        checks_failed.append(f"environment_not_allowed:{environment!r}")

    if service.strip():
        checks_passed.append("service_present")
    else:
        checks_failed.append("service_missing")

    if rollback_plan and str(rollback_plan).strip():
        checks_passed.append("rollback_plan_present")
    else:
        checks_failed.append("rollback_plan_missing")

    passed = len(checks_failed) == 0
    return {
        "_passed":           passed,
        "validation_passed": passed,
        "checks_passed":     checks_passed,
        "checks_failed":     checks_failed,
        "change_id":         change_id,
        "service":           service,
        **({"reason": "validation_failed", "violations": checks_failed} if not passed else {}),
    }
