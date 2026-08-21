#!/usr/bin/env python3
"""Archive the exact A7-v2 build-gate failed-preclaim shell.

This is a local-only administrative recovery.  It can read Cloud Run and GCS
metadata to prove absence, but has no update, execute, upload, delete, lease,
BigQuery, log-API, science-body, or outcome path.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Final

from google.cloud import storage

import recover_a7_v2_empty_preflight_shell as prior


ROOT: Final = Path(__file__).resolve().parents[1]
RUN_ID: Final = prior.RUN_ID
RECOVERY_ID: Final = "20260821-a7-v2-build-gate-preclaim-recovery-v1"
OLD_CODE_SHA: Final = prior.CODE_SHA
OLD_BUILD_ID: Final = prior.BUILD_ID
OLD_IMAGE: Final = prior.IMAGE
OLD_IMAGE_TAG: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:"
    "a7-v2-7057554-20260820"
)
GIT_SOURCE_URL: Final = "https://github.com/espechtsoftware/nfl-predictions.git"

PROTOCOL_PATH: Final = (
    "reports/2026-08-21-a7-v2-build-gate-preclaim-recovery-protocol.md"
)
PROTOCOL_SHA256: Final = (
    "3db061f916b46024d9ff91f5a106dde83673369db42265e670e1eb18a96c5e84"
)
REPAIRED_FINISHER_SHA256: Final = (
    "d1f93cbe10a9e0d0d064dff36e9f168db3259a8fb833012df56f513fad509490"
)
CLOUDBUILD_SHA256: Final = (
    # Retrieval-only smoke additions do not alter the frozen A7 worker law,
    # but the administrative recovery still pins the complete build file.
    "648b8d944d08690ab2255396c9ca6e388e8b6c29785e58be3d35f31a62c7c8c5"
)
PRIOR_HELPER_SHA256: Final = (
    "2f2e491bfbcb08353e7af64632f29067644d1714c29fad22b6195606a9d39c6b"
)

FROZEN_UNCHANGED_PATHS: Final = (
    "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol-v2.md",
    "src/nfl_dfs/research/a7_select_ladder.py",
    "scripts/run_a7_select_ladder.py",
    "scripts/freeze_a7_select_ladder.py",
    "scripts/cloud_a7_select_ladder.sh",
    "scripts/watch_a7_select_ladder_queue.sh",
)
FRESH_COMMIT_PATHS: Final = (
    "cloudbuild.yaml",
    "scripts/finish_a7_select_ladder.py",
    "tests/test_finish_a7_select_ladder.py",
    "scripts/recover_a7_v2_empty_preflight_shell.py",
    PROTOCOL_PATH,
    "scripts/recover_a7_v2_build_gate_preclaim.py",
    "tests/test_recover_a7_v2_build_gate_preclaim.py",
)
REPAIR_ENV_NAMES: Final = (
    "A7_FINISHER_REPAIR_SHA256",
    "A7_LAUNCHER_REPAIR_SHA256",
    "A7_WATCHER_REPAIR_SHA256",
)

DEFAULT_SHELL: Final = (
    ROOT / "reports/a7-select-ladder-preflight-runs" / RUN_ID
)
DEFAULT_HISTORICAL_OUT: Final = (
    ROOT / "reports/a7-select-ladder-runs" / RUN_ID
)
DEFAULT_HISTORICAL_PENDING: Final = (
    ROOT / "reports/a7-select-ladder-runs" / f".{RUN_ID}.prepare.pending"
)
DEFAULT_ARCHIVE: Final = (
    ROOT / "reports/a7-select-ladder-preflight-recovery-runs" / RECOVERY_ID
)
DEFAULT_LOG: Final = prior.DEFAULT_LOG
ARCHIVED_SHELL_NAME: Final = "failed-preclaim-shell"
ARCHIVED_LOG_NAME: Final = "watcher-failure.log"

EXPECTED_SHELL_STAT: Final = {
    "device": 2096,
    "inode": 360769,
    "mode": stat.S_IFDIR | 0o755,
    "links": 2,
    "uid": 1000,
    "gid": 1000,
    "size": 4096,
    "mtime_ns": 1787289233956666000,
    "ctime_ns": 1787289233956666000,
}
EXPECTED_ENTRY_STATS: Final = {
    ".inventory-empty": {
        "device": 2096,
        "inode": 360770,
        "mode": stat.S_IFREG | 0o644,
        "links": 1,
        "uid": 1000,
        "gid": 1000,
        "size": 0,
        "mtime_ns": 1787289232100667109,
        "ctime_ns": 1787289232100667109,
    },
    "build-metadata.json": {
        "device": 2096,
        "inode": 360773,
        "mode": stat.S_IFREG | 0o644,
        "links": 1,
        "uid": 1000,
        "gid": 1000,
        "size": 10237,
        "mtime_ns": 1787289233818215783,
        "ctime_ns": 1787289233818215783,
    },
}
EXPECTED_ENTRY_SHA256: Final = {
    ".inventory-empty": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "build-metadata.json": (
        "7695c0fc86a2f0afaf4c41cf3106d49532a296c23eeb8cbcf6328f72939613d2"
    ),
}
EXPECTED_LOG_STAT: Final = {
    "device": 2096,
    "inode": 360670,
    "mode": stat.S_IFREG | 0o644,
    "links": 1,
    "uid": 1000,
    "gid": 1000,
    "size": 370,
    "mtime_ns": 1787289234624665601,
    "ctime_ns": 1787289234624665601,
}
EXPECTED_LOG_SHA256: Final = (
    "9e71eb3266710a458b6950e5f1093b6271d657514c2edaaf69899baa72b0d514"
)

RECEIPT_FILES: Final = (
    ARCHIVED_LOG_NAME,
    "job-metadata.json",
    "job-executions.json",
    "schedulers.json",
    "cloud-absence.json",
    "process-census.json",
    "incident.json",
)

GitLoader = Callable[[Path, str, str], bytes]
JsonLoader = Callable[[], Any]
ProcessLoader = Callable[[], list[dict[str, Any]]]


def _validate_sources(
    root: Path,
    *,
    fresh_code_sha: str,
    old_git_loader: GitLoader,
    fresh_git_loader: GitLoader,
    env: Mapping[str, str],
) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", fresh_code_sha) is None or \
            fresh_code_sha == OLD_CODE_SHA:
        raise RuntimeError("A7-v2 fresh repair source identity differs")
    if any(env.get(name, "") for name in REPAIR_ENV_NAMES):
        raise RuntimeError("A7-v2 preclaim recovery forbids repair overrides")

    protocol = root / PROTOCOL_PATH
    if protocol.is_symlink() or not protocol.is_file() or \
            prior._sha(protocol) != PROTOCOL_SHA256:
        raise RuntimeError("A7-v2 build-gate recovery protocol differs")

    frozen: dict[str, str] = {}
    for relative in FROZEN_UNCHANGED_PATHS:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"A7-v2 frozen source is absent: {relative}")
        raw = path.read_bytes()
        if raw != old_git_loader(root, OLD_CODE_SHA, relative):
            raise RuntimeError(f"A7-v2 frozen source changed: {relative}")
        frozen[relative] = prior._sha_bytes(raw)

    fresh: dict[str, str] = {}
    for relative in FRESH_COMMIT_PATHS:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"A7-v2 fresh source is absent: {relative}")
        raw = path.read_bytes()
        if raw != fresh_git_loader(root, fresh_code_sha, relative):
            raise RuntimeError(f"A7-v2 fresh committed source differs: {relative}")
        fresh[relative] = prior._sha_bytes(raw)
    if fresh["scripts/finish_a7_select_ladder.py"] != \
            REPAIRED_FINISHER_SHA256 or fresh["cloudbuild.yaml"] != \
            CLOUDBUILD_SHA256 or fresh[
                "scripts/recover_a7_v2_empty_preflight_shell.py"
            ] != PRIOR_HELPER_SHA256:
        raise RuntimeError("A7-v2 exact administrative repair bytes differ")
    if prior._sha_bytes(old_git_loader(
        root, OLD_CODE_SHA, "scripts/finish_a7_select_ladder.py",
    )) == REPAIRED_FINISHER_SHA256:
        raise RuntimeError("A7-v2 build-gate repair is vacuous")
    return {
        "old_code_sha": OLD_CODE_SHA,
        "fresh_code_sha": fresh_code_sha,
        "frozen_unchanged_sha256": frozen,
        "fresh_committed_sha256": fresh,
        "repair_environment": {name: "unset" for name in REPAIR_ENV_NAMES},
    }


def _validate_build_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("id") != OLD_BUILD_ID or \
            value.get("status") != "SUCCESS" or value.get("source") != {
                "gitSource": {
                    "url": GIT_SOURCE_URL,
                    "revision": OLD_CODE_SHA,
                }
            }:
        raise RuntimeError("A7-v2 retained failed-gate build identity differs")
    substitutions = value.get("substitutions")
    steps = value.get("steps")
    results = value.get("results")
    if not isinstance(substitutions, dict) or substitutions.get(
        "_IMAGE"
    ) != OLD_IMAGE_TAG or not isinstance(steps, list) or len(steps) != 3 or \
            not isinstance(results, dict):
        raise RuntimeError("A7-v2 retained failed-gate build contract differs")
    smoke = steps[2].get("args", [None, None])[1] if isinstance(
        steps[2], dict
    ) else None
    images = results.get("images")
    if not isinstance(smoke, str) or not isinstance(images, list) or not any(
        isinstance(row, dict)
        and row.get("name") == OLD_IMAGE_TAG
        and row.get("digest") == OLD_IMAGE.rsplit("@", 1)[1]
        for row in images
    ):
        raise RuntimeError("A7-v2 retained failed-gate image differs")
    required = (
        "run_a2a_rank_factor_split_census.py --help >/dev/null",
        "run_b1_corpus_tail_model.py --help >/dev/null",
        "watch_a7_select_ladder_queue.sh",
    )
    forbidden = (
        "run_lr8_training_source.py",
        "finish_lr8_training_source_smoke.py",
        "cloud_lr8_training_source_smoke.sh",
        "watch_lr8_training_source_smoke_queue.sh",
    )
    if any(smoke.count(item) != 1 for item in required) or any(
        item in smoke for item in forbidden
    ):
        raise RuntimeError("A7-v2 retained failed-gate smoke population differs")
    return value


def _validate_shell(
    shell: Path,
    *,
    expected_shell_stat: Mapping[str, int],
    expected_entry_stats: Mapping[str, Mapping[str, int]],
    expected_entry_sha256: Mapping[str, str],
) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    shell_stat = prior._validate_stat(
        shell, expected_shell_stat, kind="failed-preclaim shell",
    )
    if not stat.S_ISDIR(shell_stat["mode"]):
        raise RuntimeError("A7-v2 failed-preclaim shell is not a directory")
    names = sorted(entry.name for entry in os.scandir(shell))
    if names != sorted(expected_entry_stats) or set(expected_entry_stats) != set(
        expected_entry_sha256
    ):
        raise RuntimeError("A7-v2 failed-preclaim shell population differs")
    receipts: dict[str, dict[str, Any]] = {}
    for name in names:
        path = shell / name
        file_stat = prior._validate_stat(
            path, expected_entry_stats[name], kind=f"failed-preclaim {name}",
        )
        if not stat.S_ISREG(file_stat["mode"]):
            raise RuntimeError(f"A7-v2 failed-preclaim entry is not regular: {name}")
        raw = path.read_bytes()
        digest = prior._sha_bytes(raw)
        if digest != expected_entry_sha256[name]:
            raise RuntimeError(f"A7-v2 failed-preclaim entry bytes differ: {name}")
        receipts[name] = {"stat": file_stat, "sha256": digest}
    if (shell / ".inventory-empty").read_bytes() != b"":
        raise RuntimeError("A7-v2 empty-prefix inventory differs")
    raw = (shell / "build-metadata.json").read_bytes()
    build = prior._strict_json_bytes(raw, label="failed-gate build metadata")
    if raw != prior._canonical_json(build):
        raise RuntimeError("A7-v2 failed-gate build metadata is not canonical")
    _validate_build_metadata(build)
    return shell_stat, receipts


def _validate_cloud_absence(client: storage.Client) -> dict[str, Any]:
    bucket, prefix = prior._gcs_parts(prior.PREFIX + "/")
    if list(client.list_blobs(bucket, prefix=prefix)):
        raise RuntimeError("A7-v2 cloud prefix is not empty")
    for uri in prior.REQUIRED_ABSENT_URIS:
        prior._require_not_found(client, uri)
    prior._require_not_found(client, prior.LEASE_URI)
    return {
        "version": "a7-v2-build-gate-preclaim-cloud-absence-v1",
        "run_id": RUN_ID,
        "prefix": prior.PREFIX,
        "prefix_objects": [],
        "direct_not_found_uris": list(prior.REQUIRED_ABSENT_URIS),
        "historical_outcome_lease": {
            "uri": prior.LEASE_URI,
            "state": "absent",
        },
        "authentication_or_network_errors_count_as_absent": False,
    }


def _matching_processes() -> list[dict[str, Any]]:
    markers = (
        "watch_a7_select_ladder_queue.sh",
        "cloud_a7_select_ladder.sh",
        "run_a7_select_ladder.py",
        "finish_a7_select_ladder.py",
    )
    rows: list[dict[str, Any]] = []
    for entry in sorted(Path("/proc").glob("[0-9]*"), key=lambda path: int(path.name)):
        try:
            raw = (entry / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        command = raw.replace(b"\0", b" ").decode(
            "utf-8", errors="replace",
        ).strip()
        if any(marker in command for marker in markers):
            rows.append({"pid": int(entry.name), "command": command})
    return rows


def recover(
    *,
    execute: bool,
    fresh_code_sha: str,
    root: Path = ROOT,
    shell: Path = DEFAULT_SHELL,
    historical_out: Path = DEFAULT_HISTORICAL_OUT,
    historical_pending: Path = DEFAULT_HISTORICAL_PENDING,
    archive: Path = DEFAULT_ARCHIVE,
    log_path: Path = DEFAULT_LOG,
    expected_shell_stat: Mapping[str, int] = EXPECTED_SHELL_STAT,
    expected_entry_stats: Mapping[str, Mapping[str, int]] = EXPECTED_ENTRY_STATS,
    expected_entry_sha256: Mapping[str, str] = EXPECTED_ENTRY_SHA256,
    expected_log_stat: Mapping[str, int] = EXPECTED_LOG_STAT,
    expected_log_sha256: str = EXPECTED_LOG_SHA256,
    client: storage.Client | None = None,
    job_loader: JsonLoader = prior._describe_job,
    executions_loader: JsonLoader = prior._list_executions,
    schedulers_loader: JsonLoader = prior._list_schedulers,
    process_loader: ProcessLoader = _matching_processes,
    old_git_loader: GitLoader = prior._git_blob,
    fresh_git_loader: GitLoader = prior._git_blob,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] = prior._default_now,
) -> dict[str, Any]:
    if not execute:
        raise RuntimeError("A7-v2 build-gate recovery requires explicit execute")
    if archive.exists() or archive.is_symlink():
        raise RuntimeError("A7-v2 build-gate recovery archive already exists")
    if any(
        target.exists() or target.is_symlink()
        for target in (historical_out, historical_pending)
    ):
        raise RuntimeError("A7-v2 historical local output unexpectedly exists")

    source_receipt = _validate_sources(
        root,
        fresh_code_sha=fresh_code_sha,
        old_git_loader=old_git_loader,
        fresh_git_loader=fresh_git_loader,
        env=os.environ if env is None else env,
    )
    shell_stat, shell_receipts = _validate_shell(
        shell,
        expected_shell_stat=expected_shell_stat,
        expected_entry_stats=expected_entry_stats,
        expected_entry_sha256=expected_entry_sha256,
    )
    log_stat = prior._validate_stat(
        log_path, expected_log_stat, kind="watcher log",
    )
    log_raw = log_path.read_bytes()
    if not log_raw or prior._sha_bytes(log_raw) != expected_log_sha256:
        raise RuntimeError("A7-v2 exact failed-gate watcher log differs")
    processes = process_loader()
    if processes:
        raise RuntimeError("A7-v2 local watcher/launcher process still exists")

    anchor_job = prior._anchor(
        root, prior.ANCHOR_JOB_PATH, prior.ANCHOR_JOB_SHA256, label="job",
    )
    prior_executions = prior._anchor(
        root, prior.ANCHOR_EXECUTIONS_PATH, prior.ANCHOR_EXECUTIONS_SHA256,
        label="execution-census",
    )
    last_execution = prior._anchor(
        root, prior.ANCHOR_LAST_EXECUTION_PATH,
        prior.ANCHOR_LAST_EXECUTION_SHA256, label="last-execution",
    )
    job = prior._validate_job(job_loader(), anchor=anchor_job)
    executions = prior._validate_executions(
        executions_loader(), prior_anchor=prior_executions,
        last_anchor=last_execution,
    )
    schedulers = prior._validate_schedulers(schedulers_loader())
    storage_client = client or storage.Client(project=prior.PROJECT)
    cloud_absence = _validate_cloud_absence(storage_client)

    captured = now()
    if captured.tzinfo is None or captured.utcoffset() != \
            timezone.utc.utcoffset(captured):
        raise RuntimeError("A7-v2 recovery capture time is not UTC")
    captured_at = captured.isoformat()
    process_receipt = {
        "version": "a7-v2-build-gate-preclaim-process-census-v1",
        "run_id": RUN_ID,
        "matching_processes": [],
        "captured_at": captured_at,
    }
    incident = {
        "version": "a7-v2-build-gate-preclaim-incident-v1",
        "recovery_id": RECOVERY_ID,
        "run_id": RUN_ID,
        "captured_at": captured_at,
        "old_build": {
            "code_sha": OLD_CODE_SHA,
            "build_id": OLD_BUILD_ID,
            "image": OLD_IMAGE,
            "image_tag": OLD_IMAGE_TAG,
            "reusable_for_a7_v2": False,
        },
        "fresh_source": source_receipt,
        "protocol": {"path": PROTOCOL_PATH, "sha256": PROTOCOL_SHA256},
        "failure": {
            "phase": "preflight-prepare-build-metadata-validation",
            "classification": "administrative-failed-preclaim",
            "exact_error": "A7 build/test/image gate differs",
            "submitted_build_matches_own_cloudbuild": True,
            "later_lr8_smokes_absent_from_submitted_contract": True,
            "working_tree_cross_experiment_coupling_removed": True,
            "repaired_gate_uses_submitted_code_sha_cloudbuild": True,
            "normalization_or_gate_relaxation_used": False,
        },
        "local_boundary": {
            "shell_path": shell.relative_to(root).as_posix(),
            "shell_stat": shell_stat,
            "shell_entries": shell_receipts,
            "watcher_log_path": str(log_path),
            "watcher_log_stat": log_stat,
            "watcher_log_sha256": expected_log_sha256,
            "watcher_log_nonempty": True,
            "historical_run_absent": True,
            "historical_pending_absent": True,
        },
        "cloud_boundary": {
            "prefix_empty": True,
            "job_claim_absent": True,
            "historical_outcome_lease_absent": True,
            "job_uid": prior.JOB_UID,
            "job_generation": prior.JOB_GENERATION,
            "job_spec_sha256": prior.JOB_SPEC_SHA256,
            "execution_count": len(executions),
            "execution_names_equal_retained_terminal_set": True,
            "reused_job_updated": False,
            "reused_job_idle": True,
            "reused_job_unscheduled": True,
        },
        "outcome_boundary": {
            "job_claim_created": False,
            "job_updated": False,
            "execution_created": False,
            "historical_outcome_lease_acquired": False,
            "scientific_artifact_body_read": False,
            "actual_score_query_executed": False,
            "historical_look_consumed": False,
        },
    }

    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.parent.is_symlink():
        raise RuntimeError("A7-v2 recovery archive parent is linked")
    archive.mkdir()
    if archive.stat().st_dev != shell_stat["device"]:
        raise RuntimeError("A7-v2 recovery archive is not on the shell filesystem")
    prior._write_durable(archive / ARCHIVED_LOG_NAME, log_raw)
    values = {
        "job-metadata.json": job,
        "job-executions.json": executions,
        "schedulers.json": schedulers,
        "cloud-absence.json": cloud_absence,
        "process-census.json": process_receipt,
        "incident.json": incident,
    }
    for name, value in values.items():
        prior._write_durable(archive / name, prior._canonical_json(value))
    prior._write_durable(
        archive / "evidence.sha256", prior._ledger(archive, RECEIPT_FILES),
    )
    prior._fsync_dir(archive)
    prior._fsync_dir(archive.parent)

    second_source = _validate_sources(
        root,
        fresh_code_sha=fresh_code_sha,
        old_git_loader=old_git_loader,
        fresh_git_loader=fresh_git_loader,
        env=os.environ if env is None else env,
    )
    second_shell = _validate_shell(
        shell,
        expected_shell_stat=expected_shell_stat,
        expected_entry_stats=expected_entry_stats,
        expected_entry_sha256=expected_entry_sha256,
    )
    if second_source != source_receipt or second_shell != (
        shell_stat, shell_receipts,
    ) or prior._validate_stat(
        log_path, expected_log_stat, kind="watcher log",
    ) != log_stat or log_path.read_bytes() != log_raw or process_loader() or \
            prior._canonical_json(prior._validate_job(
                job_loader(), anchor=anchor_job,
            )) != prior._canonical_json(job) or prior._canonical_json(
                prior._validate_executions(
                    executions_loader(), prior_anchor=prior_executions,
                    last_anchor=last_execution,
                )
            ) != prior._canonical_json(executions) or prior._canonical_json(
                prior._validate_schedulers(schedulers_loader())
            ) != prior._canonical_json(schedulers) or prior._canonical_json(
                _validate_cloud_absence(storage_client)
            ) != prior._canonical_json(cloud_absence) or historical_out.exists() or \
            historical_out.is_symlink() or historical_pending.exists() or \
            historical_pending.is_symlink():
        raise RuntimeError("A7-v2 build-gate recovery boundary changed")

    recovery = {
        "version": "a7-v2-build-gate-preclaim-recovery-v1",
        "recovery_id": RECOVERY_ID,
        "run_id": RUN_ID,
        "status": "complete-upon-final-atomic-rename",
        "captured_at": captured_at,
        "fresh_code_sha": fresh_code_sha,
        "protocol": {"path": PROTOCOL_PATH, "sha256": PROTOCOL_SHA256},
        "incident": prior._reference(archive / "incident.json", root),
        "evidence_ledger": prior._reference(
            archive / "evidence.sha256", root,
        ),
        "archive": {
            "source_path": shell.relative_to(root).as_posix(),
            "destination_path": (
                archive.relative_to(root) / ARCHIVED_SHELL_NAME
            ).as_posix(),
            "preserved_stat_before_move": shell_stat,
            "same_filesystem": True,
            "atomic_rename_is_final_state_change": True,
            "recursive_delete_used": False,
        },
        "licenses": {
            "same_v2_fresh_exact_source_build_licensed": True,
            "same_v2_first_preflight_prepare_claim_licensed": True,
            "old_build_or_image_reuse_licensed": False,
            "repair_override_licensed": False,
            "preflight_retry_licensed": False,
            "historical_scoring_licensed": False,
            "prospective_shadow_licensed": False,
            "production_law_scorefree_transfer_licensed": False,
            "production_change_licensed": False,
        },
    }
    prior._write_durable(
        archive / "recovery.json", prior._canonical_json(recovery),
    )
    prior._write_durable(
        archive / "recovery.sha256",
        prior._ledger(archive, ("evidence.sha256", "recovery.json")),
    )
    prior._fsync_dir(archive)
    prior._fsync_dir(archive.parent)

    destination = archive / ARCHIVED_SHELL_NAME
    os.rename(shell, destination)
    prior._fsync_dir(archive)
    prior._fsync_dir(shell.parent)
    moved_stat = prior._stat_receipt(destination)
    for key, value in shell_stat.items():
        if key != "ctime_ns" and moved_stat[key] != value:
            raise RuntimeError("A7-v2 archived failed-preclaim identity changed")
    archived_stat, archived_receipts = _validate_shell(
        destination,
        expected_shell_stat={**expected_shell_stat, "ctime_ns": moved_stat["ctime_ns"]},
        expected_entry_stats=expected_entry_stats,
        expected_entry_sha256=expected_entry_sha256,
    )
    if archived_stat["inode"] != shell_stat["inode"] or \
            archived_receipts != shell_receipts or shell.exists() or \
            shell.is_symlink():
        raise RuntimeError("A7-v2 failed-preclaim atomic archive did not complete")
    return recovery


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-code-sha", required=True)
    parser.add_argument(
        "--execute-build-gate-recovery",
        action="store_true",
        help="perform the one exact local-only atomic archive operation",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = recover(
        execute=args.execute_build_gate_recovery,
        fresh_code_sha=args.fresh_code_sha,
    )
    print(
        "A7_V2_BUILD_GATE_PRECLAIM_RECOVERED "
        f"run_id={result['run_id']} recovery_id={result['recovery_id']} "
        f"fresh_code_sha={result['fresh_code_sha']} "
        "fresh_exact_source_build_licensed=true first_claim_licensed=true"
    )


if __name__ == "__main__":
    main()
