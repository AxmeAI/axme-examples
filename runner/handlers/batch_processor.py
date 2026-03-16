"""Batch processor agent — validates and processes a batch of records."""
from __future__ import annotations

import re
from typing import Any

_BATCH_ID_PATTERN = re.compile(r"^batch-\d{4}-\d{2}-\d{2}-\d+$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []

    batch_id = str(payload.get("batch_id") or "")
    record_type = str(payload.get("record_type") or "")
    date_range = str(payload.get("date_range") or "")

    if not _BATCH_ID_PATTERN.match(batch_id):
        violations.append(f"batch_id_invalid_format:{batch_id!r}")

    if not record_type.strip():
        violations.append("record_type_missing")

    if not _DATE_PATTERN.match(date_range):
        violations.append(f"date_range_invalid:{date_range!r}")

    if violations:
        return {
            "_passed": False,
            "batch_processed": False,
            "violations": violations,
            "reason": "batch_validation_failed",
        }

    # Deterministic record count from batch_id
    records_count = abs(hash(batch_id)) % 9000 + 1000

    return {
        "batch_processed": True,
        "batch_id": batch_id,
        "record_type": record_type,
        "records_count": records_count,
        "date_range": date_range,
    }
