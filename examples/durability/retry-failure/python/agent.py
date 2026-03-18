"""Webhook Receiver Agent — durability/retry-failure example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Processes incoming webhook events. In this durability test scenario:
- Run WITH the agent: intent is processed normally → COMPLETED
- Run WITHOUT the agent: AXME retries delivery up to max_delivery_attempts,
  then transitions to FAILED with `intent.delivery_failed` event

Run (normal completion):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/webhook-receiver-agent
    python agent.py
    axme scenarios apply examples/durability/retry-failure/scenario.json --watch

Run (to observe retry behavior):
    # Do NOT start agent.py
    axme scenarios apply examples/durability/retry-failure/scenario.json --watch
    # Watch AXME retry delivery and eventually emit intent.delivery_failed
"""
from __future__ import annotations

import hashlib
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
log = logging.getLogger("webhook-receiver")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "webhook-receiver-agent")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


def _process_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Process incoming webhook event — real idempotent processing."""
    event_type = payload.get("event_type", "unknown")
    source     = payload.get("source", "")
    test_id    = payload.get("test_id", "")

    # Generate a deterministic fingerprint for idempotency tracking
    fingerprint = hashlib.sha256(
        f"{event_type}:{source}:{test_id}".encode()
    ).hexdigest()[:16]

    return {
        "event_type":   event_type,
        "source":       source,
        "fingerprint":  fingerprint,
        "processed":    True,
        "note":         f"webhook event {event_type!r} processed from {source!r}",
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

    result = _process_webhook(effective_payload)
    log.info("processed webhook for %s: fingerprint=%s", intent_id, result["fingerprint"])

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
    log.info("webhook-receiver starting  address=%s  binding=stream", AXME_AGENT_ADDRESS)

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
