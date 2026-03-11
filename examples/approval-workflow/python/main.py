"""
approval-workflow — Axme SDK example
=====================================
Demonstrates a 3-step approval flow (2 automated + 1 human) via the Axme
intent system. Two service-account agents are created on first run:
  • example-requester  — sends the approval request
  • example-approver   — receives and processes it through all review steps

Run:
    python main.py              # interactive scenario picker
    SCENARIO=1 python main.py   # skip the picker

Prerequisites:
    axme login                  # one-time; no env export needed afterwards
"""
from __future__ import annotations

import json
import os
import queue
import time
import threading
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

from axme import AxmeClient, AxmeClientConfig


# ---------------------------------------------------------------------------
# Scenarios  (only scenario 1 is fully wired; 2-4 kept for later)
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "1": {
        "title":   "nginx config rollout → prod-cluster-eu",
        "summary": "Update nginx config on prod-cluster-eu (change #CHG-4821)",
        "intent_type": "intent.approval.change_mgmt.v1",
        "auto_steps": [
            {
                "label":     "change-validator",
                "actor":     "process:change-validator",
                "reviewing": "verifying maintenance window and rollback plan",
                "approved":  "maintenance window confirmed, rollback plan verified",
            },
            {
                "label":     "impact-assessor",
                "actor":     "process:impact-assessor",
                "reviewing": "assessing blast radius and service dependencies",
                "approved":  "blast radius: low, zero downtime deployment confirmed",
            },
        ],
        "human_role":  "Change Advisory Board (CAB)",
        "human_label": "CAB",
    },
    "2": {
        "title":   "$47,500 cloud infrastructure budget — Q2 expansion",
        "summary": "Budget approval: $47,500 cloud infrastructure Q2 expansion (BUD-2024-Q2-EU)",
        "intent_type": "intent.approval.finance.v1",
        "auto_steps": [
            {
                "label":     "budget-validator",
                "actor":     "process:budget-validator",
                "reviewing": "validating budget envelope against Q2 allocation",
                "approved":  "within Q2 envelope, 12% headroom remaining",
            },
            {
                "label":     "cost-estimator",
                "actor":     "process:cost-estimator",
                "reviewing": "cross-checking vendor quotes and 12-month TCO",
                "approved":  "3 vendor quotes validated, TCO within 5% of estimate",
            },
        ],
        "human_role":  "CFO / Finance Committee",
        "human_label": "CFO",
    },
    "3": {
        "title":   "READ access to prod-db-eu-west-1 for svc:data-pipeline",
        "summary": "Access request: READ on prod-db-eu-west-1 for svc:data-pipeline (ITSM-ACCESS-8821)",
        "intent_type": "intent.approval.access_mgmt.v1",
        "auto_steps": [
            {
                "label":     "access-policy-checker",
                "actor":     "process:access-policy-checker",
                "reviewing": "verifying service identity and least-privilege policy",
                "approved":  "service identity verified, READ-only scope within policy",
            },
            {
                "label":     "risk-assessor",
                "actor":     "process:risk-assessor",
                "reviewing": "evaluating data sensitivity and audit trail coverage",
                "approved":  "PII fields excluded, audit logging active on target DB",
            },
        ],
        "human_role":  "Security Officer / DBA",
        "human_label": "Security Officer",
    },
    "4": {
        "title":   "AI agent action: send contract to Acme Corp ($120k)",
        "summary": "AI agent requests permission to send $120k contract to Acme Corp (CONTRACT-AC-2024-001)",
        "intent_type": "intent.approval.ai_oversight.v1",
        "auto_steps": [
            {
                "label":     "contract-validator",
                "actor":     "process:contract-validator",
                "reviewing": "validating contract terms, signatures and entity details",
                "approved":  "contract terms valid, entities match CRM records",
            },
            {
                "label":     "compliance-checker",
                "actor":     "process:compliance-checker",
                "reviewing": "running compliance checks (AML, sanctions, jurisdiction)",
                "approved":  "AML clear, no sanctions hits, jurisdiction confirmed",
            },
        ],
        "human_role":  "Account Executive / Legal",
        "human_label": "Account Executive",
    },
}


# ---------------------------------------------------------------------------
# CLI secrets
# ---------------------------------------------------------------------------

def _read_cli_secrets(context: str = "default") -> dict[str, str]:
    secrets_path = Path.home() / ".config" / "axme" / "secrets.json"
    try:
        data = json.loads(secrets_path.read_text())
        return dict(data.get(context) or data.get("default") or {})
    except Exception:
        return {}


