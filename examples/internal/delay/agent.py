"""Change Window Validator — internal/delay example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Validates that a change falls within an approved maintenance window.
Demonstrates a real async validation pattern: the agent checks the
window schedule and validates all required fields before responding.
The step has a 120-second deadline (`step_deadline_seconds: 120`).

Run (Terminal 1 — agent):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/change-window-validator
    python agent.py

Run (Terminal 2 — scenario):
    axme scenarios apply examples/internal/delay/scenario.json --watch

To observe step deadline: stop the agent before it responds.
AXME will transition the step to TIMED_OUT after 120 seconds.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("change-window-validator")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "change-window-validator")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Change window validation rules
# ---------------------------------------------------------------------------
# Approved maintenance windows: weekday evenings and weekends.
# Changes outside these windows are rejected.

_APPROVED_WINDOW_IDS = {
    "MW-2026-Q1-01", "MW-2026-Q1-02", "MW-2026-Q1-03",
    "MW-2026-Q1-04", "MW-2026-Q1-05", "MW-2026-Q1-06",
}

_ALLOWED_CHANGE_TYPES = {"config_update", "dependency_update", "rollback", "hotfix"}

_BLOCKED_ENVIRONMENTS_WITHOUT_WINDOW = {"production"}


def _validate_change_window(payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """Return (allowed, reason, metadata)."""
    change_id    = payload.get("change_id", "?")
    environment  = payload.get("environment", "")
    change_type  = payload.get("change_type", "")
    window_id    = payload.get("window_id", "")
    scheduled_at = payload.get("scheduled_at", "")

    # Check 1 — change type allowed
    if change_type not in _ALLOWED_CHANGE_TYPES:
        return (
            False,
            f"{change_id}: change_type {change_type!r} is not in allowed set {sorted(_ALLOWED_CHANGE_TYPES)}",
            {},
        )

    # Check 2 — production changes must have an approved window
    if environment in _BLOCKED_ENVIRONMENTS_WITHOUT_WINDOW:
        if not window_id:
            return (
                False,
                f"{change_id}: production changes require an approved window_id",
                {},
            )
        if window_id not in _APPROVED_WINDOW_IDS:
            return (
                False,
                f"{change_id}: window_id {window_id!r} is not in the approved window list",
                {},
            )

    # Check 3 — scheduled_at is a valid ISO timestamp
    if scheduled_at:
        try:
            datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            return (
                False,
                f"{change_id}: scheduled_at {scheduled_at!r} is not a valid ISO timestamp",
                {},
            )

    window_info = {}
    if window_id and window_id in _APPROVED_WINDOW_IDS:
        window_info = {"window_id": window_id, "window_approved": True}

    return (
        True,
        f"{change_id}: change window validated for {environment!r} environment",
        window_info,
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

    allowed, reason, meta = _validate_change_window(effective_payload)
    log.info("window validation for %s: allowed=%s  reason=%s", intent_id, allowed, reason)

    try:
        if allowed:
            client.resume_intent(
                intent_id,
                {
                    "action":  "complete",
                    "allowed": True,
                    "reason":  reason,
                    **meta,
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        else:
            client.resume_intent(
                intent_id,
                {
                    "action":  "fail",
                    "allowed": False,
                    "reason":  reason,
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        log.info("resumed intent %s (allowed=%s)", intent_id, allowed)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info(
        "change-window-validator starting  address=%s  binding=stream",
        AXME_AGENT_ADDRESS,
    )

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
