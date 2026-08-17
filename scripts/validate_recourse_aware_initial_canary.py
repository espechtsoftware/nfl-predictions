#!/usr/bin/env python3
"""Mechanically validate the one real-path recourse-aware canary."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS
from nfl_dfs.analysis.recourse_aware_initial import TAILS, VERSION

from aggregate_recourse_aware_initial_scorefree import (
    EXPECTED_SOURCE_HASHES,
    _assert_no_outcomes,
)
from run_recourse_aware_initial_scorefree import (
    CBWU_REPORT_SHA256,
    EXECUTION_PROTOCOL_SHA256,
    FORENSIC_MANIFEST_SHA256,
    RUN_ID,
    SCIENCE_PROTOCOL_SHA256,
    SOURCE_PANELS,
)


SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
EXPECTED_JOB = "recourse-initial-s2023-w1-v1"
EXPECTED_URI = (
    "gs://nfl-predictions-503414-raw/research/"
    f"recourse-aware-initial-book-runs/{RUN_ID}/slate-2023-1.json"
)
EXPECTED_RUNNER = "scripts/run_recourse_aware_initial_scorefree.py"
FORBIDDEN_DISCLOSURE_KEYS = {
    "conditions", "passed", "disposition", "gate_diagnostics",
    "selection_effective_rank", "leave_one_slate_out_influence",
}


def _manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _load_unique(path: Path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def _validate_fold_shape(row: Mapping, block: str) -> None:
    if row.get("version") != VERSION or \
            row.get("uses_realized_outcomes") is not False or \
            row.get("season") != 2023 or row.get("week") != 1 or \
            row.get("heldout_block") != block or \
            row.get("training_blocks") != [
                value for value in REGISTERED_BLOCKS if value != block
            ] or type(row.get("candidate_budget")) is not int or \
            row["candidate_budget"] < 80 or row.get("alternative_cap") != 24:
        raise ValueError("recourse-aware canary fold mechanics differ")
    for arm in ("control", "treatment"):
        book = row.get(arm)
        if not isinstance(book, Mapping) or \
                book.get("uses_realized_outcomes") is not False or \
                book.get("entries") != 80 or book.get("worlds") != 10_000:
            raise ValueError("recourse-aware canary book mechanics differ")
        for family in ("initial_coverage", "reachable_union_coverage"):
            values = book.get(family)
            if not isinstance(values, Mapping) or set(values) != {
                str(int(threshold)) for threshold in TAILS
            }:
                raise ValueError("recourse-aware canary tail schema differs")
    for key in ("control_selected_rosters", "treatment_selected_rosters"):
        rosters = row.get(key)
        if not isinstance(rosters, list) or len(rosters) != 80 or any(
            not isinstance(roster, list) or len(roster) != 9
            or len(set(map(str, roster))) != 9 for roster in rosters
        ):
            raise ValueError("recourse-aware canary exact-80 schema differs")


def validate(
    manifest_path: Path,
    execution_ledger: Path,
    execution_metadata: Path,
    object_metadata: Path,
    shard_path: Path,
) -> dict[str, object]:
    manifest = _manifest(manifest_path)
    rows = execution_ledger.read_text(encoding="utf-8").splitlines()
    if len(rows) != 1 or len(rows[0].split()) != 5:
        raise ValueError("recourse-aware canary ledger differs")
    season, week, job, execution, uri = rows[0].split()
    if (season, week, job, uri) != ("2023", "1", EXPECTED_JOB, EXPECTED_URI) or \
            not execution.startswith(job + "-"):
        raise ValueError("recourse-aware canary identity differs")
    fixed = {
        "run_id": RUN_ID,
        "output_prefix": EXPECTED_URI.rsplit("/", 1)[0],
        "science_protocol_sha256": SCIENCE_PROTOCOL_SHA256,
        "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "cbwu_report_sha256": CBWU_REPORT_SHA256,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": "14400",
        "max_retries": "0", "uses_realized_outcomes": "false",
        "production_change_licensed": "false",
        "historical_scoring_licensed": "false",
    }
    if any(manifest.get(key) != value for key, value in fixed.items()):
        raise ValueError("recourse-aware canary manifest differs")

    metadata = _load_unique(execution_metadata)
    status = metadata.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if metadata.get("metadata", {}).get("name") != execution or \
            len(completed) != 1 or completed[0].get("status") != "True" or \
            int(status.get("succeededCount") or 0) != 1 or \
            int(status.get("failedCount") or 0) != 0 or \
            int(status.get("retriedCount") or 0) != 0 or \
            not status.get("completionTime") or spec.get("parallelism") != 1 or \
            spec.get("taskCount") != 1 or len(containers) != 1:
        raise ValueError("recourse-aware canary execution mechanics differ")
    container = containers[0]
    expected_args = [
        EXPECTED_RUNNER, "--season", "2023", "--week", "1",
        "--output-uri", EXPECTED_URI,
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
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "14400" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise ValueError("recourse-aware canary execution contract differs")

    object_row = _load_unique(object_metadata)
    raw = shard_path.read_bytes()
    if not str(object_row.get("generation", "")).isdigit() or \
            int(object_row.get("size", -1)) != len(raw):
        raise ValueError("recourse-aware canary object metadata differs")
    shard = _load_unique(shard_path)
    _assert_no_outcomes(shard)
    if FORBIDDEN_DISCLOSURE_KEYS & set(shard):
        raise ValueError("recourse-aware canary contains aggregate disclosure")
    expected_top = {
        "version", "run_id", "uses_realized_outcomes",
        "production_change_licensed", "historical_scoring_licensed",
        "season", "week", "code_sha", "analysis_image", "source_hashes",
        "source_panels", "forensic_manifest_sha256", "cbwu_report_sha256",
        "decision_time", "artifact_receipts", "folds",
    }
    if set(shard) != expected_top or \
            shard.get("version") != \
            "recourse-aware-initial-book-scorefree-shard-v1" or \
            shard.get("run_id") != RUN_ID or \
            shard.get("uses_realized_outcomes") is not False or \
            shard.get("production_change_licensed") is not False or \
            shard.get("historical_scoring_licensed") is not False or \
            shard.get("season") != 2023 or shard.get("week") != 1 or \
            shard.get("code_sha") != manifest.get("code_sha") or \
            shard.get("analysis_image") != manifest.get("image") or \
            shard.get("source_hashes") != EXPECTED_SOURCE_HASHES or \
            shard.get("forensic_manifest_sha256") != FORENSIC_MANIFEST_SHA256 or \
            shard.get("cbwu_report_sha256") != CBWU_REPORT_SHA256 or \
            shard.get("source_panels") != list(SOURCE_PANELS):
        raise ValueError("recourse-aware canary shard binding differs")
    folds = shard.get("folds")
    if not isinstance(folds, list) or len(folds) != 5 or [
        row.get("heldout_block") for row in folds
    ] != list(REGISTERED_BLOCKS):
        raise ValueError("recourse-aware canary fold grid differs")
    for block, fold in zip(REGISTERED_BLOCKS, folds, strict=True):
        _validate_fold_shape(fold, block)
    receipts = shard.get("artifact_receipts")
    if not isinstance(receipts, list) or len(receipts) != 5 or [
        row.get("block") for row in receipts
    ] != list(REGISTERED_BLOCKS) or [
        row.get("source_panel") for row in receipts
    ] != list(SOURCE_PANELS):
        raise ValueError("recourse-aware canary artifact grid differs")
    return {
        "version": "recourse-aware-initial-book-canary-validation-v1",
        "status": True,
        "disposition": "actual-final-path-canary-passes",
        "run_id": RUN_ID,
        "cell": "2023-1",
        "execution": execution,
        "object_generation": str(object_row["generation"]),
        "object_sha256": sha256(raw).hexdigest(),
        "folds": 5,
        "artifact_receipts": 5,
        "remaining_cells_released": False,
        "outcome_fields_inspected": False,
        "effect_fields_inspected": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execution-ledger", type=Path, required=True)
    parser.add_argument("--execution-metadata", type=Path, required=True)
    parser.add_argument("--object-metadata", type=Path, required=True)
    parser.add_argument("--shard", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(
        args.manifest,
        args.execution_ledger,
        args.execution_metadata,
        args.object_metadata,
        args.shard,
    )
    args.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("RECOURSE_INITIAL_ACTUAL_CANARY_VALIDATED", result["execution"])


if __name__ == "__main__":
    main()
