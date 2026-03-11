"""
approval-workflow — Axme SDK example
=====================================
Demonstrates a multi-step approval flow through the Axme intent system.

Run:
    python main.py                   # interactive scenario picker
    SCENARIO=1 python main.py        # skip the picker

Prerequisites:
    axme login                       # one-time sign-in — no env export needed
"""
from __future__ import annotations

import json
import os
import queue
import sys
import time
import threading
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

from axme import AxmeClient, AxmeClientConfig


# ---------------------------------------------------------------------------
# Scenarios
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
# CLI secrets helpers
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
        print()
        print("  Not signed in. Run:  axme login")
        print()
        raise SystemExit(1)
    return value


# ---------------------------------------------------------------------------
# Pretty output helpers
# ---------------------------------------------------------------------------

STATUS_LABEL: dict[str, str] = {
    "DELIVERED":   "delivered",
    "IN_PROGRESS": "in progress",
    "WAITING":     "waiting",
    "COMPLETED":   "completed",
    "FAILED":      "failed",
    "CANCELED":    "cancelled",
}

HOLDER_LABEL: dict[str, str] = {
    "WAITING_FOR_HUMAN": "human reviewer",
    "WAITING_FOR_AGENT": "automated agent",
    "WAITING_FOR_TOOL":  "tool",
    "WAITING_FOR_TIME":  "timer",
}


def _p(tag: str, msg: str, *, indent: int = 0) -> None:
    pad = "  " * indent
    print(f"{pad}[{tag}]  {msg}", flush=True)


def _step(num: int, total: int, icon: str, title: str, note: str) -> None:
    print(f"\n  step {num}/{total}  {icon}  {title}", flush=True)
    print(f"           {note}", flush=True)


def _status(label: str, holder: str = "") -> None:
    line = f"  status    {label}"
    if holder:
        line += f"  •  управление: {holder}"
    print(line, flush=True)


def _divider() -> None:
    print("  " + "─" * 58, flush=True)


def _pause(seconds: float) -> None:
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

