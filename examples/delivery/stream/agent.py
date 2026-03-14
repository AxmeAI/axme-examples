"""Compliance Checker Agent — stream delivery binding.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)
The agent holds a persistent SSE connection to AXME.
When an intent arrives AXME pushes it over that connection immediately.

Run:
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/compliance-checker-agent
    export AXME_BASE_URL=https://api.cloud.axme.ai   # or http://localhost:8000 for local dev

    python agent.py

Then in another terminal:
    axme scenarios apply examples/delivery/stream/scenario.json --watch
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys
from typing import Any

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compliance-checker")

# ---------------------------------------------------------------------------
# Configuration — all from environment, no hard-coded values
# ---------------------------------------------------------------------------

AXME_BASE_URL     = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY      = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get(
    "AXME_AGENT_ADDRESS",
    "compliance-checker-agent",  # bare name — resolved to full address by SDK
)

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Delivery cursor — persists last_seen_seq across restarts
# ---------------------------------------------------------------------------
# The SSE stream supports ?since=<seq> for cursor-based delivery.  On startup
# we load the highest seq seen in a previous run so the agent resumes exactly
# where it left off instead of replaying the full intent history.

_SEQ_FILE = pathlib.Path.home() / ".axme" / "compliance_checker_agent_seq.txt"


def _load_since() -> int:
    """Return the last persisted delivery_seq, or 0 if none."""
    try:
        return int(_SEQ_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _save_since(seq: int) -> None:
    """Persist the delivery cursor so the next startup skips already-processed intents."""
    try:
        _SEQ_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SEQ_FILE.write_text(str(seq), encoding="utf-8")
    except Exception as exc:
        log.warning("could not persist delivery cursor: %s", exc)


# ---------------------------------------------------------------------------
# Business logic — real compliance rules, no stubs
# ---------------------------------------------------------------------------

_ALLOWED_CHANGE_WINDOW = {"Mon", "Tue", "Wed", "Thu"}

_RISK_LEVEL_REQUIRES_BACKUP = {"high", "critical"}

_BLOCKED_ENVIRONMENTS = {"production"}


def _check_compliance(payload: dict[str, Any]) -> tuple[bool, str]:
    """Return (passed, reason).  Validates a change request against compliance rules."""
    change_id   = payload.get("change_id", "?")
    environment = payload.get("environment", "")
    risk_level  = payload.get("risk_level", "low")
    backup_ok   = bool(payload.get("backup_confirmed", False))

    if environment in _BLOCKED_ENVIRONMENTS:
        return False, f"{change_id}: production changes require manual approval, not automated"

    if risk_level in _RISK_LEVEL_REQUIRES_BACKUP and not backup_ok:
        return False, f"{change_id}: risk_level={risk_level} requires backup_confirmed=true"

    return True, f"{change_id}: compliance checks passed (environment={environment}, risk={risk_level})"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def handle_intent(client: AxmeClient, delivery: dict[str, Any], *, seq: int = 0) -> None:
    intent_id = delivery.get("intent_id", "")
    if not intent_id:
        log.warning("received delivery without intent_id, skipping")
        return

    log.info("received intent %s", intent_id)

    try:
        intent = client.get_intent(intent_id)
    except Exception as exc:
        log.error("get_intent(%s) failed: %s", intent_id, exc)
        return

    # Skip intents not in actionable state — avoids reprocessing old/completed intents.
    # CREATED is included for step-intents dispatched by agent-core via workflow-commands,
    # which are immediately visible in the SSE stream before any DELIVERED transition.
    status = (intent.get("lifecycle_status") or intent.get("status") or "").upper()
    if status not in {"CREATED", "DELIVERED", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING"}:
        log.debug("skipping intent %s with status %s", intent_id, status)
        return

    payload = intent.get("payload") or {}
    passed, reason = _check_compliance(payload)

    log.info("compliance result for %s: passed=%s  reason=%s", intent_id, passed, reason)

    try:
        if passed:
            client.resume_intent(
                intent_id,
                {
                    "action":  "complete",
                    "passed":  True,
                    "reason":  reason,
                    "checked_fields": ["environment", "risk_level", "backup_confirmed"],
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        else:
            client.resume_intent(
                intent_id,
                {
                    "action": "fail",
                    "passed": False,
                    "reason": reason,
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        log.info("resumed intent %s  (passed=%s)", intent_id, passed)
        # Advance the delivery cursor so the next startup skips this intent.
        if seq > 0:
            _save_since(seq)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))

    since = _load_since()
    log.info(
        "compliance-checker-agent starting  address=%s  binding=stream  since=%d",
        AXME_AGENT_ADDRESS,
        since,
    )
    log.info("listening on %s ...", AXME_BASE_URL)

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, since=since, timeout_seconds=None):
            seq = delivery.get("seq") or 0
            handle_intent(client, delivery, seq=seq)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
