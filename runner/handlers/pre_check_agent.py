"""Pre-check agent — validates a PR before CI/CD proceeds."""
from __future__ import annotations

import re
from typing import Any

_PR_ID_PATTERN = re.compile(r"^PR-\d+$")
_MAX_FILES_CHANGED = 500


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    checks_failed: list[str] = []

    pr_id = str(payload.get("pr_id") or "")
    repository = str(payload.get("repository") or "")
    branch = str(payload.get("branch") or "")
    author = str(payload.get("author") or "")
    files_changed = payload.get("files_changed", 0)

    if not _PR_ID_PATTERN.match(pr_id):
        checks_failed.append(f"pr_id_invalid_format:{pr_id!r}")

    if not repository.strip():
        checks_failed.append("repository_missing")

    if not author.strip():
        checks_failed.append("author_missing")

    if isinstance(files_changed, (int, float)) and files_changed > _MAX_FILES_CHANGED:
        checks_failed.append(f"pr_too_large:files_changed={files_changed}")

    passed = len(checks_failed) == 0

    result = {
        "_passed": passed,
        "pre_check_passed": passed,
        "checks_failed": checks_failed,
        "pr_id": pr_id,
        "repository": repository,
        "branch": branch,
        "author": author,
    }
    if not passed:
        result["reason"] = "pre_check_failed"
    return result
