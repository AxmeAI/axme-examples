"""Risk Assessment Agent — internal/notification example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Assesses deployment risk based on number of changes, environment, and
version jump. If risk exceeds threshold, signals HIGH risk. The workflow
then triggers the built-in notification step to alert the service owner.

Run (Terminal 1 — agent):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/risk-assessment-agent
    python agent.py

Run (Terminal 2 — scenario):
    axme scenarios apply examples/internal/notification/scenario.json --watch

After the agent step, AXME sends a notification email to the owner and
waits for acknowledgement. Owner acknowledges via:
    axme tasks list
    axme tasks approve <task_id> --result '{"acknowledged":true,"decision":"proceed"}'
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
log = logging.getLogger("risk-assessment-agent")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "risk-assessment-agent")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


# ---------------------------------------------------------------------------
# Risk scoring — real deterministic logic
# ---------------------------------------------------------------------------
# Risk score = sum of factor weights.
# If score >= threshold → HIGH risk, signal for owner notification.

_VERSION_MAJOR_BUMP_WEIGHT = 40    # major version jump (e.g. 3.x → 4.x)
_VERSION_MINOR_BUMP_WEIGHT = 15    # minor version jump
_HIGH_CHANGE_COUNT_WEIGHT  = 30    # more than 30 changed files
_PROD_ENVIRONMENT_WEIGHT   = 25    # production environment
_STAGING_ENVIRONMENT_WEIGHT = 10   # staging environment


def _parse_semver(version: str) -> tuple[int, int, int]:
    """Parse MAJOR.MINOR.PATCH, return (major, minor, patch) or (0, 0, 0) on error."""
    try:
        parts = version.strip().split(".")
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return 0, 0, 0


def _assess_risk(payload: dict[str, Any]) -> tuple[int, str, list[str]]:
    """Return (risk_score, risk_level, factors)."""
    version      = payload.get("version", "0.0.0")
    environment  = payload.get("environment", "")
    change_count = int(payload.get("change_count", 0))
    threshold    = int(payload.get("risk_threshold", 30))

    major, minor, _ = _parse_semver(version)

    score:   int        = 0
    factors: list[str]  = []

    # Version jump factors
    if major >= 4:
        score += _VERSION_MAJOR_BUMP_WEIGHT
        factors.append(f"major version bump (v{major}.x) +{_VERSION_MAJOR_BUMP_WEIGHT}")
    elif minor >= 5:
        score += _VERSION_MINOR_BUMP_WEIGHT
        factors.append(f"significant minor version bump +{_VERSION_MINOR_BUMP_WEIGHT}")

    # Change volume factor
    if change_count > 30:
        score += _HIGH_CHANGE_COUNT_WEIGHT
        factors.append(f"high change count ({change_count} changes) +{_HIGH_CHANGE_COUNT_WEIGHT}")

    # Environment factor
    if environment == "production":
        score += _PROD_ENVIRONMENT_WEIGHT
        factors.append(f"production environment +{_PROD_ENVIRONMENT_WEIGHT}")
    elif environment in {"staging", "canary"}:
        score += _STAGING_ENVIRONMENT_WEIGHT
        factors.append(f"staging environment +{_STAGING_ENVIRONMENT_WEIGHT}")

    if score >= threshold:
        risk_level = "HIGH"
    elif score >= threshold // 2:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return score, risk_level, factors


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

    score, risk_level, factors = _assess_risk(effective_payload)
    log.info(
        "risk assessment for %s: score=%d  level=%s  factors=%d",
        intent_id, score, risk_level, len(factors),
    )

    try:
        client.resume_intent(
            intent_id,
            {
                "action":     "complete",
                "risk_score": score,
                "risk_level": risk_level,
                "factors":    factors,
            },
            owner_agent=AXME_AGENT_ADDRESS,
        )
        log.info("resumed intent %s (risk=%s score=%d)", intent_id, risk_level, score)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info(
        "risk-assessment-agent starting  address=%s  binding=stream",
        AXME_AGENT_ADDRESS,
    )

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