def _require_api_key() -> str:
    value = os.getenv("AXME_API_KEY", "").strip()
    if not value:
        value = _read_cli_secrets().get("api_key", "").strip()
    if not value:
        print("\n  Not signed in. Run:  axme login\n")
        raise SystemExit(1)
    return value


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_STATUS_LABEL: dict[str, str] = {
    "DELIVERED":   "DELIVERED",
    "IN_PROGRESS": "IN_PROGRESS",
    "WAITING":     "WAITING",
    "COMPLETED":   "COMPLETED",
    "FAILED":      "FAILED",
    "CANCELED":    "CANCELED",
}

_WAITING_LABEL: dict[str, str] = {
    "WAITING_FOR_HUMAN": "waiting for human",
    "WAITING_FOR_AGENT": "waiting for agent",
}


def _fmt_status(raw: str, waiting_reason: str = "") -> str:
    s = _STATUS_LABEL.get(raw, raw)
    if s == "WAITING" and waiting_reason:
        s += f" ({_WAITING_LABEL.get(waiting_reason, waiting_reason)})"
    return s


def _log(tag: str, msg: str) -> None:
    print(f"  [{tag}]  {msg}", flush=True)


def _transition(prev: str, nxt: str) -> None:
    """Print a status transition arrow.  Only prints if the state actually changed."""
    if prev != nxt:
        print(f"  status    {prev}  →  {nxt}", flush=True)


def _divider() -> None:
    print("  " + "─" * 62, flush=True)


def _pause(s: float) -> None:
    time.sleep(s)


# ---------------------------------------------------------------------------
# Org / workspace resolution
# ---------------------------------------------------------------------------

