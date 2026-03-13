"""Pre-check agent — validates a pull request before routing to human reviewer.

Checks:
  - pr_id must match pattern PR-<digits>
  - repository must be a non-empty string
  - author must be a valid email or non-empty identifier
  - files_changed must be a positive integer ≤ 500
    (oversized PRs are flagged for splitting before review)
"""
from __future__ import annotations

import re
from typing import Any

_PR_ID_PATTERN = re.compile(r"^PR-\d+$")
_MAX_FILES = 500


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    pr_id         = str(payload.get("pr_id")    or "")
    repository    = str(payload.get("repository") or "")
    author        = str(payload.get("author")   or "")
    files_changed = payload.get("files_changed")

    checks_passed: list[str] = []
    checks_failed: list[str] = []

    if _PR_ID_PATTERN.match(pr_id):
        checks_passed.append("pr_id_format")
    else:
        checks_failed.append(f"pr_id_invalid:{pr_id!r} (expected PR-<digits>)")

    if repository.strip():
        checks_passed.append("repository_present")
    else:
        checks_failed.append("repository_missing")

    if author.strip():
        checks_passed.append("author_present")
    else:
        checks_failed.append("author_missing")

    try:
        n_files = int(files_changed) if files_changed is not None else -1
        if n_files <= 0:
            checks_failed.append(f"files_changed_must_be_positive:{files_changed!r}")
        elif n_files > _MAX_FILES:
            checks_failed.append(
                f"pr_too_large:{n_files}_files_exceeds_limit_{_MAX_FILES}"
                "_split_pr_before_review"
            )
        else:
            checks_passed.append(f"pr_size_ok:{n_files}_files")
    except (TypeError, ValueError):
        checks_failed.append(f"files_changed_not_integer:{files_changed!r}")
        n_files = -1

    passed = len(checks_failed) == 0
    return {
        "_passed":         passed,
        "pre_check_passed": passed,
        "checks_passed":   checks_passed,
        "checks_failed":   checks_failed,
        "pr_id":           pr_id,
        "repository":      repository,
        **({"reason": "pre_check_failed", "violations": checks_failed} if not passed else {}),
    }
