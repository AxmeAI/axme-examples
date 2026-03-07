from __future__ import annotations

import json
import os
import queue
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _simulate_callback(callback_url: str, delay_seconds: int) -> None:
    time.sleep(max(0, delay_seconds))
    payload = {
        "provider": "billing-gateway",
        "callback_status": "approved",
        "external_reference": f"ext-{uuid4().hex[:10]}",
        "amount_cents": 4999,
    }
    request = urllib.request.Request(
        callback_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    api_key = _require_env("AXME_API_KEY")
    actor_token = os.getenv("AXME_ACTOR_TOKEN", "").strip() or None
    from_agent = os.getenv("AXME_FROM_AGENT", "agent://examples/orchestrator").strip()
    to_agent = os.getenv("AXME_TO_AGENT", "agent://examples/external-worker").strip()
    owner_agent = os.getenv("AXME_OWNER_AGENT", from_agent).strip()
    callback_host = os.getenv("AXME_CALLBACK_HOST", "127.0.0.1").strip()
    callback_port = _as_int("AXME_CALLBACK_PORT", 8787)
    callback_timeout = _as_int("AXME_CALLBACK_TIMEOUT_SECONDS", 30)
    simulate_callback = _as_bool("AXME_SIMULATE_CALLBACK", True)

    callback_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (built-in handler contract)
            content_length = int(self.headers.get("content-length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except ValueError:
                payload = {"raw": raw_body.decode("utf-8", errors="replace")}
            try:
                callback_queue.put_nowait(payload if isinstance(payload, dict) else {"payload": payload})
            except queue.Full:
                pass
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((callback_host, callback_port), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    callback_url = f"http://{callback_host}:{callback_port}/external/callback"
    print(f"[callback] listening on {callback_url}")

    if simulate_callback:
        threading.Thread(target=_simulate_callback, args=(callback_url, 2), daemon=True).start()
        print("[callback] simulation enabled; callback will be posted automatically.")

    config = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)
    correlation_id = str(uuid4())
    idempotency_key = f"external-callback-{correlation_id}"
    intent_payload = {
        "intent_type": "intent.external_callback.demo.v1",
        "correlation_id": correlation_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "payload": {
            "operation": "capture_payment",
            "order_id": f"order-{correlation_id[:8]}",
            "callback_url": callback_url,
        },
    }

    try:
        with AxmeClient(config) as client:
            created = client.create_intent(
                intent_payload,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )
            intent_id = str(created["intent_id"])
            print(f"[create] intent_id={intent_id} status={created.get('status')}")

            print(f"[callback] waiting up to {callback_timeout}s for external payload...")
            callback_payload = callback_queue.get(timeout=callback_timeout)
            print(f"[callback] received: {json.dumps(callback_payload, ensure_ascii=True)}")

            resumed = client.resume_intent(
                intent_id,
                {
                    "approve_current_step": True,
                    "reason": "external callback received",
                },
                owner_agent=owner_agent,
            )
            print(f"[resume] applied={resumed.get('applied')} policy_generation={resumed.get('policy_generation')}")

            resolved = client.resolve_intent(
                intent_id,
                {
                    "status": "COMPLETED",
                    "result": {
                        "source": "external_callback",
                        "callback_payload": callback_payload,
                    },
                },
            )
            event = resolved.get("event", {})
            print(f"[resolve] event_type={event.get('event_type')} status={event.get('status')}")

            final_intent = client.get_intent(intent_id).get("intent", {})
            print(
                f"[final] intent_id={intent_id} status={final_intent.get('status')} "
                f"lifecycle_status={final_intent.get('lifecycle_status')}"
            )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
