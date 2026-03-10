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
# Only scenario 1 is active.  Scenarios 2–4 share the same structure and will
# be wired up once scenario 1 is confirmed working.
# ---------------------------------------------------------------------------
SCENARIOS: dict[str, dict[str, Any]] = {
    "1": {
        "title":     "nginx config rollout → prod-cluster-eu",
        "summary":   "Update nginx config on prod-cluster-eu (change #CHG-4821)",
        "auto_steps": [
            {
                "actor":      "process:change-validator",
                "reviewing":  "reviewing the change request...",
                "approved":   "maintenance window confirmed, rollback plan verified",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
            {
                "actor":      "process:impact-assessor",
                "reviewing":  "assessing blast radius...",
                "approved":   "blast radius: low, zero downtime deployment",
                "waiting_reason": "WAITING_FOR_AGENT",
            },
        ],
        "human_role":         "Change Advisory Board (CAB)",
        "human_waiting_reason": "WAITING_FOR_HUMAN",
    },
}


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
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
            choice = input("  Enter number (1): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)
        if choice in SCENARIOS:
            return SCENARIOS[choice]
        print("  Please enter 1.")


# ---------------------------------------------------------------------------
# Approver worker thread
# ---------------------------------------------------------------------------
# Runs independently from the requester thread.  Receives work items via a
# queue, executes real API calls (resume_intent), and signals completion back.
# ---------------------------------------------------------------------------

class _ApprovalRequest:
    """One unit of work for the approver thread."""

    def __init__(
        self,
        intent_id: str,
        *,
        step_label: str,
        actor: str,
        reason: str,
        owner_agent: str,
        review_delay: float = 2.0,
        human_input_event: threading.Event | None = None,
    ) -> None:
        self.intent_id         = intent_id
        self.step_label        = step_label
        self.actor             = actor
        self.reason            = reason
        self.owner_agent       = owner_agent
        self.review_delay      = review_delay
        self.human_input_event = human_input_event  # set only for the human step
        self.done_event        = threading.Event()
        self.error: Exception | None = None


def _approver_worker(
    client: AxmeClient,
    work_queue: "queue.Queue[_ApprovalRequest | None]",
) -> None:
    """Background thread: processes approval requests sequentially."""
    while True:
        item = work_queue.get()
        if item is None:
            break
        try:
            if item.human_input_event is not None:
                # Wait until the human has pressed Enter before resuming.
                item.human_input_event.wait()
            else:
                # Simulate the automated reviewer taking time to review.
                time.sleep(item.review_delay)
            client.resume_intent(
                item.intent_id,
                {
                    "approve_current_step": True,
                    "reason":               item.reason,
                    "actor":                item.actor,
                },
                owner_agent=item.owner_agent,
            )
        except Exception as exc:  # noqa: BLE001
            item.error = exc
        finally:
            item.done_event.set()
            work_queue.task_done()


# ---------------------------------------------------------------------------
# Status / event display helpers
# ---------------------------------------------------------------------------

_WAITING_REASON_LABEL: dict[str, str] = {
    "WAITING_FOR_HUMAN": "waiting for human",
    "WAITING_FOR_AGENT": "waiting for agent",
    "WAITING_FOR_TOOL":  "waiting for tool",
    "WAITING_FOR_TIME":  "waiting for time",
}


def _format_status(event: dict[str, Any]) -> str:
    status         = str(event.get("status", ""))
    waiting_reason = event.get("waiting_reason") or ""
    if status == "WAITING" and waiting_reason:
        label = _WAITING_REASON_LABEL.get(waiting_reason, waiting_reason.lower())
        return f"WAITING  ({label})"
    return status


def _print_transition(prev: str | None, event: dict[str, Any]) -> None:
    current = _format_status(event)
    if prev and prev.split()[0] != current.split()[0]:
        print(f"  status  {prev} → {current}")
    else:
        print(f"  status  {current}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url    = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    api_key     = _require_env("AXME_API_KEY")
    actor_token = os.getenv("AXME_ACTOR_TOKEN", "").strip() or None
    from_agent  = os.getenv("AXME_FROM_AGENT",  "agent://examples/requester").strip()
    to_agent    = os.getenv("AXME_TO_AGENT",    "agent://examples/approver").strip()
    owner_agent = os.getenv("AXME_APPROVAL_OWNER_AGENT", from_agent).strip()

    scenario = _pick_scenario()
    auto_steps: list[dict[str, Any]] = scenario["auto_steps"]
    human_role: str = scenario["human_role"]
    n_steps = len(auto_steps) + 1
    print()

    config = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)

    correlation_id  = str(uuid4())
    idempotency_key = f"approval-{correlation_id}"

    intent_payload = {
        "intent_type":    "intent.approval.demo.v1",
        "correlation_id": correlation_id,
        "from_agent":     from_agent,
        "to_agent":       to_agent,
        "payload": {
            "request_id":    f"req-{correlation_id[:8]}",
            "summary":       scenario["summary"],
            "requested_by":  from_agent,
            "approval_mode": "manual",
        },
    }

    work_queue: queue.Queue[_ApprovalRequest | None] = queue.Queue()

    with AxmeClient(config) as client:

        # Start the background approver thread.
        approver_thread = threading.Thread(
            target=_approver_worker,
            args=(client, work_queue),
            daemon=True,
        )
        approver_thread.start()

        try:
            # ── Create intent ────────────────────────────────────────────
            created   = client.create_intent(
                intent_payload,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )
            intent_id = str(created["intent_id"])
            print(f"[intent]  {scenario['summary']}")
            print(f"[create]  intent_id={intent_id}")
            print(f"  status  {created.get('status', '')}")
            last_status_label = str(created.get("status", ""))
            # Track the highest seen event seq so each observe() call starts
            # exactly where the previous one left off — no duplicate events.
            next_since = 0

            # ── Automated approval steps ─────────────────────────────────
            for i, step in enumerate(auto_steps, start=1):
                print()
                print(f"[step {i}/{n_steps}]  {step['actor']} — {step['reviewing']}")

                req = _ApprovalRequest(
                    intent_id=intent_id,
                    step_label=f"step {i}/{n_steps}",
                    actor=step["actor"],
                    reason=f"{step['actor']} approved — {step['approved']}",
                    owner_agent=owner_agent,
                    review_delay=2.0,
                )
                work_queue.put(req)

                # Wait for the approver thread to finish calling resume_intent.
                req.done_event.wait(timeout=15)
                if req.error:
                    print(f"[warn]  approver step {i} error: {req.error}")

                # Fetch updated status and advance next_since.
                updated = client.get_intent(intent_id).get("intent", {})
                cur_status = str(updated.get("lifecycle_status") or updated.get("status") or last_status_label)
                if cur_status != last_status_label.split()[0]:
                    print(f"  status  {last_status_label} → {cur_status}")
                    last_status_label = cur_status
                # Advance next_since past all currently known events.
                listed = client.list_intent_events(intent_id)
                events = listed.get("events") or []
                for ev in events:
                    seq = ev.get("seq")
                    if isinstance(seq, int):
                        next_since = max(next_since, seq)

                print(f"[step {i}/{n_steps}]  {step['actor']} approved — {step['approved']} ✓")

                time.sleep(0.5)

            # ── Human approval step ──────────────────────────────────────
            human_step = len(auto_steps) + 1
            print()
            print(f"[step {human_step}/{n_steps}]  waiting for {human_role} sign-off")
            print()
            print(f"           Intent is paused. Press Enter to approve as {human_role}...")
            print()

            human_event = threading.Event()

            # Queue the human-gated approval — it will wait for human_event.
            human_req = _ApprovalRequest(
                intent_id=intent_id,
                step_label=f"step {human_step}/{n_steps}",
                actor=f"human:{human_role}",
                reason=f"approved by {human_role}",
                owner_agent=owner_agent,
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
            print(f"[approved] {human_role} confirmed — resuming intent")
            human_event.set()  # unblock approver thread

            # Observe until IN_PROGRESS (resume) then COMPLETED.
            human_req.done_event.wait(timeout=10)
            if human_req.error:
                print(f"[warn]  human approval error: {human_req.error}")

            # ── Resolve ──────────────────────────────────────────────────
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

            # Observe the final terminal event.
            try:
                for event in client.observe(intent_id, since=next_since, timeout_seconds=15):
                    seq = event.get("seq")
                    if isinstance(seq, int):
                        next_since = max(next_since, seq)
                    ev_status = str(event.get("status", ""))
                    _print_transition(last_status_label, event)
                    last_status_label = _format_status(event)
                    if ev_status in {"COMPLETED", "FAILED", "CANCELED"}:
                        break
            except TimeoutError:
                pass

        finally:
            work_queue.put(None)
            approver_thread.join(timeout=5)

        # ── Final summary ─────────────────────────────────────────────
        print()
        print(f"[done]    intent_id={intent_id}  lifecycle_status={last_status_label}")
        print()
        print("  Explore this intent via CLI:")
        print(f"    axme intents get {intent_id}")
        print(f"    axme intents watch {intent_id}   # replay lifecycle events")
        print(f"    axme quota show")


if __name__ == "__main__":
    main()
