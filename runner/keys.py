"""Agent API key cache for the example runner.

Each agent SA needs its OWN API key when running stream/poll/http handlers
in-process.  The initiator's key belongs to a different SA and the server
will reject it on /v1/agents/{address}/intents/stream.

Keys are persisted to ~/.config/axme/example-runner-keys.json so they
survive between runs.  On first use for a given address, a new key is
created via POST /v1/service-accounts/{sa_id}/keys and cached.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CACHE_PATH = Path.home() / ".config" / "axme" / "example-runner-keys.json"


def _load() -> dict[str, str]:
    try:
        return dict(json.loads(_CACHE_PATH.read_text()))
    except Exception:
        return {}


def _save(data: dict[str, str]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(data, indent=2))


def get_or_create_key(
    address: str,
    sa_id: str,
    *,
    create_fn: Any,  # callable(sa_id, payload) -> dict
) -> str:
    """Return cached API key for *address*, creating one if missing.

    Args:
        address:   Full ``agent://org/ws/name`` address (used as cache key).
        sa_id:     Service account ID returned by apply_scenario.
        create_fn: ``client.create_service_account_key`` (or compatible callable).
    """
    cache = _load()
    if address in cache:
        return cache[address]

    resp = create_fn(sa_id, {"name": "example-runner", "description": "auto-created by axme examples runner"})
    key: str = resp.get("api_key") or resp.get("key") or ""
    if not key:
        raise RuntimeError(
            f"create_service_account_key for {address} returned no api_key: {resp}"
        )

    cache[address] = key
    _save(cache)
    return key


def invalidate(address: str) -> None:
    """Remove cached key for *address* (e.g., after key rotation)."""
    cache = _load()
    if address in cache:
        del cache[address]
        _save(cache)
