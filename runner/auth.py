"""Auth helpers — load api_key, actor_token, base_url from env / CLI secrets."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

_SECRETS_PATH = Path.home() / ".config" / "axme" / "secrets.json"
_DEFAULT_BASE_URL = "https://api.cloud.axme.ai"


def _read_cli_secrets(context: str = "default") -> dict[str, str]:
    try:
        data = json.loads(_SECRETS_PATH.read_text())
        return dict(data.get(context) or data.get("default") or {})
    except Exception:
        return {}


def require_api_key() -> str:
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


def require_base_url() -> str:
    return (
        os.getenv("AXME_BASE_URL", "").strip()
        or _read_cli_secrets().get("base_url", "").strip()
        or _DEFAULT_BASE_URL
    )


def require_actor_token() -> str | None:
    value = os.getenv("AXME_ACTOR_TOKEN", "").strip()
    if not value:
        value = _read_cli_secrets().get("actor_token", "").strip()
    return value or None


def resolve_human_contact(api_key: str = "", base_url: str = "") -> str:
    """Return the human actor email for task assignment.

    Tries in order:
    1. AXME_USER_EMAIL env var
    2. email field in ~/.config/axme/secrets.json
    3. GET /v1/portal/personal/context via actor_token
    Returns empty string if not available.
    """
    env_email = os.getenv("AXME_USER_EMAIL", "").strip()
    if env_email:
        return env_email
    secrets = _read_cli_secrets()
    from_secrets = secrets.get("email", "").strip()
    if from_secrets:
        return from_secrets
    try:
        actor_token = secrets.get("actor_token", "").strip()
        effective_key = api_key or secrets.get("api_key", "").strip()
        effective_url = base_url or secrets.get("base_url", "").strip() or _DEFAULT_BASE_URL
        if actor_token and effective_key:
            req = urllib.request.Request(
                f"{effective_url}/v1/portal/personal/context",
                headers={
                    "X-Api-Key": effective_key,
                    "Authorization": f"Bearer {actor_token}",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read())
            email = (body.get("account") or {}).get("email", "").strip()
            if email:
                return email
    except Exception:
        pass
    return ""


class AuthContext:
    """Loaded auth credentials for a single session."""

    def __init__(self) -> None:
        self.api_key   = require_api_key()
        self.base_url  = require_base_url()
        self.actor_token = require_actor_token()
        self._human_contact: str | None = None
        self._initiator_address: str | None = None

    def human_contact(self) -> str:
        if self._human_contact is None:
            self._human_contact = resolve_human_contact(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._human_contact

    def initiator_address(self) -> str:
        """Return the SA address of the current API key owner (for reply_to inbox).

        Fetched once from GET /v1/me and cached. Returns empty string on failure.
        """
        if self._initiator_address is None:
            self._initiator_address = _resolve_initiator_address(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._initiator_address


def _resolve_initiator_address(api_key: str, base_url: str) -> str:
    """Call GET /v1/me to get the SA address of the API key owner."""
    try:
        req = urllib.request.Request(
            f"{base_url}/v1/me",
            headers={"X-Api-Key": api_key},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read())
        return str(
            body.get("address")
            or (body.get("service_account") or {}).get("address")
            or ""
        )
    except Exception:
        return ""
