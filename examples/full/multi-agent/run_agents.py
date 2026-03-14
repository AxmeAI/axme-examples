"""Run both agents for the full multi-agent scenario.

This script starts two agent processes concurrently:
  1. compliance-checker-agent  (step 1 of the workflow)
  2. risk-assessment-agent     (step 2 of the workflow)

Each agent needs its own API key from scenario-agents.json (provisioned
by `axme scenarios apply ... --watch`).

Usage:
    # Terminal 1 — run both agents
    python examples/full/multi-agent/run_agents.py

    # Terminal 2 — run the scenario
    axme scenarios apply examples/full/multi-agent/scenario.json --watch

    # After workflow pauses on step 3 (CAB approval):
    axme tasks list
    axme tasks approve <task_id>

Alternatively, run each agent in its own terminal:
    AXME_API_KEY=<compliance-key> python examples/delivery/stream/agent.py
    AXME_API_KEY=<risk-key>       python examples/internal/notification/agent.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_WORKSPACE = Path(__file__).parent.parent.parent  # axme-examples/
_AGENT_CREDS = Path.home() / ".config" / "axme" / "scenario-agents.json"

_AGENTS = [
    {
        "name_fragment": "compliance-checker",
        "script":        _WORKSPACE / "examples" / "delivery" / "stream" / "agent.py",
        "address":       "compliance-checker-agent",
    },
    {
        "name_fragment": "risk-assessment",
        "script":        _WORKSPACE / "examples" / "internal" / "notification" / "agent.py",
        "address":       "risk-assessment-agent",
    },
]


def _load_api_key(name_fragment: str) -> str:
    """Load API key for agent from scenario-agents.json."""
    try:
        data = json.loads(_AGENT_CREDS.read_text())
        for entry in data.get("agents", []):
            if name_fragment in entry.get("address", ""):
                return entry.get("api_key", "")
    except Exception as exc:
        print(f"  [error] could not read {_AGENT_CREDS}: {exc}", file=sys.stderr)
    return ""


def main() -> None:
    print("  Starting agents for full/multi-agent scenario...")
    print()

    procs: list[subprocess.Popen] = []

    for agent in _AGENTS:
        key = _load_api_key(agent["name_fragment"])
        if not key:
            env_key = os.environ.get("AXME_API_KEY", "")
            if not env_key:
                print(
                    f"  [warn] no API key found for {agent['name_fragment']!r}; "
                    f"set AXME_API_KEY or run `axme scenarios apply ... --watch` first",
                    file=sys.stderr,
                )
            key = env_key

        env = {**os.environ}
        if key:
            env["AXME_API_KEY"] = key
        env["AXME_AGENT_ADDRESS"] = agent["address"]

        print(f"  [agent]  {agent['address']} — {agent['script'].name}")
        proc = subprocess.Popen(
            [sys.executable, str(agent["script"])],
            env=env,
        )
        procs.append(proc)

    print()
    print("  Both agents running. Press Ctrl+C to stop.")
    print()

    try:
        for proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        print("\n  Shutting down agents...")
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait()


if __name__ == "__main__":
    main()
