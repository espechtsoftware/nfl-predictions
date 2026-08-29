#!/usr/bin/env python3
"""Canary-gated, quota-neutral transport for the frozen recourse experiment."""

from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
RUN_ID = "20260829-recourse-aware-initial-book-scorefree-kickoff-v2"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"recourse-aware-initial-book-runs/{RUN_ID}"
)
OUT = ROOT / "reports/recourse-aware-initial-book-runs" / RUN_ID
JOB = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
V6_CODE_SHA = "8ae6c22a1d898c2fa4517be15f44d197da9082bf"
V6_BUILD_ID = "cdd1f0a4-0210-4ee7-8cd6-692b87865006"
V6_IMAGE_TAG = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs:r6-current-bank-crossed-screen-8ae6c22a-v2"
)
V6_IMAGE_DIGEST = (
    "sha256:c491ad9e88929d359539d2a713f01b8a7f777ea15725910883a343bdd45a766d"
)
V6_SOURCE_OBJECT = (
    "source/1787935647.532217-ebf48ce4b9c8408689aa2e458b0c4bd6.tgz"
)
V6_SOURCE_GENERATION = "1787935654588405"
CODE_SHA = "cfc7942e79e1557e445922f427a2319b0f286457"
BUILD_ID = "e3552f5c-78f8-4311-ae06-e326dc0a8f96"
IMAGE_TAG = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs:recourse-kickoff-v2-cfc7942e"
)
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs@sha256:"
    "ee5448360ffbd520e51310d9955e6a2e595540d32654fe9f9a321a29dc797a08"
)
IMAGE_DIGEST = IMAGE.rsplit("@", 1)[1]
SOURCE_REPOSITORY = "https://github.com/espechtsoftware/nfl-predictions.git"
RUNNER = "scripts/run_recourse_aware_initial_scorefree.py"
AGGREGATOR = "scripts/aggregate_recourse_aware_initial_scorefree.py"
AMENDMENT = (
    ROOT / "reports/2026-08-28-recourse-aware-initial-book-"
    "single-job-transport-amendment.md"
)
SCIENCE_SHA256 = (
    "0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077"
)
EXECUTION_SHA256 = (
    "3991fdbf36c2018b2ec11625a6be62990c100fdf1f47bde3985c2327e3248c9b"
)
KICKOFF_AMENDMENT_SHA256 = (
    "fec2d7f531cc3dea4a395fec5e02322ee46e88b43d00c09228a083470c4c69db"
)
CBWU_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
FORENSIC_SHA256 = (
    "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
)
RUNTIME_PATHS = (
    "reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md",
    "reports/2026-08-17-recourse-aware-initial-book-execution-protocol.md",
    "reports/2026-08-29-recourse-aware-initial-book-kickoff-population-amendment.md",
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json",
    "src/nfl_dfs/analysis/recourse_aware_initial.py",
    "src/nfl_dfs/analysis/constraint_lattice.py",
    "src/nfl_dfs/research/realistic_recourse_sizing.py",
    "src/nfl_dfs/research/multiseed_candidate_world.py",
    "src/nfl_dfs/research/portfolio_effective_rank.py",
    "src/nfl_dfs/inference/multiseed_portfolio.py",
    "src/nfl_dfs/inference/archetype_candidate_allocator.py",
    "src/nfl_dfs/optimizer/lineup.py",
    "src/nfl_dfs/analysis/atlas_world_ranking.py",
    "scripts/run_recourse_aware_initial_scorefree.py",
    "scripts/aggregate_recourse_aware_initial_scorefree.py",
    "scripts/aggregate_constraint_lattice_scorefree.py",
    "scripts/validate_recourse_aware_initial_canary.py",
    "scripts/run_constraint_lattice_scorefree.py",
    "scripts/run_cbwu_seed_order_audit.py",
)

ALL_CELLS = tuple(
    (season, week)
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
)


class ExecutionPending(RuntimeError):
    """The immutable execution exists but has not terminalized yet."""


def _unique_json(raw: str | bytes) -> Any:
    def unique(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _create_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _create_json(path: Path, value: Mapping[str, Any]) -> None:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    _create_bytes(path, raw)


def _append_fsync(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line.rstrip("\n") + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _run(command: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        list(command), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stderr.strip()}"
        )
    return result


def _gcloud_json(arguments: Sequence[str]) -> Any:
    result = _run(["gcloud", *arguments, "--format=json"])
    return _unique_json(result.stdout)


def expected_uri(season: int, week: int) -> str:
    if season not in {2023, 2024, 2025} or week not in range(1, 19):
        raise ValueError("recourse transport cell is outside frozen grid")
    return f"{PREFIX}/slate-{season}-{week}.json"


def expected_args(season: int, week: int) -> list[str]:
    return [
        RUNNER, "--season", str(season), "--week", str(week),
        "--output-uri", expected_uri(season, week),
    ]


def cell_token(season: int, week: int) -> str:
    expected_uri(season, week)
    return f"{RUN_ID}:{season}:{week}"


def release_cells() -> list[tuple[int, int]]:
    return [cell for cell in ALL_CELLS if cell != (2023, 1)]


def job_update_command() -> list[str]:
    return [
        "gcloud", "run", "jobs", "update", JOB,
        "--project", PROJECT, "--region", REGION,
        "--image", IMAGE, "--tasks", "1", "--parallelism", "1",
        "--cpu", "4", "--memory", "16Gi", "--max-retries", "0",
        "--task-timeout", "4h", "--service-account", SERVICE_ACCOUNT,
        "--set-env-vars", f"CODE_SHA={CODE_SHA},ANALYSIS_IMAGE={IMAGE}",
        "--clear-secrets", "--clear-volumes", "--clear-volume-mounts",
        "--clear-cloudsql-instances", "--clear-vpc-connector",
        "--clear-network",
        "--command", "python", "--args", ",".join(expected_args(2023, 1)),
        "--quiet", "--format=json",
    ]


def execution_command(season: int, week: int) -> list[str]:
    return [
        "gcloud", "run", "jobs", "execute", JOB,
        "--project", PROJECT, "--region", REGION,
        "--tasks", "1", "--task-timeout", "4h",
        "--args", ",".join(expected_args(season, week)),
        "--update-env-vars", f"RECOURSE_TRANSPORT_CELL={cell_token(season, week)}",
        "--async", "--format=value(metadata.name)",
    ]


def execution_names(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise ValueError("recourse transport execution inventory schema differs")
    names = []
    for row in rows:
        metadata = row.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError("recourse transport execution inventory schema differs")
        name = str(metadata.get("name", ""))
        labels = metadata.get("labels", {})
        owners = metadata.get("ownerReferences", [])
        if not isinstance(labels, Mapping) or \
                labels.get("run.googleapis.com/job") != JOB or \
                labels.get("run.googleapis.com/jobUid") != JOB_UID or \
                not isinstance(owners, list) or len(owners) != 1 or \
                owners[0].get("kind") != "Job" or \
                owners[0].get("name") != JOB or owners[0].get("uid") != JOB_UID:
            raise ValueError("recourse transport execution inventory owner differs")
        names.append(name)
    if any(not value for value in names) or len(names) != len(set(names)):
        raise ValueError("recourse transport execution inventory differs")
    return set(names)


def inventory_delta(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]],
) -> set[str]:
    old = execution_names(before)
    current = execution_names(after)
    if not old <= current:
        raise ValueError("recourse transport lost a preexisting execution")
    return current - old


