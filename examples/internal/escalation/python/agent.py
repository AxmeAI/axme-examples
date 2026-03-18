"""Incident Classifier Agent — internal/escalation example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Classifies an incident by severity level and affected components.
After classification, the workflow routes to the on-call engineer with
a short SLA. If the engineer doesn't acknowledge within the SLA window,
AXME sends reminder emails. After max_reminders, the step times out
and AXME escalates the incident automatically.

Run (Terminal 1 — agent):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/incident-classifier-agent
    python agent.py

Run (Terminal 2 — scenario):
    axme scenarios apply examples/internal/escalation/scenario.json --watch

To see escalation: do NOT run `axme tasks approve` — wait for reminders.
To acknowledge: axme tasks list → axme tasks approve <task_id>
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("incident-classifier")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "incident-classifier-agent")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Incident classification rules
# ---------------------------------------------------------------------------
_SEVERITY_RESPONSE_SLA: dict[str, int] = {
    "P1": 5,    # 5 minutes
    "P2": 15,   # 15 minutes
    "P3": 60,   # 60 minutes
    "P4": 240,  # 4 hours
}

_CRITICAL_SERVICES = {"api-gateway", "auth-service", "payments-processor"}

_HIGH_ERROR_RATE_THRESHOLD = 0.05   # 5%


def _classify_incident(payload: dict[str, Any]) -> dict[str, Any]:
    """Return classification result with severity, components, and SLA."""
    incident_id = payload.get("incident_id", "?")
    severity    = payload.get("severity", "P3")
    service     = payload.get("service", "")
    symptom     = payload.get("symptom", "")
    sla_minutes = _SEVERITY_RESPONSE_SLA.get(severity, 60)

    is_critical_service = service in _CRITICAL_SERVICES
    has_error_rate      = "error rate" in symptom.lower() or "5xx" in symptom.lower()

    affected_components = [service] if service else []
    if is_critical_service:
        affected_components.append("downstream-dependents")

    # Suggest escalation path
    if severity in {"P1", "P2"} and is_critical_service:
        escalation_path = "on-call → team-lead → engineering-director"
    elif severity in {"P1", "P2"}:
        escalation_path = "on-call → team-lead"
    else:
        escalation_path = "on-call"

    return {
        "incident_id":          incident_id,
        "severity":             severity,
        "is_critical_service":  is_critical_service,
        "has_error_rate_signal": has_error_rate,
        "affected_components":  affected_components,
        "sla_minutes":          sla_minutes,
        "escalation_path":      escalation_path,
        "classification_note":  (
            f"{incident_id}: {severity} on {service!r} — "
            f"SLA={sla_minutes}m, escalation: {escalation_path}"
        ),
    }


def handle_intent(client: AxmeClient, delivery: dict[str, Any]) -> None:
    intent_id = delivery.get("intent_id", "")
    if not intent_id:
        log.warning("received delivery without intent_id, skipping")
        return

    log.info("received intent %s", intent_id)

    try:
        resp   = client.get_intent(intent_id)
        intent = resp.get("intent") or resp
    except Exception as exc:
        log.error("get_intent(%s) failed: %s", intent_id, exc)
        return

    status = (intent.get("lifecycle_status") or intent.get("status") or "").upper()
    if status not in {"CREATED", "DELIVERED", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING"}:
        log.debug("skipping intent %s with status %s", intent_id, status)
        return

    raw_payload       = intent.get("payload") or {}
    effective_payload = raw_payload.get("parent_payload") or raw_payload

    result = _classify_incident(effective_payload)
    log.info("classified incident %s: %s", intent_id, result["classification_note"])

    try:
        client.resume_intent(
            intent_id,
            {"action": "complete", **result},
            owner_agent=AXME_AGENT_ADDRESS,
        )
        log.info("resumed intent %s", intent_id)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info(
        "incident-classifier starting  address=%s  binding=stream",
        AXME_AGENT_ADDRESS,
    )

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
