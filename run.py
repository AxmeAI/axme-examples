#!/usr/bin/env python3
"""Axme examples runner — entry point.

Usage:
    python run.py                                        # interactive picker
    python run.py scenarios/delivery/01-stream.json     # run specific scenario
    python run.py --list                                 # list all available scenarios
    python run.py --validate scenarios/delivery/01-stream.json  # validate without running
    SCENARIO=delivery/01-stream python run.py           # via env var

Prerequisites:
    axme login        # one-time, tokens refresh automatically for 30 days
    pip install axme  # Python SDK
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT     = Path(__file__).parent
_RUNNER   = _ROOT / "runner"
_SCENARIOS = _ROOT / "scenarios"

# Add runner to path so `from runner import ...` works when running from any directory
sys.path.insert(0, str(_ROOT))

from runner.auth   import AuthContext
from runner.render import Renderer
from runner.runner import ScenarioRunner


# ---------------------------------------------------------------------------
# Scenario discovery
# ---------------------------------------------------------------------------

def _discover_scenarios() -> list[Path]:
    """Return all .json files under scenarios/ sorted by path."""
    return sorted(_SCENARIOS.rglob("*.json"))


def _load_spec(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        print(f"  [error] Cannot read {path}: {exc}")
        raise SystemExit(1)


def _short_id(path: Path) -> str:
    """Return scenarios/delivery/01-stream.json → delivery/01-stream"""
    try:
        rel = path.relative_to(_SCENARIOS)
        return str(rel.with_suffix(""))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# --list
# ---------------------------------------------------------------------------

def _cmd_list() -> None:
    files = _discover_scenarios()
    if not files:
        print("  No scenarios found in scenarios/")
        return

    print()
    print("  Available scenarios:")
    print()

    cur_group = ""
    for f in files:
        group = f.parent.name
        if group != cur_group:
            print(f"  ── {group}/ " + "─" * max(0, 60 - len(group)))
            cur_group = group
        spec = _load_spec(f)
        sid  = _short_id(f)
        title = spec.get("title") or spec.get("scenario_id") or f.stem
        print(f"    {sid:<40}  {title}")
    print()


# ---------------------------------------------------------------------------
# --validate
# ---------------------------------------------------------------------------

def _cmd_validate(path_str: str) -> None:
    path = _resolve_path(path_str)
    spec = _load_spec(path)
    print(f"  Validating: {path}")
    _validate_spec(spec)
    print("  ✓ Spec is valid (local checks passed)")

    # Optional server-side validation
    try:
        auth   = AuthContext()
        from axme import AxmeClient, AxmeClientConfig
        from runner.bundle import build_bundle
        client = AxmeClient(AxmeClientConfig(api_key=auth.api_key, base_url=auth.base_url))
        bundle = build_bundle(spec, human_contact=auth.human_contact())
        result = client.validate_scenario(bundle)
        errors = result.get("errors") or []
        if errors:
            print(f"  ✗ Server validation errors: {errors}")
        else:
            print("  ✓ Server validation passed")
    except Exception as exc:
        print(f"  (server validation skipped: {exc})")


def _validate_spec(spec: dict) -> None:
    required = ["scenario_id", "title", "workflow_steps", "intent"]
    for field in required:
        if not spec.get(field):
            print(f"  ✗ Missing required field: {field!r}")
            raise SystemExit(1)
    for i, step in enumerate(spec.get("workflow_steps") or []):
        if not step.get("step_id"):
            print(f"  ✗ workflow_steps[{i}] missing step_id")
            raise SystemExit(1)
        has_assignment = (
            step.get("assigned_to")
            or step.get("runtime_type")
        )
        if not has_assignment:
            print(f"  ✗ workflow_steps[{i}] missing assigned_to or runtime_type")
            raise SystemExit(1)


# ---------------------------------------------------------------------------
# Interactive picker
# ---------------------------------------------------------------------------

def _cmd_pick() -> Path:
    files = _discover_scenarios()
    if not files:
        print("  No scenarios found in scenarios/")
        raise SystemExit(1)

    print()
    print("  " + "─" * 74)
    print("  Axme examples runner")
    print("  " + "─" * 74)
    print()

    cur_group = ""
    index_map: dict[str, Path] = {}
    idx = 1
    for f in files:
        group = f.parent.name
        if group != cur_group:
            print(f"  ── {group}/ " + "─" * max(0, 58 - len(group)))
            cur_group = group
        spec  = _load_spec(f)
        sid   = _short_id(f)
        title = spec.get("title") or spec.get("scenario_id") or f.stem
        label = str(idx)
        index_map[label] = f
        print(f"  [{label:>2}]  {title}")
        print(f"        {sid}")
        idx += 1
    print()

    try:
        choice = input(f"  Select scenario [1-{idx-1}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(0)

    if choice not in index_map:
        print(f"  Invalid choice: {choice!r}")
        raise SystemExit(1)
    return index_map[choice]


# ---------------------------------------------------------------------------
# Path resolver
# ---------------------------------------------------------------------------

def _resolve_path(arg: str) -> Path:
    p = Path(arg)
    if p.exists():
        return p
    # Try relative to scenarios/
    p2 = _SCENARIOS / arg
    if p2.exists():
        return p2
    # Try with .json extension
    p3 = _SCENARIOS / (arg + ".json")
    if p3.exists():
        return p3
    print(f"  [error] Scenario file not found: {arg!r}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    if "--list" in args:
        _cmd_list()
        return

    if "--validate" in args:
        idx = args.index("--validate")
        target = args[idx + 1] if idx + 1 < len(args) else ""
        if not target:
            print("  Usage: python run.py --validate <scenario.json>")
            raise SystemExit(1)
        _cmd_validate(target)
        return

    # Determine which scenario to run
    if args:
        path = _resolve_path(args[0])
    else:
        env_scenario = os.getenv("SCENARIO", "").strip()
        if env_scenario:
            path = _resolve_path(env_scenario)
        else:
            path = _cmd_pick()

    spec = _load_spec(path)
    _validate_spec(spec)

    auth   = AuthContext()
    render = Renderer()
    runner = ScenarioRunner(spec, auth=auth, render=render)
    runner.run()


if __name__ == "__main__":
    main()
