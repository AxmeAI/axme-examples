"""Fulfillment Service Agent — inbox/reply_to delivery binding.

This example demonstrates the disconnect-safe initiator pattern:

  1. Initiator sends an intent with reply_to = its own inbox address.
  2. Fulfillment agent (stream binding) receives and processes the order.
  3. When COMPLETED, AXME puts the result into the initiator's inbox.
  4. Initiator can read the result at any time — no persistent connection needed.

This file is the PROCESSOR side (fulfillment-service-agent, stream binding).
See check_inbox.py for the initiator side that reads results from inbox.

Run:
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/fulfillment-service-agent
    export AXME_BASE_URL=https://api.cloud.axme.ai

    python agent.py

Then in another terminal:
    axme scenarios apply examples/delivery/inbox/scenario.json --watch

After completion, check the initiator inbox:
    python check_inbox.py
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
log = logging.getLogger("fulfillment-service")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "fulfillment-service-agent")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Business logic — order fulfillment, no stubs
# ---------------------------------------------------------------------------

_SHIPPING_ESTIMATES = {
    "express":   "1-2 business days",
    "standard":  "3-5 business days",
    "economy":   "7-10 business days",
}

_WAREHOUSE = "WH-US-EAST-1"


def _fulfill_order(payload: dict[str, Any]) -> dict[str, Any]:
    """Process an order and return fulfillment details."""
    order_id   = payload.get("order_id", "")
    customer   = payload.get("customer_id", "")
    items      = payload.get("items") or []
    shipping   = payload.get("shipping", "standard")

    if not order_id:
        return {"action": "fail", "reason": "order_id is required"}

    if not items:
        return {"action": "fail", "reason": "items list is empty"}

    if shipping not in _SHIPPING_ESTIMATES:
        return {
            "action":  "fail",
            "reason":  f"unknown shipping method={shipping!r}  available: {list(_SHIPPING_ESTIMATES)}",
        }

    total_items = sum(i.get("quantity", 0) for i in items)
    if total_items <= 0:
        return {"action": "fail", "reason": "total item quantity must be > 0"}

    # Allocate from warehouse (production: call inventory service)
    tracking_number = f"AXME-{order_id.upper()}-{abs(hash(order_id)) % 10000:04d}"
    fulfillment_id  = f"FUL-{abs(hash(order_id + customer)) % 100000:05d}"

    return {
        "action":           "complete",
        "fulfillment_id":   fulfillment_id,
        "tracking_number":  tracking_number,
        "warehouse":        _WAREHOUSE,
        "shipping_method":  shipping,
        "eta":              _SHIPPING_ESTIMATES[shipping],
        "items_shipped":    total_items,
        "status":           "fulfilled",
    }


# ---------------------------------------------------------------------------
# Intent handler
# ---------------------------------------------------------------------------

def handle_intent(client: AxmeClient, delivery: dict[str, Any]) -> None:
    intent_id = delivery.get("intent_id", "")
    if not intent_id:
        return

    log.info("received order intent %s", intent_id)

    try:
        intent = client.get_intent(intent_id)
    except Exception as exc:
        log.error("get_intent(%s) failed: %s", intent_id, exc)
        return

    payload = intent.get("payload") or {}
    result  = _fulfill_order(payload)
    action  = result.pop("action")

    try:
        client.resume_intent(
            intent_id,
            {"action": action, **result},
            owner_agent=AXME_AGENT_ADDRESS,
        )
        log.info("resumed %s  action=%s  %s", intent_id, action, result)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info(
        "fulfillment-service-agent starting  address=%s  binding=stream",
        AXME_AGENT_ADDRESS,
    )
    log.info("result will be sent to initiator inbox via reply_to")

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
