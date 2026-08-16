#!/usr/bin/env python3
"""Validate immutable primary/retry/accepted receipts for a lattice grid."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping


AMENDMENT_SHA256 = (
    "f846d4540d27c1480037b440aabf94c91a1a5121e6d9968ad5ef39f679ce63aa"
)
CONTRACTS = {
    "support": {
        "run_id": "20260816-constraint-lattice-control-support-census-v1",
        "job": "constraint-support-s{season}-w{week}-v1",
        "runner": "scripts/run_constraint_lattice_support_census.py",
        "timeout": "7200",
        "prefix": (
            "gs://nfl-predictions-503414-raw/research/"
            "constraint-lattice-support-runs/"
            "20260816-constraint-lattice-control-support-census-v1"
        ),
    },
    "scorefree": {
        "run_id": "20260816-constraint-lattice-scorefree-v1",
        "job": "constraint-lattice-s{season}-w{week}-v1",
        "runner": "scripts/run_constraint_lattice_scorefree.py",
        "timeout": "43200",
        "prefix": (
            "gs://nfl-predictions-503414-raw/research/constraint-lattice-runs/"
            "20260816-constraint-lattice-scorefree-v1"
        ),
    },
}


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _ledger(path: Path, fields: int) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()]
    if any(len(row) != fields for row in rows):
        raise ValueError(f"constraint-lattice attempt ledger differs: {path.name}")
    return rows


def _metadata_digest_set(path: Path) -> set[str]:
    rows = [line.split(maxsplit=1) for line in path.read_text().splitlines()]
    if any(len(row) != 2 for row in rows):
        raise ValueError("constraint-lattice primary metadata hash ledger differs")
    return {row[0] for row in rows}


def validate(mode: str, out: Path, manifest_path: Path) -> dict[str, object]:
    contract = CONTRACTS[mode]
    manifest = dict(
        line.split("=", 1)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    root = Path(__file__).resolve().parents[1]
    resolver = root / "scripts/cloud_prepare_constraint_lattice_attempts.sh"
    validator = Path(__file__).resolve()
    if manifest.get("attempt_amendment_sha256") != AMENDMENT_SHA256 or \
            manifest.get("attempt_resolver_sha256") != _sha(resolver) or \
            manifest.get("attempt_validator_sha256") != _sha(validator):
        raise ValueError("constraint-lattice attempt source binding differs")

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
        raise ValueError("constraint-lattice attempt receipt is incomplete")

    primary = _ledger(primary_path, 5)
    retries = _ledger(retry_path, 6)
    accepted = _ledger(accepted_path, 5)
    expected_grid = {
        (str(season), str(week))
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    }
    for rows, name in ((primary, "primary"), (accepted, "accepted")):
        if len(rows) != 54 or {(row[0], row[1]) for row in rows} != expected_grid:
            raise ValueError(f"constraint-lattice {name} population differs")
    if len({row[3] for row in primary}) != 54 or \
            len({row[3] for row in accepted}) != 54:
        raise ValueError("constraint-lattice execution identity repeats")

    primary_by_cell = {(row[0], row[1]): row for row in primary}
    retry_by_cell = {(row[0], row[1]): row for row in retries}
    accepted_by_cell = {(row[0], row[1]): row for row in accepted}
    if len(retry_by_cell) != len(retries):
        raise ValueError("constraint-lattice retry cell repeats")
    for cell, row in primary_by_cell.items():
        season, week, job, execution, uri = row
        expected_job = contract["job"].format(season=season, week=week)
        expected_uri = f"{contract['prefix']}/slate-{season}-{week}.json"
        if job != expected_job or not execution.startswith(job + "-") or \
                uri != expected_uri:
            raise ValueError("constraint-lattice primary identity differs")
        retry = retry_by_cell.get(cell)
        expected_execution = execution
        if retry:
            if retry[:4] != [season, week, job, execution] or retry[5] != uri or \
                    retry[4] == execution or not retry[4].startswith(job + "-"):
                raise ValueError("constraint-lattice retry binding differs")
            expected_execution = retry[4]
        if accepted_by_cell[cell] != [season, week, job, expected_execution, uri]:
            raise ValueError("constraint-lattice accepted binding differs")

    classification = json.loads(classification_path.read_text(encoding="utf-8"))
    resolution = json.loads(resolution_path.read_text(encoding="utf-8"))
    common = {
        "mode": mode,
        "run_id": contract["run_id"],
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
    }
    if classification.get("version") != \
            "constraint-lattice-primary-attempt-classification-v1" or any(
                classification.get(key) != value for key, value in common.items()
            ) or classification.get("bounded_retry_amendment_sha256") != \
            AMENDMENT_SHA256:
        raise ValueError("constraint-lattice attempt classification differs")
    if resolution.get("version") != "constraint-lattice-attempt-resolution-v1" or \
            any(resolution.get(key) != value for key, value in common.items()) or \
            resolution.get("disposition") not in {
                "accepted-primary-population",
                "accepted-population-with-platform-replacements",
            } or resolution.get("primary_executions") != 54 or \
            resolution.get("retry_executions") != len(retries) or \
            resolution.get("accepted_executions") != 54:
        raise ValueError("constraint-lattice attempt resolution differs")
    expected_disposition = (
        "accepted-primary-population"
        if not retries
        else "accepted-population-with-platform-replacements"
    )
    if resolution["disposition"] != expected_disposition or \
            resolution.get("classification_sha256") != _sha(classification_path) or \
            resolution.get("primary_execution_ledger_sha256") != _sha(primary_path) or \
            resolution.get("retry_execution_ledger_sha256") != _sha(retry_path) or \
            resolution.get("accepted_execution_ledger_sha256") != _sha(accepted_path):
        raise ValueError("constraint-lattice attempt hash binding differs")
    if classification.get("primary_execution_ledger_sha256") != _sha(primary_path) or \
            classification.get("primary_object_inventory_sha256") != _sha(inventory_path) or \
            classification.get("canary_completion_sha256") != _sha(canary_path) or \
            classification.get("grid_release_sha256") != _sha(grid_release_path):
        raise ValueError("constraint-lattice primary attempt hash differs")

    cells = classification.get("cells")
    if not isinstance(cells, list) or len(cells) != 54:
        raise ValueError("constraint-lattice attempt classification grid differs")
    eligible = set(retry_by_cell)
    seen = set()
    classification_by_execution = {}
    for row in cells:
        if not isinstance(row, Mapping):
            raise ValueError("constraint-lattice attempt cell differs")
        cell = (str(row.get("season")), str(row.get("week")))
        if cell not in expected_grid or cell in seen:
            raise ValueError("constraint-lattice attempt cell identity differs")
        seen.add(cell)
        expected_eligibility = (
            "eligible-platform-replacement" if cell in eligible else "primary-success"
        )
        if row.get("eligibility") != expected_eligibility or \
                row.get("primary_execution") != primary_by_cell[cell][3] or \
                row.get("uri") != primary_by_cell[cell][4]:
            raise ValueError("constraint-lattice attempt eligibility differs")
        if expected_eligibility == "primary-success":
            if row.get("status") != "True" or row.get("object_present") is not True:
                raise ValueError("constraint-lattice primary success evidence differs")
        else:
            message = str(row.get("message", "")).lower()
            if row.get("status") != "False" or row.get("object_present") is not False or \
                    "internal error running task" not in message or any(
                        token in message for token in (
                            "configured memory limit", "timeout", "signal", "sigkill",
                            "solver", "cbc", "nonzero exit",
                        )
                    ):
                raise ValueError("constraint-lattice retry eligibility evidence differs")
        classification_by_execution[row["primary_execution"]] = row
    class_disposition = "replacement-required" if retries else "all-primary-success"
    if classification.get("disposition") != class_disposition or \
            classification.get("eligible_replacements") != len(retries) or \
            classification.get("ineligible_failures") != 0:
        raise ValueError("constraint-lattice primary disposition differs")

    metadata_paths = sorted(metadata_dir.glob("season-*-week-*.json"))
    if len(metadata_paths) != 54 or \
            _metadata_digest_set(metadata_hashes) != {_sha(path) for path in metadata_paths}:
        raise ValueError("constraint-lattice primary metadata population differs")
    for path in metadata_paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        execution = metadata.get("metadata", {}).get("name")
        primary_row = next((row for row in primary if row[3] == execution), None)
        if primary_row is None or execution not in classification_by_execution:
            raise ValueError("constraint-lattice primary metadata identity differs")
        season, week, job, _execution, uri = primary_row
        spec = metadata.get("spec", {})
        task = spec.get("template", {}).get("spec", {})
        containers = task.get("containers", [])
        if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
                len(containers) != 1:
            raise ValueError("constraint-lattice primary metadata shape differs")
        container = containers[0]
        expected_args = [
            contract["runner"], "--season", season, "--week", week,
            "--output-uri", uri,
        ]
        env = {
            row.get("name"): str(row.get("value", ""))
            for row in container.get("env", [])
        }
        if container.get("image") != manifest.get("image") or \
                container.get("command") != ["python"] or \
                container.get("args") != expected_args or env != {
                    "CODE_SHA": manifest.get("code_sha"),
                    "ANALYSIS_IMAGE": manifest.get("image"),
                } or container.get("resources", {}).get("limits") != {
                    "cpu": "4", "memory": "16Gi"} or \
                task.get("maxRetries") != 0 or \
                str(task.get("timeoutSeconds")) != contract["timeout"] or \
                task.get("serviceAccountName") != \
                "817589974517-compute@developer.gserviceaccount.com":
            raise ValueError("constraint-lattice primary metadata contract differs")
        status = metadata.get("status", {})
        completed = [
            row for row in status.get("conditions", [])
            if row.get("type") == "Completed"
        ]
        evidence = classification_by_execution[execution]
        if len(completed) != 1 or completed[0].get("status") != evidence.get("status") or \
                str(completed[0].get("message", "")) != evidence.get("message") or \
                str(completed[0].get("reason", "")) != evidence.get("reason") or \
                status.get("completionTime") != evidence.get("completion_time"):
            raise ValueError("constraint-lattice primary status evidence differs")
    return resolution


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=tuple(CONTRACTS))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.mode, args.output_dir, args.manifest)
    print("CONSTRAINT_LATTICE_ATTEMPTS_VALIDATED", result["disposition"])


if __name__ == "__main__":
    main()
