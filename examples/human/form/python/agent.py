"""Access Policy Checker — human/form example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Checks access request policy before routing to the Security Officer
for structured form-based approval.

Run (Terminal 1 — agent):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/access-policy-checker
    python agent.py

Run (Terminal 2 — scenario):
    axme scenarios apply examples/human/form/scenario.json --watch

After the agent step, the workflow pauses for the Security Officer.
Approve via CLI with full form fields:
    axme tasks list
    axme tasks approve <task_id> --result '{"approved":true,"grant_duration_days":30,"scope_confirmed":true}'
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
log = logging.getLogger("access-policy-checker")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "access-policy-checker")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Access policy rules
# ---------------------------------------------------------------------------
_ALLOWED_ACCESS_TYPES = {"READ", "READ_WRITE"}

# Resources that require human sign-off regardless of policy result
_HUMAN_SIGNOFF_REQUIRED_RESOURCES = {
    "prod-analytics-db",
    "prod-customer-db",
    "prod-payments-db",
}

# PII data requires extra scrutiny
_PII_BLOCKED_ACCESS_TYPES = {"READ_WRITE", "WRITE", "ADMIN"}


def _check_policy(payload: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """Return (policy_passed, passed_checks, violations)."""
    request_id  = payload.get("request_id", "?")
    resource    = payload.get("resource", "")
    access_type = payload.get("access_type", "").upper()
    requestor   = payload.get("requestor", "")
    pii_fields  = bool(payload.get("pii_fields", False))

    violations: list[str] = []
    passed:     list[str] = []

    # Check 1 — access type is in allowed set
    if access_type in _ALLOWED_ACCESS_TYPES:
        passed.append(f"access type {access_type!r} is in allowed set")
    else:
        violations.append(
            f"access type {access_type!r} is not allowed; permitted: {sorted(_ALLOWED_ACCESS_TYPES)}"
        )

    # Check 2 — requestor identity present
    if requestor:
        passed.append(f"requestor identity {requestor!r} is present")
    else:
        violations.append("requestor identity is missing")

    # Check 3 — PII fields restrict write access
    if pii_fields and access_type in _PII_BLOCKED_ACCESS_TYPES:
        violations.append(
            f"resource contains PII fields; {access_type!r} access is not permitted on PII data"
        )
    elif pii_fields:
        passed.append(f"PII data present but {access_type!r} is read-only — acceptable")
    else:
        passed.append("resource has no PII fields — no PII restriction applies")

    return len(violations) == 0, passed, violations


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

    policy_passed, passed, violations = _check_policy(effective_payload)
    log.info(
        "policy check for %s: passed=%s  checks=%d  violations=%d",
        intent_id, policy_passed, len(passed), len(violations),
    )

    try:
        if policy_passed:
            client.resume_intent(
                intent_id,
                {
                    "action":          "complete",
                    "policy_passed":   True,
                    "passed_checks":   passed,
                    "violations":      [],
                    "requires_human_signoff": (
                        effective_payload.get("resource", "") in _HUMAN_SIGNOFF_REQUIRED_RESOURCES
                    ),
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        else:
            client.resume_intent(
                intent_id,
                {
                    "action":        "fail",
                    "policy_passed": False,
                    "passed_checks": passed,
                    "violations":    violations,
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        log.info("resumed intent %s (policy_passed=%s)", intent_id, policy_passed)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info(
        "access-policy-checker starting  address=%s  binding=stream",
        AXME_AGENT_ADDRESS,
    )

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
