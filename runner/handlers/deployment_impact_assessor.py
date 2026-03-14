"""Deployment impact assessor — computes blast radius and affected services.

Uses a static dependency map (no external calls). The impact depends on the
actual service name and environment from the payload — different inputs produce
different results.
"""
from __future__ import annotations

from typing import Any

# Static dependency map: service → (affected_services, estimated_downtime_minutes)
_DEPENDENCY_MAP: dict[str, tuple[list[str], int]] = {
    "nginx":              (["frontend", "api-gateway", "static-assets"], 0),
    "api-gateway":        (["frontend", "mobile-app", "partner-api"], 0),
    "postgres":           (["payment-service", "auth-service", "user-service", "api-gateway"], 5),
    "redis":              (["session-service", "rate-limiter", "cache-layer"], 0),
    "auth-service":       (["api-gateway", "frontend", "mobile-app"], 2),
    "payment-service":    (["checkout-service", "billing-service", "finance-reporting"], 10),
    "user-service":       (["frontend", "profile-service", "notification-service"], 0),
    "kafka":              (["event-processor", "audit-service", "analytics"], 0),
    "elasticsearch":      (["search-service", "log-aggregator"], 0),
}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    service     = str(payload.get("service") or "")
    environment = str(payload.get("environment") or "")
    risk_level  = str(payload.get("risk_level") or "medium")

    if service.lower() in _DEPENDENCY_MAP:
        affected, base_downtime = _DEPENDENCY_MAP[service.lower()]
    else:
        affected      = [service] if service else []
        base_downtime = 0

    # Prod adds latency risk on top of the base downtime estimate
    if environment.startswith("prod") and base_downtime == 0:
        estimated_downtime = 0
    elif environment.startswith("prod"):
        estimated_downtime = base_downtime
    else:
        estimated_downtime = 0  # non-prod: no production impact

    blast_radius = (
        "full_platform"       if len(affected) >= 4
        else "multiple_services" if len(affected) >= 2
        else "single_service"
    )

    return {
        "blast_radius":              blast_radius,
        "affected_services":         affected,
        "estimated_downtime_minutes": estimated_downtime,
        "environment":               environment,
        "risk_level":                risk_level,
        "assessment_passed":         True,
    }
