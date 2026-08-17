"""Outcome-blind bounded-attempt law for same-law capacity generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping


LITERAL_PLATFORM_ERROR = re.compile(
    r"Internal error running task\.?", re.IGNORECASE,
)
INELIGIBLE_TOKENS = (
    "configured memory limit",
    "memory limit",
    "timeout",
    "signal",
    "sigkill",
    "solver",
    "cbc",
    "nonzero exit",
    "cancel",
)


@dataclass(frozen=True)
class OutputInventory:
    candidate_rows: int
    feature_rows: int
    lineup_rows: int
    artifact_objects: int

    def __post_init__(self) -> None:
        if any(value < 0 for value in asdict(self).values()):
            raise ValueError("capacity output inventory cannot be negative")

    @property
    def empty(self) -> bool:
        return not any(asdict(self).values())

    @property
    def complete_season(self) -> bool:
        return (
            self.candidate_rows > 0
            and self.feature_rows > 0
            and self.lineup_rows > 0
            and self.artifact_objects == 18
        )


def _completed_condition(execution: Mapping[str, Any]) -> Mapping[str, Any] | None:
    rows = [
        row for row in execution.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"
    ]
    if len(rows) != 1:
        raise ValueError("capacity execution completion condition differs")
    row = rows[0]
    if row.get("status") == "Unknown":
        return None
    if row.get("status") not in {"True", "False"} or not execution.get(
        "status", {}
    ).get("completionTime"):
        raise ValueError("capacity execution terminal condition differs")
    return row


def classify_primary_attempt(
    execution: Mapping[str, Any],
    inventory: OutputInventory,
    *,
    is_canary: bool,
) -> dict[str, Any]:
    """Classify one primary without inspecting identities, scores, or outcomes."""
    condition = _completed_condition(execution)
    if condition is None:
        return {
            "eligibility": "pending-primary",
            "terminal": False,
            "object_or_row_output_present": not inventory.empty,
            "replacement_licensed": False,
            "effect_fields_inspected": False,
        }
    status = execution.get("status", {})
    final_status = str(condition["status"])
    message = str(condition.get("message", "")).strip()
    common = {
        "terminal": True,
        "status": final_status,
        "message": message,
        "reason": str(condition.get("reason", "")),
        "completion_time": status["completionTime"],
        "object_or_row_output_present": not inventory.empty,
        "inventory": asdict(inventory),
        "effect_fields_inspected": False,
    }
    if final_status == "True":
        accepted = (
            int(status.get("succeededCount") or 0) == 1
            and int(status.get("failedCount") or 0) == 0
            and int(status.get("retriedCount") or 0) == 0
            and inventory.complete_season
        )
        return {
            **common,
            "eligibility": (
                "primary-success"
                if accepted else "terminal-invalid-success-contract"
            ),
            "replacement_licensed": False,
        }

    lower = message.lower()
    literal = LITERAL_PLATFORM_ERROR.fullmatch(message) is not None
    blocked = any(token in lower for token in INELIGIBLE_TOKENS)
    eligible = (
        not is_canary
        and literal
        and not blocked
        and inventory.empty
        and int(status.get("succeededCount") or 0) == 0
        and int(status.get("failedCount") or 0) == 1
        and int(status.get("cancelledCount") or 0) == 0
        and int(status.get("retriedCount") or 0) == 0
    )
    return {
        **common,
        "eligibility": (
            "eligible-platform-replacement"
            if eligible else "terminal-invalid-primary"
        ),
        "replacement_licensed": eligible,
    }


__all__ = [
    "INELIGIBLE_TOKENS",
    "LITERAL_PLATFORM_ERROR",
    "OutputInventory",
    "classify_primary_attempt",
]
