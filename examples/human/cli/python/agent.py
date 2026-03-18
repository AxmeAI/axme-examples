"""Deploy Readiness Checker — human/cli example.

Delivery: stream  (GET /v1/agents/{address}/intents/stream)

Checks deployment readiness before a human operator makes the final call.
Validates: semver version format, allowed environment, non-empty rollback tag.

Run (Terminal 1 — agent):
    export AXME_API_KEY=<your-api-key>
    export AXME_AGENT_ADDRESS=agent://<org>/<workspace>/deploy-readiness-checker
    python agent.py

Run (Terminal 2 — scenario):
    axme scenarios apply examples/human/cli/scenario.json --watch

After the agent completes its step, the workflow pauses for human approval:
    axme tasks list
    axme tasks approve <task_id>   # or: axme tasks reject <task_id>
"""
from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any

from axme import AxmeClient, AxmeClientConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("deploy-readiness-checker")

AXME_BASE_URL      = os.environ.get("AXME_BASE_URL", "https://api.cloud.axme.ai")
AXME_API_KEY       = os.environ.get("AXME_API_KEY", "")
AXME_AGENT_ADDRESS = os.environ.get("AXME_AGENT_ADDRESS", "deploy-readiness-checker")

if not AXME_API_KEY:
    sys.exit("AXME_API_KEY is required")

# ---------------------------------------------------------------------------
# Semantic version pattern  (strict: MAJOR.MINOR.PATCH, no pre-release suffix)
# ---------------------------------------------------------------------------
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

_ALLOWED_ENVIRONMENTS = {"staging", "canary", "preview"}


def _check_readiness(payload: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """Return (ready, passed_checks, failures)."""
    deploy_id   = payload.get("deploy_id", "?")
    version     = payload.get("version", "")
    environment = payload.get("environment", "")
    rollback    = payload.get("rollback_tag", "")
    service     = payload.get("service", "")

    failures: list[str] = []
    passed:   list[str] = []

    # Check 1 — version is semver
    if _SEMVER_RE.match(version):
        passed.append(f"version {version!r} is valid semver")
    else:
        failures.append(f"version {version!r} is not valid semver (expected MAJOR.MINOR.PATCH)")

    # Check 2 — environment is allowed for automated deployment
    if environment in _ALLOWED_ENVIRONMENTS:
        passed.append(f"environment {environment!r} is in allowed list")
    else:
        failures.append(
            f"environment {environment!r} not in allowed set: {sorted(_ALLOWED_ENVIRONMENTS)}"
        )

    # Check 3 — rollback tag specified
    if rollback:
        passed.append(f"rollback_tag {rollback!r} is set")
    else:
        failures.append("rollback_tag is missing — deployment must have a rollback path")

    # Check 4 — service name not empty
    if service:
        passed.append(f"service {service!r} is identified")
    else:
        failures.append("service name is empty")

    return len(failures) == 0, passed, failures


def handle_intent(client: AxmeClient, delivery: dict[str, Any]) -> None:
    intent_id = delivery.get("intent_id", "")
    if not intent_id:
        log.warning("received delivery without intent_id, skipping")
        return

    log.info("received intent %s", intent_id)

    try:
        resp   = client.get_intent(intent_id)
        intent = resp.get("intent") or resp
    except Exception as exc:
        log.error("get_intent(%s) failed: %s", intent_id, exc)
        return

    status = (intent.get("lifecycle_status") or intent.get("status") or "").upper()
    if status not in {"CREATED", "DELIVERED", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING"}:
        log.debug("skipping intent %s with status %s", intent_id, status)
        return

    raw_payload      = intent.get("payload") or {}
    effective_payload = raw_payload.get("parent_payload") or raw_payload

    ready, passed, failures = _check_readiness(effective_payload)
    log.info(
        "readiness result for %s: ready=%s  passed=%d  failed=%d",
        intent_id, ready, len(passed), len(failures),
    )

    try:
        if ready:
            client.resume_intent(
                intent_id,
                {
                    "action":         "complete",
                    "ready":          True,
                    "passed_checks":  passed,
                    "failures":       [],
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        else:
            client.resume_intent(
                intent_id,
                {
                    "action":        "fail",
                    "ready":         False,
                    "passed_checks": passed,
                    "failures":      failures,
                },
                owner_agent=AXME_AGENT_ADDRESS,
            )
        log.info("resumed intent %s (ready=%s)", intent_id, ready)
    except Exception as exc:
        log.error("resume_intent(%s) failed: %s", intent_id, exc)


def main() -> None:
    client = AxmeClient(AxmeClientConfig(api_key=AXME_API_KEY, base_url=AXME_BASE_URL))
    log.info(
        "deploy-readiness-checker starting  address=%s  binding=stream",
        AXME_AGENT_ADDRESS,
    )

    try:
        for delivery in client.listen(AXME_AGENT_ADDRESS, timeout_seconds=None):
            handle_intent(client, delivery)
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()