def _assert_terminal_inventory(rows: Sequence[Mapping[str, Any]]) -> None:
    for row in rows:
        completed = [
            value for value in row.get("status", {}).get("conditions", [])
            if value.get("type") == "Completed"
        ]
        if len(completed) != 1 or completed[0].get("status") not in {
            "True", "False",
        }:
            raise ValueError("reused job still has a nonterminal execution")


def _container_task(job: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    outer = job.get("spec", {}).get("template", {}).get("spec", {})
    task = outer.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if outer.get("parallelism") != 1 or outer.get("taskCount") != 1 or \
            len(containers) != 1:
        raise ValueError("recourse reused-job task envelope differs")
    return containers[0], task


def _environment(container: Mapping[str, Any]) -> dict[str, str]:
    rows = container.get("env", [])
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("recourse runtime environment schema differs")
    names = [str(row.get("name", "")) for row in rows]
    if any(not name for name in names) or len(names) != len(set(names)) or any(
        "valueFrom" in row for row in rows
    ):
        raise ValueError("recourse runtime environment schema differs")
    return {name: str(row.get("value", "")) for name, row in zip(names, rows)}


def _assert_isolated_runtime(
    container: Mapping[str, Any], task: Mapping[str, Any],
) -> None:
    if container.get("volumeMounts") not in (None, []) or \
            task.get("volumes") not in (None, []) or \
            task.get("vpcAccess") not in (None, {}) or \
            task.get("cloudSqlInstances") not in (None, []):
        raise ValueError("recourse reused-job inherited runtime attachment")


def validate_job_contract(job: Mapping[str, Any]) -> None:
    metadata = job.get("metadata", {})
    if metadata.get("name") != JOB or metadata.get("uid") != JOB_UID:
        raise ValueError("recourse reused-job UID differs")
    container, task = _container_task(job)
    env = _environment(container)
    _assert_isolated_runtime(container, task)
    if container.get("image") != IMAGE or container.get("command") != ["python"] or \
            container.get("args") != expected_args(2023, 1) or env != {
                "CODE_SHA": CODE_SHA, "ANALYSIS_IMAGE": IMAGE,
            } or container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "14400" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise ValueError("recourse reused-job runtime contract differs")


def validate_execution_contract(
    metadata: Mapping[str, Any], execution: str, season: int, week: int,
    *, require_success: bool,
) -> None:
    if metadata.get("metadata", {}).get("name") != execution or \
            not execution.startswith(JOB + "-"):
        raise ValueError("recourse reused-job execution identity differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise ValueError("recourse execution envelope differs")
    container = containers[0]
    labels = metadata.get("metadata", {}).get("labels", {})
    owners = metadata.get("metadata", {}).get("ownerReferences", [])
    if labels.get("run.googleapis.com/job") != JOB or \
            labels.get("run.googleapis.com/jobUid") != JOB_UID or \
            len(owners) != 1 or owners[0].get("kind") != "Job" or \
            owners[0].get("name") != JOB or owners[0].get("uid") != JOB_UID:
        raise ValueError("recourse execution owner identity differs")
    env = _environment(container)
    _assert_isolated_runtime(container, task)
    if container.get("image") != IMAGE or container.get("command") != ["python"] or \
            container.get("args") != expected_args(season, week) or env != {
                "CODE_SHA": CODE_SHA, "ANALYSIS_IMAGE": IMAGE,
                "RECOURSE_TRANSPORT_CELL": cell_token(season, week),
            } or container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "14400" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise ValueError("recourse execution snapshot differs")
    if require_success:
        status = metadata.get("status", {})
        completed = [
            row for row in status.get("conditions", [])
            if row.get("type") == "Completed"
        ]
        if len(completed) != 1 or completed[0].get("status") != "True" or \
                int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0 or \
                int(status.get("retriedCount") or 0) != 0 or \
                not status.get("completionTime"):
            raise ValueError("recourse canary is not terminal successful")


def execution_state(metadata: Mapping[str, Any]) -> str:
    completed = [
        row for row in metadata.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") not in {
        "True", "False", "Unknown",
    }:
        raise ValueError("recourse execution terminal-state schema differs")
    return str(completed[0]["status"])


def validate_canary_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("version") != \
            "recourse-aware-initial-book-single-job-canary-validation-v1" or \
            receipt.get("status") is not True or \
            receipt.get("disposition") != "actual-final-path-canary-passes" or \
            receipt.get("execution") is None or \
            receipt.get("remaining_cells_released") is not False or \
            receipt.get("outcome_fields_inspected") is not False or \
            receipt.get("effect_fields_inspected") is not False:
        raise ValueError("recourse single-job canary receipt differs")


def _validate_local_sources() -> None:
    commit = _run(["git", "-C", str(ROOT), "cat-file", "-e", f"{CODE_SHA}^{{commit}}"])
    if commit.returncode != 0:
        raise ValueError("recourse image source commit is unavailable")
    for relative in RUNTIME_PATHS:
        current = (ROOT / relative).read_bytes()
        built = _run(
            ["git", "-C", str(ROOT), "show", f"{CODE_SHA}:{relative}"]
        ).stdout.encode()
        if sha256(current).digest() != sha256(built).digest():
            raise ValueError(f"recourse image/runtime source differs: {relative}")
    frozen = {
        ROOT / "reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md": SCIENCE_SHA256,
        ROOT / "reports/2026-08-17-recourse-aware-initial-book-execution-protocol.md": EXECUTION_SHA256,
        ROOT / "reports/2026-08-29-recourse-aware-initial-book-kickoff-population-amendment.md": KICKOFF_AMENDMENT_SHA256,
        ROOT / "reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json": CBWU_SHA256,
    }
    if any(not path.is_file() or _sha(path) != digest for path, digest in frozen.items()):
        raise ValueError("recourse frozen source hash differs")

    dockerfile = _run(
        ["git", "-C", str(ROOT), "show", f"{CODE_SHA}:Dockerfile"]
    ).stdout
    cloudbuild = _run(
        ["git", "-C", str(ROOT), "show", f"{CODE_SHA}:cloudbuild.yaml"]
    ).stdout
    required_docker_tokens = (
        "COPY reports ./reports",
        "COPY src ./src",
        f"COPY {RUNNER} ./{RUNNER}",
        f"COPY {AGGREGATOR} ./{AGGREGATOR}",
        "COPY scripts/run_constraint_lattice_scorefree.py",
        "COPY scripts/run_cbwu_seed_order_audit.py",
    )
    required_smokes = (
        f"python {RUNNER} --help",
        f"python {AGGREGATOR} --help",
    )
    if any(token not in dockerfile for token in required_docker_tokens) or any(
        token not in cloudbuild for token in required_smokes
    ):
        raise ValueError("recourse image dependency packaging differs")


def validate_build(build: Mapping[str, Any]) -> None:
    source = build.get("source", {}).get("gitSource", {})
    resolved = build.get("sourceProvenance", {}).get("resolvedGitSource", {})
    images = build.get("results", {}).get("images", [])
    step_rows = build.get("steps", [])
    if not isinstance(step_rows, list) or any(
        not isinstance(row, Mapping) for row in step_rows
    ):
        raise ValueError("recourse full-runtime build authority differs")
    step_ids = [str(row.get("id", "")) for row in step_rows]
    steps = {step_id: str(row.get("status")) for step_id, row in zip(step_ids, step_rows)}
    by_id = {str(row.get("id")): row for row in step_rows}
    build_args = by_id.get("build-image", {}).get("args")
    smoke_text = "\n".join(map(str, by_id.get("smoke-atlas-mvp-runner", {}).get("args", [])))
    if build.get("id") != BUILD_ID or build.get("status") != "SUCCESS" or \
            source.get("revision") != CODE_SHA or source.get("url") != SOURCE_REPOSITORY or \
            resolved.get("revision") != CODE_SHA or \
            resolved.get("url") != SOURCE_REPOSITORY or \
            step_ids != [
                "full-test-suite", "build-image", "smoke-atlas-mvp-runner",
            ] or steps != {
                "full-test-suite": "SUCCESS",
                "build-image": "SUCCESS",
                "smoke-atlas-mvp-runner": "SUCCESS",
            } or build.get("substitutions", {}).get("_IMAGE") != IMAGE_TAG or \
            build_args != ["build", "-t", IMAGE_TAG, "."] or \
            f"python {RUNNER} --help" not in smoke_text or \
            f"python {AGGREGATOR} --help" not in smoke_text or \
            IMAGE_TAG not in build.get("artifacts", {}).get("images", []) or \
            not any(row.get("name") == IMAGE_TAG and row.get("digest") == IMAGE_DIGEST
                    for row in images):
        raise ValueError("recourse full-runtime build authority differs")


def validate_narrow_v6_build(build: Mapping[str, Any], dockerfile: str) -> None:
    source = build.get("source", {}).get("storageSource", {})
    images = build.get("results", {}).get("images", [])
    if build.get("id") != V6_BUILD_ID or build.get("status") != "SUCCESS" or \
            source.get("object") != V6_SOURCE_OBJECT or \
            str(source.get("generation")) != V6_SOURCE_GENERATION or \
            not any(
                row.get("name") == V6_IMAGE_TAG and
                row.get("digest") == V6_IMAGE_DIGEST for row in images
            ) or RUNNER in dockerfile:
        raise ValueError("narrow V6 build/source incompatibility proof differs")


def validate_image(metadata: Mapping[str, Any]) -> None:
    summary = metadata.get("image_summary", {})
    if summary.get("digest") != IMAGE_DIGEST or \
            summary.get("fully_qualified_digest") != IMAGE:
        raise ValueError("recourse full-runtime registry authority differs")


def _stable_job(job: Mapping[str, Any]) -> dict[str, Any]:
    metadata = job.get("metadata", {})
    annotations = dict(metadata.get("annotations", {}) or {})
    labels = dict(metadata.get("labels", {}) or {})
    for key in (
        "run.googleapis.com/client-name",
        "run.googleapis.com/client-version",
        "run.googleapis.com/lastModifier",
        "run.googleapis.com/operation-id",
    ):
        annotations.pop(key, None)
    labels.pop("run.googleapis.com/lastUpdatedTime", None)
    return {
        "name": metadata.get("name"),
        "uid": metadata.get("uid"),
        "annotations": annotations,
        "labels": labels,
        "spec": job.get("spec"),
    }


def validate_restored_job(
    before: Mapping[str, Any], restored: Mapping[str, Any],
) -> None:
    if _stable_job(before) != _stable_job(restored):
        raise ValueError("recourse shared job restoration differs")


def _create_or_equal_json(path: Path, value: Mapping[str, Any]) -> None:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != raw:
            raise ValueError(f"immutable recourse state differs: {path}")
        return
    _create_bytes(path, raw)


def _create_or_equal_bytes(path: Path, raw: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != raw:
            raise ValueError(f"immutable recourse state differs: {path}")
        return
    _create_bytes(path, raw)


def _record_terminal_failure(phase: str, detail: str) -> None:
    if not OUT.is_dir() or OUT.is_symlink():
        return
    _create_or_equal_json(OUT / "terminal-failure.json", {
        "version": "recourse-aware-initial-book-single-job-failure-v1",
        "phase": phase,
        "detail": detail,
        "job": JOB,
        "job_uid": JOB_UID,
        "run_id": RUN_ID,
        "terminal": True,
    })


def restore_shared_job(
    reason: str, *, require_terminal_state: bool = True,
    allow_partial_contract: bool = False,
) -> None:
    if not OUT.is_dir() or OUT.is_symlink():
        raise ValueError("recourse restoration run state is absent or unsafe")
    before_path = OUT / "job-before.json"
    export_path = OUT / "job-before.export.yaml"
    if not before_path.is_file() or before_path.is_symlink() or \
            not export_path.is_file() or export_path.is_symlink():
        raise ValueError("recourse restoration source is absent or unsafe")
    if require_terminal_state and not any(
        (OUT / name).is_file()
        for name in ("harvest-completion.json", "terminal-failure.json")
    ):
        raise ValueError("recourse restoration lacks a terminal run state")
    before = _unique_json(before_path.read_bytes())
    if not isinstance(before, Mapping):
        raise ValueError("recourse restoration source schema differs")
    receipt_path = OUT / "job-restoration.json"
    current = _gcloud_json([
        "run", "jobs", "describe", JOB, "--project", PROJECT,
        "--region", REGION,
    ])
    if not isinstance(current, Mapping) or \
            current.get("metadata", {}).get("name") != JOB or \
            current.get("metadata", {}).get("uid") != JOB_UID:
        raise ValueError("recourse shared job identity changed before restoration")
    if receipt_path.is_file():
        validate_restored_job(before, current)
        return
    already_restored = _stable_job(before) == _stable_job(current)
    if not already_restored:
        if not allow_partial_contract:
            validate_job_contract(current)
        _run([
            "gcloud", "run", "jobs", "replace", str(export_path),
            "--project", PROJECT, "--region", REGION, "--quiet",
            "--format=json",
        ])
        current = _gcloud_json([
            "run", "jobs", "describe", JOB, "--project", PROJECT,
            "--region", REGION,
        ])
        if not isinstance(current, Mapping):
            raise ValueError("recourse restored job response schema differs")
        validate_restored_job(before, current)
    receipt = {
        "version": "recourse-aware-initial-book-shared-job-restoration-v1",
        "reason": reason,
        "job": JOB,
        "job_uid": JOB_UID,
        "already_restored": already_restored,
        "job_before_sha256": _sha(before_path),
        "partial_contract_recovery": allow_partial_contract,
        "job_before_export_sha256": _sha(export_path),
        "restored_stable_sha256": sha256(
            json.dumps(_stable_job(current), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "restored": True,
    }
    _create_json(receipt_path, receipt)


def _completion(path: Path) -> dict[str, str] | None:
    target = path / "completion.txt"
    if not target.is_file():
        return None
    return dict(
        line.split("=", 1) for line in target.read_text().splitlines()
        if "=" in line
    )


def queue_release_receipt() -> dict[str, Any]:
    preflight = ROOT / "reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
    repair = ROOT / "reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
    parity = ROOT / "reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"
    p = _completion(preflight)
    q = _completion(parity)
    census = repair / "terminal-census-completion.txt"
    if p is None or p.get("status") != "True" or _completion(repair) is not None or \
            not census.is_file() or q is None or q.get("status") != "True" or \
            q.get("disposition") not in {
                "real-slate-parity-passes", "real-slate-parity-fails",
            }:
        raise ValueError("recourse queue is not terminal on the frozen branch")
    files = [preflight / "completion.txt", census, parity / "completion.txt"]
    return {
        "version": "recourse-aware-queue-release-v1",
        "branch": "repair5-failed-parity-closed",
        "bindings": {str(path): _sha(path) for path in files},
    }


def _prefix_objects() -> list[str]:
    result = _run([
        "gcloud", "storage", "ls", f"{PREFIX}/**", "--recursive",
        "--project", PROJECT,
    ], check=False)
    if result.returncode != 0:
        if "matched no objects" in result.stderr.lower():
            return []
        raise RuntimeError(f"cloud prefix inventory failed: {result.stderr.strip()}")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _inventory() -> list[Mapping[str, Any]]:
    rows = _gcloud_json([
        "run", "jobs", "executions", "list", "--job", JOB,
        "--project", PROJECT, "--region", REGION,
    ])
    if not isinstance(rows, list):
        raise ValueError("recourse execution inventory is not a list")
    return rows


def _write_manifest() -> None:
    values = {
        "run_id": RUN_ID, "output_prefix": PREFIX,
        "science_protocol_sha256": SCIENCE_SHA256,
        "execution_protocol_sha256": EXECUTION_SHA256,
        "kickoff_population_amendment_sha256": KICKOFF_AMENDMENT_SHA256,
        "transport_amendment_sha256": _sha(AMENDMENT),
        "transport_operator_sha256": _sha(Path(__file__)),
        "cbwu_report_sha256": CBWU_SHA256,
        "forensic_manifest_sha256": FORENSIC_SHA256,
        "code_sha": CODE_SHA, "build_id": BUILD_ID, "image": IMAGE,
        "v6_source_revision": V6_CODE_SHA, "v6_build_id": V6_BUILD_ID,
        "v6_image_digest": V6_IMAGE_DIGEST, "v6_runtime_eligible": "false",
        "source_repository": SOURCE_REPOSITORY, "source_revision": CODE_SHA,
        "reused_job": JOB, "reused_job_uid": JOB_UID,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": "14400",
        "max_retries": "0", "uses_realized_outcomes": "false",
        "production_change_licensed": "false",
        "historical_scoring_licensed": "false",
        "build_metadata_sha256": _sha(OUT / "build-metadata.json"),
        "v6_build_metadata_sha256": _sha(OUT / "v6-build-metadata.json"),
        "image_metadata_sha256": _sha(OUT / "image-metadata.json"),
        "job_before_sha256": _sha(OUT / "job-before.json"),
        "job_before_export_sha256": _sha(OUT / "job-before.export.yaml"),
        "inventory_before_sha256": _sha(OUT / "executions-before.json"),
        "queue_release_sha256": _sha(OUT / "queue-release.json"),
        "job_after_sha256": _sha(OUT / "job-after.json"),
    }
    raw = "".join(f"{key}={value}\n" for key, value in values.items()).encode()
    _create_bytes(OUT / "manifest.txt", raw)


def prepare_canary() -> None:
    if OUT.exists() or OUT.is_symlink():
        raise FileExistsError("immutable recourse local run already exists")
    _validate_local_sources()
    if _prefix_objects():
        raise FileExistsError("immutable recourse cloud prefix already exists")
    queue = queue_release_receipt()
    v6_build = _gcloud_json([
        "builds", "describe", V6_BUILD_ID, "--project", PROJECT,
    ])
    v6_dockerfile = _run([
        "git", "-C", str(ROOT), "show",
        f"{V6_CODE_SHA}:Dockerfile.r6-current-bank-crossed-screen",
    ]).stdout
    validate_narrow_v6_build(v6_build, v6_dockerfile)
    build = _gcloud_json(["builds", "describe", BUILD_ID, "--project", PROJECT])
    validate_build(build)
    image = _gcloud_json([
        "artifacts", "docker", "images", "describe", IMAGE,
        "--project", PROJECT,
    ])
    validate_image(image)
    before = _gcloud_json([
        "run", "jobs", "describe", JOB, "--project", PROJECT,
        "--region", REGION,
    ])
    if before.get("metadata", {}).get("uid") != JOB_UID:
        raise ValueError("reused job pre-update UID differs")
    inventory = _inventory()
    _assert_terminal_inventory(inventory)
    exported = _run([
        "gcloud", "run", "jobs", "describe", JOB, "--project", PROJECT,
        "--region", REGION, "--format=export",
    ]).stdout.encode()

    OUT.mkdir(parents=True, exist_ok=False)
    _create_json(OUT / "v6-build-metadata.json", v6_build)
    _create_json(OUT / "build-metadata.json", build)
    _create_json(OUT / "image-metadata.json", image)
    _create_json(OUT / "queue-release.json", queue)
    _create_json(OUT / "job-before.json", before)
    _create_bytes(OUT / "job-before.export.yaml", exported)
    _create_json(OUT / "executions-before.json", {"executions": inventory})
    _create_json(OUT / "job-update-intent.json", {
        "version": "recourse-aware-initial-book-job-update-intent-v1",
        "job": JOB,
        "job_uid": JOB_UID,
        "job_before_sha256": _sha(OUT / "job-before.json"),
        "job_before_export_sha256": _sha(OUT / "job-before.export.yaml"),
        "target_image": IMAGE,
        "target_code_sha": CODE_SHA,
        "canary_cell": "2023-1",
    })
    try:
        after = _unique_json(_run(job_update_command()).stdout)
        if not isinstance(after, Mapping):
            raise ValueError("recourse job update response schema differs")
        validate_job_contract(after)
        _create_json(OUT / "job-after.json", after)
        post_update = _inventory()
        if inventory_delta(inventory, post_update):
            raise ValueError("job update unexpectedly created an execution")
        _create_json(
            OUT / "executions-after-update.json", {"executions": post_update},
        )
        _write_manifest()
        _create_bytes(OUT / "executions.txt", b"")
        _create_json(OUT / "launch-intents" / "2023-1.json", {
            "version": "recourse-aware-initial-book-cell-launch-intent-v1",
            "season": 2023,
            "week": 1,
            "cell_token": cell_token(2023, 1),
            "args": expected_args(2023, 1),
            "output_uri": expected_uri(2023, 1),
        })

        execution = _run(execution_command(2023, 1)).stdout.strip()
        if not execution.startswith(JOB + "-"):
            raise ValueError("recourse canary execution identity is missing")
        _append_fsync(
            OUT / "executions.txt",
            f"2023 1 {JOB} {execution} {expected_uri(2023, 1)}",
        )
        _create_json(OUT / "canary-launch.json", {
            "version": "recourse-aware-initial-book-single-job-canary-launch-v1",
            "execution": execution, "job": JOB, "job_uid": JOB_UID,
            "season": 2023, "week": 1, "cell_token": cell_token(2023, 1),
            "output_uri": expected_uri(2023, 1),
            "remaining_cells_released": False,
            "uses_realized_outcomes": False,
        })
    except Exception as exc:
        _record_terminal_failure("prepare-canary", type(exc).__name__)
        restore_shared_job(
            "prepare-canary-failure",
            require_terminal_state=True,
            allow_partial_contract=True,
        )
        raise
    print("RECOURSE_SINGLE_JOB_CANARY_LAUNCHED", execution)


def _ledger_rows() -> list[list[str]]:
    path = OUT / "executions.txt"
    if not path.is_file():
        raise ValueError("recourse execution ledger is absent")
    rows = [line.split() for line in path.read_text().splitlines() if line]
    if any(len(row) != 5 for row in rows) or len(rows) > len(ALL_CELLS):
        raise ValueError("recourse execution ledger shape differs")
    if len({row[3] for row in rows}) != len(rows):
        raise ValueError("recourse execution ledger repeats an execution")
    for row, (season, week) in zip(rows, ALL_CELLS):
        if row != [
            str(season), str(week), JOB, row[3], expected_uri(season, week),
        ] or not row[3].startswith(JOB + "-"):
            raise ValueError("recourse execution ledger order differs")
    return rows


def _load_before_inventory() -> list[Mapping[str, Any]]:
    row = _unique_json((OUT / "executions-before.json").read_bytes())
    values = row.get("executions")
    if not isinstance(values, list):
        raise ValueError("recourse pre-update inventory differs")
    return values


def _describe_execution(execution: str) -> Mapping[str, Any]:
    row = _gcloud_json([
        "run", "jobs", "executions", "describe", execution,
        "--project", PROJECT, "--region", REGION,
    ])
    if not isinstance(row, Mapping):
        raise ValueError("recourse execution description schema differs")
    return row


def _execution_cell(metadata: Mapping[str, Any], execution: str) -> tuple[int, int]:
    task = metadata.get("spec", {}).get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if len(containers) != 1:
        raise ValueError("recourse execution recovery envelope differs")
    token = _environment(containers[0]).get("RECOURSE_TRANSPORT_CELL", "")
    for season, week in ALL_CELLS:
        if token == cell_token(season, week):
            validate_execution_contract(
                metadata, execution, season, week, require_success=False,
            )
            return season, week
    raise ValueError("recourse execution recovery token differs")


def reconcile_execution_ledger() -> list[list[str]]:
    rows = _ledger_rows()
    before = _load_before_inventory()
    current = _inventory()
    delta = inventory_delta(before, current)
    ledger_names = {row[3] for row in rows}
    if not ledger_names <= delta:
        raise ExecutionPending(
            "recourse ledger execution is not yet visible in provider inventory"
        )
    extra = delta - ledger_names
    if len(extra) > 1:
        raise ValueError("recourse provider inventory has ambiguous extra executions")
    by_name = {
        str(row.get("metadata", {}).get("name", "")): row for row in current
    }
    if extra:
        execution = next(iter(extra))
        metadata = by_name.get(execution)
        if not isinstance(metadata, Mapping) or "spec" not in metadata:
            metadata = _describe_execution(execution)
        cell = _execution_cell(metadata, execution)
        if len(rows) >= len(ALL_CELLS) or cell != ALL_CELLS[len(rows)]:
            raise ValueError("recourse unledgered execution is outside next cell")
        season, week = cell
        _append_fsync(
            OUT / "executions.txt",
            f"{season} {week} {JOB} {execution} {expected_uri(season, week)}",
        )
        rows = _ledger_rows()
        ledger_names = {row[3] for row in rows}
    if delta != ledger_names:
        raise ValueError("recourse provider execution delta differs from ledger")
    return rows


def resume_canary_launch() -> None:
    if not OUT.is_dir() or OUT.is_symlink() or \
            (OUT / "terminal-failure.json").exists() or \
            (OUT / "job-restoration.json").exists() or \
            (OUT / "canary-completion.json").exists():
        raise ValueError("recourse canary resume state differs")
    current_job = _gcloud_json([
        "run", "jobs", "describe", JOB, "--project", PROJECT,
        "--region", REGION,
    ])
    validate_job_contract(current_job)
    rows = reconcile_execution_ledger()
    if len(rows) > 1:
        raise ValueError("recourse canary resume found released grid cells")
    if not rows:
        intent_path = OUT / "launch-intents/2023-1.json"
        if not intent_path.is_file() or intent_path.is_symlink():
            raise ValueError("recourse canary launch intent is absent")
        try:
            execution = _run(execution_command(2023, 1)).stdout.strip()
        except RuntimeError as exc:
            raise ExecutionPending(
                "recourse canary submission is ambiguous; wait for provider "
                "inventory before resuming"
            ) from exc
        if not execution.startswith(JOB + "-"):
            raise ExecutionPending(
                "recourse canary response is ambiguous; reconcile before retry"
            )
        _append_fsync(
            OUT / "executions.txt",
            f"2023 1 {JOB} {execution} {expected_uri(2023, 1)}",
        )
        rows = _ledger_rows()
    execution = rows[0][3]
    _create_or_equal_json(OUT / "canary-launch.json", {
        "version": "recourse-aware-initial-book-single-job-canary-launch-v1",
        "execution": execution,
        "job": JOB,
        "job_uid": JOB_UID,
        "season": 2023,
        "week": 1,
        "cell_token": cell_token(2023, 1),
        "output_uri": expected_uri(2023, 1),
        "remaining_cells_released": False,
        "uses_realized_outcomes": False,
    })
    print("RECOURSE_SINGLE_JOB_CANARY_RESUMED", execution)


def validate_canary() -> None:
    if not OUT.is_dir() or (OUT / "canary-completion.json").exists():
        raise ValueError("recourse canary validation state differs")
    _validate_local_sources()
    rows = reconcile_execution_ledger()
    if len(rows) != 1:
        raise ValueError("recourse canary must be the only submitted cell")
    season, week, job, execution, uri = rows[0]
    if (season, week, job, uri) != (
        "2023", "1", JOB, expected_uri(2023, 1),
    ) or not execution.startswith(JOB + "-"):
        raise ValueError("recourse single-job canary identity differs")

    metadata = _gcloud_json([
        "run", "jobs", "executions", "describe", execution,
        "--project", PROJECT, "--region", REGION,
    ])
    state = execution_state(metadata)
    if state == "Unknown":
        raise ExecutionPending("recourse canary is still active")
    if state == "False":
        _record_terminal_failure("validate-canary", "terminal-execution-failure")
        restore_shared_job("canary-terminal-failure")
        raise ValueError("recourse canary execution failed")
    validate_execution_contract(metadata, execution, 2023, 1, require_success=True)
    current = _inventory()
    delta = inventory_delta(_load_before_inventory(), current)
    if delta != {execution}:
        raise ValueError("recourse canary is not the exact execution delta")
    objects = _prefix_objects()
    if not objects:
        raise ExecutionPending("recourse canary object is not yet visible")
    if objects != [expected_uri(2023, 1)]:
        raise ValueError("recourse canary object inventory differs")
    object_metadata = _gcloud_json([
        "storage", "objects", "describe", expected_uri(2023, 1),
        "--project", PROJECT,
    ])
    from validate_recourse_aware_initial_canary import (  # type: ignore
        EXPECTED_JOB, validate as validate_scientific_canary,
    )

    proxy_execution = EXPECTED_JOB + "-single-job-proxy"
    proxy_metadata = copy.deepcopy(metadata)
    proxy_metadata["metadata"]["name"] = proxy_execution
    with tempfile.TemporaryDirectory(prefix="recourse-canary-proxy-") as raw_tmp:
        temp = Path(raw_tmp)
        shard_pending = temp / "canary-shard.json"
        _run([
            "gcloud", "storage", "cp", expected_uri(2023, 1),
            str(shard_pending), "--project", PROJECT,
        ])
        proxy_ledger = temp / "executions.txt"
        proxy_ledger.write_text(
            f"2023 1 {EXPECTED_JOB} {proxy_execution} {uri}\n",
            encoding="utf-8",
        )
        proxy_meta = temp / "execution.json"
        object_path = temp / "object.json"
        object_path.write_text(json.dumps(object_metadata), encoding="utf-8")
        proxy_env = proxy_metadata["spec"]["template"]["spec"][
            "containers"
        ][0]["env"]
        proxy_metadata["spec"]["template"]["spec"]["containers"][0][
            "env"
        ] = [
            row for row in proxy_env
            if row.get("name") != "RECOURSE_TRANSPORT_CELL"
        ]
        proxy_meta.write_text(json.dumps(proxy_metadata), encoding="utf-8")
        scientific = validate_scientific_canary(
            OUT / "manifest.txt", proxy_ledger, proxy_meta,
            object_path, shard_pending,
        )
        shard_raw = shard_pending.read_bytes()
    if scientific.get("status") is not True or \
            scientific.get("disposition") != "actual-final-path-canary-passes":
        raise ValueError("recourse scientific canary validator did not pass")

    _create_json(OUT / "canary-execution-metadata.json", metadata)
    _create_json(OUT / "canary-object-metadata.json", object_metadata)
    _create_bytes(OUT / "canary-shard.json", shard_raw)
    receipt = {
        **scientific,
        "version": "recourse-aware-initial-book-single-job-canary-validation-v1",
        "execution": execution,
        "job": JOB,
        "job_uid": JOB_UID,
        "preexisting_execution_count": len(_load_before_inventory()),
        "post_inventory_delta": [execution],
        "remaining_cells_released": False,
        "outcome_fields_inspected": False,
        "effect_fields_inspected": False,
    }
    _create_json(OUT / "canary-completion.json", receipt)
    print("RECOURSE_SINGLE_JOB_CANARY_VALIDATED", execution)


def release_grid() -> None:
    if not OUT.is_dir() or OUT.is_symlink() or \
            (OUT / "terminal-failure.json").exists() or \
            (OUT / "job-restoration.json").exists():
        raise ValueError("recourse grid release state differs")
    if (OUT / "grid-release.json").is_file():
        rows = reconcile_execution_ledger()
        if len(rows) != len(ALL_CELLS):
            raise ValueError("completed recourse grid ledger differs")
        print("RECOURSE_SINGLE_JOB_GRID_ALREADY_RELEASED", len(rows) - 1)
        return
    if not (OUT / "canary-completion.json").is_file():
        raise ValueError("recourse validated canary receipt is absent")
    _validate_local_sources()
    receipt = _unique_json((OUT / "canary-completion.json").read_bytes())
    validate_canary_receipt(receipt)
    rows = reconcile_execution_ledger()
    if not rows or rows[0][3] != receipt["execution"]:
        raise ValueError("recourse release does not descend from canary")
    current_job = _gcloud_json([
        "run", "jobs", "describe", JOB, "--project", PROJECT,
        "--region", REGION,
    ])
    validate_job_contract(current_job)
    objects = _prefix_objects()
    submitted_uris = {row[4] for row in rows}
    if expected_uri(2023, 1) not in objects or not set(objects) <= submitted_uris:
        raise ValueError("recourse pre-release object inventory differs")

    intent = {
        "version": "recourse-aware-initial-book-single-job-grid-release-intent-v1",
        "canary_execution": receipt["execution"],
        "cells": [f"{season}-{week}" for season, week in release_cells()],
        "job": JOB,
        "job_uid": JOB_UID,
        "uses_realized_outcomes": False,
    }
    _create_or_equal_json(OUT / "grid-release-intent.json", intent)

    for season, week in ALL_CELLS[len(rows):]:
        _create_or_equal_json(OUT / "launch-intents" / f"{season}-{week}.json", {
            "version": "recourse-aware-initial-book-cell-launch-intent-v1",
            "season": season,
            "week": week,
            "cell_token": cell_token(season, week),
            "args": expected_args(season, week),
            "output_uri": expected_uri(season, week),
        })
        try:
            execution = _run(execution_command(season, week)).stdout.strip()
        except RuntimeError as exc:
            raise ExecutionPending(
                "recourse execution submission is ambiguous; rerun release "
                "only after provider inventory is visible"
            ) from exc
        if not execution.startswith(JOB + "-") or execution in {
            row[3] for row in rows
        }:
            raise ExecutionPending(
                "recourse execution response is ambiguous; reconcile provider "
                "inventory before retry"
            )
        _append_fsync(
            OUT / "executions.txt",
            f"{season} {week} {JOB} {execution} {expected_uri(season, week)}",
        )
        rows = _ledger_rows()
    if len(rows) != 54:
        raise ValueError("recourse single-job grid is not exact 54")
    _create_json(OUT / "grid-release.json", {
        "version": "recourse-aware-initial-book-single-job-grid-release-v1",
        "canary_execution": receipt["execution"],
        "released_executions": [row[3] for row in rows[1:]],
        "primary_executions": 54,
        "released_after_canary": 53,
        "job": JOB,
        "job_uid": JOB_UID,
        "uses_realized_outcomes": False,
        "outcome_fields_inspected": False,
        "effect_fields_inspected": False,
    })
    print("RECOURSE_SINGLE_JOB_GRID_RELEASED", len(rows) - 1)


def _download_bytes(uri: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="recourse-download-") as raw_tmp:
        target = Path(raw_tmp) / "object"
        _run([
            "gcloud", "storage", "cp", uri, str(target),
            "--project", PROJECT,
        ])
        return target.read_bytes()


def _validate_object_metadata(
    metadata: Mapping[str, Any], uri: str, raw: bytes,
) -> dict[str, Any]:
    generation = str(metadata.get("generation", ""))
    if not generation.isdigit() or int(generation) <= 0 or \
            int(metadata.get("size", -1)) != len(raw):
        raise ValueError("recourse cloud object identity differs")
    normalized_uri = str(metadata.get("url", metadata.get("uri", uri)))
    if normalized_uri not in {uri, ""} and not normalized_uri.endswith(
        uri.removeprefix("gs://")
    ):
        raise ValueError("recourse cloud object URI differs")
    return {
        "uri": uri,
        "generation": generation,
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }


def _upload_report_create_once(report_path: Path) -> dict[str, Any]:
    uri = f"{PREFIX}/report.json"
    result = _run([
        "gcloud", "storage", "cp", str(report_path), uri,
        "--if-generation-match=0", "--project", PROJECT,
    ], check=False)
    try:
        metadata = _gcloud_json([
            "storage", "objects", "describe", uri, "--project", PROJECT,
        ])
        raw = _download_bytes(uri)
    except Exception:
        if result.returncode != 0:
            raise RuntimeError(
                "recourse report create-once upload failed: "
                + result.stderr.strip()
            )
        raise
    if raw != report_path.read_bytes():
        raise ValueError("recourse report cloud bytes differ")
    identity = _validate_object_metadata(metadata, uri, raw)
    return {
        "version": "recourse-aware-initial-book-report-upload-v1",
        "create_only": True,
        **identity,
    }


def harvest_grid() -> None:
    if not OUT.is_dir() or OUT.is_symlink() or \
            not (OUT / "grid-release.json").is_file() or \
            (OUT / "terminal-failure.json").exists():
        raise ValueError("recourse harvest state differs")
    if (OUT / "completion.txt").is_file():
        restore_shared_job("full-harvest-complete")
        print("RECOURSE_SINGLE_JOB_ALREADY_HARVESTED", RUN_ID)
        return
    _validate_local_sources()
    rows = reconcile_execution_ledger()
    if len(rows) != len(ALL_CELLS):
        raise ValueError("recourse harvest requires exact 54-cell ledger")

    execution_rows: list[tuple[list[str], Mapping[str, Any]]] = []
    pending = 0
    failed: list[str] = []
    for row in rows:
        metadata = _describe_execution(row[3])
        state = execution_state(metadata)
        if state == "Unknown":
            pending += 1
        elif state == "False":
            failed.append(row[3])
        execution_rows.append((row, metadata))
    if pending:
        raise ExecutionPending(f"recourse grid still has {pending} active executions")
    if failed:
        _record_terminal_failure("harvest", f"terminal-execution-failures:{len(failed)}")
        restore_shared_job("grid-terminal-failure")
        raise ValueError("recourse grid contains terminal execution failures")

    expected_shards = {expected_uri(season, week) for season, week in ALL_CELLS}
    report_uri = f"{PREFIX}/report.json"
    objects = set(_prefix_objects())
    if not expected_shards <= objects or not objects <= expected_shards | {report_uri}:
        raise ExecutionPending("recourse terminal grid object inventory is incomplete")

    _create_or_equal_json(OUT / "grid-terminal.json", {
        "version": "recourse-aware-initial-book-single-job-grid-terminal-v1",
        "executions": [row[3] for row in rows],
        "succeeded": 54,
        "failed": 0,
        "active": 0,
        "provider_execution_delta_exact": True,
    })

    shard_paths: list[Path] = []
    execution_identities = []
    object_identities = []
    for row, metadata in execution_rows:
        season, week = int(row[0]), int(row[1])
        validate_execution_contract(
            metadata, row[3], season, week, require_success=True,
        )
        execution_path = OUT / "execution-metadata" / f"{row[3]}.json"
        _create_or_equal_json(execution_path, metadata)
        uri = row[4]
        object_metadata = _gcloud_json([
            "storage", "objects", "describe", uri, "--project", PROJECT,
        ])
        if not isinstance(object_metadata, Mapping):
            raise ValueError("recourse shard metadata schema differs")
        raw = _download_bytes(uri)
        shard = _unique_json(raw)
        if not isinstance(shard, Mapping):
            raise ValueError("recourse shard JSON schema differs")
        shard_path = OUT / "shards" / f"slate-{season}-{week}.json"
        _create_or_equal_bytes(shard_path, raw)
        object_path = OUT / "object-metadata" / f"slate-{season}-{week}.json"
        _create_or_equal_json(object_path, object_metadata)
        shard_paths.append(shard_path)
        execution_identities.append({
            "execution": row[3],
            "metadata_sha256": _sha(execution_path),
        })
        object_identities.append(_validate_object_metadata(
            object_metadata, uri, raw,
        ))

    if (OUT / "canary-shard.json").read_bytes() != \
            (OUT / "shards/slate-2023-1.json").read_bytes():
        raise ValueError("recourse canary bytes changed after grid release")

    from aggregate_recourse_aware_initial_scorefree import aggregate  # type: ignore

    report = aggregate(shard_paths)
    if report.get("version") != \
            "recourse-aware-initial-book-scorefree-report-v1" or \
            report.get("run_id") != RUN_ID or \
            report.get("code_sha") != CODE_SHA or \
            report.get("analysis_image") != IMAGE or \
            report.get("uses_realized_outcomes") is not False or \
            report.get("production_change_licensed") is not False or \
            report.get("mechanical") != {
                "slates": 54,
                "folds": 270,
                "worlds_per_fold": 10_000,
                "all_valid": True,
            }:
        raise ValueError("recourse aggregate identity/mechanics differ")
    conditions = report.get("conditions", {})
    expected_conditions = {
        "reachable_p230_strict_and_three_blocks",
        "reachable_p240_p220_p210_nondecline",
        "initial_p240_p230_p220_nondecline",
        "initial_p194_retention_at_least_95pct",
        "mean_reachable_alternatives_nondecline",
        "locked_slot_signature_nondecline",
    }
    if not isinstance(conditions, Mapping) or set(conditions) != \
            expected_conditions or report.get("passed") is not all(
                bool(value) for value in conditions.values()
            ) or report.get("disposition") not in {
                "recourse-aware-initial-book-premise-passes",
                "recourse-aware-candidate-union-selector-premise-fails",
            }:
        raise ValueError("recourse aggregate gate differs")
    report_raw = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    report_path = OUT / "report.json"
    _create_or_equal_bytes(report_path, report_raw)
    upload = _upload_report_create_once(report_path)
    _create_or_equal_json(OUT / "report-upload.json", upload)
    _create_or_equal_json(OUT / "harvest-completion.json", {
        "version": "recourse-aware-initial-book-single-job-harvest-v1",
        "run_id": RUN_ID,
        "executions": 54,
        "slates": 54,
        "folds": 270,
        "execution_identities": execution_identities,
        "object_identities": object_identities,
        "report_sha256": sha256(report_raw).hexdigest(),
        "report_upload": upload,
        "passes_scorefree_gate": bool(report["passed"]),
        "historical_policy_diagnostic_licensed": bool(report["passed"]),
        "disposition": report["disposition"],
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "complete": True,
    })
    restore_shared_job("full-harvest-complete")
    completion = "".join((
        f"run_id={RUN_ID}\n",
        "executions=54\n",
        "slates=54\n",
        "folds=270\n",
        "uses_realized_outcomes=false\n",
        "production_change_licensed=false\n",
        "historical_policy_diagnostic_licensed="
        f"{str(bool(report['passed'])).lower()}\n",
        f"passes_scorefree_gate={str(bool(report['passed'])).lower()}\n",
        f"report_sha256={sha256(report_raw).hexdigest()}\n",
        f"job_restoration_sha256={_sha(OUT / 'job-restoration.json')}\n",
        f"disposition={report['disposition']}\n",
    )).encode()
    _create_or_equal_bytes(OUT / "completion.txt", completion)
    print("RECOURSE_SINGLE_JOB_HARVESTED", report["disposition"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=(
            "prepare-canary", "resume-canary", "validate-canary", "release",
            "harvest", "restore",
        ),
    )
    args = parser.parse_args()
    try:
        if args.command == "prepare-canary":
            prepare_canary()
        elif args.command == "resume-canary":
            resume_canary_launch()
        elif args.command == "validate-canary":
            validate_canary()
        elif args.command == "release":
            release_grid()
        elif args.command == "harvest":
            harvest_grid()
        else:
            restore_shared_job("explicit-terminal-restoration")
    except ExecutionPending as exc:
        print(f"RECOURSE_SINGLE_JOB_PENDING {exc}", flush=True)
        raise SystemExit(4) from exc
    except Exception as exc:
        if args.command in {"validate-canary", "release", "harvest"} and \
                OUT.is_dir() and \
                not (OUT / "terminal-failure.json").exists():
            _record_terminal_failure(args.command, type(exc).__name__)
            try:
                restore_shared_job(f"{args.command}-failure")
            except Exception as restore_error:
                raise RuntimeError(
                    "recourse operation failed and exact job restoration failed"
                ) from restore_error
        raise


if __name__ == "__main__":
    main()
