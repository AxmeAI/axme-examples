"""Terminal renderer — unified output format for all scenarios.

Rules derived from examples/approval-workflow/python/main.py.
All output goes through _tag() so the format is consistent across every scenario.
"""
from __future__ import annotations

import time
from typing import Any

_TAG_WIDTH = 20
_LINE_WIDTH = 74


def _tag(kind: str, msg: str) -> None:
    print(f"  [{kind:<{_TAG_WIDTH}}]  {msg}")


def _divider() -> None:
    print("  " + "─" * _LINE_WIDTH)


def _pause(secs: float) -> None:
    time.sleep(secs)


def _fmt_status(raw: str, reason: str = "") -> str:
    is_human = "HUMAN" in reason.upper() or "human" in reason.lower()
    mapping = {
        "CREATED":      "CREATED",
        "SUBMITTED":    "SUBMITTED",
        "DELIVERED":    "DELIVERED",
        "ACKNOWLEDGED": "ACKNOWLEDGED",
        "IN_PROGRESS":  "IN_PROGRESS",
        "WAITING":      f"WAITING (for {'human' if is_human else 'agent'})",
        "COMPLETED":    "COMPLETED ✓",
        "FAILED":       "FAILED ✗",
        "CANCELED":     "CANCELED",
        "TIMED_OUT":    "TIMED_OUT ✗",
    }
    return mapping.get(raw, raw)


def _fmt_pending_with(pw: dict[str, Any] | None) -> str:
    if not pw:
        return ""
    name = pw.get("name") or pw.get("ref") or ""
    return str(name).split("/")[-1]


def _fmt_binding(mode: str) -> str:
    labels = {
        "stream":   "stream  ← SSE listen()",
        "poll":     "poll    ← periodic pull",
        "http":     "http    ← AXME pushes to callback_url",
        "inbox":    "inbox   ← reply_to mechanism",
        "internal": "internal ← agent_core built-in",
    }
    return labels.get(mode, mode)


