#!/usr/bin/env python3
"""Strictly harvest the ATLAS hybrid historical-score v4 result."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from google.cloud import storage

from nfl_dfs.analysis.atlas_historical_score import aggregate_diagnostic
from nfl_dfs.research.atlas_historical_v3_sources import loads_json, parse_kv
from nfl_dfs.research.atlas_historical_v4_sources import (
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    PROTOCOL_SHA256,
    validate_source_receipt,
)
from nfl_dfs.research.atlas_repair6 import canonical_json
from nfl_dfs.research.atlas_repair6_hybrid import REPAIR5_PREFIX, REPAIR6_PREFIX
from historical_outcome_lease import LEASE_URI
from render_atlas_matched_diversity_repair4_command import render
from run_atlas_historical_score_diagnostic_v4 import OUTPUT_URI, _object_receipt
from run_cbwu_seed_order_audit import _parse_gcs


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/atlas-historical-score-runs" / HISTORICAL_RUN_ID
PROTOCOL = ROOT / "reports/2026-08-17-atlas-historical-score-v4-hybrid-protocol.md"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = loads_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"ATLAS historical v4 JSON source differs: {path}")
    return value


def _execution(name: str) -> dict[str, Any]:
    raw = subprocess.run([
        "gcloud", "run", "jobs", "executions", "describe", name,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ], check=True, text=True, capture_output=True).stdout
    value = loads_json(raw)
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS historical v4 execution metadata differs")
    return value


def _validate_execution(value: Mapping[str, Any], manifest: Mapping[str, str]) -> str:
    if value.get("metadata", {}).get("name") != manifest["execution"]:
        raise RuntimeError("ATLAS historical v4 execution identity differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("ATLAS historical v4 task shape differs")
    container = containers[0]
    expected_args = [
        "scripts/run_atlas_historical_score_diagnostic_v4.py",
        "--upstream-receipt-uri", manifest["upstream_receipt_uri"],
        "--upstream-receipt-generation", manifest["upstream_receipt_generation"],
        "--upstream-receipt-sha256", manifest["upstream_receipt_sha256"],
        "--output-uri", OUTPUT_URI,
    ]
    env = {item.get("name"): str(item.get("value", ""))
           for item in container.get("env", [])}
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or env != {
                "CODE_SHA": manifest["code_sha"],
                "ANALYSIS_IMAGE": manifest["image"],
            } or container.get("resources", {}).get("limits") != {
                "cpu": "8", "memory": "32Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "28800" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("ATLAS historical v4 execution contract differs")
    status = value.get("status", {})
    completed = [item for item in status.get("conditions", [])
                 if item.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") == "Unknown" or \
            not status.get("completionTime"):
        raise RuntimeError("ATLAS historical v4 execution is not terminal")
    state = str(completed[0].get("status"))
    expected_counts = (1, 0) if state == "True" else (0, 1)
    if (int(status.get("succeededCount") or 0),
            int(status.get("failedCount") or 0)) != expected_counts:
        raise RuntimeError("ATLAS historical v4 terminal status differs")
    return state


def _validate_report(
    report: Mapping[str, Any], manifest: Mapping[str, str],
    receipt: Mapping[str, Any],
) -> str:
    fixed = {
        "version": "atlas-historical-score-diagnostic-v1",
        "run_id": HISTORICAL_RUN_ID, "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "scorer_code_sha": manifest["code_sha"],
        "scorer_image": manifest["image"],
        "population": {"seasons": [2023, 2024, 2025], "slates": 54},
    }
    if any(report.get(key) != value for key, value in fixed.items()):
        raise RuntimeError("ATLAS historical v4 report identity differs")
    expected_hashes = {
        "protocol": PROTOCOL_SHA256,
        "source_module": _sha(
            ROOT / "src/nfl_dfs/research/atlas_historical_v4_sources.py"
        ),
        "runner": _sha(ROOT / "scripts/run_atlas_historical_score_diagnostic_v4.py"),
    }
    if report.get("source_hashes") != expected_hashes:
        raise RuntimeError("ATLAS historical v4 source hashes differ")
    rows = report.get("rows", [])
    if not isinstance(rows, list) or len(rows) != 54 or any(
        row.get("uses_realized_outcomes") is not True or
        row.get("mechanical_valid") is not True or
        int(row.get("atlas", {}).get("generated") or 0) != 200 or
        int(row.get("identity", {}).get("selected", {}).get("left") or 0) != 80 or
        int(row.get("identity", {}).get("selected", {}).get("right") or 0) != 80
        for row in rows
    ):
        raise RuntimeError("ATLAS historical v4 exact-80 population differs")
    expected = aggregate_diagnostic(rows)
    for key, value in expected.items():
        if report.get(key) != value:
            raise RuntimeError(f"ATLAS historical v4 aggregate differs: {key}")
    parity = report.get("native_actual_score_parity", {})
    if parity != {
        "registered_candidate_rows": 68199, "slots_per_roster": 9,
        "malformed_rosters": 0, "missing_player_outcomes": 0,
        "compared_rows": 68199,
        "maximum_absolute_error": parity.get("maximum_absolute_error"),
        "absolute_tolerance": 1e-9, "relative_tolerance": 0.0,
        "source_storage_type": "FLOAT",
    } or float(parity.get("maximum_absolute_error", 1.0)) > 1e-9:
        raise RuntimeError("ATLAS historical v4 actual-score parity differs")
    artifacts = report.get("source_artifacts", {})
    artifact_rows = artifacts.get("receipts", [])
    expected_cells = {
        (season, week, f"R{seed}")
        for season in (2023, 2024, 2025) for week in range(1, 19)
        for seed in range(5)
    }
    artifact_raw = json.dumps(
        artifact_rows, sort_keys=True, separators=(",", ":"),
    ).encode()
    if artifacts.get("count") != 270 or not isinstance(artifact_rows, list) or \
            len(artifact_rows) != 270 or {
                (int(row.get("season", -1)), int(row.get("week", -1)),
                 str(row.get("seed", ""))) for row in artifact_rows
            } != expected_cells or artifacts.get("sha256") != sha256(
                artifact_raw).hexdigest():
        raise RuntimeError("ATLAS historical v4 source artifact receipt differs")
    upstream = report.get("upstream", {})
    accepted = receipt["accepted_rows"]
    if upstream.get("run_id") != receipt["run_id"] or \
            upstream.get("population_receipt_sha256") != \
            manifest["upstream_receipt_sha256"] or \
            upstream.get("repair5_cells") != 54 - len(receipt["eligible_cells"]) or \
            upstream.get("repair6_cells") != len(receipt["eligible_cells"]) or \
            upstream.get("objects") != receipt["objects"] or \
            upstream.get("executions") != {
                f"{row[0]}-{row[1]}": row[4] for row in accepted
            } or upstream.get("disposition") != \
            "valid-complete-repair6-hybrid-population":
        raise RuntimeError("ATLAS historical v4 upstream binding differs")
    gate = report.get("gate", {})
    if set(gate) != {
        "selected_200_net", "selected_210_net", "selected_220_net",
        "selected_230_net", "selected_240_net", "candidate_200_net",
        "historical_tail_signal_positive", "disposition",
    } or gate.get("disposition") not in {
        "historical-tail-signal-positive", "historical-tail-signal-not-positive",
    }:
        raise RuntimeError("ATLAS historical v4 gate differs")
    return str(gate["disposition"])


def _write_completion(disposition: str, report_sha: str = "", slates: int = 54) -> None:
    path = OUT / "completion.txt"
    if path.exists():
        raise RuntimeError("ATLAS historical v4 immutable completion exists")
    lines = [
        f"run_id={HISTORICAL_RUN_ID}", f"disposition={disposition}",
        "uses_realized_outcomes=true", "production_change_licensed=false",
        "seasons=2023,2024,2025", f"slates={slates}",
    ]
    if report_sha:
        lines.append(f"report_sha256={report_sha}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "completion.sha256").write_text(
        f"{_sha(path)}  {path}\n", encoding="utf-8",
    )


def finish() -> str:
    manifest_path = OUT / "manifest.txt"
    execution_path = OUT / "execution.txt"
    source_path = OUT / "upstream-receipt.json"
    source_object_path = OUT / "upstream-receipt-object.json"
    lease_path = OUT / "historical-outcome-lease.json"
    for path in (manifest_path, execution_path, source_path, source_object_path, lease_path):
        if not path.is_file():
            raise RuntimeError(f"ATLAS historical v4 launch receipt missing: {path}")
    if any((OUT / name).exists() for name in (
        "execution.json", "report.json", "report-object.json", "completion.txt",
    )):
        raise RuntimeError("ATLAS historical v4 immutable harvest exists")
    manifest = parse_kv(manifest_path)
    fixed = {
        "run_id": HISTORICAL_RUN_ID, "job": "atlas-historical-score-v4",
        "output_prefix": HISTORICAL_PREFIX, "output_uri": OUTPUT_URI,
        "protocol_sha256": PROTOCOL_SHA256, "tasks": "1",
        "parallelism": "1", "cpu": "8", "memory": "32Gi",
        "timeout_seconds": "28800", "max_retries": "0",
        "uses_realized_outcomes": "true", "production_change_licensed": "false",
    }
    sources = {
        "source_module_sha256": ROOT / "src/nfl_dfs/research/atlas_historical_v4_sources.py",
        "runner_sha256": ROOT / "scripts/run_atlas_historical_score_diagnostic_v4.py",
        "finisher_sha256": Path(__file__),
    }
    if any(manifest.get(key) != value for key, value in fixed.items()) or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")) or \
            any(manifest.get(key) != _sha(path) for key, path in sources.items()) or \
            _sha(PROTOCOL) != PROTOCOL_SHA256:
        raise RuntimeError("ATLAS historical v4 manifest differs")
    if execution_path.read_text(encoding="utf-8").split() != [
        manifest["job"], manifest["execution"], manifest["output_uri"],
    ]:
        raise RuntimeError("ATLAS historical v4 execution ledger differs")
    receipt = _load(source_path)
    receipt_object = _load(source_object_path)
    validate_source_receipt(
        receipt, repair5_grid_command=render(REPAIR5_PREFIX),
        repair6_grid_command=render(REPAIR6_PREFIX),
    )
    if _sha(source_path) != manifest["upstream_receipt_sha256"] or \
            receipt_object.get("uri") != manifest["upstream_receipt_uri"] or \
            receipt_object.get("generation") != manifest["upstream_receipt_generation"] or \
            receipt_object.get("sha256") != manifest["upstream_receipt_sha256"]:
        raise RuntimeError("ATLAS historical v4 source object differs")
    lease = _load(lease_path)
    lease_value, lease_object = lease.get("lease", {}), lease.get("object", {})
    if lease_value.get("version") != "historical-outcome-active-v1" or \
            lease_value.get("run_id") != HISTORICAL_RUN_ID or \
            lease_value.get("job") != manifest["job"] or \
            lease_value.get("code_sha") != manifest["code_sha"] or \
            lease_value.get("image") != manifest["image"] or \
            lease_object.get("uri") != LEASE_URI or \
            not str(lease_object.get("generation", "")).isdigit() or \
            lease_object.get("sha256") != sha256(canonical_json(lease_value)).hexdigest() or \
            lease_object.get("create_only") is not True:
        raise RuntimeError("ATLAS historical v4 outcome lease differs")
    execution = _execution(manifest["execution"])
    state = _validate_execution(execution, manifest)
    execution_raw = canonical_json(execution)
    (OUT / "execution.json").write_bytes(execution_raw)
    (OUT / "execution.sha256").write_text(
        f"{sha256(execution_raw).hexdigest()}  {OUT / 'execution.json'}\n",
        encoding="utf-8",
    )
    if state != "True":
        _write_completion("terminal-invalid-execution", slates=0)
        return "terminal-invalid-execution"
    client = storage.Client(project=PROJECT)
    lease_bucket, lease_name = _parse_gcs(LEASE_URI)
    lease_blob = client.bucket(lease_bucket).blob(
        lease_name, generation=int(lease_object["generation"]),
    )
    if lease_blob.download_as_bytes() != canonical_json(lease_value):
        raise RuntimeError("ATLAS historical v4 active outcome lease differs")
    bucket, name = _parse_gcs(OUTPUT_URI)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    object_receipt = _object_receipt(blob, OUTPUT_URI, raw)
    report = loads_json(raw.decode("utf-8"))
    if not isinstance(report, dict):
        raise RuntimeError("ATLAS historical v4 report payload differs")
    disposition = _validate_report(report, manifest, receipt)
    (OUT / "report.json").write_bytes(raw)
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
    print("ATLAS_HISTORICAL_V4_HARVESTED", disposition)
    if disposition == "terminal-invalid-execution":
        raise SystemExit(10)


if __name__ == "__main__":
    main()
