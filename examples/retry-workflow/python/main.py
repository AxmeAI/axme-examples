from __future__ import annotations

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


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _run_external_step(attempt: int, *, simulated_failures: int) -> dict[str, Any]:
    if attempt <= simulated_failures:
        raise RuntimeError(f"transient dependency failure on attempt {attempt}")
    return {
        "status": "ok",
        "attempt": attempt,
        "job_reference": f"job-{uuid4().hex[:10]}",
    }


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    api_key = _require_env("AXME_API_KEY")
    actor_token = os.getenv("AXME_ACTOR_TOKEN", "").strip() or None
    # from_agent is derived by the server from the API key (no longer passed explicitly)
    to_agent = os.getenv("AXME_TO_AGENT", "").strip() or None
    owner_agent = os.getenv("AXME_OWNER_AGENT", "").strip() or None
    max_attempts = _as_int("AXME_MAX_ATTEMPTS", 5)
    simulated_failures = _as_int("AXME_SIMULATED_FAILURES", 2)
    base_backoff_seconds = _as_int("AXME_BASE_BACKOFF_SECONDS", 1)

    config = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)
    correlation_id = str(uuid4())
    idempotency_key = f"retry-{correlation_id}"
    payload: dict[str, Any] = {
        "intent_type": "intent.retry.demo.v1",
        "correlation_id": correlation_id,
        "payload": {
            "task": "sync_remote_inventory",
            "target_system": "warehouse-api",
        },
    }
    if to_agent:
        payload["to_agent"] = to_agent

    print(f"[agent]   to_agent={to_agent or '(derived by server)'}")
    print(f"[agent]   from_agent=(derived from API key)")
    print()

    with AxmeClient(config) as client:
        created_first = client.create_intent(payload, correlation_id=correlation_id, idempotency_key=idempotency_key)
        created_second = client.create_intent(payload, correlation_id=correlation_id, idempotency_key=idempotency_key)
        intent_id = str(created_first["intent_id"])
        print(f"[create] intent_id={intent_id}")
        print(f"  status     {created_first.get('status')}")
        print(f"  🎾 ball at  retry-worker (executing, may fail transiently)")
        print(f"[idempotency] replay_intent_id={created_second.get('intent_id')}")

        attempts = 0
        delays: list[int] = []
        external_result: dict[str, Any] | None = None

        while attempts < max_attempts:
            attempts += 1
            try:
                external_result = _run_external_step(attempts, simulated_failures=simulated_failures)
                print(f"[attempt {attempts}] external step succeeded")
                break
            except RuntimeError as exc:
                delay_seconds = base_backoff_seconds * (2 ** (attempts - 1))
                delays.append(delay_seconds)
                print(f"[attempt {attempts}] {exc}; backing off for {delay_seconds}s")
                control_body = client.update_intent_controls(
                    intent_id,
                    {
                        "controls_patch": {
                            "last_retry_attempt": attempts,
                            "next_retry_delay_seconds": delay_seconds,
                        },
                        "reason": f"retry attempt {attempts} failed",
                    },
                )
                print(
                    "[controls] "
                    f"applied={control_body.get('applied')} policy_generation={control_body.get('policy_generation')}"
                )
                print(f"  🎾 ball at  retry-worker (backing off, attempt {attempts}/{max_attempts})")
                time.sleep(max(0, delay_seconds))

        if external_result is not None:
            print(f"  🎾 ball at  orchestrator (all attempts done, resolving COMPLETED)")
            resolved = client.resolve_intent(
                intent_id,
                {
                    "status": "COMPLETED",
                    "result": {
                        "attempts": attempts,
                        "retry_backoff_seconds": delays,
                        "external_result": external_result,
                    },
                },
            )
            terminal_status = resolved.get('event', {}).get('status', 'COMPLETED')
            print(f"[resolve] status={terminal_status}")
        else:
            print(f"  🎾 ball at  orchestrator (max attempts reached, resolving FAILED)")
            failed = client.resolve_intent(
                intent_id,
                {
                    "status": "FAILED",
                    "error": {
                        "code": "max_attempts_exceeded",
                        "attempts": attempts,
                        "retry_backoff_seconds": delays,
                    },
                },
            )
            terminal_status = failed.get('event', {}).get('status', 'FAILED')
            print(f"[resolve] status={terminal_status}")

        print(f"  🎾 ball at  🟢 done  — terminal state {terminal_status}")
        final_intent = client.get_intent(intent_id).get("intent", {})
        print()
        print(f"[done]   intent_id={intent_id}")
        print(f"         status={final_intent.get('status')}  lifecycle_status={final_intent.get('lifecycle_status')}")
        print()
        print("  Explore via CLI:")
        print(f"    axme intents get {intent_id}")
        print(f"    axme intents watch {intent_id}")


if __name__ == "__main__":
    main()