class Renderer:
    """Stateful renderer for one scenario run."""

    def __init__(self) -> None:
        self._cur_status = ""
        self._cur_holder = ""

    # ------------------------------------------------------------------
    # Scenario lifecycle
    # ------------------------------------------------------------------

    def header(self, spec: dict[str, Any]) -> None:
        print()
        _divider()
        print(f"  Axme scenario runner  ·  {spec.get('scenario_id', '?')}")
        _divider()
        print(f"  {spec.get('title', '')}")
        if spec.get("description"):
            print(f"  {spec['description']}")
        print()

        steps = spec.get("workflow_steps") or []
        agents_by_role: dict[str, dict] = {
            a["role"]: a for a in (spec.get("agents") or [])
        }
        humans_by_role: dict[str, dict] = {
            h["role"]: h for h in (spec.get("humans") or [])
        }
        n = len(steps)
        for i, step in enumerate(steps, 1):
            role = step.get("assigned_to", "")
            rt   = step.get("runtime_type", "")

            if rt:
                kind  = "internal"
                label = f"{rt} (internal runtime)"
            elif role in humans_by_role:
                kind  = "human"
                h     = humans_by_role[role]
                label = h.get("display_name") or role
            elif role in agents_by_role:
                a     = agents_by_role[role]
                kind  = "agent"
                mode  = a.get("delivery_mode", "internal")
                label = f"{a.get('display_name') or role}  [{_fmt_binding(mode)}]"
            else:
                kind  = "step"
                label = role or step.get("step_id", "?")

            desc = step.get("description", "")
            print(f"  [{kind}:step {i}/{n}{'':>{max(0,4-len(str(n)))}}"
                  f"{'':>{_TAG_WIDTH - 12 - len(str(i)) - len(str(n))}}"
                  f"]  {label}" + (f"  ({desc})" if desc else ""))

        dur = spec.get("durability") or {}
        dl  = dur.get("deadline_minutes")
        mda = dur.get("max_delivery_attempts")
        parts = []
        if dl:
            parts.append(f"deadline: {dl} min")
        if mda:
            parts.append(f"max_delivery_attempts: {mda}")
        if parts:
            print()
            _tag("system", " · ".join(parts))
        print()

    def scenario_applied(self, apply_resp: dict[str, Any], spec: dict[str, Any]) -> None:
        intent_id  = apply_resp.get("intent_id", "?")
        compile_id = apply_resp.get("compile_id") or ""
        provisioned = apply_resp.get("agents_provisioned") or []

        for ag in provisioned:
            _tag("agent:create", str(ag))
        _pause(0.2)

        agents = spec.get("agents") or []
        for a in agents:
            mode  = a.get("delivery_mode", "internal")
            label = a.get("display_name") or a.get("address") or a.get("role")
            _tag("agent:assign", f"{label}  [{_fmt_binding(mode)}]")

        humans = spec.get("humans") or []
        for h in humans:
            label   = h.get("display_name") or h.get("role")
            contact = h.get("contact", "")
            suffix  = f"  <{contact}>" if contact else ""
            _tag("human:assign", f"{label}{suffix}")

        print()
        _tag("intent:create", f"intent_id={intent_id}")
        if compile_id:
            _tag("intent:create", f"workflow compile_id={compile_id}")
        _pause(0.1)

        self._cur_status = "DELIVERED"
        self._cur_holder = ""
        _tag("status:change", "—  →  DELIVERED")
        print()

    def agent_handler_started(self, address: str, mode: str) -> None:
        short = address.split("/")[-1]
        _tag("binding", f"{short}  [{_fmt_binding(mode)}]  connected")

    def agent_received(self, address: str) -> None:
        short = address.split("/")[-1]
        _tag("agent:received", f"{short}  received intent")

    def agent_processing(self, address: str, delay_secs: float | None = None) -> None:
        short = address.split("/")[-1]
        suffix = f"  ({delay_secs:.1f}s)" if delay_secs else ""
        _tag("agent:processing", f"{short}  processing…{suffix}")

    def agent_resumed(self, address: str, outcome: str) -> None:
        short = address.split("/")[-1]
        _tag("agent:resume", f"{short}  →  resume {outcome}")

    # ------------------------------------------------------------------
    # Intent lifecycle events (from observe() loop)
    # ------------------------------------------------------------------

    def on_event(self, event: dict[str, Any], spec: dict[str, Any]) -> str | None:
        """Process one event from observe().

        Returns intent_id to stop after if terminal, else None.
        """
        ev_status = str(event.get("status") or "")
        ev_reason = str(
            event.get("lifecycle_waiting_reason")
            or event.get("reason")
            or ""
        )
        ev_type   = str(event.get("event_type") or "")
        raw_pw    = event.get("pending_with")
        new_holder = (
            _fmt_pending_with(raw_pw) if isinstance(raw_pw, dict)
            else self._cur_holder
        )

        # ── Special event types ──────────────────────────────────────
        if ev_type == "intent.human_task_assigned":
            return self._on_human_task_assigned(event, spec, new_holder)

        if ev_type == "intent.reminder":
            _tag("reminder", f"REMINDER sent to {new_holder or '?'}")
            return None

        if ev_type == "intent.escalated":
            escalated_to = (event.get("details") or {}).get("escalated_to", "?")
            _tag("escalation", f"escalated to {escalated_to}")
            self._cur_holder = escalated_to
            return None

        if ev_type == "intent.timed_out":
            _tag("timeout", "TIMED_OUT — deadline exceeded")
            return None

        if ev_type == "intent.delivery_failed":
            attempts = (event.get("details") or {}).get("delivery_attempt", "?")
            _tag("delivery:failed", f"max_delivery_attempts reached  (attempt={attempts})")
            return None

        # ── Status change ────────────────────────────────────────────
        if not ev_status:
            return None

        new_fmt = _fmt_status(ev_status, ev_reason)

        if new_holder and new_holder != self._cur_holder:
            self._print_step_header(new_holder, spec)

        if new_fmt != self._cur_status:
            _tag("status:change", f"{self._cur_status}  →  {new_fmt}")
            _pause(0.2)

        if new_holder and new_holder != self._cur_holder:
            _tag("cur_holder", f"{self._cur_holder}  →  {new_holder}")
            _pause(0.2)

        self._cur_status = new_fmt
        self._cur_holder = new_holder or self._cur_holder

        _TERMINAL = {"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"}
        if ev_status in _TERMINAL:
            return ev_status
        return None

    def _print_step_header(self, holder: str, spec: dict[str, Any]) -> None:
        steps   = spec.get("workflow_steps") or []
        agents  = {a["role"]: a for a in (spec.get("agents") or [])}
        humans  = {h["role"]: h for h in (spec.get("humans") or [])}
        n       = len(steps)

        for i, step in enumerate(steps, 1):
            role  = step.get("assigned_to", "")
            label = (agents.get(role) or humans.get(role) or {}).get(
                "display_name"
            ) or role
            if holder in label or label in holder or holder == role:
                is_human = role in humans
                icon  = "👤" if is_human else "⚙"
                print()
                _divider()
                print(f"  ── step {i}/{n}  {icon}  {label}")
                _divider()
                desc = step.get("description", "")
                if desc:
                    _tag("system", desc)
                return

    def _on_human_task_assigned(
        self,
        event: dict[str, Any],
        spec: dict[str, Any],
        new_holder: str,
    ) -> None:
        ht     = event.get("human_task") or {}
        title  = ht.get("title") or "Human approval required"
        schema = ht.get("form_schema")

        steps  = spec.get("workflow_steps") or []
        humans = {h["role"]: h for h in (spec.get("humans") or [])}
        n      = len(steps)

        # Find which human step this is
        for i, step in enumerate(steps, 1):
            role = step.get("assigned_to", "")
            if role in humans:
                label = humans[role].get("display_name") or role
                print()
                _divider()
                print(f"  ── step {i}/{n}  👤  {label}")
                _divider()
                break

        _tag("system", f"task: {title}")
        _tag("status:change", f"{self._cur_status}  →  {_fmt_status('WAITING', 'WAITING_FOR_HUMAN')}")
        if new_holder:
            _tag("cur_holder", f"{self._cur_holder}  →  {new_holder}")
        self._cur_status = _fmt_status("WAITING", "WAITING_FOR_HUMAN")
        self._cur_holder = new_holder

        if schema:
            fields = list((schema.get("properties") or {}).keys())
            _tag("system", f"form fields: {', '.join(fields)}")
        return None

    # ------------------------------------------------------------------
    # Human interaction prompt
    # ------------------------------------------------------------------

    def prompt_human_action(
        self,
        spec: dict[str, Any],
        intent_id: str,
        human_task: dict[str, Any],
    ) -> dict[str, Any]:
        """Interactive prompt for human task. Returns task_result dict."""
        handler_spec = _find_human_handler(spec)
        htype = (handler_spec or {}).get("type", "interactive")

        humans = spec.get("humans") or []
        human_label = (humans[0].get("display_name") if humans else None) or "Human"

        print()
        _tag("system", f"You are acting as:  {human_label}")

        if htype == "auto_approve":
            _tag("system", "auto_approve mode — approving automatically")
            _pause(0.5)
            result = {"approved": True}
        elif htype == "auto_reject":
            _tag("system", "auto_reject mode — rejecting automatically")
            _pause(0.5)
            result = {"approved": False, "reason": "auto_reject"}
        elif htype == "human_cli_hint":
            _tag("system", f"Run in another terminal:  axme tasks approve {intent_id}")
            _tag("system", "Waiting for CLI action… (Ctrl+C to cancel)")
            try:
                input("  > (press Enter after running the CLI command) ")
            except (EOFError, KeyboardInterrupt):
                raise SystemExit(0)
            return {}
        else:  # interactive
            _tag("system", "Press Enter to approve, or type 'reject' then Enter:")
            print()
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  [cancelled]")
                raise SystemExit(0)
            result = {"approved": choice != "reject"}

        outcome = "approved" if result.get("approved", True) else "rejected"
        _tag(
            "action:approve" if outcome == "approved" else "action:reject",
            f"{human_label}  {outcome}",
        )
        _pause(0.2)
        return {"outcome": outcome, "task_result": result}

    # ------------------------------------------------------------------
    # Final summary + audit log
    # ------------------------------------------------------------------

    def final_summary(
        self,
        spec: dict[str, Any],
        intent_id: str,
        compile_id: str,
    ) -> None:
        print()
        _divider()
        print()
        print("  Result:")
        print(f"    Scenario:     {spec.get('title', spec.get('scenario_id', '?'))}")
        print(f"    Intent ID:    {intent_id}")
        print(f"    Final status: {self._cur_status}")
        if compile_id:
            print(f"    Workflow:     compile_id={compile_id}")

        # Show which bindings were used
        agents = spec.get("agents") or []
        bindings = sorted({a.get("delivery_mode", "internal") for a in agents})
        if bindings:
            print(f"    Bindings:     {', '.join(bindings)}")
        print()
        print("  Verify via CLI:")
        print(f"    axme intents get {intent_id}")
        print(f"    axme intents watch {intent_id}")
        print(f"    axme agents list")
        print(f"    axme quota show")
        print()

    def audit_log(self, events_resp: dict[str, Any]) -> None:
        events = events_resp.get("events") or []
        _divider()
        print()
        print("  Intent event log (server audit trail):")
        print()
        if not events:
            print("  (no events returned)")
            print()
            return

        col_w = [5, 21, 32, 28, 26]
        header = (
            f"  {'#':<{col_w[0]}}"
            f"{'time (UTC)':<{col_w[1]}}"
            f"{'status':<{col_w[2]}}"
            f"{'actor':<{col_w[3]}}"
            f"{'pending_with':<{col_w[4]}}"
        )
        print(header)
        print("  " + "─" * (sum(col_w) + 2))
        for ev in events:
            seq    = str(ev.get("seq", ""))
            at     = str(ev.get("at", ""))[:19].replace("T", " ")
            status = str(ev.get("status", ""))
            actor  = str(ev.get("actor") or "").split("/")[-1][: col_w[3] - 2]
            pw     = ev.get("pending_with") or {}
            holder = (
                str(pw.get("name") or pw.get("ref") or "").split("/")[-1][: col_w[4] - 2]
                if pw else ""
            )
            reason = str(
                (ev.get("details") or {}).get("reason") or
                (ev.get("details") or {}).get("next_handler") or
                ev.get("event_type") or ""
            )
            status_col = f"{status} ({reason})" if reason else status
            print(
                f"  {seq:<{col_w[0]}}"
                f"{at:<{col_w[1]}}"
                f"{status_col:<{col_w[2]}}"
                f"{actor:<{col_w[3]}}"
                f"{holder:<{col_w[4]}}"
            )
        print()

    def error(self, msg: str) -> None:
        _tag("error", msg)

    def info(self, msg: str) -> None:
        _tag("system", msg)


def _find_human_handler(spec: dict[str, Any]) -> dict[str, Any] | None:
    for h in (spec.get("humans") or []):
        if "handler" in h:
            return h["handler"]
    return None
