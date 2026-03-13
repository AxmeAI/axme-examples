"""ScenarioBundleRequest builder — converts a scenario JSON spec into the bundle
dict accepted by POST /v1/scenarios/apply (or /v1/scenarios/bundle).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


_EXAMPLE_ONLY_STEP_FIELDS = frozenset(
    {"label", "description", "outcome", "delivery_mode", "handler"}
)


def build_bundle(spec: dict[str, Any], *, human_contact: str = "") -> dict[str, Any]:
    """Build a ScenarioBundleRequest dict from a scenario spec."""

    # ── Agents ──────────────────────────────────────────────────────
    agents = [
        {
            "role":              a["role"],
            "address":           a["address"],
            "create_if_missing": True,
            "display_name":      a.get("display_name") or a["address"],
            # delivery_mode and callback_url are SA-level fields, not bundle-level
        }
        for a in (spec.get("agents") or [])
    ]

    # ── Humans ──────────────────────────────────────────────────────
    humans: list[dict[str, Any]] = []
    for h in (spec.get("humans") or []):
        entry: dict[str, Any] = {
            "role":         h["role"],
            "display_name": h.get("display_name") or h["role"],
        }
        # Use spec-level contact first, then the logged-in user's contact
        contact = h.get("contact") or human_contact
        if contact:
            entry["contact"] = contact
        humans.append(entry)

    # ── Workflow steps ───────────────────────────────────────────────
    workflow_steps = [
        {k: v for k, v in step.items() if k not in _EXAMPLE_ONLY_STEP_FIELDS}
        for step in (spec.get("workflow_steps") or [])
    ]

    # ── Intent ──────────────────────────────────────────────────────
    intent_spec: dict[str, Any] = dict(spec.get("intent") or {})
    dur = spec.get("durability") or {}

    # deadline_seconds takes priority (for fast-demo timeout scenarios)
    deadline_seconds = dur.get("deadline_seconds")
    deadline_minutes = dur.get("deadline_minutes") or intent_spec.pop(
        "deadline_minutes", None
    )
    if deadline_seconds and "deadline_at" not in intent_spec:
        intent_spec["deadline_at"] = (
            datetime.now(tz=timezone.utc) + timedelta(seconds=int(deadline_seconds))
        ).isoformat()
    elif deadline_minutes and "deadline_at" not in intent_spec:
        intent_spec["deadline_at"] = (
            datetime.now(tz=timezone.utc) + timedelta(minutes=int(deadline_minutes))
        ).isoformat()

    if dur.get("max_delivery_attempts") and "max_delivery_attempts" not in intent_spec:
        intent_spec["max_delivery_attempts"] = dur["max_delivery_attempts"]

    for field in (
        "remind_after_seconds",
        "remind_interval_seconds",
        "max_reminders",
        "escalate_to",
    ):
        if dur.get(field) and field not in intent_spec:
            intent_spec[field] = dur[field]

    bundle: dict[str, Any] = {
        "scenario_id": spec.get("scenario_id", ""),
        "description": spec.get("description") or spec.get("title") or "",
        "agents":      agents,
        "humans":      humans,
        "workflow":    {"steps": workflow_steps},
        "intent":      intent_spec,
    }
    return bundle
