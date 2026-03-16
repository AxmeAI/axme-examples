"""Deployment impact assessor — evaluates the blast radius and affected services."""
from __future__ import annotations

from typing import Any

_SERVICE_DEPENDENCIES: dict[str, list[str]] = {
    "nginx": ["nginx", "api-gateway", "load-balancer"],
    "postgres": ["postgres", "api-server", "analytics"],
    "redis": ["redis", "session-service"],
    "payment-service": ["payment-service", "billing", "order-service"],
}


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    service = str(payload.get("service") or "")
    environment = str(payload.get("environment") or "")
    risk_level = str(payload.get("risk_level") or "low")

    affected = _SERVICE_DEPENDENCIES.get(service, [service])
    blast_radius = "multiple_services" if len(affected) >= 2 else "single_service"

    downtime = 0
    if environment.startswith("prod"):
        if service == "postgres":
            downtime = 15
        elif risk_level in ("high", "critical"):
            downtime = 5

    return {
        "assessment_passed": True,
        "service": service,
        "affected_services": affected,
        "blast_radius": blast_radius,
        "estimated_downtime_minutes": downtime,
        "environment": environment,
    }
