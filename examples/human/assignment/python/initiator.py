"""Assignment — human/assignment example.

Creates an intent with a human assignment step. The workflow pauses
and emails the on-call manager a link to assign an incident commander.

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
log = logging.getLogger("assignment-initiator")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info("creating assignment intent ...")
    intent_id = client.send_intent(
        {
            "intent_type": "intent.incident.assignment.v1",
            "from_agent": "initiator://human-assignment",
            "to_agent": "agent://agent_core",
            "payload": {
                "incident_id": "INC-2026-1847",
                "severity": "P1",
                "service": "payment-api",
            },
            "human_task": {
                "title": "Assign incident commander",
                "description": "Incident INC-2026-1847 classified as P1 affecting payment-api. Please designate an incident commander.",
                "task_type": "assignment",
                "notify_email": os.environ.get("AXME_NOTIFY_EMAIL", "oncall@example.com"),
                "allowed_outcomes": ["assigned", "declined"],
                "form_schema": {
                    "type": "object",
                    "required": ["assignee"],
                    "properties": {
                        "assignee": {
                            "type": "string",
                            "description": "Email of the designated incident commander",
                        },
                        "priority": {
                            "type": "string",
                            "description": "Override priority level",
                            "enum": ["P1", "P2", "P3", "P4"],
                        },
                    },
                },
            },
        },
    )
    log.info("intent created: %s", intent_id)
    log.info("Check your email for the task link.")


if __name__ == "__main__":
    main()
