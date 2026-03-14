"""Compliance checker agent — validates change requests against policy rules.

Checks:
  - rollback_plan must be present and non-empty
  - environment == "prod" + risk_level == "critical" requires CAB escalation
  - change_type == "schema_migration" requires backup_confirmed == True
  - environment must be in the allowed set
"""
from __future__ import annotations

from typing import Any

_ALLOWED_ENVIRONMENTS = {"dev", "staging", "prod", "prod-cluster-eu", "prod-cluster-us"}
_ALLOWED_CHANGE_TYPES = {"config_update", "schema_migration", "code_deploy", "infra_change", "rollback"}
_CHECKED_RULES = [
    "rollback_plan_required",
    "critical_risk_prod_requires_cab",
    "schema_migration_requires_backup",
    "environment_allowlist",
]


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []

    environment  = str(payload.get("environment") or "")
    risk_level   = str(payload.get("risk_level")  or "")
    rollback_plan = payload.get("rollback_plan")
    change_type   = str(payload.get("change_type") or "")
    backup_confirmed = payload.get("backup_confirmed")

    if not rollback_plan or not str(rollback_plan).strip():
        violations.append("rollback_plan_missing")

    if environment not in _ALLOWED_ENVIRONMENTS:
        violations.append(f"environment_not_allowed:{environment!r}")

    if environment == "prod" and risk_level == "critical":
        violations.append("critical_risk_in_prod_requires_cab_escalation")

    if change_type == "schema_migration" and backup_confirmed is not True:
        violations.append("schema_migration_requires_backup_confirmed:true")

    passed = len(violations) == 0
    return {
        "_passed":          passed,
        "compliance_passed": passed,
        "violations":        violations,
        "checked_rules":     _CHECKED_RULES,
        "environment":       environment,
        "risk_level":        risk_level,
        **({"reason": "compliance_violations"} if not passed else {}),
    }
