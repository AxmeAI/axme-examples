"""Slow Batch Processor — durability/timeout example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Demonstrates AXME's step deadline enforcement. This agent processes
batch intents normally. The scenario is configured with a very short
`step_deadline_seconds: 10`. The agent validates the batch parameters
but rejects oversized batches (above _MAX_BATCH_RECORDS) to simulate
a legitimate processing constraint.

The timeout demonstration:
- The scenario.json sets step_deadline_seconds=10
- Run WITHOUT the agent: AXME delivers the intent but no one picks it up
- After 10 seconds: AXME transitions the step to TIMED_OUT

Run (to observe timeout):
    # Do NOT start agent.py
    axme scenarios apply examples/durability/timeout/scenario.json --watch
    # Watch step_deadline_seconds elapse → TIMED_OUT

Run (normal completion — agent rejects oversized batch):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/slow-batch-processor
    python agent.py
    axme scenarios apply examples/durability/timeout/scenario.json --watch
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
log = logging.getLogger("slow-batch-processor")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "slow-batch-processor")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

_MAX_BATCH_RECORDS = 10_000   # reject batches larger than this


def _process_batch(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Return (ok, result). Rejects oversized batches."""
    batch_id     = payload.get("batch_id", "?")
    record_count = int(payload.get("record_count", 0))

    if record_count > _MAX_BATCH_RECORDS:
        return False, {
            "batch_id":    batch_id,
            "error":       f"batch too large: {record_count} records exceeds limit of {_MAX_BATCH_RECORDS}",
            "record_count": record_count,
        }

    return True, {
        "batch_id":      batch_id,
        "record_count":  record_count,
        "processed":     True,
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

    ok, result = _process_batch(effective_payload)
    log.info("batch result for %s: ok=%s", intent_id, ok)

    try:
        if ok:
            client.resume_intent(
                intent_id,
                {"action": "complete", **result},
                owner_agent=AXME_AGENT_ADDRESS,
            )
        else:
            client.resume_intent(
                intent_id,
                {"action": "fail", **result},
                owner_agent=AXME_AGENT_ADDRESS,
            )
        log.info("resumed intent %s", intent_id)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info("slow-batch-processor starting  address=%s  binding=stream", AXME_AGENT_ADDRESS)

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
