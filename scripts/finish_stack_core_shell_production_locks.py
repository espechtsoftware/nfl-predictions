#!/usr/bin/env python3
"""Strictly harvest and publish the outcome-free production-form locks."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from google.cloud import storage

from aggregate_stack_core_shell_production_locks import REPORT_VERSION, aggregate
import manage_stack_core_shell_lock_attempts as attempts
import manage_stack_core_shell_support_attempts as transport
from run_cbwu_seed_order_audit import _upload_create_only
from run_stack_core_shell_production_lock import (
    HISTORICAL_PROTOCOL_SHA256,
    RUN_ID,
)


PROJECT = "nfl-predictions-503414"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/"
    f"{RUN_ID}"
)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports/stack-core-shell-lock-runs" / RUN_ID
SCORE_FREE_RUN_ID = "20260816-stack-core-shell-scorefree-v1"
SCORE_FREE_LOCAL = ROOT / "reports/stack-core-shell-runs" / SCORE_FREE_RUN_ID


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _ledger(path: Path, fields: int) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()]
    if any(len(row) != fields for row in rows):
        raise RuntimeError(f"production-lock harvest ledger differs: {path.name}")
    return rows


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _gcs_parts(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None:
        raise RuntimeError("production-lock harvest URI differs")
    return match.group(1), match.group(2)


def _validate_manifest(out: Path, value: dict[str, str]) -> None:
    fixed = {
        "run_id": RUN_ID, "output_prefix": PREFIX,
        "historical_protocol_sha256": HISTORICAL_PROTOCOL_SHA256,
        "execution_protocol_sha256": attempts.EXECUTION_PROTOCOL_SHA256,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": "7200",
        "max_retries": "0", "uses_realized_outcomes": "false",
        "effect_fields_inspected": "false", "actual_scores_queried": "false",
        "treatment_constructed": "true", "production_change_licensed": "false",
        "historical_scoring_licensed": "true",
    }
    if any(value.get(key) != expected for key, expected in fixed.items()) or \
            value.get("finisher_sha256") != _sha(Path(__file__)) or \
            value.get("attempt_manager_sha256") != _sha(Path(attempts.__file__)) or \
            not re.fullmatch(r"[0-9a-f]{40}", value.get("code_sha", "")) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", value.get("image", "")) or \
            not re.fullmatch(
                r"[0-9a-f]{64}", value.get("scorefree_report_sha256", ""),
            ) or not re.fullmatch(
                r"[0-9a-f]{64}", value.get("scorefree_completion_sha256", ""),
            ):
        raise RuntimeError("production-lock harvest manifest differs")
    for key, relative in (
        ("runner_sha256", "scripts/run_stack_core_shell_production_lock.py"),
        ("aggregator_sha256", "scripts/aggregate_stack_core_shell_production_locks.py"),
        ("source_loader_sha256", "scripts/stack_core_shell_sources.py"),
        ("canary_sha256", "scripts/cloud_wait_stack_core_shell_lock_canary.sh"),
        ("canary_validator_sha256", "scripts/validate_stack_core_shell_lock_canary.py"),
    ):
        if value.get(key) != _sha(ROOT / relative):
            raise RuntimeError(f"production-lock harvest source differs: {key}")
    scorefree = ROOT / "reports/stack-core-shell-runs" / SCORE_FREE_RUN_ID
    if _sha(scorefree / "report.json") != value["scorefree_report_sha256"] or \
            _sha(scorefree / "completion.txt") != \
            value["scorefree_completion_sha256"] or \
            _sha(scorefree / "accepted-executions.txt") != \
            value["scorefree_accepted_execution_ledger_sha256"]:
        raise RuntimeError("production-lock score-free binding differs")
    completion = _manifest(scorefree / "completion.txt")
    if completion.get("disposition") != "stack-core-shell-shadow-licensed" or \
            completion.get("historical_scoring_licensed") != "true" or \
            completion.get("report_sha256") != value["scorefree_report_sha256"] or \
            completion.get("accepted_execution_ledger_sha256") != \
            value["scorefree_accepted_execution_ledger_sha256"]:
        raise RuntimeError("production-lock score-free license differs")


def finish(out: Path = DEFAULT_OUT) -> dict[str, object]:
    required = [
        out / "manifest.txt", out / "executions.txt",
        out / "retry-executions.txt", out / "accepted-executions.txt",
        out / "primary-attempt-classification.json",
        out / "primary-object-status.json", out / "attempt-resolution.json",
        out / "canary-completion.txt", out / "grid-release.txt",
        out / "build-metadata.json",
    ]
    if not all(path.is_file() for path in required):
        raise RuntimeError("production-lock strict harvest receipt is incomplete")
    immutable = [
        out / "report.json", out / "completion.txt", out / "execution-metadata",
        out / "object-metadata", out / "shards",
    ]
    if any(path.exists() for path in immutable):
        raise RuntimeError("immutable production-lock strict harvest already exists")
    manifest = _manifest(out / "manifest.txt")
    _validate_manifest(out, manifest)
    resolution = attempts.validate(out)
    if resolution.get("disposition") not in {
        "accepted-primary-population",
        "accepted-population-with-platform-replacements",
    }:
        raise RuntimeError("production-lock attempt population is terminally invalid")
    primary = _ledger(out / "executions.txt", 5)
    retries = _ledger(out / "retry-executions.txt", 6)
    accepted = _ledger(out / "accepted-executions.txt", 5)
    if len(primary) != 54 or len(accepted) != 54 or \
            _sha(out / "accepted-executions.txt") != \
            resolution.get("accepted_execution_ledger_sha256"):
        raise RuntimeError("production-lock accepted execution ledger differs")

    metadata_pending = out / "execution-metadata.pending"
    object_pending = out / "object-metadata.pending"
    shards_pending = out / "shards.pending"
    for path in (metadata_pending, object_pending, shards_pending):
        path.mkdir()
    primary_by_job = {row[2]: row[3] for row in primary}
    retry_by_job = {row[2]: row[4] for row in retries}
    objects: dict[tuple[int, int], tuple[str, dict]] = {}
    for season, week, job, execution, uri in accepted:
        expected_attempts = sorted(filter(None, [
            primary_by_job.get(job), retry_by_job.get(job),
        ]))
        if transport._job_executions(job) != expected_attempts:
            raise RuntimeError("production-lock Cloud attempt population differs")
        metadata = transport._execution_metadata(execution)
        attempts._validate_contract(
            metadata, manifest, [season, week, job, execution, uri],
        )
        completed = transport._completed(metadata)
        status = metadata["status"]
        if completed.get("status") != "True" or \
                int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0:
            raise RuntimeError("production-lock accepted execution is not successful")
        object_value = transport._object_metadata(uri)
        if object_value is None:
            raise RuntimeError("production-lock accepted output object is absent")
        _write_json(metadata_pending / f"{execution}.json", metadata)
        _write_json(object_pending / f"slate-{season}-{week}.json", object_value)
        objects[(int(season), int(week))] = (uri, object_value)

    gcs = storage.Client(project=PROJECT)
    for (season, week), (uri, object_value) in sorted(objects.items()):
        bucket, name = _gcs_parts(uri)
        blob = gcs.bucket(bucket).blob(name)
        blob.reload()
        raw = blob.download_as_bytes()
        if str(blob.generation) != str(object_value.get("generation")) or \
                len(raw) != int(object_value.get("size", -1)):
            raise RuntimeError("production-lock shard changed before download")
        json.loads(raw)
        (shards_pending / f"slate-{season}-{week}.json").write_bytes(raw)

    report = aggregate(sorted(shards_pending.glob("slate-*.json")))
    if report.get("version") != REPORT_VERSION or \
            report.get("run_id") != RUN_ID or \
            report.get("code_sha") != manifest["code_sha"] or \
            report.get("analysis_image") != manifest["image"] or \
            report.get("uses_realized_outcomes") is not False or \
            report.get("actual_scores_queried") is not False or \
            report.get("production_change_licensed") is not False or \
            report.get("historical_scoring_licensed") is not True:
        raise RuntimeError("production-lock aggregate identity or license differs")
    report_raw = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    report_sha = sha256(report_raw).hexdigest()
    report_path = out / "report.pending.json"
    report_path.write_bytes(report_raw)
    completion_lines = [
        "validated_at=" + datetime.now(timezone.utc).isoformat(),
        f"run_id={RUN_ID}", "executions=54", "slates=54",
        "source_artifacts=270", f"report_sha256={report_sha}",
        f"accepted_execution_ledger_sha256={_sha(out / 'accepted-executions.txt')}",
        f"scorefree_report_sha256={manifest['scorefree_report_sha256']}",
        f"scorefree_completion_sha256={manifest['scorefree_completion_sha256']}",
        "uses_realized_outcomes=false", "actual_scores_queried=false",
        "production_change_licensed=false", "historical_scoring_licensed=true",
        "rosters_locked_before_actual_query=true",
    ]
    completion_raw = ("\n".join(completion_lines) + "\n").encode()
    completion_path = out / "completion.pending.txt"
    completion_path.write_bytes(completion_raw)

    report_upload = _upload_create_only(gcs, f"{PREFIX}/report.json", report_raw)
    completion_upload = _upload_create_only(
        gcs, f"{PREFIX}/completion.txt", completion_raw,
    )
    _write_json(out / "report-upload.json", report_upload)
    _write_json(out / "completion-upload.json", completion_upload)
    metadata_pending.rename(out / "execution-metadata")
    object_pending.rename(out / "object-metadata")
    shards_pending.rename(out / "shards")
    report_path.rename(out / "report.json")
    completion_path.rename(out / "completion.txt")
    (out / "report.sha256").write_text(
        f"{report_sha}  {out / 'report.json'}\n", encoding="utf-8",
    )
    (out / "completion.sha256").write_text(
        f"{sha256(completion_raw).hexdigest()}  {out / 'completion.txt'}\n",
        encoding="utf-8",
    )
    print("STACK_CORE_SHELL_PRODUCTION_LOCKS_STRICTLY_HARVESTED")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    finish(args.output_dir)


if __name__ == "__main__":
    main()
