"""Risk calculator agent — computes a risk score from change request fields.

Scoring:
  base score: low=10, medium=35, high=70, critical=95
  modifiers:
    +15  environment is "prod*"
    -10  rollback_plan is present and non-empty
    +20  change_type is "schema_migration"
    +10  version field absent (unversioned change)

Final risk_level derived from score:
  < 25  -> low
  < 55  -> medium
  < 80  -> high
  >= 80 -> critical

blast_radius:
  prod environment + score >= 55 -> "multiple_services"
  otherwise -> "single_service"
"""
from __future__ import annotations

from typing import Any

_BASE_SCORES: dict[str, int] = {
    "low": 10,
    "medium": 35,
    "high": 70,
    "critical": 95,
}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    risk_level = str(payload.get("risk_level") or "medium").lower()
    environment = str(payload.get("environment") or "")
    rollback_plan = payload.get("rollback_plan")
    change_type = str(payload.get("change_type") or "")
    version = payload.get("version")

    score = _BASE_SCORES.get(risk_level, 35)

    if environment.startswith("prod"):
        score += 15
    if rollback_plan and str(rollback_plan).strip():
        score -= 10
    if change_type == "schema_migration":
        score += 20
    if not version:
        score += 10

    score = max(0, min(100, score))

    if score < 25:
        final_level = "low"
    elif score < 55:
        final_level = "medium"
    elif score < 80:
        final_level = "high"
    else:
        final_level = "critical"

    is_prod = environment.startswith("prod")
    blast_radius = "multiple_services" if is_prod and score >= 55 else "single_service"

    return {
        "risk_score": score,
        "risk_level": final_level,
        "blast_radius": blast_radius,
        "rollback_available": bool(rollback_plan and str(rollback_plan).strip()),
        "environment": environment,
    }
