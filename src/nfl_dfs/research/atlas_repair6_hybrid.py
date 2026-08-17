"""Strict score-free receipt for the ATLAS repair5/repair6 hybrid population."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from nfl_dfs.research.atlas_repair6 import (
    EXPECTED_CELLS,
    PROTOCOL_SHA256,
    REPAIR5_RUN_ID,
    REPAIR6_RUN_ID,
)


SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
REPAIR5_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    f"{REPAIR5_RUN_ID}"
)
REPAIR6_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    f"{REPAIR6_RUN_ID}"
)
PROOF_PREFIX = REPAIR6_PREFIX + "-proof"
REPAIR5_CODE_SHA = "60f296fdad769b30c0bb7334118698f156e462b9"
REPAIR5_IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
)


def _validate_object(value: Mapping[str, Any], uri: str) -> None:
    if value.get("uri") != uri or \
            not str(value.get("generation", "")).isdigit() or \
            int(value.get("bytes") or 0) <= 0 or \
            not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", ""))):
        raise ValueError("ATLAS repair6 hybrid object receipt differs")


def _validate_execution(
    value: Mapping[str, Any], row: Sequence[str], *, image: str, code_sha: str,
    grid_command: str,
) -> None:
    season, week, _source, job, execution, uri = row
    if value.get("metadata", {}).get("name") != execution:
        raise ValueError("ATLAS repair6 hybrid execution name differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise ValueError("ATLAS repair6 hybrid task shape differs")
    container = containers[0]
    env = {item.get("name"): str(item.get("value", ""))
           for item in container.get("env", [])}
    if container.get("image") != image or \
            container.get("command") != ["python"] or \
            container.get("args") != [
                "-c", grid_command, "--season", season, "--week", week,
                "--output-uri", uri,
            ] or env != {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image} or \
            container.get("resources", {}).get("limits") != {
                "cpu": "8", "memory": "32Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "43200" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise ValueError("ATLAS repair6 hybrid execution contract differs")
    status = value.get("status", {})
    completed = [item for item in status.get("conditions", [])
                 if item.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            int(status.get("succeededCount") or 0) != 1 or \
            int(status.get("failedCount") or 0) != 0 or \
            int(status.get("cancelledCount") or 0) != 0 or \
            not status.get("completionTime"):
        raise ValueError("ATLAS repair6 hybrid execution was not successful")


def validate_hybrid_receipt(
    receipt: Mapping[str, Any], *, repair5_grid_command: str,
    repair6_grid_command: str,
) -> dict[str, Any]:
    """Validate the exact 54-cell population without opening a shard body."""
    fixed = {
        "version": "atlas-repair6-hybrid-population-receipt-v1",
        "run_id": REPAIR6_RUN_ID,
        "repair5_run_id": REPAIR5_RUN_ID,
        "repair5_prefix": REPAIR5_PREFIX,
        "repair6_prefix": REPAIR6_PREFIX,
        "proof_prefix": PROOF_PREFIX,
        "protocol_sha256": PROTOCOL_SHA256,
        "repair5_code_sha": REPAIR5_CODE_SHA,
        "repair5_image": REPAIR5_IMAGE,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "effect_fields_inspected": False,
        "production_change_licensed": False,
        "disposition": "valid-complete-repair6-hybrid-population",
        "cells": 54,
    }
    if any(receipt.get(key) != value for key, value in fixed.items()) or \
            not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("repair6_code_sha", ""))) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", str(receipt.get("repair6_image", ""))):
        raise ValueError("ATLAS repair6 hybrid receipt identity differs")
    for key in (
        "repair5_terminal_census_sha256", "eligibility_classification_sha256",
        "code_diff_proof_sha256", "dual_canary_completion_sha256",
        "repair6_grid_release_sha256", "accepted_execution_ledger_sha256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(key, ""))):
            raise ValueError("ATLAS repair6 hybrid source hash differs")

    accepted = receipt.get("accepted_rows")
    eligible = receipt.get("eligible_cells")
    objects = receipt.get("objects")
    executions = receipt.get("execution_metadata")
    job_names = receipt.get("job_execution_names")
    inventories = receipt.get("prefix_inventories")
    primary = receipt.get("repair5_primary_rows")
    if not isinstance(accepted, list) or not isinstance(eligible, list) or \
            not isinstance(objects, dict) or not isinstance(executions, dict) or \
            not isinstance(job_names, dict) or not isinstance(inventories, dict) or \
            not isinstance(primary, list):
        raise ValueError("ATLAS repair6 hybrid population fields differ")
    rows = [[str(field) for field in row] for row in accepted]
    primary_rows = [[str(field) for field in row] for row in primary]
    eligible_cells = {(int(row[0]), int(row[1])) for row in eligible
                      if isinstance(row, list) and len(row) == 2}
    expected = set(EXPECTED_CELLS)
    if len(rows) != 54 or any(len(row) != 6 for row in rows) or \
            {(int(row[0]), int(row[1])) for row in rows} != expected or \
            len({row[4] for row in rows}) != 54 or \
            len(primary_rows) != 54 or any(len(row) != 5 for row in primary_rows) or \
            {(int(row[0]), int(row[1])) for row in primary_rows} != expected or \
            not eligible_cells or not eligible_cells <= expected:
        raise ValueError("ATLAS repair6 hybrid exact cell grid differs")
    primary_by_cell = {(int(row[0]), int(row[1])): row for row in primary_rows}
    object_uris = set()
    for row in rows:
        season, week = int(row[0]), int(row[1])
        source, job, execution, uri = row[2:]
        key = f"{season}-{week}"
        expected_source = "repair6" if (season, week) in eligible_cells else "repair5"
        expected_job = f"atlas-md-s{season}-w{week}-r{6 if expected_source == 'repair6' else 5}"
        expected_prefix = REPAIR6_PREFIX if expected_source == "repair6" else REPAIR5_PREFIX
        if source != expected_source or job != expected_job or \
                not execution.startswith(job + "-") or \
                uri != f"{expected_prefix}/slate-{season}-{week}.json" or \
                key not in objects or key not in executions:
            raise ValueError("ATLAS repair6 hybrid accepted-cell binding differs")
        primary_row = primary_by_cell[(season, week)]
        expected_primary_job = f"atlas-md-s{season}-w{week}-r5"
        if primary_row[2] != expected_primary_job or \
                not primary_row[3].startswith(expected_primary_job + "-") or \
                primary_row[4] != f"{REPAIR5_PREFIX}/slate-{season}-{week}.json":
            raise ValueError("ATLAS repair6 hybrid primary-cell binding differs")
        if source == "repair5" and [row[0], row[1], row[3], row[4], row[5]] != primary_row:
            raise ValueError("ATLAS repair6 hybrid reused execution differs")
        _validate_object(objects[key], uri)
        _validate_execution(
            executions[key], row,
            image=receipt["repair6_image"] if source == "repair6" else REPAIR5_IMAGE,
            code_sha=receipt["repair6_code_sha"] if source == "repair6" else REPAIR5_CODE_SHA,
            grid_command=repair6_grid_command if source == "repair6" else repair5_grid_command,
        )
        object_uris.add(uri)

    r5_uris = {row[5] for row in rows if row[2] == "repair5"}
    r6_uris = {row[5] for row in rows if row[2] == "repair6"}
    proof_uri = f"{PROOF_PREFIX}/slate-2023-1.json"
    if set(inventories) != {"repair5", "repair6", "proof"} or \
            set(inventories["repair5"]) != r5_uris or \
            set(inventories["repair6"]) != r6_uris or \
            set(inventories["proof"]) != {proof_uri} or \
            object_uris != r5_uris | r6_uris:
        raise ValueError("ATLAS repair6 hybrid object inventory differs")

    accepted_by_cell = {(int(row[0]), int(row[1])): row for row in rows}
    for season, week in EXPECTED_CELLS:
        primary_row = primary_by_cell[(season, week)]
        accepted_row = accepted_by_cell[(season, week)]
        r5_job = f"atlas-md-s{season}-w{week}-r5"
        r6_job = f"atlas-md-s{season}-w{week}-r6"
        if job_names.get(r5_job) != [primary_row[3]]:
            raise ValueError("ATLAS repair6 hybrid repair5 execution population differs")
        expected_r6 = [accepted_row[4]] if (season, week) in eligible_cells else []
        if job_names.get(r6_job) != expected_r6:
            raise ValueError("ATLAS repair6 hybrid repair6 execution population differs")
    proof_execution = str(receipt.get("proof_execution", ""))
    if job_names.get("atlas-md-s2023-w1-r6-proof") != [proof_execution] or \
            not proof_execution.startswith("atlas-md-s2023-w1-r6-proof-") or \
            set(job_names) != {
                *(f"atlas-md-s{s}-w{w}-r5" for s, w in EXPECTED_CELLS),
                *(f"atlas-md-s{s}-w{w}-r6" for s, w in EXPECTED_CELLS),
                "atlas-md-s2023-w1-r6-proof",
            }:
        raise ValueError("ATLAS repair6 hybrid complete execution census differs")
    return {
        "accepted_rows": rows,
        "eligible_cells": sorted(eligible_cells),
        "objects": objects,
    }


__all__ = [
    "PROOF_PREFIX", "REPAIR5_CODE_SHA", "REPAIR5_IMAGE", "REPAIR5_PREFIX",
    "REPAIR6_PREFIX", "validate_hybrid_receipt",
]
