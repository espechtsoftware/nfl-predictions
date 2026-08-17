"""Pure receipt validation for the frozen capacity-generation population."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


CELL_FIELDS = ("replicate", "season", "job", "execution")


def _cell(row: Mapping[str, Any]) -> tuple[str, int]:
    return str(row.get("replicate", "")), int(row.get("season", -1))


def _indexed(
    rows: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> dict[tuple[str, int], Mapping[str, Any]]:
    result: dict[tuple[str, int], Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"capacity {label} row differs")
        cell = _cell(row)
        if cell in result:
            raise ValueError(f"capacity {label} cell repeats")
        result[cell] = row
    return result


def validate_attempt_ledgers(
    manifest: Mapping[str, Any],
    primary_rows: Sequence[Mapping[str, Any]],
    retry_rows: Sequence[Mapping[str, Any]],
    accepted_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate exact primary/retry/accepted identity binding for 135 cells."""
    schedule = manifest.get("schedule")
    if not isinstance(schedule, list) or len(schedule) != 135 or \
            manifest.get("primary_executions") != 135 or \
            manifest.get("remaining_cells_released_before_canary") != 0 or \
            manifest.get("max_task_retries") != 0 or \
            manifest.get("max_external_replacements_per_cell") != 1 or \
            manifest.get("uses_realized_outcomes") is not False:
        raise ValueError("capacity generation manifest receipt differs")
    schedule_by_cell = _indexed(schedule, label="schedule")
    expected_order = [_cell(row) for row in schedule]
    if expected_order[0] != ("R5", 2023):
        raise ValueError("capacity generation canary schedule differs")

    primary = _indexed(primary_rows, label="primary")
    retries = _indexed(retry_rows, label="retry")
    accepted = _indexed(accepted_rows, label="accepted")
    expected = set(expected_order)
    if len(primary_rows) != 135 or set(primary) != expected:
        raise ValueError("capacity primary population differs")
    if len(accepted_rows) != 135 or set(accepted) != expected:
        raise ValueError("capacity accepted population differs")
    if len(retry_rows) != len(retries) or not set(retries) <= expected:
        raise ValueError("capacity retry population differs")
    if ("R5", 2023) in retries:
        raise ValueError("capacity canary is not retry eligible")

    executions: set[str] = set()
    for cell in expected_order:
        scheduled = schedule_by_cell[cell]
        primary_row = primary[cell]
        accepted_row = accepted[cell]
        job = str(scheduled.get("job", ""))
        primary_execution = str(primary_row.get("execution", ""))
        if any(
            primary_row.get(field) != scheduled.get(field)
            for field in ("replicate", "season", "job")
        ) or not primary_execution.startswith(job + "-"):
            raise ValueError("capacity primary identity differs")
        if primary_execution in executions:
            raise ValueError("capacity execution identity repeats")
        executions.add(primary_execution)
        expected_execution = primary_execution
        retry = retries.get(cell)
        if retry is not None:
            retry_execution = str(retry.get("retry_execution", ""))
            if any(
                retry.get(field) != scheduled.get(field)
                for field in ("replicate", "season", "job")
            ) or retry.get("primary_execution") != primary_execution or \
                    retry_execution == primary_execution or \
                    not retry_execution.startswith(job + "-") or \
                    retry.get("eligibility") != "eligible-platform-replacement":
                raise ValueError("capacity retry binding differs")
            if retry_execution in executions:
                raise ValueError("capacity execution identity repeats")
            executions.add(retry_execution)
            expected_execution = retry_execution
        if any(
            accepted_row.get(field) != scheduled.get(field)
            for field in ("replicate", "season", "job")
        ) or accepted_row.get("execution") != expected_execution:
            raise ValueError("capacity accepted binding differs")

    return {
        "version": "same-law-capacity-attempt-ledger-validation-v1",
        "run_id": manifest.get("run_id"),
        "primary_executions": 135,
        "retry_executions": len(retries),
        "accepted_executions": 135,
        "canary_accepted_as_primary": accepted[("R5", 2023)]["execution"]
        == primary[("R5", 2023)]["execution"],
        "task_max_retries": 0,
        "max_external_replacements_per_cell": 1,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "disposition": "valid-complete-attempt-ledgers",
    }


__all__ = ["CELL_FIELDS", "validate_attempt_ledgers"]