def _resolve_org_workspace(
    base_url: str,
    api_key: str,
    actor_token: str | None,
) -> tuple[str | None, str | None]:
    """Return (org_id, workspace_id) from env overrides or personal context."""
    org_id       = os.getenv("AXME_ORG_ID", "").strip() or None
    workspace_id = os.getenv("AXME_WORKSPACE_ID", "").strip() or None
    if org_id and workspace_id:
        return org_id, workspace_id
    if not actor_token:
        return org_id, workspace_id
    try:
        req = urllib.request.Request(
            f"{base_url}/v1/portal/personal/context",
            headers={
                "X-Api-Key":     api_key,
                "Authorization": f"Bearer {actor_token}",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ctx = json.loads(resp.read()).get("context") or {}
        org_id       = org_id       or ctx.get("org_id", "").strip() or None
        workspace_id = workspace_id or ctx.get("workspace_id", "").strip() or None
    except Exception:
        pass
    return org_id, workspace_id


def _ensure_approver_agent(
    client: AxmeClient,
    org_id: str,
    workspace_id: str,
) -> str:
    """
    Return agent_address of an existing SA with agent_address, or create one.
    Printed progress goes to stdout so the user sees it.
    """
    # 1. Look for an existing agent
    try:
        sa_resp = client.list_service_accounts(org_id=org_id, workspace_id=workspace_id)
        for sa in sa_resp.get("service_accounts") or []:
            addr = (sa.get("agent_address") or "").strip()
            if addr:
                return addr
    except Exception:
        pass

    # 2. Create a new one
    sa_name = f"approver-{int(time.time())}"
    print(f"           создаю агент  {sa_name} …", flush=True)
    new_sa = client.create_service_account(
        {
            "name":        sa_name,
            "org_id":      org_id,
            "workspace_id": workspace_id,
            "description": "approver agent — создан примером approval-workflow",
        },
        idempotency_key=f"example-approver-{org_id}-{workspace_id}",
    )
    addr = (new_sa.get("agent_address") or "").strip()
    if not addr:
        raise RuntimeError("сервер не вернул agent_address для нового SA")
    return addr


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
        self.intent_id  = intent_id
        self.actor      = actor
        self.reason     = reason
        self.owner_agent = owner_agent
        self.delay      = delay
        self.gate       = gate
        self.done       = threading.Event()
        self.error: Exception | None = None


def _resume_worker(
    client: AxmeClient,
    q: "queue.Queue[_ResumeTask | None]",
) -> None:
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
    print("  Выберите сценарий:")
    print()
    for k, s in SCENARIOS.items():
        print(f"    {k}.  {s['title']}")
    print()
    while True:
        try:
            choice = input("  Введите номер (1–4): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)
        if choice in SCENARIOS:
            return SCENARIOS[choice]
        print("  Введите 1, 2, 3 или 4.")


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
    to_agent_override = os.getenv("AXME_TO_AGENT", "").strip() or None

    scenario    = _pick_scenario()
    auto_steps  = scenario["auto_steps"]
    human_role  = scenario["human_role"]
    human_label = scenario["human_label"]
    n_steps     = len(auto_steps) + 1

    # SA-scoped config (no actor_token) — owner_scope = SA agent, needed for resume_intent
    sa_cfg = AxmeClientConfig(base_url=base_url, api_key=api_key)
    # Personal config — actor_token included, used only to resolve org/workspace
    personal_cfg = AxmeClientConfig(base_url=base_url, api_key=api_key, actor_token=actor_token)

    print()
    print(f"  ══════════════════════════════════════════════════════════")
    print(f"  Сценарий:  {scenario['title']}")
    print(f"  Запрос:    {scenario['summary']}")
    print(f"  ══════════════════════════════════════════════════════════")
    print()

    # ── Phase 1: resolve org/workspace ────────────────────────────────────
    _p("подготовка", "определяю организацию и рабочее пространство…")
    org_id, workspace_id = _resolve_org_workspace(base_url, api_key, actor_token)
    if not org_id or not workspace_id:
        print()
        print("  Не удалось определить org_id / workspace_id.")
        print("  Задайте переменные AXME_ORG_ID и AXME_WORKSPACE_ID, либо выполните 'axme login'.")
        print()
        raise SystemExit(1)
    _p("подготовка", f"org={org_id}  workspace={workspace_id}")
    _pause(0.4)

    # ── Phase 2: ensure approver agent ────────────────────────────────────
    with AxmeClient(personal_cfg) as probe:
        if to_agent_override:
            approver_address = to_agent_override
            _p("агент", f"используется AXME_TO_AGENT={approver_address}")
        else:
            _p("агент", "ищу зарегистрированного approver-агента…")
            approver_address = _ensure_approver_agent(probe, org_id, workspace_id)
            _p("агент", f"approver → {approver_address}")
        _pause(0.4)

    # ── Phase 3: create intent ────────────────────────────────────────────
    correlation_id  = str(uuid4())
    idempotency_key = f"approval-{correlation_id}"

    intent_payload: dict[str, Any] = {
        "intent_type":    scenario["intent_type"],
        "correlation_id": correlation_id,
        "to_agent":       approver_address,
        "payload": {
            "request_id":    f"req-{correlation_id[:8]}",
            "summary":       scenario["summary"],
            "approval_mode": "manual",
        },
    }

    resume_q: queue.Queue[_ResumeTask | None] = queue.Queue()

    with AxmeClient(sa_cfg) as client:
        resume_thread = threading.Thread(
            target=_resume_worker,
            args=(client, resume_q),
            daemon=True,
        )
        resume_thread.start()

        try:
            _p("интент", "отправляю запрос на согласование…")
            created = client.create_intent(
                intent_payload,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )
            intent_id   = str(created["intent_id"])
            init_status = str(created.get("lifecycle_status") or created.get("status") or "")
            _p("интент", f"создан  id={intent_id}")
            _status(STATUS_LABEL.get(init_status, init_status), "отправитель (этот процесс)")
            _pause(0.6)

            # ── Automated steps ───────────────────────────────────────────
            for i, step in enumerate(auto_steps, start=1):
                _step(i, n_steps, "⚙", step["label"], step["reviewing"] + "…")
                _status("ожидание", f"агент  {step['label']}")
                _pause(0.5)

                task = _ResumeTask(
                    intent_id    = intent_id,
                    actor        = step["actor"],
                    reason       = f"{step['actor']} approved — {step['approved']}",
                    owner_agent  = approver_address,
                    delay        = 1.5,
                )
                resume_q.put(task)
                task.done.wait(timeout=20)

                if task.error:
                    print(f"  [!] ошибка на шаге {i}: {task.error}", flush=True)
                    raise RuntimeError(f"шаг {i} не прошёл: {task.error}")

                updated      = client.get_intent(intent_id).get("intent", {})
                cur_status   = str(updated.get("lifecycle_status") or updated.get("status") or "")
                waiting_reas = str(updated.get("lifecycle_waiting_reason") or "")
                _status(STATUS_LABEL.get(cur_status, cur_status))
                print(f"  ✓  {step['approved']}", flush=True)
                _pause(0.8)

            # ── Human step ────────────────────────────────────────────────
            hs = n_steps
            _step(hs, n_steps, "👤", human_role, "ожидаю решения человека…")
            _status("пауза — ожидание", "человек")
            _divider()
            print(f"\n  Вы выступаете в роли:  {human_role}")
            print(f"  Нажмите Enter чтобы одобрить, или Ctrl+C чтобы отменить.\n")

            human_gate = threading.Event()
            human_task = _ResumeTask(
                intent_id   = intent_id,
                actor       = f"human:{human_label}",
                reason      = f"одобрено — {human_role}",
                owner_agent = approver_address,
                gate        = human_gate,
            )
            resume_q.put(human_task)

            try:
                input("  > ")
            except (EOFError, KeyboardInterrupt):
                print("\n  [отмена]  согласование отменено пользователем.")
                resume_q.put(None)
                raise SystemExit(0)

            print(flush=True)
            _p("решение", f"{human_role} подтвердил(а) — продолжаю…")
            human_gate.set()

            human_task.done.wait(timeout=15)
            if human_task.error:
                print(f"  [!] ошибка human-шага: {human_task.error}", flush=True)
                raise RuntimeError(f"human-шаг не прошёл: {human_task.error}")

            _pause(0.6)

            # ── Resolve intent ────────────────────────────────────────────
            _p("завершение", "закрываю интент со статусом COMPLETED…")
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
            _pause(0.5)

            # ── Wait for terminal event ───────────────────────────────────
            final_status = "COMPLETED"
            try:
                for event in client.observe(intent_id, since=0, timeout_seconds=10):
                    ev_status = str(event.get("status") or "")
                    if ev_status in {"COMPLETED", "FAILED", "CANCELED"}:
                        final_status = ev_status
                        break
            except Exception:
                pass

            # ── Final report ──────────────────────────────────────────────
            print()
            _divider()
            print()
            print(f"  Итог:")
            print(f"    Сценарий:    {scenario['title']}")
            print(f"    Intent ID:   {intent_id}")
            print(f"    Статус:      {STATUS_LABEL.get(final_status, final_status).upper()}")
            print(f"    Одобрил:     {human_role}")
            print()
            print(f"  Проверить через CLI:")
            print(f"    axme intents get {intent_id}")
            print(f"    axme intents watch {intent_id}")
            print(f"    axme quota show")
            print()

        finally:
            resume_q.put(None)
            resume_thread.join(timeout=5)


if __name__ == "__main__":
    main()
