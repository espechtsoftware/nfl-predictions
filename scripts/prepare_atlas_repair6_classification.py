#!/usr/bin/env python3
"""Seal the score-free repair5 failure classification for ATLAS repair6."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from nfl_dfs.research.atlas_historical_v3_sources import loads_json, parse_kv
from nfl_dfs.research.atlas_repair6 import (
    REPAIR5_RUN_ID,
    REPAIR6_RUN_ID,
    canonical_json,
    classify_repair5_for_repair6,
)
from validate_atlas_repair6_code_diff import validate as validate_code_diff


PROJECT = "nfl-predictions-503414"
ROOT = Path(__file__).resolve().parents[1]
REPAIR5 = ROOT / "reports/atlas-matched-diversity-runs" / REPAIR5_RUN_ID
OUT = ROOT / "reports/atlas-matched-diversity-runs" / REPAIR6_RUN_ID
REPAIR6_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    f"{REPAIR6_RUN_ID}"
)


def _load(path: Path) -> dict[str, Any]:
    value = loads_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"ATLAS repair6 JSON source differs: {path}")
    return value


def _verify_sha_receipt(path: Path, receipt: Path) -> None:
    expected = f"{sha256(path.read_bytes()).hexdigest()}  {path}\n"
    if not receipt.is_file() or \
            receipt.read_text(encoding="utf-8").splitlines(keepends=True).count(
                expected
            ) != 1:
        raise RuntimeError(f"ATLAS repair6 hash receipt differs: {path}")


def _error_log(execution: str) -> tuple[list[dict[str, Any]], str]:
    query = (
        'resource.type="cloud_run_job" AND '
        f'labels."run.googleapis.com/execution_name"="{execution}" AND '
        "severity>=ERROR"
    )
    raw = subprocess.run([
        "gcloud", "logging", "read", query, "--project", PROJECT,
        "--limit=100", "--order=asc", "--format=json",
    ], check=True, text=True, capture_output=True).stdout
    value = loads_json(raw)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise RuntimeError("ATLAS repair6 Cloud Logging payload differs")
    messages = []
    for row in value:
        text = row.get("textPayload")
        if isinstance(text, str) and text.strip():
            messages.append(text.rstrip())
        payload = row.get("jsonPayload")
        if isinstance(payload, dict) and isinstance(payload.get("message"), str) \
                and payload["message"].strip():
            messages.append(payload["message"].rstrip())
    return value, "\n".join(messages) + ("\n" if messages else "")


def prepare() -> dict[str, Any]:
    if OUT.exists():
        raise RuntimeError("ATLAS repair6 immutable local run exists")
    required = (
        REPAIR5 / "terminal-census-completion.txt",
        REPAIR5 / "terminal-census.json",
        REPAIR5 / "primary-attempt-classification.json",
        REPAIR5 / "attempt-resolution.json",
        REPAIR5 / "terminal-census-object-inventory.txt",
    )
    if any(not path.is_file() for path in required):
        raise RuntimeError("ATLAS repair6 awaits repair5 terminal census")
    completion = parse_kv(required[0])
    if completion != {
        "validated_at": completion.get("validated_at"),
        "primary_executions": "54", "retry_executions": "0",
        "all_declared_attempts_terminal": "true",
        "scientific_result_valid": "false",
        "effect_fields_inspected": "false",
        "uses_realized_outcomes": "false",
        "historical_scoring_licensed": "false",
        "continuous_parity_capacity_released": "true",
        "production_change_licensed": "false",
    } or not str(completion.get("validated_at", "")).endswith("Z"):
        raise RuntimeError("ATLAS repair6 repair5 terminal completion differs")
    receipts = (
        REPAIR5 / "terminal-census-completion.sha256",
        REPAIR5 / "terminal-census.sha256",
        REPAIR5 / "primary-attempt-classification.sha256",
        REPAIR5 / "attempt-resolution.sha256",
        REPAIR5 / "terminal-census-object-inventory.sha256",
    )
    for path, receipt in zip(required, receipts, strict=True):
        _verify_sha_receipt(path, receipt)

    census = _load(required[1])
    classification = _load(required[2])
    resolution = _load(required[3])
    if census.get("attempt_classification_sha256") != \
            sha256(required[2].read_bytes()).hexdigest() or \
            census.get("attempt_resolution_sha256") != \
            sha256(required[3].read_bytes()).hexdigest() or \
            census.get("output_object_inventory_sha256") != \
            sha256(required[4].read_bytes()).hexdigest() or \
            resolution.get("classification_sha256") != \
            sha256(required[2].read_bytes()).hexdigest():
        raise RuntimeError("ATLAS repair6 repair5 census source hashes differ")
    inventory = [
        line.strip() for line in required[4].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failed = [
        str(row.get("execution", "")) for row in census.get("terminal", [])
        if isinstance(row, dict) and row.get("status") == "False"
    ]
    if not failed or len(failed) != len(set(failed)):
        raise RuntimeError("ATLAS repair6 repair5 failed population differs")

    raw_logs = {}
    error_logs = {}
    for execution in failed:
        rows, text = _error_log(execution)
        raw_logs[execution] = rows
        error_logs[execution] = text
    result = classify_repair5_for_repair6(
        census=census, primary_classification=classification,
        attempt_resolution=resolution, object_inventory=inventory,
        error_logs=error_logs,
    )
    if result["repair6_launch_licensed"] and not any(
        row["season"] == 2023 and row["week"] == 7
        for row in result["eligible_tiebreak_failures"]
    ):
        raise RuntimeError("ATLAS repair6 defect canary cell is absent")
    code_diff = validate_code_diff()

    pending = OUT.with_name(OUT.name + ".classification-pending")
    if pending.exists():
        raise RuntimeError("ATLAS repair6 pending classification exists")
    pending.mkdir(parents=True)
    logs_dir = pending / "repair5-failure-logs"
    logs_dir.mkdir()
    log_hashes = []
    for execution in sorted(raw_logs):
        path = logs_dir / f"{execution}.json"
        path.write_bytes(canonical_json(raw_logs[execution]))
        final_path = OUT / "repair5-failure-logs" / path.name
        log_hashes.append(
            f"{sha256(path.read_bytes()).hexdigest()}  {final_path}\n"
        )
    (pending / "repair5-failure-logs.sha256").write_text(
        "".join(log_hashes), encoding="utf-8",
    )
    classification_path = pending / "eligibility-classification.json"
    classification_path.write_bytes(canonical_json(result))
    (pending / "eligibility-classification.sha256").write_text(
        f"{sha256(classification_path.read_bytes()).hexdigest()}  "
        f"{OUT / classification_path.name}\n", encoding="utf-8",
    )
    proof_path = pending / "code-diff-proof.json"
    proof_path.write_bytes(canonical_json(code_diff))
    (pending / "code-diff-proof.sha256").write_text(
        f"{sha256(proof_path.read_bytes()).hexdigest()}  "
        f"{OUT / proof_path.name}\n",
        encoding="utf-8",
    )
    eligible_path = pending / "eligible-cells.txt"
    eligible_path.write_text("".join(
        f"{row['season']} {row['week']} {row['primary_execution']} "
        f"{row['world']} atlas-md-s{row['season']}-w{row['week']}-r6 "
        f"{REPAIR6_PREFIX}/slate-{row['season']}-{row['week']}.json\n"
        for row in result["eligible_tiebreak_failures"]
    ), encoding="utf-8")
    (pending / "eligible-cells.sha256").write_text(
        f"{sha256(eligible_path.read_bytes()).hexdigest()}  "
        f"{OUT / eligible_path.name}\n",
        encoding="utf-8",
    )
    completion_path = pending / "classification-completion.txt"
    completion_path.write_text("\n".join((
        f"run_id={REPAIR6_RUN_ID}", f"disposition={result['disposition']}",
        f"repair5_successes={result['repair5_successes']}",
        f"repair5_failures={result['repair5_failures']}",
        f"eligible_tiebreak_failures={len(result['eligible_tiebreak_failures'])}",
        f"ineligible_failures={len(result['ineligible_failures'])}",
        "uses_realized_outcomes=false", "candidate_or_lineup_scores_read=false",
        "effect_fields_inspected=false", "production_change_licensed=false",
    )) + "\n", encoding="utf-8")
    (pending / "classification-completion.sha256").write_text(
        f"{sha256(completion_path.read_bytes()).hexdigest()}  "
        f"{OUT / completion_path.name}\n",
        encoding="utf-8",
    )
    pending.rename(OUT)
    return result


def main() -> None:
    argparse.ArgumentParser().parse_args()
    result = prepare()
    print("ATLAS_REPAIR6_CLASSIFIED " + json.dumps({
        "disposition": result["disposition"],
        "eligible": len(result["eligible_tiebreak_failures"]),
        "ineligible": len(result["ineligible_failures"]),
    }, sort_keys=True))
    if not result["repair6_launch_licensed"]:
        raise SystemExit(10)


if __name__ == "__main__":
    main()
