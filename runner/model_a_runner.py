"""ModelAScenarioRunner — runs Model A (manual lifecycle) scenarios.

Model A = no ScenarioBundle, no server-side workflow DAG.
The client:
  1. Provisions agent SAs directly via POST /v1/service-accounts
  2. Starts delivery handlers (stream / poll / http — same as Model B)
  3. Creates the intent directly via POST /v1/intents
  4. Observes the lifecycle via observe()

Agents receive intents via their delivery binding, run real handler logic,
and call resume_intent() — the server records each transition.

For multi-step patterns, the initiator creates a second intent with the
result from step 1 embedded in the payload (as model_a_step.extra_payload).
"""
from __future__ import annotations

import datetime
import time
from typing import Any
from uuid import uuid4

from axme import AxmeClient, AxmeClientConfig

from .agents import AgentHandler, HttpAgentHandler, NoOpHandler, make_handler
from .auth import AuthContext
from .keys import get_or_create_key
from .render import Renderer


class ModelAScenarioRunner:
    """Runs a Model A (manual-intent) scenario end-to-end."""

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

        render.header(spec)
        render.info("Model A — manual lifecycle (POST /v1/intents, no ScenarioBundle)")

        # 1. Provision agents
        agent_map = self._provision_agents()

        # 2. Start delivery handlers
        handlers = self._start_handlers(agent_map)

        # Give stream handlers time to establish SSE connection
        if any(isinstance(h, AgentHandler) for h in handlers):
            time.sleep(0.4)

        # 3. Create intent(s) based on pattern
        pattern = spec.get("pattern", "request_response")
        intent_id = self._create_first_intent(agent_map)
        if not intent_id:
            for h in handlers:
                h.stop()
            return

        render.info(f"intent created: {intent_id}")

        try:
            # 4. Observe lifecycle
            if pattern == "fire_and_forget":
                self._observe_fire_and_forget(intent_id, agent_map)
            elif pattern == "manual_multi_step":
                self._observe_multi_step(intent_id, spec, agent_map, handlers)
            else:
                self._observe_loop(intent_id, spec)
        except KeyboardInterrupt:
            print("\n  [cancelled]")
        finally:
            for h in handlers:
                h.stop()

        # 5. Final summary
        render.final_summary(spec, intent_id, "")
        try:
            events_resp = self._client.list_intent_events(intent_id)
            render.audit_log(events_resp)
        except Exception as exc:
            render.error(f"could not fetch event log: {exc}")

    # ------------------------------------------------------------------
    # Agent provisioning
    # ------------------------------------------------------------------

    def _provision_agents(self) -> dict[str, dict[str, Any]]:
        """Provision SAs for all agents. Returns {role → {sa_id, address, api_key}}."""
        result: dict[str, dict[str, Any]] = {}
        for agent_spec in (self.spec.get("agents") or []):
            role    = agent_spec["role"]
            address = agent_spec["address"]
            mode    = agent_spec.get("delivery_mode", "stream")

            self.render.info(f"provisioning agent: {address} ({mode})")

            try:
                sa_resp = self._client.create_service_account(
                    {
                        "name":          address.rsplit("/", 1)[-1],
                        "display_name":  agent_spec.get("display_name") or address,
                        "delivery_mode": mode,
                    },
                    idempotency_key=f"model-a-sa-{address}",
                )
            except Exception as exc:
                # Already exists (409) or other error — try to find by listing
                self.render.info(f"  SA create returned: {exc} — searching existing SAs")
                sa_resp = self._find_existing_sa(address)
                if not sa_resp:
                    self.render.error(f"could not provision SA for {address}: {exc}")
                    raise SystemExit(1)

            sa_id    = sa_resp.get("service_account_id") or sa_resp.get("id") or ""
            resolved = sa_resp.get("address") or address

            if not sa_id:
                self.render.error(f"SA creation returned no service_account_id for {address}")
                raise SystemExit(1)

            try:
                api_key = get_or_create_key(
                    resolved,
                    sa_id,
                    create_fn=self._client.create_service_account_key,
                )
            except Exception as exc:
                self.render.error(f"could not get API key for {address}: {exc}")
                raise SystemExit(1)

            result[role] = {
                "sa_id":   sa_id,
                "address": resolved,
                "api_key": api_key,
                "spec":    agent_spec,
            }
            self.render.info(f"  ✓ {resolved} (sa_id={sa_id[:8]}…)")

        return result

    def _find_existing_sa(self, address: str) -> dict[str, Any] | None:
        """Try to find an existing SA by address name via list API."""
        try:
            name = address.rsplit("/", 1)[-1]
            resp = self._client.list_service_accounts(
                org_id=self.auth.org_id() if hasattr(self.auth, "org_id") else "",
            )
            for sa in (resp.get("service_accounts") or resp.get("items") or []):
                if sa.get("name") == name or sa.get("address") == address:
                    return sa
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Handler startup
    # ------------------------------------------------------------------

    def _start_handlers(
        self, agent_map: dict[str, dict[str, Any]]
    ) -> list[Any]:
        handlers = []
        for role, info in agent_map.items():
            agent_spec = info["spec"]
            mode       = agent_spec.get("delivery_mode", "stream")

            if mode == "internal":
                handlers.append(NoOpHandler(agent_spec, render=self.render))
                continue

            h = make_handler(
                agent_spec,
                api_key=info["api_key"],
                base_url=self.auth.base_url,
                render=self.render,
            )

            if isinstance(h, HttpAgentHandler):
                h.start()
                h.wait_ready()
                if info["sa_id"]:
                    try:
                        self._register_http_callback(info["sa_id"], h.callback_url)
                    except Exception as exc:
                        self.render.error(
                            f"could not set callback_url on SA {info['sa_id']}: {exc}"
                        )
            else:
                h.start()

            handlers.append(h)
        return handlers

    def _register_http_callback(self, sa_id: str, callback_url: str) -> None:
        self._client._request_json(
            "PATCH",
            f"/v1/service-accounts/{sa_id}",
            json_body={"delivery_mode": "http", "callback_url": callback_url},
            retryable=False,
        )

    # ------------------------------------------------------------------
    # Intent creation
    # ------------------------------------------------------------------

    def _create_first_intent(
        self, agent_map: dict[str, dict[str, Any]]
    ) -> str | None:
        spec        = self.spec
        intent_spec = spec.get("intent") or {}
        agents_spec = spec.get("agents") or []

        if not agents_spec:
            self.render.error("Model A spec requires at least one agent")
            return None

        # to_agent: from spec or first agent's address
        to_agent = intent_spec.get("to_agent") or ""
        if not to_agent:
            first_role = agents_spec[0]["role"]
            info = agent_map.get(first_role)
            to_agent = info["address"] if info else agents_spec[0]["address"]
        else:
            # Resolve to_agent role reference → full address
            for role, info in agent_map.items():
                if to_agent == role or to_agent == info["spec"]["address"]:
                    to_agent = info["address"]
                    break

        payload = dict(intent_spec.get("payload") or {})
        intent_type = intent_spec.get("type") or "intent.model_a.v1"

        # reply_to: for fire-and-forget — inject initiator's inbox address
        reply_to = intent_spec.get("reply_to") or ""
        if spec.get("pattern") == "fire_and_forget" and not reply_to:
            reply_to = self.auth.initiator_address() or ""

        intent_body: dict[str, Any] = {
            "to_agent":    to_agent,
            "intent_type": intent_type,
            "payload":     payload,
        }

        if reply_to:
            intent_body["reply_to"] = reply_to

        # Deadline
        durability   = spec.get("durability") or {}
        deadline_min = durability.get("deadline_minutes")
        deadline_sec = durability.get("deadline_seconds")
        if deadline_sec:
            dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=float(deadline_sec))
            intent_body["deadline_at"] = dt.isoformat() + "Z"
        elif deadline_min:
            dt = datetime.datetime.utcnow() + datetime.timedelta(minutes=float(deadline_min))
            intent_body["deadline_at"] = dt.isoformat() + "Z"

        max_attempts = durability.get("max_delivery_attempts")
        if max_attempts:
            intent_body["max_delivery_attempts"] = int(max_attempts)

        human_task = intent_spec.get("human_task")
        if human_task:
            intent_body["human_task"] = human_task

        try:
            resp = self._client.create_intent(
                intent_body,
                correlation_id=str(uuid4()),
                idempotency_key=str(uuid4()),
            )
            return str(resp.get("intent_id") or "")
        except Exception as exc:
            self.render.error(f"create_intent failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Observation patterns
    # ------------------------------------------------------------------

    def _observe_loop(
        self, intent_id: str, spec: dict[str, Any]
    ) -> None:
        render = self.render
        _TERMINAL = {"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"}
        pending_human_task: dict[str, Any] | None = None

        try:
            for event in self._client.observe(intent_id, since=0, timeout_seconds=600):
                ev_type = str(event.get("event_type") or "")

                if ev_type == "intent.human_task_assigned":
                    pending_human_task = event.get("human_task") or {}

                terminal = render.on_event(event, spec)

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
            render.error("observation timed out after 10 min")
            render.info(f"axme intents get {intent_id}")
            raise SystemExit(1)

    def _observe_fire_and_forget(
        self,
        intent_id: str,
        agent_map: dict[str, dict[str, Any]],
    ) -> None:
        render = self.render
        render.info("fire-and-forget: waiting for agent to process (then reading from inbox)…")

        # Wait for COMPLETED status by observing
        try:
            for event in self._client.observe(intent_id, since=0, timeout_seconds=120):
                render.on_event(event, self.spec)
                status = str(event.get("status") or event.get("event_type") or "")
                if status in {"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"}:
                    break
                if "intent.completed" in status or "intent.failed" in status:
                    break
        except (TimeoutError, Exception):
            pass

        # Read result from inbox
        render.info("reading result from initiator inbox…")
        try:
            inbox_resp = self._client.list_inbox()
            threads = inbox_resp.get("threads") or inbox_resp.get("items") or []
            render.info(f"inbox threads found: {len(threads)}")
            for thread in threads[:3]:
                tid    = thread.get("thread_id") or thread.get("id") or ""
                status = thread.get("status") or ""
                render.info(f"  thread {tid}: {status}")
        except Exception as exc:
            render.error(f"list_inbox failed: {exc}")

    def _observe_multi_step(
        self,
        first_intent_id: str,
        spec: dict[str, Any],
        agent_map: dict[str, dict[str, Any]],
        handlers: list[Any],
    ) -> None:
        render = self.render
        render.info("step 1/2: waiting for first intent to complete…")

        first_result: dict[str, Any] = {}
        try:
            for event in self._client.observe(first_intent_id, since=0, timeout_seconds=120):
                render.on_event(event, spec)
                if event.get("status") == "COMPLETED":
                    first_result = event.get("result") or event.get("payload") or {}
                    break
                ev_type = str(event.get("event_type") or "")
                if "intent.completed" in ev_type:
                    first_result = event.get("result") or {}
                    break
                if ev_type in {"intent.failed", "intent.timed_out"}:
                    render.error("step 1 did not complete — aborting multi-step")
                    return
        except (TimeoutError, Exception) as exc:
            render.error(f"step 1 observation error: {exc}")
            return

        render.info(f"step 1 result: {first_result}")

        # Build step 2 intent — embed step 1 result in payload
        second_intent_spec = spec.get("second_intent") or {}
        agents_spec        = spec.get("agents") or []
        second_role        = second_intent_spec.get("to_role") or (
            agents_spec[1]["role"] if len(agents_spec) > 1 else ""
        )
        second_info  = agent_map.get(second_role)
        second_agent = second_info["address"] if second_info else ""

        if not second_agent:
            render.error("no second agent defined for multi-step pattern")
            return

        second_payload = dict(second_intent_spec.get("payload") or {})
        second_payload.update(first_result)  # embed step 1 result

        render.info(f"step 2/2: sending to {second_agent}…")
        try:
            resp = self._client.create_intent(
                {
                    "to_agent":    second_agent,
                    "intent_type": second_intent_spec.get("type") or "intent.model_a.step2.v1",
                    "payload":     second_payload,
                },
                correlation_id=str(uuid4()),
                idempotency_key=str(uuid4()),
            )
            second_id = str(resp.get("intent_id") or "")
        except Exception as exc:
            render.error(f"step 2 create_intent failed: {exc}")
            return

        render.info(f"step 2 intent: {second_id}")
        self._observe_loop(second_id, spec)
