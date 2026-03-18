"""Budget Envelope Validator — human/email example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Validates a budget request against quarterly allocations before routing
the task to a human approver via email.

Run (Terminal 1 — agent):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/budget-envelope-validator
    python agent.py

Run (Terminal 2 — scenario):
    axme scenarios apply examples/human/email/scenario.json --watch

After the agent completes its step, AXME emails the human approver
(the email is set via `axme login` / AXME_USER_EMAIL env var).
The approver clicks the link in the email to approve or reject.
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
log = logging.getLogger("budget-envelope-validator")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "budget-envelope-validator")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Budget validation rules
# ---------------------------------------------------------------------------
# Quarterly budget envelopes by category.  Any request within the envelope
# and below the single-approval threshold is approved automatically.
# Requests that exceed the envelope are rejected outright.

_QUARTERLY_ENVELOPES: dict[str, float] = {
    "cloud_infrastructure": 50_000,
    "software_licenses":    20_000,
    "contractor_services":  40_000,
    "hardware":             15_000,
}

_AUTO_APPROVE_THRESHOLD = 5_000   # amounts below this skip human approval


def _validate_budget(payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """Return (within_envelope, reason, metadata)."""
    budget_id = payload.get("budget_id", "?")
    amount    = float(payload.get("amount", 0))
    currency  = payload.get("currency", "USD")
    category  = payload.get("category", "")

    envelope = _QUARTERLY_ENVELOPES.get(category)
    if envelope is None:
        return (
            False,
            f"{budget_id}: unknown category {category!r}; known: {sorted(_QUARTERLY_ENVELOPES)}",
            {},
        )

    if amount > envelope:
        return (
            False,
            f"{budget_id}: {currency} {amount:,.0f} exceeds quarterly envelope of {currency} {envelope:,.0f} for {category!r}",
            {"envelope": envelope, "overage": amount - envelope},
        )

    headroom_pct = round((envelope - amount) / envelope * 100, 1)
    return (
        True,
        f"{budget_id}: {currency} {amount:,.0f} is within {category!r} envelope ({headroom_pct}% headroom)",
        {"envelope": envelope, "headroom_pct": headroom_pct},
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

    within_envelope, reason, meta = _validate_budget(effective_payload)
    log.info("budget validation for %s: ok=%s  reason=%s", intent_id, within_envelope, reason)

    try:
        if within_envelope:
            client.resume_intent(
                intent_id,
                {
                    "action":           "complete",
                    "within_envelope":  True,
                    "reason":           reason,
                    "envelope":         meta.get("envelope"),
                    "headroom_pct":     meta.get("headroom_pct"),
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        else:
            client.resume_intent(
                intent_id,
                {
                    "action":          "fail",
                    "within_envelope": False,
                    "reason":          reason,
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        log.info("resumed intent %s (within_envelope=%s)", intent_id, within_envelope)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info(
        "budget-envelope-validator starting  address=%s  binding=stream",
        AXME_AGENT_ADDRESS,
    )

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
