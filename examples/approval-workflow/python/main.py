from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

from axme import AxmeClient, AxmeClientConfig


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


def _print_events(events: list[dict[str, Any]]) -> None:
    for event in events:
        seq = int(event.get("seq", 0))
        status = str(event.get("status", "unknown"))
        event_type = str(event.get("event_type", "unknown"))
        waiting_reason = event.get("waiting_reason")
        suffix = f" waiting_reason={waiting_reason}" if waiting_reason else ""
        print(f"[event] seq={seq} type={event_type} status={status}{suffix}")


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    api_key = _require_env("AXME_API_KEY")
    actor_token = os.getenv("AXME_ACTOR_TOKEN", "").strip() or None
    from_agent = os.getenv("AXME_FROM_AGENT", "agent://examples/requester").strip()
    to_agent = os.getenv("AXME_TO_AGENT", "agent://examples/approver").strip()
    owner_agent = os.getenv("AXME_APPROVAL_OWNER_AGENT", from_agent).strip()

    config = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)

    correlation_id = str(uuid4())
    idempotency_key = f"approval-{correlation_id}"

    intent_payload = {
        "intent_type": "intent.approval.demo.v1",
        "correlation_id": correlation_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "payload": {
            "request_id": f"req-{correlation_id[:8]}",
            "summary": "Auto-approved rollout request.",
            "requested_by": from_agent,
            "approval_mode": "automatic",
        },
    }

    with AxmeClient(config) as client:
        created = client.create_intent(
            intent_payload,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        intent_id = str(created["intent_id"])
        print(f"[create] intent_id={intent_id} status={created.get('status')}")
        print("[approval] auto-approval path enabled; no manual waiting.")

        resumed = client.resume_intent(
            intent_id,
            {
                "approve_current_step": True,
                "reason": "auto-approved by policy",
            },
            owner_agent=owner_agent,
        )
        print(
            "[resume] "
            f"applied={resumed.get('applied')} policy_generation={resumed.get('policy_generation')}"
        )

        resolved = client.resolve_intent(
            intent_id,
            {
                "status": "COMPLETED",
                "result": {
                    "approval_result": "auto-approved",
                    "approval_mode": "automatic",
                },
            },
        )
        terminal_event = resolved.get("event", {})
        print(
            f"[resolve] terminal_type={terminal_event.get('event_type')} "
            f"status={terminal_event.get('status')}"
        )

        listed = client.list_intent_events(intent_id)
        events = listed.get("events", [])
        if isinstance(events, list):
            normalized = [item for item in events if isinstance(item, dict)]
            _print_events(normalized)

        final_intent = client.get_intent(intent_id).get("intent", {})
        print(
            f"[final] intent_id={intent_id} status={final_intent.get('status')} "
            f"lifecycle_status={final_intent.get('lifecycle_status')}"
        )


if __name__ == "__main__":
    main()
