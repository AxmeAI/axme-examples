"""Review — human/review example.

Creates an intent with a human review step. The workflow pauses
and emails the reviewer a link to approve, request changes, or reject a PR.

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
log = logging.getLogger("review-initiator")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    log.info("creating review intent ...")
    intent_id = client.send_intent(
        {
            "intent_type": "intent.code.review.v1",
            "from_agent": "initiator://human-review",
            "to_agent": "agent://agent_core",
            "payload": {
                "pr_number": 847,
                "title": "Add retry logic to payment service",
                "author": "alice",
            },
            "human_task": {
                "title": "Review PR #847",
                "description": "PR #847 'Add retry logic to payment service' by alice is ready for review. Please approve, request changes, or reject.",
                "task_type": "review",
                "notify_email": os.environ.get("AXME_NOTIFY_EMAIL", "reviewer@example.com"),
                "allowed_outcomes": ["approved", "changes_requested", "rejected"],
            },
        },
    )
    log.info("intent created: %s", intent_id)
    log.info("Check your email for the task link.")


if __name__ == "__main__":
    main()
