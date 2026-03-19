"""Manual action — human/manual-action example.

Creates an intent with a human manual-action step. The workflow pauses
and emails the technician a link to report on a physical rack inspection.

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
log = logging.getLogger("manual-action-initiator")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info("creating manual-action intent ...")
    intent_id = client.send_intent(
        {
            "intent_type": "intent.dc.manual_action.v1",
            "from_agent": "initiator://human-manual-action",
            "to_agent": "agent://agent_core",
            "payload": {
                "rack_id": "B-14",
                "location": "DC-East",
                "alert": "elevated_temperature",
            },
            "human_task": {
                "title": "Inspect server rack B-14",
                "description": "Elevated temperature alert in rack B-14 at DC-East. Please physically inspect the rack, check airflow and cooling, and report findings with evidence.",
                "task_type": "manual_action",
                "notify_email": os.environ.get("AXME_NOTIFY_EMAIL", "dc-ops@example.com"),
                "allowed_outcomes": ["completed", "failed"],
                "evidence_required": True,
            },
        },
    )
    log.info("intent created: %s", intent_id)
    log.info("Check your email for the task link.")


if __name__ == "__main__":
    main()