def _resolve_org_workspace(
    base_url: str,
    api_key: str,
    actor_token: str | None,
) -> tuple[str | None, str | None]:
    org_id       = os.getenv("AXME_ORG_ID", "").strip() or None
    workspace_id = os.getenv("AXME_WORKSPACE_ID", "").strip() or None
    if org_id and workspace_id:
        return org_id, workspace_id
    if not actor_token:
        return org_id, workspace_id
    try:
        req = urllib.request.Request(
            f"{base_url}/v1/portal/personal/context",
            headers={"X-Api-Key": api_key, "Authorization": f"Bearer {actor_token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ctx = json.loads(resp.read()).get("context") or {}
        org_id       = org_id       or ctx.get("org_id", "").strip() or None
        workspace_id = workspace_id or ctx.get("workspace_id", "").strip() or None
    except Exception:
        pass
    return org_id, workspace_id


# ---------------------------------------------------------------------------
# Agent provisioning
# ---------------------------------------------------------------------------

def _find_agent(client: AxmeClient, org_id: str, workspace_id: str, name: str) -> str | None:
    """Return agent_address of a SA with the given name, or None."""
    try:
        resp = client.list_service_accounts(org_id=org_id, workspace_id=workspace_id)
        for sa in resp.get("service_accounts") or []:
            if sa.get("name") == name:
                return (sa.get("agent_address") or "").strip() or None
    except Exception:
        pass
    return None


def _create_agent(
    client: AxmeClient,
    org_id: str,
    workspace_id: str,
    name: str,
    description: str,
) -> str:
    """Create a service account and return its agent_address."""
    result = client.create_service_account(
        {"name": name, "org_id": org_id, "workspace_id": workspace_id,
         "description": description},
        idempotency_key=f"example-{name}-{org_id}",
    )
    # Response is either flat or nested under "service_account"
    sa = result.get("service_account") or result
    addr = (sa.get("agent_address") or "").strip()
    if not addr:
        raise RuntimeError(f"server did not return agent_address for '{name}'")
    return addr


def _provision_agents(
    client: AxmeClient,
    org_id: str,
    workspace_id: str,
) -> tuple[str, str]:
    """
    Ensure 'example-requester' and 'example-approver' agents exist.
    Prints one line per agent showing create/reuse and its address.
    Returns (requester_address, approver_address).
    """
    agents: dict[str, dict[str, str]] = {
        "example-requester": {
            "role":        "requester",
            "description": "Sends approval requests — created by approval-workflow example",
        },
        "example-approver": {
            "role":        "approver",
            "description": "Receives and processes approval intents — created by approval-workflow example",
        },
    }

    addresses: dict[str, str] = {}
    for sa_name, meta in agents.items():
        existing = _find_agent(client, org_id, workspace_id, sa_name)
        if existing:
            _log("agent", f"{meta['role']:12s}  (existing)  {existing}")
            addresses[sa_name] = existing
        else:
            _log("agent", f"{meta['role']:12s}  creating {sa_name} …")
            addr = _create_agent(client, org_id, workspace_id, sa_name, meta["description"])
            _log("agent", f"{meta['role']:12s}  created   {addr}")
            addresses[sa_name] = addr
        _pause(0.3)

    return addresses["example-requester"], addresses["example-approver"]


# ---------------------------------------------------------------------------
# Resume worker (background thread)
# ---------------------------------------------------------------------------

class _ResumeTask:
    def __init__(
        self,
        intent_id: str,
        actor: str,
        reason: str,
        owner_agent: str,
        *,
        delay: float = 0.0,
        gate: threading.Event | None = None,
    ) -> None:
        self.intent_id   = intent_id
        self.actor       = actor
        self.reason      = reason
        self.owner_agent = owner_agent
        self.delay       = delay
        self.gate        = gate
        self.done        = threading.Event()
        self.error: Exception | None = None


def _resume_worker(client: AxmeClient, q: "queue.Queue[_ResumeTask | None]") -> None:
    while True:
        task = q.get()
        if task is None:
            break
        try:
            if task.gate:
                task.gate.wait()
            elif task.delay:
                time.sleep(task.delay)
            client.resume_intent(
                task.intent_id,
                {"approve_current_step": True, "reason": task.reason, "actor": task.actor},
                owner_agent=task.owner_agent,
            )
        except Exception as exc:
            task.error = exc
        finally:
            task.done.set()
            q.task_done()


# ---------------------------------------------------------------------------
# Scenario picker
# ---------------------------------------------------------------------------

def _pick_scenario() -> dict[str, Any]:
    env = os.getenv("SCENARIO", "").strip()
    if env in SCENARIOS:
        return SCENARIOS[env]
    print()
    print("  Select a scenario:")
    print()
    for k, s in SCENARIOS.items():
        print(f"    {k}.  {s['title']}")
    print()
    while True:
        try:
            choice = input("  Enter number (1–4): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)
        if choice in SCENARIOS:
            return SCENARIOS[choice]
        print("  Please enter 1, 2, 3 or 4.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    base_url    = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    cli_secrets = _read_cli_secrets()
    api_key     = _require_api_key()
    actor_token = (os.getenv("AXME_ACTOR_TOKEN", "").strip()
                   or cli_secrets.get("actor_token", "").strip()
                   or None)

    scenario    = _pick_scenario()
    auto_steps  = scenario["auto_steps"]
    human_role  = scenario["human_role"]
    human_label = scenario["human_label"]
    n_steps     = len(auto_steps) + 1

    # SA-scoped config: owner_scope = SA agent address → allows resume_intent
    sa_cfg       = AxmeClientConfig(base_url=base_url, api_key=api_key)
    # Personal config: includes actor_token for portal/personal/context only
    personal_cfg = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)

    # ── Header ────────────────────────────────────────────────────────────
    print()
    _divider()
    print(f"  Scenario:  {scenario['title']}")
    print(f"  Request:   {scenario['summary']}")
    _divider()
    print()

    # ── Resolve org / workspace ───────────────────────────────────────────
    _log("setup", "resolving org and workspace …")
    org_id, workspace_id = _resolve_org_workspace(base_url, api_key, actor_token)
    if not org_id or not workspace_id:
        print("\n  Could not determine org_id / workspace_id.")
        print("  Set AXME_ORG_ID + AXME_WORKSPACE_ID, or run 'axme login'.\n")
        raise SystemExit(1)
    _log("setup", f"org={org_id}  workspace={workspace_id}")
    _pause(0.3)

    # ── Provision agents ──────────────────────────────────────────────────
    print()
    _log("agents", f"provisioning agents for this scenario ({n_steps} steps) …")
    with AxmeClient(personal_cfg) as probe:
        requester_addr, approver_addr = _provision_agents(probe, org_id, workspace_id)
    _log("agents", "ready")
    print()
    _pause(0.3)

    # ── Create intent ─────────────────────────────────────────────────────
    correlation_id  = str(uuid4())
    idempotency_key = f"approval-{correlation_id}"

    intent_payload: dict[str, Any] = {
        "intent_type":    scenario["intent_type"],
        "correlation_id": correlation_id,
        "to_agent":       approver_addr,
        "payload": {
            "request_id":    f"req-{correlation_id[:8]}",
            "summary":       scenario["summary"],
            "approval_mode": "manual",
        },
    }

    resume_q: queue.Queue[_ResumeTask | None] = queue.Queue()

    with AxmeClient(sa_cfg) as client:
        worker = threading.Thread(target=_resume_worker, args=(client, resume_q), daemon=True)
        worker.start()

        try:
            _log("intent", "sending approval request to server …")
            created     = client.create_intent(intent_payload,
                                               correlation_id=correlation_id,
                                               idempotency_key=idempotency_key)
            intent_id   = str(created["intent_id"])
            cur_status  = _fmt_status(
                str(created.get("lifecycle_status") or created.get("status") or "DELIVERED")
            )
            _log("intent", f"created  id={intent_id}")
            print(f"  status    {cur_status}  •  with: requester ({requester_addr.split('/')[-1]})")
            _pause(0.6)

            # ── Automated steps ───────────────────────────────────────────
            for i, step in enumerate(auto_steps, start=1):
                print()
                print(f"  ── step {i}/{n_steps}  ⚙  {step['label']} ──────────────────────────────")
                print(f"     task:    {step['reviewing']}")
                print(f"     with:    {approver_addr.split('/')[-1]}")

                prev_status = cur_status
                cur_status  = _fmt_status("WAITING", "WAITING_FOR_AGENT")
                _transition(prev_status, cur_status)
                _pause(0.4)

                task = _ResumeTask(
                    intent_id   = intent_id,
                    actor       = step["actor"],
                    reason      = f"{step['actor']} approved — {step['approved']}",
                    owner_agent = approver_addr,
                    delay       = 1.8,
                )
                resume_q.put(task)
                task.done.wait(timeout=20)

                if task.error:
                    print(f"\n  [error]  step {i} failed: {task.error}", flush=True)
                    raise RuntimeError(f"step {i} failed: {task.error}")

                updated    = client.get_intent(intent_id).get("intent", {})
                new_status = _fmt_status(
                    str(updated.get("lifecycle_status") or updated.get("status") or ""),
                    str(updated.get("lifecycle_waiting_reason") or ""),
                )
                _transition(cur_status, new_status)
                cur_status = new_status
                print(f"     result:  ✓  {step['approved']}")
                _pause(0.7)

            # ── Human step ────────────────────────────────────────────────
            print()
            print(f"  ── step {n_steps}/{n_steps}  👤  {human_role} ──────────────────────────────")
            print(f"     task:    manual sign-off required")
            print(f"     with:    you ({human_role})")

            prev_status = cur_status
            cur_status  = _fmt_status("WAITING", "WAITING_FOR_HUMAN")
            _transition(prev_status, cur_status)

            _divider()
            print()
            print(f"  You are acting as:  {human_role}")
            print(f"  Press Enter to approve, or Ctrl+C to cancel.")
            print()

            human_gate = threading.Event()
            human_task = _ResumeTask(
                intent_id   = intent_id,
                actor       = f"human:{human_label}",
                reason      = f"approved by {human_role}",
                owner_agent = approver_addr,
                gate        = human_gate,
            )
            resume_q.put(human_task)

            try:
                input("  > ")
            except (EOFError, KeyboardInterrupt):
                print("\n  [cancelled]  approval cancelled by user.")
                resume_q.put(None)
                raise SystemExit(0)

            print()
            _log("decision", f"{human_role} approved — resuming …")
            human_gate.set()

            human_task.done.wait(timeout=15)
            if human_task.error:
                print(f"\n  [error]  human step failed: {human_task.error}", flush=True)
                raise RuntimeError(f"human step failed: {human_task.error}")

            prev_status = cur_status
            cur_status  = _fmt_status("IN_PROGRESS")
            _transition(prev_status, cur_status)
            _pause(0.5)

            # ── Resolve ───────────────────────────────────────────────────
            _log("resolve", "closing intent as COMPLETED …")
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
            _pause(0.4)

            # ── Wait for terminal event ───────────────────────────────────
            final_status = "COMPLETED"
            try:
                for event in client.observe(intent_id, since=0, timeout_seconds=10):
                    ev = str(event.get("status") or "")
                    if ev in {"COMPLETED", "FAILED", "CANCELED"}:
                        final_status = ev
                        break
            except Exception:
                pass

            prev_status = cur_status
            cur_status  = _fmt_status(final_status)
            _transition(prev_status, cur_status)

            # ── Summary ───────────────────────────────────────────────────
            print()
            _divider()
            print()
            print(f"  Result:")
            print(f"    Scenario:    {scenario['title']}")
            print(f"    Intent ID:   {intent_id}")
            print(f"    Final status: {cur_status}")
            print(f"    Approved by:  {human_role}")
            print()
            print(f"  Verify via CLI:")
            print(f"    axme intents get {intent_id}")
            print(f"    axme intents watch {intent_id}")
            print(f"    axme agents list")
            print(f"    axme quota show")
            print()

        finally:
            resume_q.put(None)
            worker.join(timeout=5)


if __name__ == "__main__":
    main()
