#!/usr/bin/env python3
"""Resolve the frozen score-free grid with only literal platform replacements."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

import manage_stack_core_shell_support_attempts as base


RUN_ID = "20260816-stack-core-shell-scorefree-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-runs/"
    f"{RUN_ID}"
)
JOB_PATTERN = "stack-shell-scorefree-s{season}-w{week}-v1"
RUNNER = "scripts/run_stack_core_shell_scorefree.py"
TIMEOUT = "14400"
EXECUTION_PROTOCOL_SHA256 = (
    "e786783334d994caf4378beffaef6a048e6ba9fb13541382b7e491bf412dc78d"
)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports/stack-core-shell-runs" / RUN_ID
GRID = base.GRID


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _read_manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _read_ledger(path: Path, fields: int) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()]
    if any(len(row) != fields for row in rows):
        raise RuntimeError(f"stack-core/shell score-free ledger differs: {path.name}")
    return rows


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _validate_contract(
    metadata: Mapping,
    manifest: Mapping[str, str],
    row: Sequence[str],
) -> None:
    season, week, job, execution, uri = row
    expected_job = JOB_PATTERN.format(season=season, week=week)
    expected_uri = f"{PREFIX}/slate-{season}-{week}.json"
    if metadata.get("metadata", {}).get("name") != execution or \
            job != expected_job or not execution.startswith(job + "-") or \
            uri != expected_uri:
        raise RuntimeError("stack-core/shell score-free execution identity differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("stack-core/shell score-free execution shape differs")
    container = containers[0]
    expected_args = [
        RUNNER, "--season", season, "--week", week, "--output-uri", uri,
        "--support-uri", manifest.get("support_report_uri"),
        "--support-sha256", manifest.get("support_report_sha256"),
    ]
    env = {
        value.get("name"): str(value.get("value", ""))
        for value in container.get("env", [])
    }
    if container.get("image") != manifest.get("image") or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or env != {
                "CODE_SHA": manifest.get("code_sha"),
                "ANALYSIS_IMAGE": manifest.get("image"),
            } or container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != TIMEOUT or \
            task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise RuntimeError("stack-core/shell score-free execution contract differs")


def _validate_launch_receipts(
    out: Path,
) -> tuple[dict[str, str], list[list[str]]]:
    manifest_path = out / "manifest.txt"
    primary_path = out / "executions.txt"
    canary_path = out / "canary-completion.txt"
    release_path = out / "grid-release.txt"
    if not all(path.is_file() for path in (
        manifest_path, primary_path, canary_path, release_path,
    )):
        raise RuntimeError("stack-core/shell score-free launch receipt is incomplete")
    manifest = _read_manifest(manifest_path)
    fixed = {
        "run_id": RUN_ID,
        "output_prefix": PREFIX,
        "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": TIMEOUT,
        "max_retries": "0", "uses_realized_outcomes": "false",
        "effect_fields_inspected": "false",
        "treatment_constructed": "true",
        "production_change_licensed": "false",
        "historical_scoring_licensed": "false",
    }
    if any(manifest.get(key) != value for key, value in fixed.items()) or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
            not re.fullmatch(
                r".+@sha256:[0-9a-f]{64}", manifest.get("image", ""),
            ) or not re.fullmatch(
                r"[0-9a-f]{64}", manifest.get("support_report_sha256", ""),
            ) or not re.fullmatch(
                r"[0-9a-f]{64}", manifest.get("support_completion_sha256", ""),
            ):
        raise RuntimeError("stack-core/shell score-free manifest differs")
    primary = _read_ledger(primary_path, 5)
    if len(primary) != 54 or \
            {(int(row[0]), int(row[1])) for row in primary} != set(GRID) or \
            len({row[3] for row in primary}) != 54:
        raise RuntimeError("stack-core/shell score-free primary grid differs")
    canary = _read_manifest(canary_path)
    release = _read_manifest(release_path)
    if canary.get("status") != "True" or \
            canary.get("disposition") != "real-path-canary-passes" or \
            canary.get("cell") != "2023-1" or \
            canary.get("remaining_cells_released") != "false" or \
            canary.get("object_content_inspected") != "false" or \
            canary.get("effect_fields_inspected") != "false" or \
            canary.get("treatment_constructed") != "true" or \
            release.get("primary_executions") != "54" or \
            release.get("released_after_canary") != "53" or \
            release.get("canary_completion_sha256") != _sha(canary_path):
        raise RuntimeError("stack-core/shell score-free canary/grid receipt differs")
    return manifest, primary


_ORIGINAL_CLASSIFY = base._classify
_ORIGINAL_WRITE_RESOLUTION = base._write_resolution


def _classify(
    out: Path,
    manifest: Mapping[str, str],
    primary: list[list[str]],
) -> dict:
    payload = _ORIGINAL_CLASSIFY(out, manifest, primary)
    payload.update({
        "version": "stack-core-shell-scorefree-primary-attempt-classification-v1",
        "run_id": RUN_ID,
        "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "treatment_constructed": True,
    })
    _write_json(out / "primary-attempt-classification.json", payload)
    return payload


def _write_resolution(
    out: Path,
    classification: Mapping,
    disposition: str,
    primary: Sequence[Sequence[str]],
    retries: Sequence[Sequence[str]],
    accepted: Sequence[Sequence[str]],
) -> dict:
    payload = _ORIGINAL_WRITE_RESOLUTION(
        out, classification, disposition, primary, retries, accepted,
    )
    payload.update({
        "version": "stack-core-shell-scorefree-attempt-resolution-v1",
        "run_id": RUN_ID,
        "treatment_constructed": True,
        "classification_sha256": _sha(out / "primary-attempt-classification.json"),
    })
    _write_json(out / "attempt-resolution.json", payload)
    return payload


def _configure_base() -> None:
    base.RUN_ID = RUN_ID
    base.PREFIX = PREFIX
    base.JOB_PATTERN = JOB_PATTERN
    base.RUNNER = RUNNER
    base.TIMEOUT = TIMEOUT
    base.EXECUTION_PROTOCOL_SHA256 = EXECUTION_PROTOCOL_SHA256
    base.DEFAULT_OUT = DEFAULT_OUT
    base._validate_contract = _validate_contract
    base._validate_launch_receipts = _validate_launch_receipts
    base._classify = _classify
    base._write_resolution = _write_resolution
    base.validate = validate


def validate(out: Path) -> dict:
    _manifest_value, primary = _validate_launch_receipts(out)
    paths = base._classification_paths(out)
    if not all(paths[name].is_file() for name in (
        "classification", "objects", "retries", "resolution",
    )) or not paths["metadata"].is_dir():
        raise RuntimeError("stack-core/shell score-free attempt receipt incomplete")
    classification = json.loads(paths["classification"].read_text(encoding="utf-8"))
    resolution = json.loads(paths["resolution"].read_text(encoding="utf-8"))
    retries = _read_ledger(paths["retries"], 6)
    accepted = _read_ledger(paths["accepted"], 5) if paths["accepted"].is_file() else []
    common = {
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": True,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
    }
    if classification.get("version") != \
            "stack-core-shell-scorefree-primary-attempt-classification-v1" or any(
                classification.get(key) != value for key, value in common.items()
            ) or classification.get("execution_protocol_sha256") != \
            EXECUTION_PROTOCOL_SHA256 or \
            classification.get("primary_executions") != 54 or \
            classification.get("primary_execution_ledger_sha256") != \
            _sha(out / "executions.txt") or \
            classification.get("canary_completion_sha256") != \
            _sha(out / "canary-completion.txt") or \
            classification.get("grid_release_sha256") != \
            _sha(out / "grid-release.txt"):
        raise RuntimeError("stack-core/shell score-free classification differs")
    if resolution.get("version") != \
            "stack-core-shell-scorefree-attempt-resolution-v1" or any(
                resolution.get(key) != value for key, value in common.items()
            ) or resolution.get("classification_sha256") != \
            _sha(paths["classification"]) or \
            resolution.get("primary_execution_ledger_sha256") != \
            _sha(out / "executions.txt") or \
            resolution.get("retry_execution_ledger_sha256") != _sha(paths["retries"]):
        raise RuntimeError("stack-core/shell score-free resolution differs")
    disposition = resolution.get("disposition")
    allowed = {
        "accepted-primary-population",
        "accepted-population-with-platform-replacements",
        "terminal-invalid-primary", "terminal-invalid-replacement",
    }
    if disposition not in allowed or resolution.get("primary_executions") != 54 or \
            resolution.get("retry_executions") != len(retries) or \
            resolution.get("accepted_executions") != len(accepted):
        raise RuntimeError("stack-core/shell score-free resolution population differs")
    if disposition.startswith("accepted-"):
        if len(accepted) != 54 or \
                {(int(row[0]), int(row[1])) for row in accepted} != set(GRID) or \
                resolution.get("accepted_execution_ledger_sha256") != \
                _sha(paths["accepted"]):
            raise RuntimeError("stack-core/shell score-free accepted grid differs")
        primary_by_cell = {(row[0], row[1]): row for row in primary}
        retry_by_cell = {(row[0], row[1]): row for row in retries}
        for row in accepted:
            original = primary_by_cell[(row[0], row[1])]
            retry = retry_by_cell.get((row[0], row[1]))
            expected = [
                original[0], original[1], original[2],
                retry[4] if retry else original[3], original[4],
            ]
            if row != expected:
                raise RuntimeError("stack-core/shell score-free accepted binding differs")
    cells = classification.get("cells")
    if not isinstance(cells, list) or len(cells) != 54 or \
            {(int(row["season"]), int(row["week"])) for row in cells} != set(GRID):
        raise RuntimeError("stack-core/shell score-free classification grid differs")
    eligible = {
        (str(row["season"]), str(row["week"])) for row in cells
        if row.get("eligibility") == "eligible-platform-replacement"
    }
    ineligible = [
        row for row in cells if row.get("eligibility") not in {
            "primary-success", "eligible-platform-replacement",
        }
    ]
    retry_cells = {(row[0], row[1]) for row in retries}
    if len(retry_cells) != len(retries) or retry_cells != eligible or \
            classification.get("eligible_replacements") != len(eligible) or \
            classification.get("ineligible_failures") != len(ineligible):
        raise RuntimeError("stack-core/shell score-free eligibility differs")
    expected_classification = (
        "terminal-invalid-primary" if ineligible else
        "replacement-required" if eligible else "all-primary-success"
    )
    expected_resolution = (
        "terminal-invalid-primary" if ineligible else
        "accepted-population-with-platform-replacements"
        if retries and disposition.startswith("accepted-") else
        "terminal-invalid-replacement" if retries else "accepted-primary-population"
    )
    if classification.get("disposition") != expected_classification or \
            disposition != expected_resolution:
        raise RuntimeError("stack-core/shell score-free attempt disposition differs")
    object_status = json.loads(paths["objects"].read_text(encoding="utf-8"))
    if not isinstance(object_status, list) or len(object_status) != 54 or \
            {(int(row["season"]), int(row["week"])) for row in object_status} != \
            set(GRID) or len(list(paths["metadata"].glob("season-*-week-*.json"))) != 54:
        raise RuntimeError("stack-core/shell score-free evidence grid differs")
    print("STACK_CORE_SHELL_SCOREFREE_ATTEMPTS_VALIDATED", disposition)
    return resolution


def prepare(out: Path) -> dict:
    _configure_base()
    return base.prepare(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    _configure_base()
    result = base.prepare(args.output_dir) if args.action == "prepare" else \
        validate(args.output_dir)
    print("STACK_CORE_SHELL_SCOREFREE_ATTEMPT_RESULT", result["disposition"])


if __name__ == "__main__":
    main()
