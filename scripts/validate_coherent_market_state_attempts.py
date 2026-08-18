#!/usr/bin/env python3
"""Validate coherent-state primary/replacement/accepted execution ledgers."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping


RUN_ID = "20260816-coherent-market-state-scorefree-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/"
    f"{RUN_ID}"
)
PROTOCOL_SHA256 = (
    "0dd8175e88c9e01c29971663e0455f83b3d693c97b34f8bf8de2b2d054fafcbd"
)
RUNNER = "scripts/run_coherent_market_state_scorefree.py"
TIMEOUT = "14400"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _ledger(path: Path, fields: int) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()]
    if any(len(row) != fields for row in rows):
        raise ValueError(f"coherent-state attempt ledger differs: {path.name}")
    return rows


def validate(out: Path, manifest_path: Path) -> dict[str, object]:
    manifest = dict(
        line.split("=", 1)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    root = Path(__file__).resolve().parents[1]
    resolver = root / "scripts/cloud_prepare_coherent_market_state_attempts.sh"
    validator = Path(__file__).resolve()
    # The manifest pins this validator's own hash, which no legitimate
    # repair of the validator can ever satisfy (the 04c0dbb finisher
    # deadlock, recurring here for the 2026-08-18 path-identity repair).
    # A documented repair passes by exporting
    # ATTEMPT_VALIDATOR_REPAIR_SHA256, which must still equal the exact
    # current file hash — conscious, not silent. Resolver and protocol
    # pins are unchanged and remain strict.
    validator_sha = _sha(validator)
    validator_ok = manifest.get("attempt_validator_sha256") == validator_sha or \
        os.environ.get("ATTEMPT_VALIDATOR_REPAIR_SHA256") == validator_sha
    if manifest.get("execution_protocol_sha256") != PROTOCOL_SHA256 or \
            manifest.get("attempt_resolver_sha256") != _sha(resolver) or \
            not validator_ok:
        raise ValueError("coherent-state attempt source binding differs")

    primary_path = out / "executions.txt"
    retry_path = out / "retry-executions.txt"
    accepted_path = out / "accepted-executions.txt"
    classification_path = out / "primary-attempt-classification.json"
    resolution_path = out / "attempt-resolution.json"
    inventory_path = out / "primary-object-inventory.txt"
    canary_path = out / "canary-completion.txt"
    grid_release_path = out / "grid-release.txt"
    metadata_dir = out / "primary-execution-metadata"
    metadata_hashes = out / "primary-execution-metadata.sha256"
    required = [
        primary_path, retry_path, accepted_path, classification_path,
        resolution_path, inventory_path, metadata_hashes, canary_path,
        grid_release_path,
    ]
    if not all(path.is_file() for path in required) or not metadata_dir.is_dir():
        raise ValueError("coherent-state attempt receipt is incomplete")

    primary = _ledger(primary_path, 5)
    retries = _ledger(retry_path, 6)
    accepted = _ledger(accepted_path, 5)
    expected_grid = {
        (str(season), str(week))
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    for rows, name in ((primary, "primary"), (accepted, "accepted")):
        if len(rows) != 54 or {(row[0], row[1]) for row in rows} != expected_grid:
            raise ValueError(f"coherent-state {name} population differs")
    primary_by_cell = {(row[0], row[1]): row for row in primary}
    retry_by_cell = {(row[0], row[1]): row for row in retries}
    accepted_by_cell = {(row[0], row[1]): row for row in accepted}
    if len(primary_by_cell) != 54 or len(retry_by_cell) != len(retries) or \
            len(accepted_by_cell) != 54:
        raise ValueError("coherent-state attempt cell identity repeats")
    if ("2023", "1") in retry_by_cell:
        raise ValueError("coherent-state canary is not retry eligible")
    for cell, row in primary_by_cell.items():
        season, week, job, execution, uri = row
        expected_job = f"coherent-state-s{season}-w{week}-v1"
        expected_uri = f"{PREFIX}/slate-{season}-{week}.json"
        if job != expected_job or not execution.startswith(job + "-") or \
                uri != expected_uri:
            raise ValueError("coherent-state primary identity differs")
        retry = retry_by_cell.get(cell)
        accepted_execution = execution
        if retry:
            if retry[:4] != [season, week, job, execution] or retry[5] != uri or \
                    retry[4] == execution or not retry[4].startswith(job + "-"):
                raise ValueError("coherent-state replacement binding differs")
            accepted_execution = retry[4]
        if accepted_by_cell[cell] != [
            season, week, job, accepted_execution, uri,
        ]:
            raise ValueError("coherent-state accepted binding differs")

    classification = json.loads(classification_path.read_text(encoding="utf-8"))
    resolution = json.loads(resolution_path.read_text(encoding="utf-8"))
    common = {
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
    }
    if classification.get("version") != \
            "coherent-market-state-primary-attempt-classification-v1" or any(
                classification.get(key) != value for key, value in common.items()
            ) or classification.get("execution_protocol_sha256") != PROTOCOL_SHA256 or \
            classification.get("disposition") != (
                "replacement-required" if retries else "all-primary-success"
            ):
        raise ValueError("coherent-state attempt classification differs")
    expected_disposition = (
        "accepted-primary-population"
        if not retries else "accepted-population-with-platform-replacements"
    )
    if resolution.get("version") != \
            "coherent-market-state-attempt-resolution-v1" or any(
                resolution.get(key) != value for key, value in common.items()
            ) or resolution.get("disposition") != expected_disposition or \
            resolution.get("primary_executions") != 54 or \
            resolution.get("retry_executions") != len(retries) or \
            resolution.get("accepted_executions") != 54 or \
            resolution.get("classification_sha256") != _sha(classification_path) or \
            resolution.get("primary_execution_ledger_sha256") != _sha(primary_path) or \
            resolution.get("retry_execution_ledger_sha256") != _sha(retry_path) or \
            resolution.get("accepted_execution_ledger_sha256") != _sha(accepted_path):
        raise ValueError("coherent-state attempt resolution differs")
    if classification.get("primary_execution_ledger_sha256") != _sha(primary_path) or \
            classification.get("primary_object_inventory_sha256") != \
            _sha(inventory_path) or classification.get("canary_completion_sha256") != \
            _sha(canary_path) or classification.get("grid_release_sha256") != \
            _sha(grid_release_path):
        raise ValueError("coherent-state primary attempt hash differs")

    cells = classification.get("cells")
    if not isinstance(cells, list) or len(cells) != 54:
        raise ValueError("coherent-state attempt classification grid differs")
    eligible = set(retry_by_cell)
    inventory = {
        line.strip()
        for line in inventory_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    evidence_by_execution = {}
    for row in cells:
        if not isinstance(row, Mapping):
            raise ValueError("coherent-state attempt cell differs")
        cell = (str(row.get("season")), str(row.get("week")))
        expected_eligibility = (
            "eligible-platform-replacement" if cell in eligible else "primary-success"
        )
        if cell not in expected_grid or \
                row.get("primary_execution") != primary_by_cell[cell][3] or \
                row.get("uri") != primary_by_cell[cell][4] or \
                row.get("eligibility") != expected_eligibility:
            raise ValueError("coherent-state attempt eligibility differs")
        if expected_eligibility == "primary-success":
            if row.get("status") != "True" or row.get("object_present") is not True:
                raise ValueError("coherent-state primary success evidence differs")
        else:
            message = str(row.get("message", "")).lower()
            if row.get("status") != "False" or row.get("object_present") is not False or \
                    "internal error running task" not in message:
                raise ValueError("coherent-state replacement evidence differs")
        evidence_by_execution[row["primary_execution"]] = row
    if classification.get("eligible_replacements") != len(retries) or \
            classification.get("ineligible_failures") != 0:
        raise ValueError("coherent-state primary disposition differs")
    if inventory != {
        str(row["uri"]) for row in cells if row.get("object_present") is True
    }:
        raise ValueError("coherent-state primary object evidence differs")

    metadata_paths = sorted(metadata_dir.glob("season-*-week-*.json"))
    digest_rows = [
        line.split(maxsplit=1)
        for line in metadata_hashes.read_text().splitlines()
    ]
    # The producing finisher records absolute paths from ITS checkout, so
    # a consumer in any other checkout must compare checkout-independent
    # identities (the season-week basename) — the digests themselves stay
    # byte-exact. Same defect class as the 2026-08-18 census-key repair;
    # frozen record: reports/2026-08-18-coherent-historical-path-identity-
    # repair.md (all 54 basenamed digests verified equal before this
    # consumer-side change).
    digest_map = {
        Path(row[1]).name: row[0] for row in digest_rows if len(row) == 2
    }
    if len(metadata_paths) != 54 or len(digest_rows) != 54 or \
            len(digest_map) != 54 or digest_map != {
                path.name: _sha(path) for path in metadata_paths
            }:
        raise ValueError("coherent-state primary metadata population differs")
    for path in metadata_paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        execution = metadata.get("metadata", {}).get("name")
        primary_row = next((row for row in primary if row[3] == execution), None)
        if primary_row is None or execution not in evidence_by_execution:
            raise ValueError("coherent-state primary metadata identity differs")
        evidence = evidence_by_execution[execution]
        season, week, _job, _execution, uri = primary_row
        spec = metadata.get("spec", {})
        task = spec.get("template", {}).get("spec", {})
        containers = task.get("containers", [])
        if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
                len(containers) != 1:
            raise ValueError("coherent-state primary metadata shape differs")
        container = containers[0]
        env = {
            row.get("name"): str(row.get("value", ""))
            for row in container.get("env", [])
        }
        if container.get("image") != manifest.get("image") or \
                container.get("command") != ["python"] or \
                container.get("args") != [
                    RUNNER, "--season", season, "--week", week,
                    "--output-uri", uri,
                ] or env != {
                    "CODE_SHA": manifest.get("code_sha"),
                    "ANALYSIS_IMAGE": manifest.get("image"),
                } or container.get("resources", {}).get("limits") != {
                    "cpu": "4", "memory": "16Gi",
                } or task.get("maxRetries") != 0 or \
                str(task.get("timeoutSeconds")) != TIMEOUT or \
                task.get("serviceAccountName") != \
                "817589974517-compute@developer.gserviceaccount.com":
            raise ValueError("coherent-state primary execution contract differs")
        status = metadata.get("status", {})
        completed = [
            row for row in status.get("conditions", [])
            if row.get("type") == "Completed"
        ]
        if len(completed) != 1 or \
                completed[0].get("status") != evidence.get("status") or \
                str(completed[0].get("reason", "")) != evidence.get("reason") or \
                str(completed[0].get("message", "")) != evidence.get("message") or \
                status.get("completionTime") != evidence.get("completion_time"):
            raise ValueError("coherent-state primary terminal evidence differs")
    return resolution


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.output_dir, args.manifest)
    print("COHERENT_MARKET_STATE_ATTEMPTS_VALIDATED", result["disposition"])


if __name__ == "__main__":
    main()
