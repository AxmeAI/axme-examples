"""Model A — Manual Multi-Step: initiator chains two agents sequentially.

The initiator manually orchestrates a 2-step workflow without ScenarioBundle:
  Step 1: compliance-checker validates the change
  Step 2: risk-assessment-agent scores the risk (receives step 1 result)

Run:
    # Terminal 1 — start both agents
    AXME_API_KEY=<compliance-key> AXME_AGENT_ADDRESS=compliance-checker-agent \
      python examples/delivery/stream/agent.py &
    AXME_API_KEY=<risk-key> AXME_AGENT_ADDRESS=risk-assessment-agent \
      python examples/internal/notification/agent.py &

    # Terminal 2 — run the initiator
    AXME_API_KEY=<workspace-api-key> \
    AXME_AGENT_1=agent://org/ws/compliance-checker-agent \
    AXME_AGENT_2=agent://org/ws/risk-assessment-agent \
      python examples/model-a/manual-multi-step/initiator.py
"""
from __future__ import annotations

import logging
import os
import sys

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s  [%(levelname)s]  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("manual-multi-step")

AXME_BASE_URL = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY  = os.environ.get("AXME_API_KEY", "")
AGENT_1       = os.environ.get("AXME_AGENT_1", "")
AGENT_2       = os.environ.get("AXME_AGENT_2", "")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")
if not AGENT_1 or not AGENT_2:
    sys.exit("AXME_AGENT_1 and AXME_AGENT_2 are required (full canonical agent:// addresses)")


def _wait_for_done(client: AxmeClient, intent_id: str, timeout: int = 60) -> str:
    """Wait until the intent reaches a done state (IN_PROGRESS or terminal).

    In Model A (no agent-core), resume_intent sets IN_PROGRESS which is the
    agent's "done" signal.
    """
    for event in client.observe(intent_id, timeout_seconds=timeout):
        status = event.get("status", "")
        if status in ("COMPLETED", "IN_PROGRESS", "FAILED", "CANCELED", "TIMED_OUT"):
            return status
    return "UNKNOWN"


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    change_payload = {
        "change_id": "CHG-MULTI-STEP-001",
        "service": "api-gateway",
        "version": "5.0.0",
        "environment": "staging",
        "change_type": "config_update",
        "risk_level": "medium",
        "risk_threshold": 30,
    }

    # ── Step 1: Compliance Check ──────────────────────────────────────
    log.info("STEP 1: compliance check → %s", AGENT_1)
    step1_id = client.send_intent(
        {
            "intent_type": "intent.compliance.check.v1",
            "from_agent": "initiator://manual-multi-step",
            "to_agent": AGENT_1,
            "payload": change_payload,
        },
    )
    log.info("step 1 intent: %s — waiting...", step1_id)
    step1_status = _wait_for_done(client, step1_id)
    log.info("step 1 → %s", step1_status)

    if step1_status not in ("COMPLETED", "IN_PROGRESS"):
        log.error("step 1 failed (%s) — aborting pipeline", step1_status)
        return

    # ── Step 2: Risk Assessment ───────────────────────────────────────
    log.info("STEP 2: risk assessment → %s", AGENT_2)
    step2_id = client.send_intent(
        {
            "intent_type": "intent.risk.assessment.v1",
            "from_agent": "initiator://manual-multi-step",
            "to_agent": AGENT_2,
            "payload": {
                **change_payload,
                "compliance_result": "passed",
                "compliance_intent_id": step1_id,
            },
        },
    )
    log.info("step 2 intent: %s — waiting...", step2_id)
    step2_status = _wait_for_done(client, step2_id)
    log.info("step 2 → %s", step2_status)

    # ── Summary ───────────────────────────────────────────────────────
    log.info("")
    log.info("=== Manual Multi-Step Pipeline ===")
    log.info("  Step 1 (compliance): %s  id=%s", step1_status, step1_id)
    log.info("  Step 2 (risk):       %s  id=%s", step2_status, step2_id)
    if step1_status in ("COMPLETED", "IN_PROGRESS") and step2_status in ("COMPLETED", "IN_PROGRESS"):
        log.info("  Result: ALL STEPS PASSED")
    else:
        log.info("  Result: PIPELINE FAILED")


if __name__ == "__main__":
    main()
