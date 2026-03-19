"""Override — human/override example.

Creates an intent with a human override step. The workflow pauses
and emails the senior operator a link to approve or reject a deployment
freeze override with justification.

Run:
    AXME_API_KEY=<key> python initiator.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s  [%(levelname)s]  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("override-initiator")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info("creating override intent ...")
    intent_id = client.send_intent(
        {
            "intent_type": "intent.deploy.override.v1",
            "from_agent": "initiator://human-override",
            "to_agent": "agent://agent_core",
            "payload": {
                "service": "api-gateway",
                "version": "v3.5.0",
                "ticket": "CHG-2026-892",
            },
            "human_task": {
                "title": "Override deployment freeze",
                "description": "Deployment of api-gateway v3.5.0 is blocked by a deployment freeze (ticket CHG-2026-892). A senior operator must approve the override with justification or reject.",
                "task_type": "override",
                "notify_email": os.environ.get("AXME_NOTIFY_EMAIL", "senior-ops@example.com"),
                "allowed_outcomes": ["override_approved", "rejected"],
                "required_comment": True,
            },
        },
    )
    log.info("intent created: %s", intent_id)
    log.info("Check your email for the task link.")


if __name__ == "__main__":
    main()
