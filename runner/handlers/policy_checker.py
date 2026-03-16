"""Policy checker agent — validates access requests against RBAC rules.

Checks:
  - resource: protected resources (prod-*, secrets-*) require a non-empty justification
  - access_type: must be in the allowed set for the resource class
  - requestor: must be a non-empty string
  - justification: required for sensitive resources
"""
from __future__ import annotations

from typing import Any

_READ_ONLY_TYPES = {"LIST", "GET", "DESCRIBE", "READ"}
_ALL_ACCESS_TYPES = {"WRITE", "READ", "LIST", "EXECUTE", "ADMIN", "GET", "DESCRIBE", "DELETE"}
_PROTECTED_PREFIXES = ("prod-", "secrets-", "pki-", "vault-", "hsm-")


def _is_protected(resource: str) -> bool:
    return any(resource.startswith(p) for p in _PROTECTED_PREFIXES)


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    resource = str(payload.get("resource") or "")
    access_type = str(payload.get("access_type") or "").upper()
    requestor = str(payload.get("requestor") or "")
    justification = str(payload.get("justification") or "")

    violations: list[str] = []

    if not requestor.strip():
        violations.append("requestor_missing")

    if access_type not in _ALL_ACCESS_TYPES:
        violations.append(f"access_type_unknown:{access_type!r}")

    protected = _is_protected(resource)

    if protected:
        if not justification.strip():
            violations.append(
                f"justification_required_for_protected_resource:{resource!r}"
            )
        if access_type not in _READ_ONLY_TYPES:
            violations.append(
                f"write_access_to_protected_resource_requires_cab_approval:access_type="
                f"{access_type!r},resource={resource!r}"
            )

    passed = len(violations) == 0
    checked_policies = [
        "requestor_present",
        "access_type_allowlist",
        "protected_resource_justification",
        "write_access_to_protected",
    ]

    result = {
        "_passed": passed,
        "policy_passed": passed,
        "violations": violations,
        "checked_policies": checked_policies,
        "resource": resource,
        "access_type": access_type,
        "is_protected": protected,
    }
    if not passed:
        result["reason"] = "policy_violations"
    return result
