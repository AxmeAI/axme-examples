"""Model A — Fire and Forget: send intent, disconnect, check result later.

The initiator creates an intent with reply_to, disconnects immediately,
then later checks the intent status.

Run:
    # Terminal 1 — start the agent
    AXME_API_KEY=<agent-key> AXME_AGENT_ADDRESS=compliance-checker-agent \
      python examples/delivery/stream/agent.py

    # Terminal 2 — run the initiator
    AXME_API_KEY=<workspace-api-key> \
    AXME_TO_AGENT=agent://org/workspace/compliance-checker-agent \
      python examples/model-a/fire-and-forget/initiator.py
"""
from __future__ import annotations

import logging
import os
import sys
import time

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s  [%(levelname)s]  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("fire-and-forget")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")
AXME_TO_AGENT = os.environ.get("AXME_TO_AGENT", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")
if not AXME_TO_AGENT:
    sys.exit("AXME_TO_AGENT is required")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    # 1. Fire: create intent
    log.info("firing intent to %s ...", AXME_TO_AGENT)
    intent_id = client.send_intent(
        {
            "intent_type": "intent.compliance.check.v1",
            "from_agent": "initiator://fire-and-forget",
            "to_agent": AXME_TO_AGENT,
            "reply_to": "initiator://fire-and-forget",
            "payload": {
                "change_id": "CHG-FIRE-FORGET-001",
                "service": "payments-service",
                "version": "2.1.0",
                "environment": "staging",
                "change_type": "config_update",
                "risk_level": "medium",
            },
        },
    )
    log.info("intent sent: %s — disconnecting", intent_id)

    # 2. Forget: simulate doing other work
    log.info("doing other work for 15 seconds...")
    time.sleep(15)

    # 3. Come back and check result
    log.info("checking intent status...")
    intent = client.get_intent(intent_id)
    intent_data = intent.get("intent", intent)
    final_status = intent_data.get("lifecycle_status", intent_data.get("status", "?"))
    log.info("intent %s → %s", intent_id, final_status)

    if final_status in ("COMPLETED", "IN_PROGRESS"):
        log.info("SUCCESS — fire-and-forget pattern verified")
    else:
        log.info("status: %s (agent may still be processing)", final_status)


if __name__ == "__main__":
    main()
