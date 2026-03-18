"""Pre-Approval Validator — durability/reminder-escalation example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Validates a change request before routing to the human approver.
The human approval step has a short SLA with reminders configured.

Run (Terminal 1 — agent):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/pre-approval-validator
    python agent.py

Run (Terminal 2 — scenario):
    axme scenarios apply examples/durability/reminder-escalation/scenario.json --watch

To observe escalation: run the scenario but do NOT approve the task.
Watch [reminder] events every 30 seconds, then TIMED_OUT after max_reminders.
To approve normally: axme tasks list → axme tasks approve <task_id>
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
log = logging.getLogger("pre-approval-validator")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "pre-approval-validator")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

_ALLOWED_CHANGE_TYPES = {"config_update", "dependency_update", "rollback", "hotfix"}
_VALID_RISK_LEVELS    = {"low", "medium", "high", "critical"}


def _validate_change(payload: dict[str, Any]) -> tuple[bool, str]:
    """Return (valid, reason) — pre-flight validation before human approval."""
    change_id   = payload.get("change_id", "?")
    change_type = payload.get("change_type", "")
    risk_level  = payload.get("risk_level", "")
    service     = payload.get("service", "")
    environment = payload.get("environment", "")

    if not service:
        return False, f"{change_id}: service is required"

    if change_type not in _ALLOWED_CHANGE_TYPES:
        return (
            False,
            f"{change_id}: change_type {change_type!r} not in {sorted(_ALLOWED_CHANGE_TYPES)}",
        )

    if risk_level not in _VALID_RISK_LEVELS:
        return (
            False,
            f"{change_id}: risk_level {risk_level!r} not in {sorted(_VALID_RISK_LEVELS)}",
        )

    return (
        True,
        f"{change_id}: pre-validation passed for {service!r}/{environment!r} ({change_type}, {risk_level} risk)",
    )


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

    valid, reason = _validate_change(effective_payload)
    log.info("pre-validation for %s: valid=%s  reason=%s", intent_id, valid, reason)

    try:
        if valid:
            client.resume_intent(
                intent_id,
                {"action": "complete", "valid": True, "reason": reason},
                owner_agent=AXME_AGENT_ADDRESS,
            )
        else:
            client.resume_intent(
                intent_id,
                {"action": "fail", "valid": False, "reason": reason},
                owner_agent=AXME_AGENT_ADDRESS,
            )
        log.info("resumed intent %s (valid=%s)", intent_id, valid)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info("pre-approval-validator starting  address=%s  binding=stream", AXME_AGENT_ADDRESS)

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
