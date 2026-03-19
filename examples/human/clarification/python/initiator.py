"""Clarification — human/clarification example.

Creates an intent with a human clarification step. The workflow pauses
and emails the assignee a link to provide missing information or decline.

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
log = logging.getLogger("clarification-initiator")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info("creating clarification intent ...")
    intent_id = client.send_intent(
        {
            "intent_type": "intent.customer.clarification.v1",
            "from_agent": "initiator://human-clarification",
            "to_agent": "agent://agent_core",
            "payload": {
                "customer": "ABC Corp",
                "ticket": "ONBOARD-429",
            },
            "human_task": {
                "title": "Clarification needed \u2014 ABC Corp onboarding",
                "description": "Ticket ONBOARD-429 for ABC Corp requires additional information before onboarding can proceed. Please provide the requested details or decline.",
                "task_type": "clarification",
                "notify_email": os.environ.get("AXME_NOTIFY_EMAIL", "cs@example.com"),
                "allowed_outcomes": ["provided", "declined"],
                "required_comment": True,
            },
        },
    )
    log.info("intent created: %s", intent_id)
    log.info("Check your email for the task link.")


if __name__ == "__main__":
    main()
