"""ScenarioRunner — main orchestrator.

Usage:
    from runner import ScenarioRunner
    from runner.auth import AuthContext
    from runner.render import Renderer

    runner = ScenarioRunner(spec, auth=AuthContext(), render=Renderer())
    runner.run()
"""
from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from axme import AxmeClient, AxmeClientConfig

from .agents import AgentHandler, HttpAgentHandler, NoOpHandler, make_handler
from .auth import AuthContext
from .bundle import build_bundle
from .keys import get_or_create_key
from .render import Renderer


class ScenarioRunner:
    """Runs a scenario spec end-to-end."""

    def __init__(
        self,
        spec: dict[str, Any],
        *,
        auth: AuthContext,
        render: Renderer,
    ) -> None:
        self.spec   = spec
        self.auth   = auth
        self.render = render
        self._client = AxmeClient(
            AxmeClientConfig(
                api_key=auth.api_key,
                base_url=auth.base_url,
                actor_token=auth.actor_token,
            )
        )

    def run(self) -> None:
        spec   = self.spec
        render = self.render

        # 1. Print scenario header
        render.header(spec)

        # 2. Build ScenarioBundleRequest
        bundle = build_bundle(spec, human_contact=self.auth.human_contact())

        # 3. Apply scenario — provisions agents, compiles workflow, creates intent
        render.info("applying scenario (provisioning agents, compiling workflow)…")
        try:
            apply_resp = self._client.apply_scenario(
                bundle,
                idempotency_key=str(uuid4()),
            )
        except Exception as exc:
            render.error(f"apply_scenario failed: {exc}")
            raise SystemExit(1)

        intent_id  = str(apply_resp.get("intent_id") or "")
        compile_id = str(apply_resp.get("compile_id") or "")
        if not intent_id:
            render.error("server returned no intent_id")
            raise SystemExit(1)

        render.scenario_applied(apply_resp, spec)

        # 4. Resolve agent API keys + start delivery handlers
        provisioned_map = self._build_provisioned_map(apply_resp)
        handlers        = self._start_handlers(provisioned_map)

        # Small settle time so stream connections are established before intent arrives
        if any(isinstance(h, AgentHandler) for h in handlers):
            time.sleep(0.4)

        try:
            # 5. Observe lifecycle
            self._observe_loop(intent_id)
        except KeyboardInterrupt:
            print("\n  [cancelled]")
        finally:
            # 6. Stop all handlers
            for h in handlers:
                h.stop()

        # 7. Final summary + server audit log
        render.final_summary(spec, intent_id, compile_id)
        try:
            events_resp = self._client.list_intent_events(intent_id)
            render.audit_log(events_resp)
        except Exception as exc:
            render.error(f"could not fetch event log: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_provisioned_map(
        self, apply_resp: dict[str, Any]
    ) -> dict[str, str]:
        """Build {agent_address → sa_id} from apply_scenario response."""
        result: dict[str, str] = {}
        for item in (apply_resp.get("agents_provisioned") or []):
            if isinstance(item, dict):
                addr  = item.get("address") or item.get("agent_address") or ""
                sa_id = item.get("service_account_id") or item.get("sa_id") or ""
                if addr and sa_id:
                    result[addr] = sa_id
        return result

    def _start_handlers(
        self, provisioned_map: dict[str, str]
    ) -> list[Any]:
        handlers = []
        for agent_spec in (self.spec.get("agents") or []):
            mode = agent_spec.get("delivery_mode", "internal")
            if mode in ("internal",):
                handlers.append(NoOpHandler(agent_spec, render=self.render))
                continue

            address = agent_spec["address"]

            # Resolve short address to full agent:// URI if needed
            full_address = _resolve_address(address, provisioned_map)
            sa_id        = provisioned_map.get(full_address) or provisioned_map.get(address)

            if not sa_id:
                self.render.info(
                    f"warning: no sa_id found for {address} — "
                    "handler will use initiator key (may fail on server)"
                )
                agent_api_key = self.auth.api_key
            else:
                try:
                    agent_api_key = get_or_create_key(
                        full_address or address,
                        sa_id,
                        create_fn=self._client.create_service_account_key,
                    )
                except Exception as exc:
                    self.render.error(
                        f"could not get API key for {address}: {exc} — "
                        "falling back to initiator key"
                    )
                    agent_api_key = self.auth.api_key

            h = make_handler(
                agent_spec,
                api_key=agent_api_key,
                base_url=self.auth.base_url,
                render=self.render,
            )

            # For HTTP handler — register callback_url on SA before starting
            if isinstance(h, HttpAgentHandler):
                h.start()
                h.wait_ready()
                if sa_id:
                    try:
                        self._register_http_callback(sa_id, h.callback_url)
                    except Exception as exc:
                        self.render.error(
                            f"could not set callback_url on SA {sa_id}: {exc}"
                        )
            else:
                h.start()

            handlers.append(h)
        return handlers

    def _register_http_callback(self, sa_id: str, callback_url: str) -> None:
        """Update SA delivery_mode=http and callback_url."""
        self._client._request_json(
            "PATCH",
            f"/v1/service-accounts/{sa_id}",
            json_body={"delivery_mode": "http", "callback_url": callback_url},
            retryable=False,
        )

    def _observe_loop(self, intent_id: str) -> None:
        render = self.render
        spec   = self.spec

        _TERMINAL = {"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"}

        pending_human_task: dict[str, Any] | None = None

        try:
            for event in self._client.observe(intent_id, since=0, timeout_seconds=600):
                ev_type = str(event.get("event_type") or "")

                # Save human task info for the prompt
                if ev_type == "intent.human_task_assigned":
                    pending_human_task = event.get("human_task") or {}

                terminal = render.on_event(event, spec)

                # After human_task_assigned — prompt user
                if ev_type == "intent.human_task_assigned":
                    task_result = render.prompt_human_action(
                        spec, intent_id, pending_human_task or {}
                    )
                    if task_result:
                        try:
                            self._client.resume_intent(intent_id, task_result)
                        except Exception as exc:
                            render.error(f"resume_intent (human) failed: {exc}")

                if terminal:
                    break

        except TimeoutError:
            render.error("observation timed out after 10 min — check intent status manually")
            render.info(f"axme intents get {intent_id}")
            raise SystemExit(1)


def _resolve_address(short: str, provisioned_map: dict[str, str]) -> str:
    """Try to find the full agent:// address for a short name."""
    for full in provisioned_map:
        if full.endswith(f"/{short}") or full == short:
            return full
    return short
