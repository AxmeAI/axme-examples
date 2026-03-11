from __future__ import annotations

import os
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


def _create_child_intent(
    client: AxmeClient,
    *,
    to_agent: str | None,
    service_name: str,
    parent_intent_id: str,
) -> str:
    correlation_id = str(uuid4())
    body: dict[str, Any] = {
        "intent_type": "intent.service_step.demo.v1",
        "correlation_id": correlation_id,
        "payload": {
            "service": service_name,
            "parent_intent_id": parent_intent_id,
            "task": f"run_{service_name}_step",
        },
    }
    if to_agent:
        body["to_agent"] = to_agent
    created = client.create_intent(
        body,
        correlation_id=correlation_id,
        idempotency_key=f"child-{service_name}-{correlation_id}",
    )
    return str(created["intent_id"])


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    api_key = _require_env("AXME_API_KEY")
    actor_token = os.getenv("AXME_ACTOR_TOKEN", "").strip() or None
    # from_agent is derived by the server from the API key (no longer passed explicitly)
    parent_to_agent = os.getenv("AXME_PARENT_TO_AGENT", "").strip() or None
    service_b_agent = os.getenv("AXME_SERVICE_B_AGENT", "").strip() or None
    service_c_agent = os.getenv("AXME_SERVICE_C_AGENT", "").strip() or None

    config = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)

    print(f"[agent]   parent_to_agent={parent_to_agent or '(derived by server)'}")
    print(f"[agent]   service_b_agent={service_b_agent or '(derived by server)'}")
    print(f"[agent]   service_c_agent={service_c_agent or '(derived by server)'}")
    print(f"[agent]   from_agent=(derived from API key)")
    print()

    with AxmeClient(config) as client:
        parent_correlation = str(uuid4())
        parent_payload: dict[str, Any] = {
            "intent_type": "intent.multi_service.demo.v1",
            "correlation_id": parent_correlation,
            "payload": {
                "operation": "provision_enterprise_workspace",
                "steps": ["service_b", "service_c"],
            },
        }
        if parent_to_agent:
            parent_payload["to_agent"] = parent_to_agent
        parent = client.create_intent(
            parent_payload,
            correlation_id=parent_correlation,
            idempotency_key=f"parent-{parent_correlation}",
        )
        parent_intent_id = str(parent["intent_id"])
        print(f"[parent:create] intent_id={parent_intent_id}")
        print(f"  status     {parent.get('status')}")
        print(f"  🎾 ball at  orchestrator (starting sub-services)")

        resumed_parent = client.resume_intent(
            parent_intent_id,
            {"approve_current_step": True, "reason": "start orchestration"},
        )
        print(
            "[parent:resume] "
            f"applied={resumed_parent.get('applied')} policy_generation={resumed_parent.get('policy_generation')}"
        )

        child_b_id = _create_child_intent(
            client,
            to_agent=service_b_agent,
            service_name="service_b",
            parent_intent_id=parent_intent_id,
        )
        child_c_id = _create_child_intent(
            client,
            to_agent=service_c_agent,
            service_name="service_c",
            parent_intent_id=parent_intent_id,
        )
        print(f"[child:create] service_b_intent_id={child_b_id}")
        print(f"  🎾 ball at  service-b")
        print(f"[child:create] service_c_intent_id={child_c_id}")
        print(f"  🎾 ball at  service-c (parallel)")

        child_b_result: dict[str, Any] = {
            "service": "service_b",
            "status": "done",
            "artifact": f"artifact-{uuid4().hex[:8]}",
        }
        child_c_result: dict[str, Any] = {
            "service": "service_c",
            "status": "done",
            "artifact": f"artifact-{uuid4().hex[:8]}",
        }

        client.resolve_intent(child_b_id, {"status": "COMPLETED", "result": child_b_result})
        client.resolve_intent(child_c_id, {"status": "COMPLETED", "result": child_c_result})
        print("[child:resolve] service_b=COMPLETED service_c=COMPLETED")
        print(f"  🎾 ball at  orchestrator (all children done, resolving parent)")

        parent_result = {
            "operation": "provision_enterprise_workspace",
            "children": [
                {"intent_id": child_b_id, "result": child_b_result},
                {"intent_id": child_c_id, "result": child_c_result},
            ],
        }
        resolved_parent = client.resolve_intent(
            parent_intent_id,
            {"status": "COMPLETED", "result": parent_result},
        )
        terminal_status = resolved_parent.get('event', {}).get('status', 'COMPLETED')
        print(f"[parent:resolve] status={terminal_status}")
        print(f"  🎾 ball at  🟢 done  — terminal state {terminal_status}")

        final_parent = client.get_intent(parent_intent_id).get("intent", {})
        print()
        print(f"[done]   parent_intent_id={parent_intent_id}")
        print(f"         status={final_parent.get('status')}  lifecycle_status={final_parent.get('lifecycle_status')}")
        print()
        print("  Explore via CLI:")
        print(f"    axme intents get {parent_intent_id}")
        print(f"    axme intents watch {parent_intent_id}")


if __name__ == "__main__":
    main()
