from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

from axme import AxmeClient, AxmeClientConfig

# ---------------------------------------------------------------------------
# Approval scenarios
# ---------------------------------------------------------------------------
# Each scenario uses the same two-thread flow:
#   - main thread:     creates intent, drives auto steps, handles human input
#   - approver thread: calls resume_intent on behalf of each reviewer
#
# Ball tracking legend printed during run:
#   ⚙  [process-agent]  — automated reviewer holds the ball
#   👤 [human]          — human reviewer holds the ball
#   🟢 [done]           — intent completed
# ---------------------------------------------------------------------------
SCENARIOS: dict[str, dict[str, Any]] = {
    "1": {
        "title":   "nginx config rollout → prod-cluster-eu",
        "summary": "Update nginx config on prod-cluster-eu (change #CHG-4821)",
        "intent_type": "intent.approval.change_mgmt.v1",
        "auto_steps": [
            {
                "actor":    "process:change-validator",
                "label":    "change-validator",
                "reviewing": "verifying maintenance window and rollback plan...",
                "approved":  "maintenance window confirmed, rollback plan verified",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
            {
                "actor":    "process:impact-assessor",
                "label":    "impact-assessor",
                "reviewing": "assessing blast radius and service dependencies...",
                "approved":  "blast radius: low, zero downtime deployment confirmed",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
        ],
        "human_role":         "Change Advisory Board (CAB)",
        "human_label":        "CAB",
        "human_waiting_reason": "WAITING_FOR_HUMAN",
    },
    "2": {
        "title":   "$47,500 cloud infrastructure budget — Q2 expansion",
        "summary": "Budget approval request: $47,500 cloud infrastructure Q2 expansion (BUD-2024-Q2-EU)",
        "intent_type": "intent.approval.finance.v1",
        "auto_steps": [
            {
                "actor":    "process:budget-validator",
                "label":    "budget-validator",
                "reviewing": "validating budget envelope against Q2 allocation...",
                "approved":  "within Q2 envelope, 12% headroom remaining",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
            {
                "actor":    "process:cost-estimator",
                "label":    "cost-estimator",
                "reviewing": "cross-checking vendor quotes and 12-month TCO...",
                "approved":  "3 vendor quotes validated, TCO within 5% of estimate",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
        ],
        "human_role":         "CFO / Finance Committee",
        "human_label":        "CFO",
        "human_waiting_reason": "WAITING_FOR_HUMAN",
    },
    "3": {
        "title":   "READ access to prod-db-eu-west-1 for svc:data-pipeline",
        "summary": "Access request: READ on prod-db-eu-west-1 for svc:data-pipeline (ITSM-ACCESS-8821)",
        "intent_type": "intent.approval.access_mgmt.v1",
        "auto_steps": [
            {
                "actor":    "process:access-policy-checker",
                "label":    "access-policy-checker",
                "reviewing": "verifying service identity and least-privilege policy...",
                "approved":  "service identity verified, READ-only scope within policy",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
            {
                "actor":    "process:risk-assessor",
                "label":    "risk-assessor",
                "reviewing": "evaluating data sensitivity and audit trail coverage...",
                "approved":  "PII fields excluded, audit logging active on target DB",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
        ],
        "human_role":         "Security Officer / DBA",
        "human_label":        "Security Officer",
        "human_waiting_reason": "WAITING_FOR_HUMAN",
    },
    "4": {
        "title":   "AI agent action: send contract to client (Acme Corp, $120k)",
        "summary": "AI agent requests permission to send $120k contract to Acme Corp (CONTRACT-AC-2024-001)",
        "intent_type": "intent.approval.ai_oversight.v1",
        "auto_steps": [
            {
                "actor":    "process:contract-validator",
                "label":    "contract-validator",
                "reviewing": "validating contract terms, signatures and entity details...",
                "approved":  "contract terms valid, entities match CRM records",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
            {
                "actor":    "process:compliance-checker",
                "label":    "compliance-checker",
                "reviewing": "running compliance checks (AML, sanctions, jurisdiction)...",
                "approved":  "AML clear, no sanctions hits, jurisdiction confirmed",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
        ],
        "human_role":         "Account Executive / Legal",
        "human_label":        "Account Executive",
        "human_waiting_reason": "WAITING_FOR_HUMAN",
    },
}


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
        raise RuntimeError(
            f"{name} is not set. Run 'axme login' to sign in, then:\n"
            f"  export {name}=$(axme context show --show-key --json | jq -r .api_key)"
        )
    return value


def _pick_scenario() -> dict[str, Any]:
    scenario_env = os.getenv("SCENARIO", "").strip()
    if scenario_env in SCENARIOS:
        return SCENARIOS[scenario_env]

    print()
    print("  Select a scenario:")
    print()
    for key, s in SCENARIOS.items():
        print(f"    {key}.  {s['title']}")
    print()

    while True:
        try:
            choice = input("  Enter number (1–4): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)
        if choice in SCENARIOS:
            return SCENARIOS[choice]
        print("  Please enter 1, 2, 3, or 4.")


# ---------------------------------------------------------------------------
# Approver worker thread
# ---------------------------------------------------------------------------

class _ApprovalRequest:
    def __init__(
        self,
        intent_id: str,
        *,
        step_label: str,
        actor: str,
        reason: str,
        review_delay: float = 2.0,
        human_input_event: threading.Event | None = None,
    ) -> None:
        self.intent_id         = intent_id
        self.step_label        = step_label
        self.actor             = actor
        self.reason            = reason
        self.review_delay      = review_delay
        self.human_input_event = human_input_event
        self.done_event        = threading.Event()
        self.error: Exception | None = None


def _approver_worker(
    client: AxmeClient,
    work_queue: "queue.Queue[_ApprovalRequest | None]",
) -> None:
    while True:
        item = work_queue.get()
        if item is None:
            break
        try:
            if item.human_input_event is not None:
                item.human_input_event.wait()
            else:
                time.sleep(item.review_delay)
            client.resume_intent(
                item.intent_id,
                {
                    "approve_current_step": True,
                    "reason":               item.reason,
                    "actor":                item.actor,
                },
            )
        except Exception as exc:  # noqa: BLE001
            item.error = exc
        finally:
            item.done_event.set()
            work_queue.task_done()


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_WAITING_REASON_LABEL: dict[str, str] = {
    "WAITING_FOR_HUMAN": "waiting for human",
    "WAITING_FOR_AGENT": "waiting for agent",
    "WAITING_FOR_TOOL":  "waiting for tool",
    "WAITING_FOR_TIME":  "waiting for time",
}


def _format_status(status: str, waiting_reason: str = "") -> str:
    if status == "WAITING" and waiting_reason:
        label = _WAITING_REASON_LABEL.get(waiting_reason, waiting_reason.lower())
        return f"WAITING  ({label})"
    return status


def _print_ball(holder: str, note: str = "") -> None:
    """Print a single 'ball at' line showing who has execution control."""
    suffix = f"  — {note}" if note else ""
    print(f"  🎾 ball at  {holder}{suffix}")


def _print_status_line(prev: str | None, status: str, waiting_reason: str = "") -> str:
    current = _format_status(status, waiting_reason)
    if prev is None:
        print(f"  status     {current}")
    elif prev.split()[0] != current.split()[0]:
        print(f"  status     {prev} → {current}")
    return current


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url    = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    api_key     = _require_env("AXME_API_KEY")
    actor_token = os.getenv("AXME_ACTOR_TOKEN", "").strip() or None
    to_agent    = os.getenv("AXME_TO_AGENT", "").strip() or None

    scenario    = _pick_scenario()
    auto_steps: list[dict[str, Any]] = scenario["auto_steps"]
    human_role: str  = scenario["human_role"]
    human_label: str = scenario["human_label"]
    n_steps = len(auto_steps) + 1

    config = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)

    print()
    print(f"[scenario]  {scenario['title']}")
    print(f"[summary]   {scenario['summary']}")
    print()

    # ── Resolve agent addresses from registry ─────────────────────────────
    # The from_agent is derived automatically by the server from the API key.
    # to_agent should be set via AXME_TO_AGENT env var (agent://org/ws/name).
    # If not set, we print guidance and pick the first registered agent.
    with AxmeClient(config) as probe:
        org_id       = os.getenv("AXME_ORG_ID", "").strip() or None
        workspace_id = os.getenv("AXME_WORKSPACE_ID", "").strip() or None

        if to_agent is None and org_id and workspace_id:
            try:
                agents_resp = probe.list_agents(org_id=org_id, workspace_id=workspace_id)
                agents      = agents_resp.get("agents") or []
                if agents and isinstance(agents, list):
                    first = agents[0]
                    if isinstance(first, dict):
                        to_agent = str(first.get("address", ""))
            except Exception:  # noqa: BLE001
                pass

        if to_agent is None:
            print(
                "[hint]  AXME_TO_AGENT not set. Set it to the agent address that should receive\n"
                "        this intent, e.g.:\n"
                "          export AXME_TO_AGENT=agent://acme-corp/production/approver\n"
                "        or set AXME_ORG_ID + AXME_WORKSPACE_ID to auto-pick from registry.\n"
                "        Proceeding without to_agent (server may reject or route internally).\n"
            )

    print(f"[agent]     to_agent={to_agent or '(not set, derived by server)'}")
    print(f"[agent]     from_agent=(derived from API key)")
    print(f"[steps]     {n_steps} approval steps: {len(auto_steps)} automated + 1 human ({human_label})")
    print()

    correlation_id  = str(uuid4())
    idempotency_key = f"approval-{correlation_id}"

    intent_payload: dict[str, Any] = {
        "intent_type":    scenario["intent_type"],
        "correlation_id": correlation_id,
        "payload": {
            "request_id":    f"req-{correlation_id[:8]}",
            "summary":       scenario["summary"],
            "approval_mode": "manual",
        },
    }
    if to_agent:
        intent_payload["to_agent"] = to_agent

    work_queue: queue.Queue[_ApprovalRequest | None] = queue.Queue()

    with AxmeClient(config) as client:

        approver_thread = threading.Thread(
            target=_approver_worker,
            args=(client, work_queue),
            daemon=True,
        )
        approver_thread.start()

        try:
            # ── Create intent ──────────────────────────────────────────────
            created   = client.create_intent(
                intent_payload,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )
            intent_id = str(created["intent_id"])
            init_status = str(created.get("status", ""))
            print(f"[create]    intent_id={intent_id}")
            last_status = _print_status_line(None, init_status)
            _print_ball("requester (this process)")
            next_since = 0

            # ── Automated approval steps ───────────────────────────────────
            for i, step in enumerate(auto_steps, start=1):
                print()
                print(f"[step {i}/{n_steps}]  ⚙  {step['label']} — {step['reviewing']}")
                _print_ball(f"process-agent:{step['label']}")

                req = _ApprovalRequest(
                    intent_id=intent_id,
                    step_label=f"step {i}/{n_steps}",
                    actor=step["actor"],
                    reason=f"{step['actor']} approved — {step['approved']}",
                    review_delay=2.0,
                )
                work_queue.put(req)

                req.done_event.wait(timeout=15)
                if req.error:
                    print(f"  [warn]    approver step {i} error: {req.error}")

                updated = client.get_intent(intent_id).get("intent", {})
                cur = str(updated.get("lifecycle_status") or updated.get("status") or last_status)
                last_status = _print_status_line(last_status, cur)

                listed = client.list_intent_events(intent_id)
                for ev in (listed.get("events") or []):
                    seq = ev.get("seq")
                    if isinstance(seq, int):
                        next_since = max(next_since, seq)

                print(f"  [approved] {step['label']}  ✓  {step['approved']}")
                _print_ball("requester (this process)", "moving to next step")
                time.sleep(0.5)

            # ── Human approval step ────────────────────────────────────────
            human_step = len(auto_steps) + 1
            print()
            print(f"[step {human_step}/{n_steps}]  👤  {human_role} — waiting for sign-off")
            _print_ball(f"human:{human_label}")
            print()
            print(f"           Intent is paused. You are acting as {human_role}.")
            print(f"           Press Enter to approve, or Ctrl+C to cancel.")
            print()

            human_event = threading.Event()

            human_req = _ApprovalRequest(
                intent_id=intent_id,
                step_label=f"step {human_step}/{n_steps}",
                actor=f"human:{human_label}",
                reason=f"approved by {human_role}",
                human_input_event=human_event,
            )
            work_queue.put(human_req)

            try:
                input("           > ")
            except (EOFError, KeyboardInterrupt):
                print("\n[cancelled]  approval cancelled")
                work_queue.put(None)
                return

            print()
            print(f"[approved]  {human_role} confirmed — resuming intent")
            _print_ball("requester (this process)", "human approved, calling resume")
            human_event.set()

            human_req.done_event.wait(timeout=10)
            if human_req.error:
                print(f"  [warn]    human approval error: {human_req.error}")

            # ── Resolve ────────────────────────────────────────────────────
            client.resolve_intent(
                intent_id,
                {
                    "status": "COMPLETED",
                    "result": {
                        "approval_result": "approved",
                        "approved_by":     human_role,
                        "summary":         scenario["summary"],
                    },
                },
            )
            _print_ball("server", "resolve_intent called → terminal event incoming")

            # ── Observe terminal event ─────────────────────────────────────
            try:
                for event in client.observe(intent_id, since=next_since, timeout_seconds=15):
                    seq = event.get("seq")
                    if isinstance(seq, int):
                        next_since = max(next_since, seq)
                    ev_status      = str(event.get("status", ""))
                    waiting_reason = str(event.get("waiting_reason") or "")
                    last_status    = _print_status_line(last_status, ev_status, waiting_reason)
                    if ev_status in {"COMPLETED", "FAILED", "CANCELED"}:
                        _print_ball("🟢 done", f"intent reached terminal state {ev_status}")
                        break
            except TimeoutError:
                pass

        finally:
            work_queue.put(None)
            approver_thread.join(timeout=5)

        # ── Final summary ──────────────────────────────────────────────────
        print()
        print(f"[done]    intent_id={intent_id}  status={last_status.split()[0]}")
        print()
        print("  Explore via CLI:")
        print(f"    axme intents get {intent_id}")
        print(f"    axme intents watch {intent_id}   # replay lifecycle events")
        print( "    axme quota show")


if __name__ == "__main__":
    main()
