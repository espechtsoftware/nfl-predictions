"""Score-free classification and receipts for the ATLAS repair6 extension."""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence


REPAIR5_RUN_ID = "20260816-atlas-matched-diversity-mvp-v1-repair5"
REPAIR6_RUN_ID = "20260817-atlas-matched-diversity-mvp-v1-repair6"
PROTOCOL_SHA256 = (
    "b4a98543b1dcd776d50ae00e380fbc695346debb0de6452131fdfd0ba7c2820a"
)
EXPECTED_CELLS = tuple(
    (season, week)
    for season in (2023, 2024, 2025) for week in range(1, 19)
)
TRACE_RE = re.compile(
    r"(?:^|\n)RuntimeError: ATLAS world ([0-9]+) identity tiebreak is infeasible\s*$"
)
FORBIDDEN_FAILURE_TOKENS = (
    "configured memory limit", "timeout", "sigkill", "signal 9",
    "pulpsolvererror", "cbc child", "internal error running task",
)


def canonical_json(value: object) -> bytes:
    return (json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode()


def _digest_text(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def classify_repair5_for_repair6(
    *,
    census: Mapping[str, Any],
    primary_classification: Mapping[str, Any],
    attempt_resolution: Mapping[str, Any],
    object_inventory: Sequence[str],
    error_logs: Mapping[str, str],
) -> dict[str, Any]:
    """Classify a complete failed repair5 population without opening shards."""
    if census.get("version") != \
            "atlas-matched-diversity-repair5-terminal-census-v1" or \
            census.get("run_id") != REPAIR5_RUN_ID or \
            census.get("protocol_sha256") != \
            "94a792d80c4a908aed56034add9635478c738a29522554670c09360458561d0f" or \
            census.get("uses_realized_outcomes") is not False or \
            census.get("effect_fields_inspected") is not False or \
            census.get("scientific_result_valid") is not False or \
            census.get("historical_scoring_licensed") is not False or \
            census.get("production_change_licensed") is not False or \
            census.get("executions") != 54 or \
            int(census.get("terminal_failed") or 0) < 1 or \
            int(census.get("terminal_succeeded") or 0) + \
            int(census.get("terminal_failed") or 0) != 54:
        raise ValueError("ATLAS repair6 terminal census differs")
    if primary_classification.get("version") != \
            "atlas-repair5-primary-attempt-classification-v1" or \
            primary_classification.get("run_id") != REPAIR5_RUN_ID or \
            primary_classification.get("disposition") != \
            "terminal-invalid-primary" or \
            primary_classification.get("uses_realized_outcomes") is not False or \
            primary_classification.get("effect_fields_inspected") is not False or \
            primary_classification.get("primary_executions") != 54 or \
            int(primary_classification.get("ineligible_failures") or 0) < 1:
        raise ValueError("ATLAS repair6 primary classification differs")
    if attempt_resolution.get("version") != \
            "atlas-repair5-attempt-resolution-v1" or \
            attempt_resolution.get("run_id") != REPAIR5_RUN_ID or \
            attempt_resolution.get("disposition") != "terminal-invalid-primary" or \
            attempt_resolution.get("uses_realized_outcomes") is not False or \
            attempt_resolution.get("effect_fields_inspected") is not False or \
            attempt_resolution.get("primary_executions") != 54 or \
            attempt_resolution.get("retry_executions") != 0 or \
            attempt_resolution.get("accepted_executions") != 0:
        raise ValueError("ATLAS repair6 attempt resolution differs")

    terminal = census.get("terminal")
    classified = primary_classification.get("cells")
    if not isinstance(terminal, list) or not isinstance(classified, list) or \
            len(terminal) != 54 or len(classified) != 54:
        raise ValueError("ATLAS repair6 cell population differs")
    terminal_by_cell = {
        (int(row.get("season", -1)), int(row.get("week", -1))): row
        for row in terminal if isinstance(row, Mapping)
    }
    classified_by_cell = {
        (int(row.get("season", -1)), int(row.get("week", -1))): row
        for row in classified if isinstance(row, Mapping)
    }
    if set(terminal_by_cell) != set(EXPECTED_CELLS) or \
            set(classified_by_cell) != set(EXPECTED_CELLS):
        raise ValueError("ATLAS repair6 cell identities differ")
    inventory = [str(uri) for uri in object_inventory if str(uri)]
    if len(inventory) != len(set(inventory)) or \
            len(inventory) != int(census.get("output_objects_present") or 0):
        raise ValueError("ATLAS repair6 repair5 inventory differs")
    inventory_set = set(inventory)

    eligible = []
    closed = []
    successes = []
    failed_executions = set()
    for season, week in EXPECTED_CELLS:
        terminal_row = terminal_by_cell[(season, week)]
        classified_row = classified_by_cell[(season, week)]
        execution = str(terminal_row.get("execution", ""))
        uri = str(classified_row.get("uri", ""))
        if terminal_row.get("job") != f"atlas-md-s{season}-w{week}-r5" or \
                classified_row.get("job") != terminal_row.get("job") or \
                classified_row.get("primary_execution") != execution or \
                uri != (
                    "gs://nfl-predictions-503414-raw/research/"
                    "atlas-matched-diversity-runs/"
                    f"{REPAIR5_RUN_ID}/slate-{season}-{week}.json"
                ):
            raise ValueError("ATLAS repair6 repair5 cell binding differs")
        status = str(terminal_row.get("status", ""))
        object_present = uri in inventory_set
        if classified_row.get("object_present") is not object_present:
            raise ValueError("ATLAS repair6 object-presence binding differs")
        if status == "True":
            if classified_row.get("eligibility") != "primary-success" or \
                    not object_present or execution in error_logs:
                raise ValueError("ATLAS repair6 successful reuse cell differs")
            successes.append({
                "season": season, "week": week, "job": terminal_row["job"],
                "execution": execution, "uri": uri,
            })
            continue
        if status != "False" or object_present or \
                classified_row.get("eligibility") != \
                "ineligible-primary-failure":
            raise ValueError("ATLAS repair6 failed cell contract differs")
        failed_executions.add(execution)
        log = error_logs.get(execution)
        if not isinstance(log, str) or not log.strip():
            raise ValueError("ATLAS repair6 failed cell log is missing")
        lowered = log.lower()
        match = TRACE_RE.search(log)
        exact_class = (
            terminal_row.get("reason") == "NonZeroExitCode"
            and "exit code: 1" in str(terminal_row.get("message", "")).lower()
            and match is not None
            and sum(1 for _ in TRACE_RE.finditer(log)) == 1
            and not any(token in lowered for token in FORBIDDEN_FAILURE_TOKENS)
        )
        row = {
            "season": season, "week": week, "job": terminal_row["job"],
            "primary_execution": execution, "repair5_uri": uri,
            "log_sha256": _digest_text(log),
            "world": int(match.group(1)) if match else None,
        }
        if exact_class:
            eligible.append(row)
        else:
            closed.append({**row, "reason": "non-tiebreak-terminal-failure"})
    if set(error_logs) != failed_executions:
        raise ValueError("ATLAS repair6 failed execution log population differs")
    if len(successes) != int(census["terminal_succeeded"]) or \
            len(eligible) + len(closed) != int(census["terminal_failed"]):
        raise ValueError("ATLAS repair6 terminal counts differ")

    repair6_licensed = bool(eligible) and not closed
    return {
        "version": "atlas-repair6-eligibility-classification-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "repair5_run_id": REPAIR5_RUN_ID,
        "repair6_run_id": REPAIR6_RUN_ID,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "effect_fields_inspected": False,
        "production_change_licensed": False,
        "repair5_successes": len(successes),
        "repair5_failures": len(eligible) + len(closed),
        "eligible_tiebreak_failures": eligible,
        "ineligible_failures": closed,
        "reused_success_cells": successes,
        "repair6_launch_licensed": repair6_licensed,
        "disposition": (
            "repair6-dual-canary-licensed" if repair6_licensed
            else "repair6-closed-by-non-tiebreak-failure"
        ),
    }


__all__ = [
    "EXPECTED_CELLS", "PROTOCOL_SHA256", "REPAIR5_RUN_ID", "REPAIR6_RUN_ID",
    "canonical_json", "classify_repair5_for_repair6",
]
