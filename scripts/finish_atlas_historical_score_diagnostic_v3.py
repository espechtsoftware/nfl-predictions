#!/usr/bin/env python3
"""Strictly harvest and reproduce the ATLAS historical-score v3 result."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from google.cloud import storage

from nfl_dfs.analysis.atlas_historical_score import aggregate_diagnostic
from nfl_dfs.research.atlas_historical_v3_sources import (
    EXPECTED_SOURCE_HASHES,
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    UPSTREAM_CODE_SHA,
    UPSTREAM_IMAGE,
    UPSTREAM_PREFIX,
    canonical_json,
    file_sha,
    load_json,
    parse_kv,
    validate_receipt,
)
from render_atlas_matched_diversity_repair4_command import render
from run_atlas_historical_score_diagnostic_v3 import _object_receipt
from run_cbwu_seed_order_audit import _parse_gcs


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/atlas-historical-score-runs" / HISTORICAL_RUN_ID
OUTPUT_URI = f"{HISTORICAL_PREFIX}/report.json"
JOB = "atlas-historical-score-v3"


def _execution(name: str) -> dict[str, Any]:
    output = subprocess.run([
        "gcloud", "run", "jobs", "executions", "describe", name,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ], check=True, text=True, capture_output=True).stdout
    value = json.loads(output)
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS historical v3 execution metadata differs")
    return value


def _validate_execution(value: dict[str, Any], manifest: dict[str, str]) -> str:
    name = manifest["execution"]
    if value.get("metadata", {}).get("name") != name:
        raise RuntimeError("ATLAS historical v3 execution identity differs")
    status = value.get("status", {})
    completed = [row for row in status.get("conditions", [])
                 if row.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") == "Unknown" or \
            not status.get("completionTime"):
        raise RuntimeError("ATLAS historical v3 execution is not terminal")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    expected_args = [
        "scripts/run_atlas_historical_score_diagnostic_v3.py",
        "--upstream-receipt-uri", manifest["upstream_receipt_uri"],
        "--upstream-receipt-generation", manifest["upstream_receipt_generation"],
        "--upstream-receipt-sha256", manifest["upstream_receipt_sha256"],
        "--output-uri", OUTPUT_URI,
    ]
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("ATLAS historical v3 task shape differs")
    container = containers[0]
    env = {row.get("name"): str(row.get("value", ""))
           for row in container.get("env", [])}
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or \
            env != {"CODE_SHA": manifest["code_sha"],
                    "ANALYSIS_IMAGE": manifest["image"]} or \
            container.get("resources", {}).get("limits") != {
                "cpu": "8", "memory": "32Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "28800" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("ATLAS historical v3 execution contract differs")
    state = str(completed[0].get("status"))
    if state == "True" and (int(status.get("succeededCount") or 0) != 1 or
                            int(status.get("failedCount") or 0) != 0):
        raise RuntimeError("ATLAS historical v3 successful status differs")
    if state == "False" and (int(status.get("succeededCount") or 0) != 0 or
                             int(status.get("failedCount") or 0) != 1):
        raise RuntimeError("ATLAS historical v3 failed status differs")
    return state


def _validate_report(
    report: dict[str, Any], manifest: dict[str, str], receipt: dict[str, Any],
) -> str:
    fixed = {
        "version": "atlas-historical-score-diagnostic-v1",
        "run_id": HISTORICAL_RUN_ID,
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "scorer_code_sha": manifest["code_sha"],
        "scorer_image": manifest["image"],
        "source_hashes": EXPECTED_SOURCE_HASHES,
        "population": {"seasons": [2023, 2024, 2025], "slates": 54},
    }
    if any(report.get(key) != value for key, value in fixed.items()):
        raise RuntimeError("ATLAS historical v3 report identity differs")
    rows = report.get("rows", [])
    if not isinstance(rows, list) or len(rows) != 54 or any(
        row.get("uses_realized_outcomes") is not True or
        row.get("mechanical_valid") is not True or
        int(row.get("atlas", {}).get("generated") or 0) != 200 or
        int(row.get("identity", {}).get("candidate", {}).get("left") or 0) !=
        int(row.get("candidate_budget") or 0) or
        int(row.get("identity", {}).get("candidate", {}).get("right") or 0) !=
        int(row.get("candidate_budget") or 0) or
        int(row.get("identity", {}).get("selected", {}).get("left") or 0) != 80 or
        int(row.get("identity", {}).get("selected", {}).get("right") or 0) != 80
        for row in rows
    ):
        raise RuntimeError("ATLAS historical v3 exact-80 row population differs")
    expected = aggregate_diagnostic(rows)
    for key, value in expected.items():
        if report.get(key) != value:
            raise RuntimeError(f"ATLAS historical v3 aggregate differs: {key}")
    parity = report.get("native_actual_score_parity", {})
    if parity != {
        "registered_candidate_rows": 68199,
        "slots_per_roster": 9,
        "malformed_rosters": 0,
        "missing_player_outcomes": 0,
        "compared_rows": 68199,
        "maximum_absolute_error": parity.get("maximum_absolute_error"),
        "absolute_tolerance": 1e-9,
        "relative_tolerance": 0.0,
        "source_storage_type": "FLOAT",
    } or float(parity.get("maximum_absolute_error", 1.0)) > 1e-9:
        raise RuntimeError("ATLAS historical v3 actual-score parity differs")
    artifacts = report.get("source_artifacts", {})
    artifact_receipts = artifacts.get("receipts", [])
    artifact_raw = json.dumps(
        artifact_receipts, sort_keys=True, separators=(",", ":"),
    ).encode()
    expected_artifact_cells = {
        (season, week, f"R{seed}")
        for season in (2023, 2024, 2025) for week in range(1, 19)
        for seed in range(5)
    }
    if artifacts.get("count") != 270 or \
            not isinstance(artifact_receipts, list) or len(artifact_receipts) != 270 or \
            {(int(row.get("season", -1)), int(row.get("week", -1)),
              str(row.get("seed", ""))) for row in artifact_receipts} != \
            expected_artifact_cells or artifacts.get("sha256") != \
            sha256(artifact_raw).hexdigest():
        raise RuntimeError("ATLAS historical v3 source artifact receipt differs")
    upstream = report.get("upstream", {})
    receipt_object = upstream.get("receipt_object", {})
    if upstream.get("run_id") != receipt["upstream_run_id"] or \
            upstream.get("code_sha") != UPSTREAM_CODE_SHA or \
            upstream.get("image") != UPSTREAM_IMAGE or \
            upstream.get("objects") != receipt["objects"] or \
            upstream.get("executions") != {
                f"{row[0]}-{row[1]}": row[3]
                for row in receipt["accepted_execution_rows"]
            } or upstream.get("strict_harvest") != receipt["strict_harvest"] or \
            upstream.get("attempt_disposition") != \
            receipt["attempt"]["resolution"]["disposition"] or \
            upstream.get("scorefree_gate_passed") != \
            load_json(ROOT / "reports/atlas-matched-diversity-runs" /
                      receipt["upstream_run_id"] / "report.json").get(
                          "gate", {}
                      ).get("passes_scorefree_gate") or \
            receipt_object.get("uri") != manifest["upstream_receipt_uri"] or \
            receipt_object.get("generation") != manifest["upstream_receipt_generation"] or \
            receipt_object.get("sha256") != manifest["upstream_receipt_sha256"]:
        raise RuntimeError("ATLAS historical v3 upstream source binding differs")
    gate = report.get("gate", {})
    if set(gate) != {
        "selected_200_net", "selected_210_net", "selected_220_net",
        "selected_230_net", "selected_240_net", "candidate_200_net",
        "historical_tail_signal_positive", "disposition",
    } or gate.get("disposition") not in {
        "historical-tail-signal-positive", "historical-tail-signal-not-positive",
    }:
        raise RuntimeError("ATLAS historical v3 gate receipt differs")
    return str(gate["disposition"])


def _write_completion(disposition: str, report_sha: str = "") -> None:
    path = OUT / "completion.txt"
    if path.exists():
        raise RuntimeError("ATLAS historical v3 immutable completion exists")
    lines = [
        f"run_id={HISTORICAL_RUN_ID}", f"disposition={disposition}",
        "uses_realized_outcomes=true", "production_change_licensed=false",
        "seasons=2023,2024,2025", "slates=54",
    ]
    if report_sha:
        lines.append(f"report_sha256={report_sha}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "completion.sha256").write_text(
        f"{file_sha(path)}  {path}\n", encoding="utf-8",
    )


def finish() -> str:
    manifest_path = OUT / "manifest.txt"
    execution_path = OUT / "execution.txt"
    source_path = OUT / "upstream-receipt.json"
    object_path = OUT / "upstream-receipt-object.json"
    for path in (manifest_path, execution_path, source_path, object_path):
        if not path.is_file():
            raise RuntimeError(f"ATLAS historical v3 launch receipt is missing: {path}")
    if any((OUT / name).exists() for name in (
        "execution.json", "report.json", "report-object.json", "completion.txt",
    )):
        raise RuntimeError("ATLAS historical v3 immutable harvest exists")
    manifest = parse_kv(manifest_path)
    receipt = load_json(source_path)
    receipt_object = load_json(object_path)
    if not isinstance(receipt, dict) or not isinstance(receipt_object, dict):
        raise RuntimeError("ATLAS historical v3 source receipt differs")
    validate_receipt(receipt, render(UPSTREAM_PREFIX))
    if file_sha(source_path) != manifest.get("upstream_receipt_sha256") or \
            receipt_object.get("uri") != manifest.get("upstream_receipt_uri") or \
            receipt_object.get("generation") != manifest.get("upstream_receipt_generation") or \
            receipt_object.get("sha256") != manifest.get("upstream_receipt_sha256"):
        raise RuntimeError("ATLAS historical v3 source object receipt differs")
    execution = _execution(manifest["execution"])
    state = _validate_execution(execution, manifest)
    execution_raw = canonical_json(execution)
    (OUT / "execution.json").write_bytes(execution_raw)
    (OUT / "execution.sha256").write_text(
        f"{sha256(execution_raw).hexdigest()}  {OUT / 'execution.json'}\n",
        encoding="utf-8",
    )
    if state != "True":
        _write_completion("terminal-invalid-execution")
        return "terminal-invalid-execution"

    client = storage.Client(project=PROJECT)
    bucket, name = _parse_gcs(OUTPUT_URI)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    object_receipt = _object_receipt(blob, OUTPUT_URI, raw)
    report = json.loads(raw)
    if not isinstance(report, dict):
        raise RuntimeError("ATLAS historical v3 report payload differs")
    disposition = _validate_report(report, manifest, receipt)
    with (OUT / "report.json").open("xb") as handle:
        handle.write(raw)
    (OUT / "report.sha256").write_text(
        f"{sha256(raw).hexdigest()}  {OUT / 'report.json'}\n", encoding="utf-8",
    )
    object_raw = canonical_json(object_receipt)
    (OUT / "report-object.json").write_bytes(object_raw)
    (OUT / "report-object.sha256").write_text(
        f"{sha256(object_raw).hexdigest()}  {OUT / 'report-object.json'}\n",
        encoding="utf-8",
    )
    _write_completion(disposition, sha256(raw).hexdigest())
    return disposition


def main() -> None:
    disposition = finish()
    print("ATLAS_HISTORICAL_V3_HARVESTED", disposition)
    if disposition == "terminal-invalid-execution":
        raise SystemExit(10)


if __name__ == "__main__":
    main()
