"""
approval-workflow — Axme SDK example (Model B / ScenarioBundle)
===============================================================
Demonstrates a durable 3-step approval workflow using POST /v1/scenarios/apply.
The server provisions agents, compiles the workflow DAG, and drives all step
transitions autonomously.  The client only observes the event stream and handles
the one human-input step.

Workflow:
  step 1 — change-management-validator   (automated: verifies maintenance window)
  step 2 — deployment-impact-assessor    (automated: assesses blast radius)
  step 3 — Change Advisory Board (you)   (human: final sign-off, requires_approval)

Run:
    python main.py              # interactive scenario picker
    SCENARIO=1 python main.py   # skip the picker

Prerequisites:
    axme login                  # one-time; refreshes automatically for 30 days
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from axme import AxmeClient, AxmeClientConfig


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "1": {
        "title":       "nginx config rollout → prod-cluster-eu",
        "summary":     "Update nginx config on prod-cluster-eu (change #CHG-4821)",
        "scenario_id": "approval.nginx_rollout.v1",
        "intent_type": "intent.approval.change_mgmt.v1",
        "agents": [
            {
                "role":        "requester",
                "address":     "nginx-rollout-requester",
                "display_name": "Nginx Rollout Requester",
                "description": "step 1/3 — auto: verifying maintenance window and rollback plan",
            },
            {
                "role":        "validator",
                "address":     "change-management-validator",
                "display_name": "Change Management Validator",
                "description": "step 2/3 — auto: assessing blast radius and service dependencies",
            },
            {
                "role":        "assessor",
                "address":     "deployment-impact-assessor",
                "display_name": "Deployment Impact Assessor",
            },
        ],
        "humans": [
            {
                "role":         "cab",
                "display_name": "Change Advisory Board (CAB)",
                "description":  "step 3/3 — human: final sign-off",
            },
        ],
        "workflow_steps": [
            {
                "step_id":              "validate_change",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "validator",
                "step_deadline_seconds": 300,
                "label":                "change-management-validator",
                "description":          "verifying maintenance window and rollback plan",
                "outcome":              "maintenance window confirmed, rollback plan verified",
            },
            {
                "step_id":              "assess_impact",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "assessor",
                "step_deadline_seconds": 300,
                "label":                "deployment-impact-assessor",
                "description":          "assessing blast radius and service dependencies",
                "outcome":              "blast radius: low, zero downtime deployment confirmed",
            },
            {
                "step_id":             "cab_signoff",
                "tool_id":             "axme.approval.v1",
                "assigned_to":         "cab",
                "requires_approval":   True,
                "step_deadline_seconds": 3600,
                "remind_after_seconds": 300,
                "remind_interval_seconds": 300,
                "max_reminders":       3,
                "human_task": {
                    "title":       "Final CAB sign-off — nginx rollout to prod-cluster-eu",
                    "description": "Review and approve the nginx config rollout to prod-cluster-eu",
                    "form_schema": {
                        "type":     "object",
                        "required": ["approved"],
                        "properties": {
                            "approved": {"type": "boolean"},
                            "notes":    {"type": "string"},
                        },
                    },
                },
                "label":       "Change Advisory Board (CAB)",
                "description": "final sign-off required",
            },
        ],
        "intent_payload": {
            "change_id":     "CHG-4821",
            "service":       "nginx",
            "environment":   "prod-cluster-eu",
            "description":   "Update nginx config for load balancing improvements",
            "risk_level":    "medium",
            "rollback_plan": "revert to previous nginx.conf via git tag v2.1.1",
        },
        "deadline_minutes": 60,
    },
    "2": {
        "title":       "$47,500 cloud infrastructure budget — Q2 expansion",
        "summary":     "Budget approval: $47,500 cloud infrastructure Q2 expansion (BUD-2024-Q2-EU)",
        "scenario_id": "approval.budget_request.v1",
        "intent_type": "intent.approval.finance.v1",
        "agents": [
            {
                "role":    "requester",
                "address": "budget-request-agent",
                "display_name": "Budget Request Agent",
            },
            {
                "role":    "envelope_validator",
                "address": "budget-envelope-validator",
                "display_name": "Budget Envelope Validator",
                "description": "step 1/3 — auto: validating budget envelope against Q2 allocation",
            },
            {
                "role":    "cost_estimator",
                "address": "vendor-cost-estimator",
                "display_name": "Vendor Cost Estimator",
                "description": "step 2/3 — auto: cross-checking vendor quotes and 12-month TCO",
            },
        ],
        "humans": [
            {
                "role":         "cfo",
                "display_name": "CFO / Finance Committee",
                "description":  "step 3/3 — human: final budget approval",
            },
        ],
        "workflow_steps": [
            {
                "step_id":              "validate_envelope",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "envelope_validator",
                "step_deadline_seconds": 300,
                "label":                "budget-envelope-validator",
                "description":          "validating budget envelope against Q2 allocation",
                "outcome":              "within Q2 envelope, 12% headroom remaining",
            },
            {
                "step_id":              "estimate_cost",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "cost_estimator",
                "step_deadline_seconds": 300,
                "label":                "vendor-cost-estimator",
                "description":          "cross-checking vendor quotes and 12-month TCO",
                "outcome":              "3 vendor quotes validated, TCO within 5% of estimate",
            },
            {
                "step_id":             "cfo_approval",
                "tool_id":             "axme.approval.v1",
                "assigned_to":         "cfo",
                "requires_approval":   True,
                "step_deadline_seconds": 86400,
                "remind_after_seconds": 3600,
                "remind_interval_seconds": 3600,
                "max_reminders":       2,
                "human_task": {
                    "title":       "Budget approval — Q2 cloud infrastructure $47,500",
                    "description": "Approve the Q2 cloud expansion budget within allocated envelope",
                    "form_schema": {
                        "type":     "object",
                        "required": ["approved"],
                        "properties": {
                            "approved": {"type": "boolean"},
                            "notes":    {"type": "string"},
                        },
                    },
                },
                "label":       "CFO / Finance Committee",
                "description": "final budget sign-off required",
            },
        ],
        "intent_payload": {
            "budget_id":   "BUD-2024-Q2-EU",
            "amount":      47500,
            "currency":    "USD",
            "category":    "cloud_infrastructure",
            "description": "Q2 cloud expansion — EU region capacity increase",
        },
        "deadline_minutes": 1440,
    },
    "3": {
        "title":       "READ access to prod-db-eu-west-1 for svc:data-pipeline",
        "summary":     "Access request: READ on prod-db-eu-west-1 for svc:data-pipeline (ITSM-ACCESS-8821)",
        "scenario_id": "approval.access_request.v1",
        "intent_type": "intent.approval.access_mgmt.v1",
        "agents": [
            {
                "role":    "requester",
                "address": "access-request-agent",
                "display_name": "Access Request Agent",
            },
            {
                "role":    "policy_checker",
                "address": "access-policy-checker",
                "display_name": "Access Policy Checker",
                "description": "step 1/3 — auto: verifying service identity and least-privilege policy",
            },
            {
                "role":    "risk_assessor",
                "address": "data-risk-assessor",
                "display_name": "Data Risk Assessor",
                "description": "step 2/3 — auto: evaluating data sensitivity and audit trail coverage",
            },
        ],
        "humans": [
            {
                "role":         "security_officer",
                "display_name": "Security Officer / DBA",
                "description":  "step 3/3 — human: access grant sign-off",
            },
        ],
        "workflow_steps": [
            {
                "step_id":              "check_policy",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "policy_checker",
                "step_deadline_seconds": 300,
                "label":                "access-policy-checker",
                "description":          "verifying service identity and least-privilege policy",
                "outcome":              "service identity verified, READ-only scope within policy",
            },
            {
                "step_id":              "assess_risk",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "risk_assessor",
                "step_deadline_seconds": 300,
                "label":                "data-risk-assessor",
                "description":          "evaluating data sensitivity and audit trail coverage",
                "outcome":              "PII fields excluded, audit logging active on target DB",
            },
            {
                "step_id":             "security_signoff",
                "tool_id":             "axme.approval.v1",
                "assigned_to":         "security_officer",
                "requires_approval":   True,
                "step_deadline_seconds": 7200,
                "remind_after_seconds": 1800,
                "remind_interval_seconds": 1800,
                "max_reminders":       2,
                "human_task": {
                    "title":       "Access grant approval — READ on prod-db-eu-west-1",
                    "description": "Grant READ access for svc:data-pipeline to prod-db-eu-west-1",
                    "form_schema": {
                        "type":     "object",
                        "required": ["approved"],
                        "properties": {
                            "approved":   {"type": "boolean"},
                            "grant_until": {"type": "string"},
                            "notes":      {"type": "string"},
                        },
                    },
                },
                "label":       "Security Officer / DBA",
                "description": "access grant sign-off required",
            },
        ],
        "intent_payload": {
            "request_id":  "ITSM-ACCESS-8821",
            "resource":    "prod-db-eu-west-1",
            "access_type": "READ",
            "requestor":   "svc:data-pipeline",
            "justification": "ETL pipeline requires read access to replicate production data for analytics",
        },
        "deadline_minutes": 120,
    },
    "4": {
        "title":       "AI agent action: send contract to Acme Corp ($120k)",
        "summary":     "AI agent requests permission to send $120k contract to Acme Corp (CONTRACT-AC-2024-001)",
        "scenario_id": "approval.contract_send.v1",
        "intent_type": "intent.approval.ai_oversight.v1",
        "agents": [
            {
                "role":    "ai_agent",
                "address": "ai-action-requester",
                "display_name": "AI Action Requester",
            },
            {
                "role":    "terms_validator",
                "address": "contract-terms-validator",
                "display_name": "Contract Terms Validator",
                "description": "step 1/3 — auto: validating contract terms and entity details",
            },
            {
                "role":    "compliance_checker",
                "address": "compliance-aml-checker",
                "display_name": "Compliance AML Checker",
                "description": "step 2/3 — auto: running compliance checks (AML, sanctions)",
            },
        ],
        "humans": [
            {
                "role":         "account_executive",
                "display_name": "Account Executive / Legal",
                "description":  "step 3/3 — human: contract send approval",
            },
        ],
        "workflow_steps": [
            {
                "step_id":              "validate_terms",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "terms_validator",
                "step_deadline_seconds": 300,
                "label":                "contract-terms-validator",
                "description":          "validating contract terms, signatures and entity details",
                "outcome":              "contract terms valid, entities match CRM records",
            },
            {
                "step_id":              "check_compliance",
                "tool_id":              "axme.approval.v1",
                "assigned_to":          "compliance_checker",
                "step_deadline_seconds": 300,
                "label":                "compliance-aml-checker",
                "description":          "running compliance checks (AML, sanctions, jurisdiction)",
                "outcome":              "AML clear, no sanctions hits, jurisdiction confirmed",
            },
            {
                "step_id":             "exec_approval",
                "tool_id":             "axme.approval.v1",
                "assigned_to":         "account_executive",
                "requires_approval":   True,
                "step_deadline_seconds": 7200,
                "remind_after_seconds": 1800,
                "remind_interval_seconds": 1800,
                "max_reminders":       3,
                "human_task": {
                    "title":       "Contract send approval — Acme Corp $120k",
                    "description": "Approve AI agent action to send the $120k contract to Acme Corp",
                    "form_schema": {
                        "type":     "object",
                        "required": ["approved"],
                        "properties": {
                            "approved": {"type": "boolean"},
                            "notes":    {"type": "string"},
                        },
                    },
                },
                "label":       "Account Executive / Legal",
                "description": "contract send sign-off required",
            },
        ],
        "intent_payload": {
            "contract_id": "CONTRACT-AC-2024-001",
            "counterparty": "Acme Corp",
            "value":       120000,
            "currency":    "USD",
            "action":      "send_contract",
            "deadline":    "2024-12-31",
        },
        "deadline_minutes": 120,
    },
}


# ---------------------------------------------------------------------------
# Secrets / auth
# ---------------------------------------------------------------------------

_SECRETS_PATH = Path.home() / ".config" / "axme" / "secrets.json"


def _read_cli_secrets(context: str = "default") -> dict[str, str]:
    try:
        data = json.loads(_SECRETS_PATH.read_text())
        return dict(data.get(context) or data.get("default") or {})
    except Exception:
        return {}


def _require_api_key() -> str:
    value = os.getenv("AXME_API_KEY", "").strip()
    if not value:
        value = _read_cli_secrets().get("api_key", "").strip()
    if not value:
        print(
            "\n  [error] No API key found.\n"
            "  Run:  axme login\n"
            "  Or:   export AXME_API_KEY=<your-key>\n"
        )
        raise SystemExit(1)
    return value


def _require_human_contact() -> str:
    """Return the actor email from CLI secrets (used as human contact in the bundle)."""
    return _read_cli_secrets().get("email", "").strip() or os.getenv("AXME_USER_EMAIL", "").strip()


def _require_base_url() -> str:
    return (
        os.getenv("AXME_BASE_URL", "").strip()
        or _read_cli_secrets().get("base_url", "").strip()
        or "https://api.cloud.axme.ai"
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_COL = 22


def _tag(kind: str, msg: str) -> None:
    print(f"  [{kind:<20}]  {msg}")


def _divider() -> None:
    print("  " + "─" * 72)


def _pause(secs: float) -> None:
    time.sleep(secs)


def _fmt_status(raw: str, reason: str = "") -> str:
    mapping = {
        "DELIVERED":         "DELIVERED",
        "ACKNOWLEDGED":      "ACKNOWLEDGED",
        "IN_PROGRESS":       "IN_PROGRESS",
        "WAITING":           f"WAITING ({'for human' if 'HUMAN' in reason.upper() else 'for agent'})",
        "COMPLETED":         "COMPLETED ✓",
        "FAILED":            "FAILED ✗",
        "CANCELED":          "CANCELED",
        "TIMED_OUT":         "TIMED_OUT ✗",
    }
    return mapping.get(raw, raw)


def _fmt_pending_with(pw: dict[str, Any] | None) -> str:
    if not pw:
        return ""
    name = pw.get("name") or pw.get("ref") or ""
    return str(name).split("/")[-1]


# ---------------------------------------------------------------------------
# Scenario picker
# ---------------------------------------------------------------------------

def _pick_scenario() -> dict[str, Any]:
    env_scenario = os.getenv("SCENARIO", "").strip()
    if env_scenario in SCENARIOS:
        return SCENARIOS[env_scenario]

    print()
    _divider()
    print("  Axme — approval workflow example  (Model B · ScenarioBundle)")
    _divider()
    for key, sc in SCENARIOS.items():
        print(f"  [{key}]  {sc['title']}")
    print()
    try:
        choice = input("  Select scenario [1-4]: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(0)
    if choice not in SCENARIOS:
        print(f"  Invalid choice: {choice!r}")
        raise SystemExit(1)
    return SCENARIOS[choice]


# ---------------------------------------------------------------------------
# Bundle builder
# ---------------------------------------------------------------------------

def _build_bundle(scenario: dict[str, Any], human_contact: str) -> dict[str, Any]:
    """Convert scenario definition into a ScenarioBundleRequest dict."""
    deadline_iso = (
        datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .__class__(
            *(datetime.now(tz=timezone.utc).timetuple()[:6]),
            tzinfo=timezone.utc,
        )
    )
    # Compute deadline_at = now + deadline_minutes
    from datetime import timedelta
    deadline_at = (
        datetime.now(tz=timezone.utc) + timedelta(minutes=scenario["deadline_minutes"])
    ).isoformat()

    # Agents
    agents = [
        {
            "role":             a["role"],
            "address":          a["address"],
            "create_if_missing": True,
            "display_name":     a.get("display_name", a["address"]),
        }
        for a in scenario["agents"]
    ]

    # Humans: inject the logged-in user's contact for human steps
    humans = []
    for h in scenario["humans"]:
        entry: dict[str, Any] = {
            "role":         h["role"],
            "display_name": h.get("display_name", h["role"]),
        }
        if human_contact:
            entry["contact"] = human_contact
        humans.append(entry)

    # Workflow steps (strip example-only fields: label, description, outcome)
    _example_only = {"label", "description", "outcome"}
    workflow_steps = [
        {k: v for k, v in step.items() if k not in _example_only}
        for step in scenario["workflow_steps"]
    ]

    return {
        "scenario_id": scenario["scenario_id"],
        "description": scenario["summary"],
        "agents":      agents,
        "humans":      humans,
        "workflow":    {"steps": workflow_steps},
        "intent": {
            "type":        scenario["intent_type"],
            "payload":     scenario["intent_payload"],
            "deadline_at": deadline_at,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    scenario = _pick_scenario()

    api_key       = _require_api_key()
    base_url      = _require_base_url()
    human_contact = _require_human_contact()

    client = AxmeClient(
        AxmeClientConfig(
            api_key=api_key,
            base_url=base_url,
        )
    )

    n_steps     = len(scenario["workflow_steps"])
    human_role  = scenario["humans"][0]["display_name"]

    # ── Print scenario overview ───────────────────────────────────────────
    print()
    _divider()
    print(f"  [scenario]  {scenario['title']}")
    _divider()
    print(f"  [summary]   {scenario['summary']}")
    print()

    for i, step in enumerate(scenario["workflow_steps"], 1):
        is_human = step.get("requires_approval", False)
        kind     = "human" if is_human else "agent"
        label    = step.get("label") or step.get("assigned_to") or step["step_id"]
        desc     = step.get("description", "")
        print(f"  [{kind}:step]   step {i}/{n_steps} — {label}  ({desc})")
    print()

    print(f"  [system]    deadline: {scenario['deadline_minutes']} min from now")
    print()

    # ── Apply scenario (one call — server does everything) ────────────────
    _tag("system", "resolving org and workspace …")
    _pause(0.2)

    bundle = _build_bundle(scenario, human_contact)
    idempotency_key = str(uuid4())

    _tag("system",
         f"provisioning {len(scenario['agents'])} SA agent(s) + "
         f"{len(scenario['humans'])} human role(s) via ScenarioBundle …")
    _pause(0.3)

    try:
        apply_resp = client.apply_scenario(bundle, idempotency_key=idempotency_key)
    except Exception as exc:
        _tag("error", f"apply_scenario failed: {exc}")
        raise SystemExit(1)

    intent_id  = str(apply_resp.get("intent_id", ""))
    compile_id = str(apply_resp.get("compile_id") or "")

    if not intent_id:
        _tag("error", "server returned no intent_id")
        raise SystemExit(1)

    for ag in apply_resp.get("agents_provisioned") or []:
        _tag("agent:create", f"agent:{{{ag}}}")
    _pause(0.3)

    for step_spec in scenario["agents"]:
        _tag("agent:assign",
             f"agent:{{{step_spec['address']}}}  AS  {step_spec.get('description', step_spec['role'])}")
    _tag("human:assign",
         f"human:{{{human_role}}}  AS  {scenario['humans'][0].get('description', 'final sign-off (you)')}")
    print()

    _tag("intent:create", f"intent_id={intent_id}")
    if compile_id:
        _tag("intent:create", f"workflow compile_id={compile_id}")
    _tag("status:change",  "—  →  DELIVERED")
    print()

    # ── Observe event stream ──────────────────────────────────────────────
    # Track display state
    cur_status   = "DELIVERED"
    cur_holder   = scenario["agents"][0]["address"]
    step_counter = 0

    _TERMINAL = {"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"}

    try:
        for event in client.observe(intent_id, since=0, timeout_seconds=600):
            ev_status    = str(event.get("status") or "")
            ev_reason    = str(event.get("lifecycle_waiting_reason") or event.get("reason") or "")
            ev_type      = str(event.get("event_type") or "")
            raw_pw       = event.get("pending_with")
            new_holder   = _fmt_pending_with(raw_pw) if isinstance(raw_pw, dict) else cur_holder

            # ── human_task_assigned: pause and wait for Enter ─────────────
            if ev_type == "intent.human_task_assigned":
                ht     = event.get("human_task") or {}
                title  = ht.get("title") or f"{human_role} approval"
                schema = ht.get("form_schema")

                step_counter += 1
                print()
                _divider()
                print(f"  ── step {n_steps}/{n_steps}  👤  {human_role} approval")
                _divider()
                _tag("system",       f"task: {title}")
                _tag("status:change", f"{cur_status}  →  {_fmt_status('WAITING', 'WAITING_FOR_HUMAN')}")
                _tag("cur_holder:change",
                     f"{cur_holder}  →  {new_holder or human_role}")

                cur_status = _fmt_status("WAITING", "WAITING_FOR_HUMAN")
                cur_holder = new_holder or human_role

                if schema:
                    fields = list((schema.get("properties") or {}).keys())
                    _tag("system", f"form fields: {', '.join(fields)}")
                print()
                _tag("system",  f"You are acting as:  {human_role}")
                _tag("system",  "Press Enter to approve, or Ctrl+C to cancel.")
                print()

                try:
                    input("  > ")
                except (EOFError, KeyboardInterrupt):
                    print("\n  [cancelled]  approval cancelled.")
                    raise SystemExit(0)

                print()
                _tag("action:approve", f"{human_role} approved")
                _pause(0.3)

                # Submit approval back to server
                try:
                    client.resume_intent(
                        intent_id,
                        {
                            "action":      "approve",
                            "task_result": {"approved": True},
                        },
                    )
                except Exception as exc:
                    _tag("error", f"resume_intent (human) failed: {exc}")
                    raise

                continue

            # ── Normal lifecycle status events ────────────────────────────
            if not ev_status:
                continue

            new_fmt = _fmt_status(ev_status, ev_reason)

            # Step header when holder changes or step advances
            if new_holder and new_holder != cur_holder:
                # Figure out which step we're on
                for i, step in enumerate(scenario["workflow_steps"], 1):
                    step_label = step.get("label") or step.get("assigned_to") or step["step_id"]
                    if new_holder in step_label or step_label in new_holder:
                        step_counter = i
                        break
                if step_counter > 0 and not scenario["workflow_steps"][step_counter - 1].get("requires_approval"):
                    step = scenario["workflow_steps"][step_counter - 1]
                    label = step.get("label") or step.get("assigned_to") or step["step_id"]
                    desc  = step.get("description", "")
                    print()
                    _divider()
                    print(f"  ── step {step_counter}/{n_steps}  ⚙  {label} approval")
                    _divider()
                    _tag("system", f"task: {desc}")

            if new_fmt != cur_status:
                _tag("status:change", f"{cur_status}  →  {new_fmt}")
                _pause(0.3)

            if new_holder and new_holder != cur_holder:
                _tag("cur_holder:change", f"{cur_holder}  →  {new_holder}")

                # If automated step: print approval outcome after a brief delay
                for step in scenario["workflow_steps"]:
                    if not step.get("requires_approval"):
                        step_label = step.get("label") or step.get("assigned_to") or step["step_id"]
                        if cur_holder in step_label or step_label in cur_holder:
                            outcome = step.get("outcome")
                            if outcome:
                                _pause(0.5)
                                _tag("action:approve", f"{step_label} approved — {outcome}")
                            break

                _pause(0.4)

            cur_status = new_fmt
            cur_holder = new_holder or cur_holder

            if ev_status in _TERMINAL:
                break

    except TimeoutError:
        _tag("error", "observation timed out after 10 min — check intent status manually")
        _tag("system", f"axme intents get {intent_id}")
        raise SystemExit(1)

    # ── Final summary ─────────────────────────────────────────────────────
    print()
    _divider()
    print()
    print(f"  Result:")
    print(f"    Scenario:     {scenario['title']}")
    print(f"    Intent ID:    {intent_id}")
    print(f"    Final status: {cur_status}")
    if compile_id:
        print(f"    Workflow:     compile_id={compile_id}")
    print()
    print(f"  Verify via CLI:")
    print(f"    axme intents get {intent_id}")
    print(f"    axme intents watch {intent_id}")
    print(f"    axme agents list")
    print(f"    axme quota show")
    print()

    # ── Full event history from server ────────────────────────────────────
    _divider()
    print()
    print("  Intent event log (server audit trail):")
    print()
    try:
        events_resp = client.list_intent_events(intent_id)
        events      = events_resp.get("events") or []
        if events:
            col_w  = [5, 21, 28, 30, 28]
            header = (
                f"  {'#':<{col_w[0]}}"
                f"{'time (UTC)':<{col_w[1]}}"
                f"{'status':<{col_w[2]}}"
                f"{'actor':<{col_w[3]}}"
                f"{'cur_holder (pending_with)':<{col_w[4]}}"
            )
            print(header)
            print("  " + "─" * (sum(col_w) + 2))
            for ev in events:
                seq    = str(ev.get("seq", ""))
                at     = str(ev.get("at", ""))[:19].replace("T", " ")
                status = str(ev.get("status", ""))
                actor  = str(ev.get("actor") or "").split("/")[-1][:28]
                pw     = ev.get("pending_with") or {}
                holder = str(
                    pw.get("name") or pw.get("ref") or ""
                ).split("/")[-1][:26] if pw else ""
                reason = str(
                    (ev.get("details") or {}).get("reason") or
                    (ev.get("details") or {}).get("next_handler") or ""
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
        else:
            print("  (no events returned)")
            print()
    except Exception as exc:
        print(f"  (could not fetch event log: {exc})")
        print()


if __name__ == "__main__":
    main()
