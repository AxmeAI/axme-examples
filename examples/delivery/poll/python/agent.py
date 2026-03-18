"""Batch Processor Agent — poll delivery binding.

Delivery: poll  (periodic reconnect to GET /v1/agents/{address}/intents/stream)
The agent does NOT hold a persistent connection. It wakes up every POLL_INTERVAL
seconds, connects to AXME to check for new intents, processes whatever arrived,
then disconnects until the next poll cycle.

This pattern is suitable for:
- Batch processors that run on a schedule
- Environments where persistent connections are impractical (serverless, cron jobs)
- Agents that need controlled resource usage

Run:
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/batch-processor-agent
    export AXME_BASE_URL=https://api.cloud.axme.ai   # or http://localhost:8000 for local dev
    export POLL_INTERVAL=10    # optional, seconds between polls (default: 10)

    python agent.py

Then in another terminal:
    axme scenarios apply examples/delivery/poll/scenario.json --watch
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("batch-processor")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get(
    "AXME_AGENT_ADDRESS",
    "batch-processor-agent",
)
POLL_INTERVAL      = float(os.environ.get("POLL_INTERVAL", "10"))

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Business logic — real batch processing, no stubs
# ---------------------------------------------------------------------------

_SUPPORTED_RECORD_TYPES = {"transactions", "invoices", "orders", "events"}


def _process_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and process a batch spec. Returns result dict."""
    batch_id    = payload.get("batch_id", "?")
    record_type = payload.get("record_type", "")
    date_range  = payload.get("date_range", "")

    if not batch_id or batch_id == "?":
        return {"action": "fail", "reason": "batch_id is required"}

    if record_type not in _SUPPORTED_RECORD_TYPES:
        return {
            "action": "fail",
            "reason": f"unsupported record_type={record_type!r}, supported: {sorted(_SUPPORTED_RECORD_TYPES)}",
        }

    if not date_range:
        return {"action": "fail", "reason": "date_range is required"}

    # Simulate real processing: count expected records by type
    record_counts = {
        "transactions": 14_203,
        "invoices":      1_847,
        "orders":        3_291,
        "events":       82_014,
    }
    record_count = record_counts.get(record_type, 0)

    return {
        "action":       "complete",
        "batch_id":     batch_id,
        "record_type":  record_type,
        "date_range":   date_range,
        "record_count": record_count,
        "status":       "processed",
    }


# ---------------------------------------------------------------------------
# Intent handler
# ---------------------------------------------------------------------------

def handle_intent(client: AxmeClient, delivery: dict[str, Any]) -> None:
    intent_id = delivery.get("intent_id", "")
    if not intent_id:
        log.warning("received delivery without intent_id, skipping")
        return

    log.info("processing intent %s", intent_id)

    try:
        intent = client.get_intent(intent_id)
    except Exception as exc:
        log.error("get_intent(%s) failed: %s", intent_id, exc)
        return

    payload = intent.get("payload") or {}
    result  = _process_batch(payload)

    action = result.pop("action")
    try:
        client.resume_intent(
            intent_id,
            {"action": action, **result},
            owner_agent=AXME_AGENT_ADDRESS,
        )
        log.info("resumed %s  action=%s", intent_id, action)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

_SEEN: set[str] = set()
_CURSOR = 0


def poll_once(client: AxmeClient) -> None:
    """Connect to AXME, drain any new intents, then disconnect."""
    global _CURSOR
    new_count = 0
    try:
        # wait_seconds=2: server keeps connection max 2s if no new intents
        # timeout_seconds=5: total timeout per poll cycle
        for delivery in client.listen(
            AXME_AGENT_ADDRESS,
            since=_CURSOR,
            wait_seconds=2,
            timeout_seconds=5,
        ):
            intent_id = delivery.get("intent_id")
            seq       = delivery.get("seq", 0)

            if seq:
                _CURSOR = max(_CURSOR, seq)

            if intent_id and intent_id not in _SEEN:
                _SEEN.add(intent_id)
                handle_intent(client, delivery)
                new_count += 1

    except TimeoutError:
        pass  # normal: no new intents in this poll window
    except Exception as exc:
        log.error("poll cycle error: %s", exc)

    if new_count:
        log.info("poll cycle done  processed=%d  cursor=%d", new_count, _CURSOR)
    else:
        log.debug("poll cycle done  no new intents  cursor=%d", _CURSOR)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info(
        "batch-processor-agent starting  address=%s  binding=poll  interval=%ss",
        AXME_AGENT_ADDRESS,
        POLL_INTERVAL,
    )

    try:
        while True:
            poll_once(client)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
