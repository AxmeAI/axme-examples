"""Agent handlers — one class per delivery binding.

Each handler runs in its own daemon thread.  The runner starts all handlers
BEFORE submitting the intent so they are ready to receive it.

Handler types (handler_spec["type"]):
  auto_complete  — after delay_seconds calls resume_intent(COMPLETED)
  auto_fail      — after delay_seconds calls resume_intent(FAILED)
  no_op          — receives but does nothing (for timeout/retry tests)
  interactive    — prompts the user in the terminal
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from axme import AxmeClient, AxmeClientConfig

from .render import Renderer


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class AgentHandler(threading.Thread):
    """Base class for all delivery-binding handlers."""

    def __init__(
        self,
        agent_spec: dict[str, Any],
        *,
        api_key: str,
        base_url: str,
        render: Renderer,
    ) -> None:
        super().__init__(daemon=True, name=f"agent-{agent_spec['address']}")
        self.agent_spec   = agent_spec
        self.address      = agent_spec["address"]
        self.handler_spec = agent_spec.get("handler") or {}
        self.render       = render
        self._stop_event  = threading.Event()
        self._client      = AxmeClient(
            AxmeClientConfig(api_key=api_key, base_url=base_url)
        )

    def stop(self) -> None:
        self._stop_event.set()

    def _execute_handler(self, intent_id: str) -> None:
        htype       = self.handler_spec.get("type", "auto_complete")
        delay       = float(self.handler_spec.get("delay_seconds", 1.0))
        outcome     = self.handler_spec.get("outcome") or {}
        fail_reason = self.handler_spec.get("reason", "handler_failed")

        self.render.agent_received(self.address)

        if htype == "no_op":
            self.render.info(f"{self.address}  no_op — not responding (testing retry/timeout)")
            return

        if htype == "interactive":
            print()
            print(f"  [agent prompt]  Agent '{self.address}' received intent {intent_id}")
            print(f"  [agent prompt]  Press Enter to complete, or type 'fail' then Enter:")
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if choice == "fail":
                self.render.agent_processing(self.address)
                self.render.agent_resumed(self.address, "FAILED")
                self._client.resume_intent(intent_id, {"action": "fail", "reason": "operator_rejected"})
            else:
                self.render.agent_processing(self.address)
                self.render.agent_resumed(self.address, "COMPLETED")
                self._client.resume_intent(intent_id, {"action": "complete", **outcome})
            return

        # auto_complete / auto_fail
        self.render.agent_processing(self.address, delay_secs=delay)
        time.sleep(delay)

        if htype == "auto_fail":
            self.render.agent_resumed(self.address, "FAILED")
            try:
                self._client.resume_intent(intent_id, {"action": "fail", "reason": fail_reason})
            except Exception as exc:
                self.render.error(f"{self.address} resume(FAILED) error: {exc}")
        else:  # auto_complete
            self.render.agent_resumed(self.address, "COMPLETED")
            try:
                self._client.resume_intent(intent_id, {"action": "complete", **outcome})
            except Exception as exc:
                self.render.error(f"{self.address} resume(COMPLETED) error: {exc}")


# ---------------------------------------------------------------------------
# Stream handler — uses client.listen()
# ---------------------------------------------------------------------------

class StreamAgentHandler(AgentHandler):
    """Receives intents via SSE (GET /v1/agents/{address}/intents/stream)."""

    def run(self) -> None:
        self.render.agent_handler_started(self.address, "stream")
        try:
            for delivery in self._client.listen(
                self.address,
                timeout_seconds=None,  # listen until stopped
            ):
                if self._stop_event.is_set():
                    break
                intent_id = delivery.get("intent_id")
                if intent_id:
                    self._execute_handler(intent_id)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.render.error(f"stream handler [{self.address}]: {exc}")


# ---------------------------------------------------------------------------
# Poll handler — periodically calls list_intent_events
# ---------------------------------------------------------------------------

class PollAgentHandler(AgentHandler):
    """Receives intents by polling GET /v1/agents/{address}/intents (poll binding)."""

    def __init__(self, *args: Any, poll_interval: float = 3.0, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._poll_interval = poll_interval
        self._seen: set[str] = set()

    def run(self) -> None:
        self.render.agent_handler_started(self.address, "poll")
        cursor = 0
        while not self._stop_event.is_set():
            try:
                resp = self._client.list_intent_events_for_address(
                    self.address, since=cursor
                )
                intents = resp.get("intents") or []
                for item in intents:
                    intent_id = item.get("intent_id")
                    if intent_id and intent_id not in self._seen:
                        self._seen.add(intent_id)
                        self._execute_handler(intent_id)
                new_cursor = resp.get("next_cursor") or resp.get("cursor")
                if new_cursor:
                    cursor = new_cursor
            except Exception as exc:
                if not self._stop_event.is_set():
                    self.render.error(f"poll handler [{self.address}]: {exc}")
            self._stop_event.wait(timeout=self._poll_interval)


# ---------------------------------------------------------------------------
# HTTP handler — starts a local server, AXME POSTs intents to callback_url
# ---------------------------------------------------------------------------

class HttpAgentHandler(AgentHandler):
    """Receives intents via HTTP POST from AXME (http delivery binding).

    Starts a local HTTPServer on localhost:PORT.
    The SA must be registered with delivery_mode=http and
    callback_url=http://localhost:{PORT}/intent.
    """

    def __init__(
        self,
        *args: Any,
        port: int = 0,  # 0 = auto-assign free port
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._port        = port
        self._httpd: HTTPServer | None = None
        self._ready       = threading.Event()

    @property
    def callback_url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("server not started yet")
        _, port = self._httpd.server_address
        return f"http://localhost:{port}/intent"

    def run(self) -> None:
        handler_ref = self  # closure for BaseHTTPRequestHandler

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: Any) -> None:
                pass  # suppress default access log

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body   = self.rfile.read(length)
                self.send_response(200)
                self.end_headers()
                try:
                    payload   = json.loads(body)
                    intent_id = payload.get("intent_id")
                    if intent_id:
                        threading.Thread(
                            target=handler_ref._execute_handler,
                            args=(intent_id,),
                            daemon=True,
                        ).start()
                except Exception as exc:
                    handler_ref.render.error(f"http handler parse error: {exc}")

        self._httpd = HTTPServer(("localhost", self._port), _Handler)
        actual_port = self._httpd.server_address[1]
        self._ready.set()
        self.render.agent_handler_started(
            self.address,
            f"http (callback_url=http://localhost:{actual_port}/intent)",
        )
        while not self._stop_event.is_set():
            self._httpd.handle_request()

    def wait_ready(self, timeout: float = 5.0) -> None:
        if not self._ready.wait(timeout=timeout):
            raise RuntimeError(f"HTTP handler for {self.address} did not start in time")

    def stop(self) -> None:
        super().stop()
        if self._httpd:
            self._httpd.server_close()


# ---------------------------------------------------------------------------
# No-op (internal or absent agent)
# ---------------------------------------------------------------------------

class NoOpHandler:
    """Placeholder for agents with delivery_mode=internal (handled by agent_core)."""

    def __init__(self, agent_spec: dict[str, Any], *, render: Renderer) -> None:
        self.agent_spec = agent_spec
        self.address    = agent_spec["address"]
        self.render     = render

    def start(self) -> None:
        pass  # agent_core handles this step

    def stop(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_handler(
    agent_spec: dict[str, Any],
    *,
    api_key: str,
    base_url: str,
    render: Renderer,
    http_port: int = 0,
) -> AgentHandler | NoOpHandler:
    mode = agent_spec.get("delivery_mode", "internal")

    if mode == "stream":
        return StreamAgentHandler(agent_spec, api_key=api_key, base_url=base_url, render=render)
    if mode == "poll":
        return PollAgentHandler(agent_spec, api_key=api_key, base_url=base_url, render=render)
    if mode == "http":
        return HttpAgentHandler(agent_spec, api_key=api_key, base_url=base_url, render=render, port=http_port)
    # internal / no_op / external
    return NoOpHandler(agent_spec, render=render)
