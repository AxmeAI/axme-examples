from __future__ import annotations

"""Multi-actor approval: Requester and Approver use distinct actor_tokens.

This example demonstrates the core AXP pattern for human-in-the-loop approvals
where two different actors (requester and approver) each present their own
actor_token to the same AXME Cloud workspace.

Flow:
  1. Requester creates an approval intent (enters WAITING state after creation).
  2. Runtime puts the intent in WAITING — execution pauses until unblocked.
  3. Approver (different actor) resumes the intent with their actor_token.
  4. Requester polls for the terminal state and reads the approval result.

Why this matters (vs. single-actor flow):
  - The durable lifecycle is preserved across both actors — no polling for
    hand-off, no shared mutable state outside the intent.
  - Each actor's token creates an auditable action chain in the lifecycle events.
  - The approval decision is recorded durably and can be inspected after the fact.

Usage:
    export AXME_API_KEY="axme_sa_..."
    export AXME_REQUESTER_TOKEN="eyJ..."   # JWT for the requesting actor
    export AXME_APPROVER_TOKEN="eyJ..."    # JWT for the approving actor
    python main.py
"""

import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

from axme import AxmeClient, AxmeClientConfig


def _read_cli_key_from_secrets(context: str = "default") -> str:
    import json, pathlib
    secrets_path = pathlib.Path.home() / ".config" / "axme" / "secrets.json"
    try:
        data = json.loads(secrets_path.read_text())
        key = (data.get(context) or data.get("default") or {}).get("api_key", "").strip()
        return key
    except Exception:
        return ""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value and name == "AXME_API_KEY":
        value = _read_cli_key_from_secrets()
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


def _print_events(label: str, events: list[dict[str, Any]]) -> None:
    print(f"\n[{label}] lifecycle events:")
    for event in events:
        seq = event.get("seq", 0)
        status = event.get("status", "unknown")
        actor = event.get("actor_id") or event.get("actor") or "system"
        waiting_reason = event.get("waiting_reason")
        suffix = f" waiting_reason={waiting_reason}" if waiting_reason else ""
        print(f"  seq={seq}  status={status}  actor={actor}{suffix}")


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    api_key = _require_env("AXME_API_KEY")
    requester_token = _require_env("AXME_REQUESTER_TOKEN")
    approver_token = _require_env("AXME_APPROVER_TOKEN")

    requester_agent = os.getenv("AXME_REQUESTER_AGENT", "").strip() or None
    approver_agent  = os.getenv("AXME_APPROVER_AGENT",  "").strip() or None

    # --- Step 1: Requester creates the approval intent ---
    print("\n=== Step 1: Requester creates approval intent ===")
    requester_config = AxmeClientConfig(
        base_url=base_url,
        api_key=api_key,
        actor_token=requester_token,
    )
    correlation_id = str(uuid4())
    idempotency_key = f"multi-actor-approval-{correlation_id}"

    with AxmeClient(requester_config) as requester:
        intent_body: dict[str, Any] = {
            "intent_type": "intent.approval.multi_actor.v1",
            "correlation_id": correlation_id,
            "payload": {
                "request_id": f"req-{correlation_id[:8]}",
                "summary": "Deploy backend service v2.4.1 to production",
                "approval_mode": "manual",
                "risk_level": "high",
            },
        }
        if requester_agent:
            intent_body["from_agent"] = requester_agent
        if approver_agent:
            intent_body["to_agent"] = approver_agent

        created = requester.create_intent(
            intent_body,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        intent_id = str(created["intent_id"])
        initial_status = created.get("status")
        print(f"[requester] intent_id={intent_id}")
        print(f"  status     {initial_status}")
        print(f"  🎾 ball at  requester (intent created)")
        print(f"[requester] correlation_id={correlation_id}")

        print("\n[requester] Intent is in WAITING state. Handing off to approver.")
        print(f"  🎾 ball at  human:approver (WAITING_FOR_HUMAN)")

    # --- Step 2: Approver reviews and resumes the intent ---
    # This simulates the approver opening their approval queue, seeing the intent,
    # and making a decision. They use their own actor_token.
    print("\n=== Step 2: Approver reviews and approves ===")

    # Small pause to simulate the approver being a different system/user.
    time.sleep(0.5)

    approver_config = AxmeClientConfig(
        base_url=base_url,
        api_key=api_key,
        actor_token=approver_token,
    )

    with AxmeClient(approver_config) as approver:
        # Approver can inspect the intent before deciding.
        intent_detail = approver.get_intent(intent_id).get("intent", {})
        print(f"[approver] reviewing intent_id={intent_id}")
        print(f"[approver] current status={intent_detail.get('status')}")
        payload_data = intent_detail.get("payload") or {}
        summary = payload_data.get("summary") or "(no summary)"
        risk_level = payload_data.get("risk_level") or "unknown"
        print(f"[approver] summary: {summary}")
        print(f"[approver] risk_level: {risk_level}")

        # Approver makes their decision via resume.
        resumed = approver.resume_intent(
            intent_id,
            {
                "approve_current_step": True,
                "reason": "Reviewed deployment plan — approved for production.",
                "approved_by": approver_agent or "approver",
                "approval_timestamp": correlation_id,
            },
            owner_agent=approver_agent,
        )
        print(
            f"[approver] resume applied={resumed.get('applied')} "
            f"policy_generation={resumed.get('policy_generation')}"
        )
        print(f"  🎾 ball at  approver (resolving)")

        # Approver resolves the intent to COMPLETED with the approval result.
        resolved = approver.resolve_intent(
            intent_id,
            {
                "status": "COMPLETED",
                "result": {
                    "approval_result": "approved",
                    "approved_by": approver_agent or "approver",
                    "summary": summary,
                    "notes": "Production deployment approved by on-call lead.",
                },
            },
        )
        terminal_event = resolved.get("event", {})
        print(
            f"[approver] resolve status={terminal_event.get('status')} "
            f"type={terminal_event.get('event_type')}"
        )
        print(f"  🎾 ball at  requester (reading final result)")

    # --- Step 3: Requester reads the final result ---
    print("\n=== Step 3: Requester reads approval result ===")

    with AxmeClient(requester_config) as requester:
        final_intent = requester.get_intent(intent_id).get("intent", {})
        result = final_intent.get("result") or {}
        print(f"[requester] intent_id={intent_id}")
        print(f"[requester] final status={final_intent.get('status')}")
        print(f"  🎾 ball at  🟢 done  — terminal state {final_intent.get('status')}")
        print(f"[requester] approval_result={result.get('approval_result')}")
        print(f"[requester] approved_by={result.get('approved_by')}")
        print(f"[requester] notes={result.get('notes')}")

        # Read lifecycle events — both actors appear in the event chain.
        listed = requester.list_intent_events(intent_id)
        events = listed.get("events", [])
        if isinstance(events, list):
            _print_events("lifecycle", [e for e in events if isinstance(e, dict)])

    print("\n=== Done ===")
    print(
        "The full lifecycle is recorded durably. Each actor's action is "
        "traceable via the event chain — no shared mutable state outside "
        "the intent was needed."
    )


if __name__ == "__main__":
    main()
