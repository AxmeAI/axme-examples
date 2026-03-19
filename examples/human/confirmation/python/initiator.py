"""Confirmation — human/confirmation example.

Creates an intent with a human confirmation step. The workflow pauses
and emails the assignee a link to a web task page where they confirm
or deny DNS propagation.

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
log = logging.getLogger("confirmation-initiator")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info("creating confirmation intent ...")
    intent_id = client.send_intent(
        {
            "intent_type": "intent.dns.confirmation.v1",
            "from_agent": "initiator://human-confirmation",
            "to_agent": "agent://agent_core",
            "payload": {
                "domain": "api.example.com",
                "record_type": "CNAME",
                "new_value": "new-lb.example.com",
            },
            "human_task": {
                "title": "Confirm DNS propagation",
                "description": "DNS change submitted: api.example.com CNAME -> new-lb.example.com. Please verify propagation is complete.",
                "task_type": "confirmation",
                "notify_email": os.environ.get("AXME_NOTIFY_EMAIL", "ops@example.com"),
                "allowed_outcomes": ["confirmed", "denied"],
            },
        },
    )
    log.info("intent created: %s", intent_id)
    log.info("Check your email for the task link.")


if __name__ == "__main__":
    main()
