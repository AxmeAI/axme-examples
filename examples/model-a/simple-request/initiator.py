"""Model A — Simple Request: initiator waits for agent response.

The initiator creates an intent directly via POST /v1/intents,
then observes the intent lifecycle until the agent completes it.

Run:
    # Terminal 1 — start the agent (reuses compliance-checker)
    AXME_API_KEY=<agent-key> AXME_AGENT_ADDRESS=compliance-checker-agent \
      python examples/delivery/stream/agent.py

    # Terminal 2 — run the initiator (AXME_TO_AGENT = full canonical address)
    AXME_API_KEY=<workspace-api-key> \
    AXME_TO_AGENT=agent://org/workspace/compliance-checker-agent \
      python examples/model-a/simple-request/initiator.py
"""
from __future__ import annotations

import logging
import os
import sys

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s  [%(levelname)s]  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("simple-request-initiator")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")
AXME_TO_AGENT = os.environ.get("AXME_TO_AGENT", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required (workspace API key)")
if not AXME_TO_AGENT:
    sys.exit("AXME_TO_AGENT is required (e.g. agent://org/workspace/compliance-checker-agent)")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    # 1. Create intent — sends directly to an agent
    log.info("creating intent to %s ...", AXME_TO_AGENT)
    intent_id = client.send_intent(
        {
            "intent_type": "intent.compliance.check.v1",
            "from_agent": "initiator://simple-request",
            "to_agent": AXME_TO_AGENT,
            "payload": {
                "change_id": "CHG-MODEL-A-001",
                "service": "api-gateway",
                "version": "4.0.0",
                "environment": "staging",
                "change_type": "config_update",
                "risk_level": "low",
            },
        },
    )
    log.info("intent created: %s", intent_id)

    # 2. Wait for the agent to process and resume.
    # In Model A (no ScenarioBundle/agent-core), resume_intent transitions to
    # IN_PROGRESS which is the "done" signal from the agent's perspective.
    log.info("waiting for agent response...")
    for event in client.observe(intent_id, timeout_seconds=120):
        status = event.get("status", "")
        if status in ("COMPLETED", "IN_PROGRESS", "FAILED", "CANCELED", "TIMED_OUT"):
            log.info("intent %s → %s", intent_id, status)
            if status in ("COMPLETED", "IN_PROGRESS"):
                log.info("SUCCESS — agent processed the request")
            else:
                log.warning("intent ended with status: %s", status)
            break


if __name__ == "__main__":
    main()
