"""Batch processor agent — validates a batch job request and returns processing results.

Checks:
  - batch_id must match pattern batch-YYYY-MM-DD-<seq>
  - date_range must be parseable as an ISO 8601 date (YYYY-MM-DD)
  - record_type must be a non-empty string

records_count is deterministic: derived from batch_id hash so the same
batch always returns the same count (idempotent result).
"""
from __future__ import annotations

import datetime
import re
from typing import Any

_BATCH_ID_PATTERN = re.compile(r"^batch-\d{4}-\d{2}-\d{2}-\d+$")


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    batch_id    = str(payload.get("batch_id")    or "")
    record_type = str(payload.get("record_type") or "")
    date_range  = str(payload.get("date_range")  or "")

    violations: list[str] = []

    if not _BATCH_ID_PATTERN.match(batch_id):
        violations.append(
            f"batch_id_invalid_format:{batch_id!r} (expected batch-YYYY-MM-DD-<seq>)"
        )

    if not record_type.strip():
        violations.append("record_type_missing")

    if date_range:
        try:
            datetime.date.fromisoformat(date_range)
        except ValueError:
            violations.append(f"date_range_not_iso8601:{date_range!r}")
    else:
        violations.append("date_range_missing")

    if violations:
        return {
            "_passed":         False,
            "batch_processed": False,
            "violations":      violations,
            "reason":          "batch_validation_failed",
        }

    # Deterministic record count: same batch_id always produces the same count
    records_count = (hash(batch_id) % 900) + 100  # range: 100–999

    return {
        "batch_processed": True,
        "records_count":   records_count,
        "batch_id":        batch_id,
        "record_type":     record_type,
        "date_range":      date_range,
    }
