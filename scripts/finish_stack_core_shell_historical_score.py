#!/usr/bin/env python3
"""Strictly validate and publish completion for the historical score report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from google.cloud import storage

from nfl_dfs.analysis.stack_core_shell_historical import (
    REPORT_VERSION,
    aggregate_historical,
)
import manage_stack_core_shell_historical_score_attempt as attempts
from run_cbwu_seed_order_audit import _upload_create_only
from run_stack_core_shell_historical_score import RUN_ID


PROJECT = "nfl-predictions-503414"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-historical-runs/"
    f"{RUN_ID}"
)
REPORT_URI = f"{PREFIX}/report.json"
COMPLETION_URI = f"{PREFIX}/completion.txt"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports/stack-core-shell-historical-runs" / RUN_ID
LOCK_ID = "20260816-stack-core-shell-production-lock-v1"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _validate_manifest(value: dict[str, str]) -> None:
    fixed = {
        "run_id": RUN_ID, "output_prefix": PREFIX, "output_uri": REPORT_URI,
        "protocol_sha256": "f562ce6e9a7e0458a1fd3382692f6761f1d9de56edb06ab4350403584cd702fc",
        "execution_protocol_sha256": attempts.EXECUTION_PROTOCOL_SHA256,
        "tasks": "1", "parallelism": "1", "cpu": "4", "memory": "16Gi",
        "timeout_seconds": "7200", "max_retries": "0",
        "uses_realized_outcomes": "true", "actual_scores_queried": "true",
        "production_change_licensed": "false",
    }
    if any(value.get(key) != expected for key, expected in fixed.items()) or \
            value.get("finisher_sha256") != _sha(Path(__file__)) or \
            value.get("attempt_manager_sha256") != _sha(Path(attempts.__file__)) or \
            value.get("runner_sha256") != _sha(
                ROOT / "scripts/run_stack_core_shell_historical_score.py"
            ) or not re.fullmatch(r"[0-9a-f]{40}", value.get("code_sha", "")) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", value.get("image", "")) or \
            not re.fullmatch(r"[0-9a-f]{64}", value.get("lock_report_sha256", "")) or \
            not re.fullmatch(
                r"[0-9a-f]{64}", value.get("lock_completion_sha256", ""),
            ):
        raise RuntimeError("historical-score strict manifest differs")
    lock = ROOT / "reports/stack-core-shell-lock-runs" / LOCK_ID
    if _sha(lock / "report.json") != value["lock_report_sha256"] or \
            _sha(lock / "completion.txt") != value["lock_completion_sha256"] or \
            _sha(lock / "accepted-executions.txt") != \
            value["lock_accepted_execution_ledger_sha256"]:
        raise RuntimeError("historical-score production-lock binding differs")


def _validate_report(report: dict, manifest: dict[str, str]) -> None:
    if report.get("version") != REPORT_VERSION or report.get("run_id") != RUN_ID or \
            report.get("scorer_code_sha") != manifest["code_sha"] or \
            report.get("scorer_image") != manifest["image"] or \
            report.get("historical_protocol_sha256") != manifest["protocol_sha256"] or \
            report.get("uses_realized_outcomes") is not True or \
            report.get("mechanical_valid") is not True or \
            report.get("production_change_licensed") is not False or \
            report.get("population") != {"seasons": [2023, 2024, 2025], "slates": 54}:
        raise RuntimeError("historical-score report identity differs")
    rows = report.get("rows")
    if not isinstance(rows, list) or len(rows) != 54:
        raise RuntimeError("historical-score report population differs")
    rebuilt = aggregate_historical(rows)
    if any(report.get(key) != value for key, value in rebuilt.items()):
        raise RuntimeError("historical-score report does not reproduce")
    parity = report.get("native_actual_score_parity")
    if not isinstance(parity, dict) or parity != {
        "registered_candidate_rows": 68_199,
        "slots_per_roster": 9,
        "malformed_rosters": 0,
        "missing_player_outcomes": 0,
        "compared_rows": 68_199,
        "maximum_absolute_error": parity.get("maximum_absolute_error"),
        "absolute_tolerance": 1e-9,
        "relative_tolerance": 0.0,
        "source_storage_type": "FLOAT",
    } or not isinstance(parity.get("maximum_absolute_error"), (int, float)) or \
            not 0 <= float(parity["maximum_absolute_error"]) <= 1e-9:
        raise RuntimeError("historical-score native parity differs")
    source = report.get("source_artifacts")
    if not isinstance(source, dict) or source.get("count") != 270 or \
            not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
        raise RuntimeError("historical-score source artifact receipt differs")
    lock = report.get("lock_receipt")
    if not isinstance(lock, dict) or \
            lock.get("report", {}).get("uri") != manifest["lock_report_uri"] or \
            lock.get("report", {}).get("sha256") != manifest["lock_report_sha256"] or \
            lock.get("completion", {}).get("uri") != manifest["lock_completion_uri"] or \
            lock.get("completion", {}).get("sha256") != \
            manifest["lock_completion_sha256"] or \
            lock.get("accepted_execution_ledger_sha256") != \
            manifest["lock_accepted_execution_ledger_sha256"]:
        raise RuntimeError("historical-score lock receipt differs")
    gate = report.get("gate", {})
    if gate.get("disposition") not in {
        "historical-tail-first-positive", "historical-tail-first-not-supported",
    } or gate.get("production_change_licensed") is not False:
        raise RuntimeError("historical-score frozen disposition differs")


def finish(out: Path = DEFAULT_OUT) -> dict:
    required = [
        out / "manifest.txt", out / "executions.txt",
        out / "retry-executions.txt", out / "accepted-executions.txt",
        out / "attempt-resolution.json", out / "primary-execution-metadata.json",
        out / "primary-object-status.json", out / "build-metadata.json",
    ]
    if not all(path.is_file() for path in required):
        raise RuntimeError("historical-score strict receipt is incomplete")
    if any(path.exists() for path in (
        out / "report.json", out / "completion.txt",
        out / "accepted-execution-metadata.json", out / "object-metadata.json",
    )):
        raise RuntimeError("immutable historical-score strict harvest exists")
    manifest = _manifest(out / "manifest.txt")
    _validate_manifest(manifest)
    resolution = attempts.validate(out)
    if resolution.get("disposition") not in {
        "accepted-primary", "accepted-platform-replacement",
    }:
        raise RuntimeError("historical-score attempt is terminally invalid")
    accepted = (out / "accepted-executions.txt").read_text(encoding="utf-8").split()
    if len(accepted) != 3 or accepted[0] != attempts.JOB or \
            accepted[2] != REPORT_URI or accepted[1] != \
            resolution.get("accepted_execution"):
        raise RuntimeError("historical-score accepted ledger differs")
    expected_executions = [resolution["primary_execution"]]
    if resolution.get("replacement_execution"):
        expected_executions.append(resolution["replacement_execution"])
    if attempts._job_executions() != sorted(expected_executions):
        raise RuntimeError("historical-score Cloud attempt population differs")
    metadata = attempts._execution(accepted[1])
    attempts._validate_contract(metadata, manifest, accepted[1])
    condition = attempts._completed(metadata)
    status = metadata["status"]
    if condition.get("status") != "True" or \
            int(status.get("succeededCount") or 0) != 1 or \
            int(status.get("failedCount") or 0) != 0:
        raise RuntimeError("historical-score accepted execution is not successful")
    object_value = attempts._object()
    if object_value is None:
        raise RuntimeError("historical-score report object is absent")

    gcs = storage.Client(project=PROJECT)
    bucket, name = REPORT_URI[5:].split("/", 1)
    blob = gcs.bucket(bucket).blob(name)
    blob.reload()
    raw = blob.download_as_bytes()
    if str(blob.generation) != str(object_value.get("generation")) or \
            len(raw) != int(object_value.get("size", -1)):
        raise RuntimeError("historical-score report changed before download")
    report = json.loads(raw)
    if not isinstance(report, dict):
        raise RuntimeError("historical-score report JSON differs")
    _validate_report(report, manifest)
    report_sha = sha256(raw).hexdigest()
    completion_lines = [
        "validated_at=" + datetime.now(timezone.utc).isoformat(),
        f"run_id={RUN_ID}", f"report_sha256={report_sha}",
        f"accepted_execution={accepted[1]}",
        f"accepted_execution_ledger_sha256={_sha(out / 'accepted-executions.txt')}",
        f"attempt_disposition={resolution['disposition']}",
        f"lock_report_sha256={manifest['lock_report_sha256']}",
        f"lock_completion_sha256={manifest['lock_completion_sha256']}",
        f"disposition={report['gate']['disposition']}",
        "uses_realized_outcomes=true", "actual_scores_queried=true",
        "production_change_licensed=false",
    ]
    completion_raw = ("\n".join(completion_lines) + "\n").encode()
    completion_upload = _upload_create_only(gcs, COMPLETION_URI, completion_raw)
    (out / "report.json").write_bytes(raw)
    (out / "completion.txt").write_bytes(completion_raw)
    _write_json(out / "completion-upload.json", completion_upload)
    _write_json(out / "accepted-execution-metadata.json", metadata)
    _write_json(out / "object-metadata.json", object_value)
    (out / "report.sha256").write_text(
        f"{report_sha}  {out / 'report.json'}\n", encoding="utf-8",
    )
    (out / "completion.sha256").write_text(
        f"{sha256(completion_raw).hexdigest()}  {out / 'completion.txt'}\n",
        encoding="utf-8",
    )
    print("STACK_CORE_SHELL_HISTORICAL_SCORE_STRICTLY_HARVESTED", report["gate"]["disposition"])
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    finish(args.output_dir)


if __name__ == "__main__":
    main()
