"""
approval-workflow — Axme SDK example
=====================================
Demonstrates a 3-step approval flow (2 automated + 1 human) via the Axme
intent system. Three service-account agents are provisioned on first run:
  • nginx-rollout-requester        — sends the change request
  • change-management-validator    — automated step 1: validates change window & rollback plan
  • deployment-impact-assessor     — automated step 2: assesses blast radius & dependencies
  Human final sign-off is provided interactively (Change Advisory Board).

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
        "title":       "nginx config rollout → prod-cluster-eu",
        "summary":     "Update nginx config on prod-cluster-eu (change #CHG-4821)",
        "intent_type": "intent.approval.change_mgmt.v1",
        "requester": {
            "name":        "nginx-rollout-requester",
            "description": "Sends nginx rollout change requests — approval-workflow example",
            "label":       "requester",
        },
        "auto_steps": [
            {
                "label":       "change-management-validator",
                "agent_name":  "change-management-validator",
                "description": "Validates change window and rollback plan — approval-workflow example",
                "reviewing":   "verifying maintenance window and rollback plan",
                "approved":    "maintenance window confirmed, rollback plan verified",
            },
            {
                "label":       "deployment-impact-assessor",
                "agent_name":  "deployment-impact-assessor",
                "description": "Assesses blast radius and service dependencies — approval-workflow example",
                "reviewing":   "assessing blast radius and service dependencies",
                "approved":    "blast radius: low, zero downtime deployment confirmed",
            },
        ],
        "human_role":  "Change Advisory Board (CAB)",
        "human_label": "CAB",
    },
    "2": {
        "title":       "$47,500 cloud infrastructure budget — Q2 expansion",
        "summary":     "Budget approval: $47,500 cloud infrastructure Q2 expansion (BUD-2024-Q2-EU)",
        "intent_type": "intent.approval.finance.v1",
        "requester": {
            "name":        "budget-request-agent",
            "description": "Sends budget approval requests — approval-workflow example",
            "label":       "requester",
        },
        "auto_steps": [
            {
                "label":       "budget-envelope-validator",
                "agent_name":  "budget-envelope-validator",
                "description": "Validates budget envelope against Q2 allocation — approval-workflow example",
                "reviewing":   "validating budget envelope against Q2 allocation",
                "approved":    "within Q2 envelope, 12% headroom remaining",
            },
            {
                "label":       "vendor-cost-estimator",
                "agent_name":  "vendor-cost-estimator",
                "description": "Cross-checks vendor quotes and 12-month TCO — approval-workflow example",
                "reviewing":   "cross-checking vendor quotes and 12-month TCO",
                "approved":    "3 vendor quotes validated, TCO within 5% of estimate",
            },
        ],
        "human_role":  "CFO / Finance Committee",
        "human_label": "CFO",
    },
    "3": {
        "title":       "READ access to prod-db-eu-west-1 for svc:data-pipeline",
        "summary":     "Access request: READ on prod-db-eu-west-1 for svc:data-pipeline (ITSM-ACCESS-8821)",
        "intent_type": "intent.approval.access_mgmt.v1",
        "requester": {
            "name":        "access-request-agent",
            "description": "Sends access approval requests — approval-workflow example",
            "label":       "requester",
        },
        "auto_steps": [
            {
                "label":       "access-policy-checker",
                "agent_name":  "access-policy-checker",
                "description": "Verifies service identity and least-privilege policy — approval-workflow example",
                "reviewing":   "verifying service identity and least-privilege policy",
                "approved":    "service identity verified, READ-only scope within policy",
            },
            {
                "label":       "data-risk-assessor",
                "agent_name":  "data-risk-assessor",
                "description": "Evaluates data sensitivity and audit trail coverage — approval-workflow example",
                "reviewing":   "evaluating data sensitivity and audit trail coverage",
                "approved":    "PII fields excluded, audit logging active on target DB",
            },
        ],
        "human_role":  "Security Officer / DBA",
        "human_label": "Security Officer",
    },
    "4": {
        "title":       "AI agent action: send contract to Acme Corp ($120k)",
        "summary":     "AI agent requests permission to send $120k contract to Acme Corp (CONTRACT-AC-2024-001)",
        "intent_type": "intent.approval.ai_oversight.v1",
        "requester": {
            "name":        "ai-action-requester",
            "description": "AI agent requesting contract send approval — approval-workflow example",
            "label":       "requester",
        },
        "auto_steps": [
            {
                "label":       "contract-terms-validator",
                "agent_name":  "contract-terms-validator",
                "description": "Validates contract terms, signatures and entity details — approval-workflow example",
                "reviewing":   "validating contract terms, signatures and entity details",
                "approved":    "contract terms valid, entities match CRM records",
            },
            {
                "label":       "compliance-aml-checker",
                "agent_name":  "compliance-aml-checker",
                "description": "Runs compliance checks (AML, sanctions, jurisdiction) — approval-workflow example",
                "reviewing":   "running compliance checks (AML, sanctions, jurisdiction)",
                "approved":    "AML clear, no sanctions hits, jurisdiction confirmed",
            },
        ],
        "human_role":  "Account Executive / Legal",
        "human_label": "Account Executive",
    },
}


# ---------------------------------------------------------------------------
# CLI secrets
# ---------------------------------------------------------------------------

_SECRETS_PATH = Path.home() / ".config" / "axme" / "secrets.json"


def _read_cli_secrets(context: str = "default") -> dict[str, str]:
    try:
        data = json.loads(_SECRETS_PATH.read_text())
        return dict(data.get(context) or data.get("default") or {})
    except Exception:
        return {}


def _save_cli_secrets(secrets: dict[str, str], context: str = "default") -> None:
    """Persist updated secrets (e.g. refreshed actor_token) back to disk."""
    try:
        try:
            data: dict = json.loads(_SECRETS_PATH.read_text())
        except Exception:
            data = {}
        existing = dict(data.get(context) or data.get("default") or {})
        existing.update({k: v for k, v in secrets.items() if v})
        data[context] = existing
        _SECRETS_PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _refresh_actor_token(base_url: str, api_key: str, refresh_token: str) -> str | None:
    """Exchange a refresh_token for a new actor_token via /v1/auth/refresh.
    Always re-reads refresh_token from disk just before use to avoid stale cached values.
    """
    try:
        # Re-read from disk in case another process already rotated the token
        fresh_secrets = _read_cli_secrets()
        current_refresh = fresh_secrets.get("refresh_token", "").strip() or refresh_token
        payload = json.dumps({"refresh_token": current_refresh}).encode()
        req = urllib.request.Request(
            f"{base_url}/v1/auth/refresh",
            data=payload,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
        new_token   = body.get("access_token", "").strip() or None
        new_refresh = body.get("refresh_token", "").strip() or None
        if new_token:
            _save_cli_secrets({
                "actor_token":   new_token,
                "refresh_token": new_refresh or current_refresh,
            })
        return new_token
    except Exception:
        return None


def _is_jwt_expired(token: str) -> bool:
    """Return True if a JWT is expired or will expire within 30 seconds."""
    try:
        import base64 as _b64
        part = token.split(".")[1]
        part += "=" * (4 - len(part) % 4)
        claims = json.loads(_b64.urlsafe_b64decode(part))
        return int(claims.get("exp", 0)) - int(time.time()) < 30
    except Exception:
        return True


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

_WAITING_LABEL: dict[str, str] = {
    "WAITING_FOR_HUMAN": "waiting for human",
    "WAITING_FOR_AGENT": "waiting for agent",
}


def _fmt_status(raw: str, waiting_reason: str = "") -> str:
    s = raw.upper() if raw else raw
    if s == "WAITING" and waiting_reason:
        s += f" ({_WAITING_LABEL.get(waiting_reason, waiting_reason)})"
    return s


def _fmt_pending_with(pw: dict[str, Any] | None) -> str:
    """Format pending_with from API response into a short readable label."""
    if not pw:
        return "—"
    ref = pw.get("ref") or pw.get("name") or ""
    if ref.startswith("agent://"):
        parts = ref.split("/")
        return parts[-1] if parts[-1] else ref
    return ref


def _tag(tag: str, msg: str) -> None:
    """Print a structured log line: [tag]  message"""
    print(f"  [{tag}]  {msg}", flush=True)


def _divider() -> None:
    print("  " + "─" * 64, flush=True)


def _pause(s: float) -> None:
    time.sleep(s)


# ---------------------------------------------------------------------------
# Org / workspace resolution
# ---------------------------------------------------------------------------

def _resolve_org_workspace(
    base_url: str,
    api_key: str,
    actor_token: str | None,
    refresh_token: str | None = None,
) -> tuple[str | None, str | None]:
    org_id       = os.getenv("AXME_ORG_ID", "").strip() or None
    workspace_id = os.getenv("AXME_WORKSPACE_ID", "").strip() or None
    if org_id and workspace_id:
        return org_id, workspace_id
    if not actor_token:
        return org_id, workspace_id

    # Auto-refresh if the actor_token is expired or about to expire
    if _is_jwt_expired(actor_token):
        if not refresh_token:
            print("\n  Session expired and no refresh token found. Run:  axme login\n")
            raise SystemExit(1)
        refreshed = _refresh_actor_token(base_url, api_key, refresh_token)
        if refreshed:
            actor_token = refreshed
        else:
            # Refresh token was already consumed (reuse detection) — need fresh login
            print("\n  Session expired. Run:  axme login\n")
            raise SystemExit(1)

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
    sa = result.get("service_account") or result
    addr = (sa.get("agent_address") or "").strip()
    if not addr:
        raise RuntimeError(f"server did not return agent_address for '{name}'")
    return addr


def _provision_agents(
    client: AxmeClient,
    org_id: str,
    workspace_id: str,
    scenario: dict[str, Any],
    human_role: str,
) -> dict[str, str]:
    """
    Provision all SA agents for this scenario.
    Returns dict: agent_name → agent_address.
    """
    n_auto = len(scenario["auto_steps"])
    _tag("system", f"provisioning {n_auto + 1} SA agents + 1 human role for this scenario")
    _pause(0.2)

    # Roles for display in [agent:assign]
    role_labels: dict[str, str] = {
        scenario["requester"]["name"]: "initiator",
    }
    for step in scenario["auto_steps"]:
        role_labels[step["agent_name"]] = step["label"]

    agents_to_provision = [scenario["requester"]] + [
        {"name": step["agent_name"], "description": step["description"], "label": step["label"]}
        for step in scenario["auto_steps"]
    ]

    addresses: dict[str, str] = {}
    for meta in agents_to_provision:
        sa_name = meta["name"]
        role    = role_labels.get(sa_name, sa_name)
        existing = _find_agent(client, org_id, workspace_id, sa_name)
        if existing:
            addresses[sa_name] = existing
            _tag("agent:assign", f"agent:{{{sa_name}}}  AS {role}")
        else:
            addr = _create_agent(client, org_id, workspace_id, sa_name, meta["description"])
            addresses[sa_name] = addr
            _tag("agent:create", f"agent:{{{sa_name}}}")
            _tag("agent:assign", f"agent:{{{sa_name}}}  AS {role}")
        _pause(0.25)

    _tag("human:assign", f"human:{{{human_role}}}  AS final sign-off (you)")
    print()
    _tag("system", "ready")
    print()
    return addresses


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
        next_handler: str | None = None,
        delay: float = 0.0,
        gate: threading.Event | None = None,
    ) -> None:
        self.intent_id    = intent_id
        self.actor        = actor
        self.reason       = reason
        self.owner_agent  = owner_agent
        self.next_handler = next_handler
        self.delay        = delay
        self.gate         = gate
        self.done         = threading.Event()
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
            resume_payload: dict[str, Any] = {
                "approve_current_step": True,
                "reason": task.reason,
                "actor":  task.actor,
            }
            if task.next_handler:
                resume_payload["next_handler"] = task.next_handler
            client.resume_intent(
                task.intent_id,
                resume_payload,
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

    base_url      = os.getenv("AXME_BASE_URL", "https://api.cloud.axme.ai").strip()
    cli_secrets   = _read_cli_secrets()
    api_key       = _require_api_key()
    actor_token   = (os.getenv("AXME_ACTOR_TOKEN", "").strip()
                     or cli_secrets.get("actor_token", "").strip()
                     or None)
    refresh_token = cli_secrets.get("refresh_token", "").strip() or None

    scenario    = _pick_scenario()
    auto_steps  = scenario["auto_steps"]
    human_role  = scenario["human_role"]
    human_label = scenario["human_label"]
    n_steps     = len(auto_steps) + 1

    sa_cfg       = AxmeClientConfig(base_url=base_url, api_key=api_key)
    personal_cfg = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)

    # ── Header ────────────────────────────────────────────────────────────
    print()
    _divider()
    print(f"  [scenario]  {scenario['title']}")
    print(f"  [summary]   {scenario['summary']}")
    _divider()
    print()

    # ── Resolve org / workspace ───────────────────────────────────────────
    _tag("system", "resolving org and workspace …")
    org_id, workspace_id = _resolve_org_workspace(base_url, api_key, actor_token, refresh_token)
    if not org_id or not workspace_id:
        print("\n  Could not determine org_id / workspace_id.")
        print("  Set AXME_ORG_ID + AXME_WORKSPACE_ID, or run 'axme login'.\n")
        raise SystemExit(1)
    _tag("system", f"org={org_id}  workspace={workspace_id}")
    _pause(0.3)

    # ── Provision agents ──────────────────────────────────────────────────
    print()
    with AxmeClient(personal_cfg) as probe:
        agent_addrs = _provision_agents(probe, org_id, workspace_id, scenario, human_role)
    _pause(0.2)

    requester_addr = agent_addrs[scenario["requester"]["name"]]
    # to_agent = first auto-step agent (change-management-validator)
    approver_addr  = agent_addrs[scenario["auto_steps"][0]["agent_name"]]

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
            _tag("intent:send", f"sending approval request …")
            created    = client.create_intent(intent_payload,
                                              correlation_id=correlation_id,
                                              idempotency_key=idempotency_key)
            intent_id  = str(created["intent_id"])
            raw_status = str(created.get("lifecycle_status") or created.get("status") or "DELIVERED")
            # Fetch full intent to get real pending_with (create_intent returns minimal response)
            full       = client.get_intent(intent_id).get("intent", {})
            raw_pw     = full.get("pending_with") or created.get("pending_with")
            cur_status = _fmt_status(raw_status)
            # prev_holder = the requester SA that sent the intent (logical sender)
            prev_holder = requester_addr.split("/")[-1]
            cur_holder  = _fmt_pending_with(raw_pw) if raw_pw else approver_addr.split("/")[-1]
            _tag("intent:create", f"id={intent_id}")
            _tag("status:change",     f"CREATED  →  SUBMITTED  →  {cur_status}")
            _tag("cur_holder:change", f"{prev_holder}  →  {cur_holder}")
            _pause(0.8)

            # ── Automated steps ───────────────────────────────────────────
            for i, step in enumerate(auto_steps, start=1):
                step_agent_addr = agent_addrs[step["agent_name"]]
                # next step agent (for next_handler): next auto-step or human label
                if i < len(auto_steps):
                    next_step         = auto_steps[i]
                    next_agent_addr   = agent_addrs[next_step["agent_name"]]
                    next_holder_label = next_step["label"]
                else:
                    next_agent_addr   = None   # human step — no SA address
                    next_holder_label = f"{human_label} (human)"

                print()
                _divider()
                print(f"  ── step {i}/{n_steps}  ⚙  {step['label']} approval")
                _divider()
                _tag("system", f"task: {step['reviewing']}")
                _pause(0.3)

                # Server will write WAITING (handoff) then IN_PROGRESS in one transaction.
                # We show WAITING first (optimistic), then confirm real status after resume.
                prev_status = cur_status
                prev_holder = cur_holder
                cur_holder  = step["label"]
                _tag("status:change", f"{prev_status}  →  {_fmt_status('WAITING', 'WAITING_FOR_AGENT')}")
                _pause(0.5)

                # owner_agent must be from_agent (change-management-validator) — it created
                # the intent and is the only SA authorised to call resume.
                # actor in the payload is the logical step executor for audit trail.
                task = _ResumeTask(
                    intent_id    = intent_id,
                    actor        = step_agent_addr,
                    reason       = f"{step['label']} approved — {step['approved']}",
                    owner_agent  = approver_addr,
                    next_handler = next_agent_addr,
                    delay        = 1.5,
                )
                resume_q.put(task)
                task.done.wait(timeout=20)

                if task.error:
                    _tag("error", f"step {i} failed: {task.error}")
                    try:
                        client.resolve_intent(
                            intent_id,
                            {
                                "status": "FAILED",
                                "result": {
                                    "error": str(task.error),
                                    "failed_step": i,
                                    "failed_actor": step["label"],
                                },
                            },
                        )
                    except Exception:
                        pass
                    raise RuntimeError(f"step {i} failed: {task.error}")

                _tag("action:approve", f"{step['label']} approved — {step['approved']}")

                # Fetch real status + cur_holder from server
                updated    = client.get_intent(intent_id).get("intent", {})
                new_raw    = str(updated.get("lifecycle_status") or updated.get("status") or "")
                new_reason = str(updated.get("lifecycle_waiting_reason") or "")
                raw_pw     = updated.get("pending_with")
                new_status = _fmt_status(new_raw, new_reason)
                new_holder = _fmt_pending_with(raw_pw) if raw_pw else next_holder_label

                _tag("status:change",     f"{_fmt_status('WAITING', 'WAITING_FOR_AGENT')}  →  {new_status}")
                _tag("cur_holder:change", f"{cur_holder}  →  {new_holder}")

                cur_status = new_status
                cur_holder = new_holder
                _pause(0.6)

            # ── Human step ────────────────────────────────────────────────
            print()
            _divider()
            print(f"  ── step {n_steps}/{n_steps}  👤  {human_role} approval")
            _divider()
            _tag("system", "task: manual sign-off required")
            _pause(0.3)

            prev_status = cur_status
            prev_holder = cur_holder
            cur_status  = _fmt_status("WAITING", "WAITING_FOR_HUMAN")
            cur_holder  = f"{human_label} (human)"
            _tag("status:change",     f"{prev_status}  →  {cur_status}")
            _tag("cur_holder:change", f"{prev_holder}  →  {cur_holder}")
            print()
            _tag("system", f"You are acting as: {human_role}")
            _tag("system", "Press Enter to approve, or Ctrl+C to cancel.")
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
            human_gate.set()

            human_task.done.wait(timeout=15)
            if human_task.error:
                _tag("error", f"human step failed: {human_task.error}")
                try:
                    client.resolve_intent(
                        intent_id,
                        {
                            "status": "FAILED",
                            "result": {
                                "error": str(human_task.error),
                                "failed_step": n_steps,
                                "failed_actor": human_role,
                            },
                        },
                    )
                except Exception:
                    pass
                raise RuntimeError(f"human step failed: {human_task.error}")

            _tag("action:approve", f"{human_role} approved")

            updated    = client.get_intent(intent_id).get("intent", {})
            new_raw    = str(updated.get("lifecycle_status") or updated.get("status") or "IN_PROGRESS")
            raw_pw     = updated.get("pending_with")
            new_status = _fmt_status(new_raw)
            new_holder = _fmt_pending_with(raw_pw) if raw_pw else approver_addr.split("/")[-1]

            _tag("status:change",     f"{cur_status}  →  {new_status}")
            _pause(0.5)

            cur_status = new_status
            cur_holder = new_holder

            # ── Resolve ───────────────────────────────────────────────────
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
            _tag("status:change", f"{prev_status}  →  {cur_status}")

            # ── Summary ───────────────────────────────────────────────────
            print()
            _divider()
            print()
            print(f"  Result:")
            print(f"    Scenario:     {scenario['title']}")
            print(f"    Intent ID:    {intent_id}")
            print(f"    Final status: {cur_status}")
            print()
            print(f"  Verify via CLI:")
            print(f"    axme intents get {intent_id}")
            print(f"    axme intents watch {intent_id}")
            print(f"    axme agents list")
            print(f"    axme quota show")
            print()

            # ── Full event history from server ────────────────────────────
            _divider()
            print()
            print("  Intent event log (server audit trail):")
            print()
            try:
                events_resp = client.list_intent_events(intent_id)
                events = events_resp.get("events") or []
                if events:
                    col_w = [5, 21, 13, 34, 26]
                    header = (
                        f"  {'#':<{col_w[0]}}"
                        f"{'time (UTC)':<{col_w[1]}}"
                        f"{'status':<{col_w[2]}}"
                        f"{'actor':<{col_w[3]}}"
                        f"{'cur_holder (pending_with)':<{col_w[4]}}"
                    )
                    print(header)
                    print("  " + "─" * (sum(col_w) + 4))
                    for ev in events:
                        seq    = str(ev.get("seq", ""))
                        at     = str(ev.get("at", ""))[:19].replace("T", " ")
                        status = str(ev.get("status", ""))
                        actor  = str(ev.get("actor") or "").split("/")[-1][:32]
                        pw     = (ev.get("pending_with") or {})
                        holder = str(pw.get("name") or pw.get("ref") or "").split("/")[-1][:24] if pw else ""
                        print(
                            f"  {seq:<{col_w[0]}}"
                            f"{at:<{col_w[1]}}"
                            f"{status:<{col_w[2]}}"
                            f"{actor:<{col_w[3]}}"
                            f"{holder:<{col_w[4]}}"
                        )
                    print()
                    # Show reason for each step that has it
                    for ev in events:
                        details = ev.get("details") or {}
                        reason  = details.get("reason") or details.get("next_handler") or ""
                        if reason:
                            seq = ev.get("seq", "")
                            print(f"    #{seq} reason: {reason}")
                    print()
                else:
                    print("  (no events returned)")
                    print()
            except Exception as _e:
                print(f"  (could not fetch event log: {_e})")
                print()

        finally:
            resume_q.put(None)
            worker.join(timeout=5)


if __name__ == "__main__":
    main()
