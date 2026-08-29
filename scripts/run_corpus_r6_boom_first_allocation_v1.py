#!/usr/bin/env python3
"""Prepare, run, seal, and separately grade the 54-slate K=1 allocation test.

``prepare`` is score-blind: it reads the already-keyed historical generation
rows, requires ``proj_tourney``, binds them to the immutable later-source
world artifacts (including the repaired R3/2025-W1 source), and publishes 54
create-once task snapshots plus one manifest.  ``task`` regenerates both arms
and publishes one score-free exact-80 result.  ``collect`` exact-opens all 54
results before creating the terminal.  Only the separately armed ``grade``
command can open the existing catalog-wide outcome snapshot.

Every command is default-off.  This file contains no automatic scheduler or
deployment mutation; the manifest records the exact 54-task launch shape for
the existing batch job.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
from typing import Final

import numpy as np
import pandas as pd
import scipy


ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_boom_first_allocation_v1 as science,
)
from nfl_dfs.optimizer.lineup import StackRules  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_novel_roster_realized_grader_v1 as grader,
)
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as l2b_panel  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_combined_population_all_block_execution_v1 as provider_execution,
)
from nfl_dfs.research import lr8_later_period_source as later_source  # noqa: E402

import run_atlas_minimal_world_selection_c as atlas  # noqa: E402
import run_corpus_r6_combined_population_all_block_v1 as transport  # noqa: E402


MANIFEST_SCHEMA: Final = "corpus-r6-boom-first-allocation-manifest/v2"
PREPARE_RESULT_SCHEMA: Final = "corpus-r6-boom-first-allocation-prepare-result/v2"
COLLECT_RESULT_SCHEMA: Final = "corpus-r6-boom-first-allocation-collect-result/v2"
GRADE_RESULT_SCHEMA: Final = "corpus-r6-boom-first-allocation-grade-result/v3"
JOB_CONFIGURATION_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-provider-job-configuration/v1"
)
PREFLIGHT_SMOKE_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-real-artifact-preflight-smoke/v1"
)
MANIFEST_SMOKE_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-real-artifact-manifest-smoke/v1"
)
LAUNCH_CLAIM_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-provider-launch-claim/v1"
)
LAUNCH_RECEIPT_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-provider-launch-receipt/v1"
)

SELECTION_ENABLE_ENV: Final = "R6_BOOM_FIRST_ALLOCATION_ENABLE"
SELECTION_ENABLE_VALUE: Final = "I_UNDERSTAND_SCORE_BLIND_BOOM_FIRST_K1_V1"
GRADE_ENABLE_ENV: Final = "R6_BOOM_FIRST_ALLOCATION_GRADE_ENABLE"
GRADE_ENABLE_VALUE: Final = "I_UNDERSTAND_POST_TERMINAL_REALIZED_GRADE_V1"
MANIFEST_IDENTITY_ENV: Final = "R6_BOOM_FIRST_ALLOCATION_MANIFEST_IDENTITY"
TASK0_SMOKE_SHA_ENV: Final = "R6_BOOM_FIRST_ALLOCATION_TASK0_SMOKE_SHA256"
JOB_AUTHORITY_SHA_ENV: Final = "R6_BOOM_FIRST_ALLOCATION_JOB_AUTHORITY_SHA256"
BUILD_SOURCE_COMMIT_ENV: Final = "BOOM_FIRST_BUILD_SOURCE_COMMIT"
SOURCE_PROVENANCE_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-scoped-source-provenance/v1"
)
SCOPED_SOURCE_PATHS: Final = (
    "src/nfl_dfs/research/corpus_r6_boom_first_allocation_v1.py",
    "scripts/run_corpus_r6_boom_first_allocation_v1.py",
)

FIXED_PROJECT: Final = provider_execution.FIXED_GCP_PROJECT
FIXED_REGION: Final = provider_execution.FIXED_REGION
FIXED_REUSED_JOB_NAME: Final = provider_execution.FIXED_REUSED_JOB_NAME
FIXED_REUSED_JOB_UID: Final = provider_execution.FIXED_REUSED_JOB_UID
FIXED_SERVICE_ACCOUNT: Final = (
    "817589974517-compute@developer.gserviceaccount.com"
)
FIXED_TASK_COUNT: Final = science.TASK_COUNT
FIXED_PARALLELISM: Final = science.TASK_COUNT
FIXED_CPU: Final = provider_execution.FIXED_CPU
FIXED_MEMORY: Final = provider_execution.FIXED_MEMORY
FIXED_TIMEOUT_SECONDS: Final = provider_execution.FIXED_TIMEOUT_SECONDS
FIXED_MAX_RETRIES: Final = 0
EXPECTED_TASK_COMMAND: Final = (
    "/usr/local/bin/python3.11", "-I",
    "/app/scripts/run_corpus_r6_boom_first_allocation_v1.py",
    "task", "--execute",
)

PLAYER_TABLE: Final = f"{FIXED_PROJECT}.nfl_predictions.slate_player_features"
CANDIDATE_TABLE: Final = f"{FIXED_PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_SQL: Final = f"""
SELECT panel_run_id, season, week, id, gsis_id, name, pos, team, opp,
       game_id, salary, proj, proj_tourney, own_est, consensus_div,
       market_points, model_points_pre, mean_projection, proj_p10,
       proj_p50, proj_p90, proj_std
FROM `{PLAYER_TABLE}`
WHERE season IN UNNEST(@seasons) AND (
  (panel_run_id IN UNNEST(@source_panels)
   AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1))
  OR (panel_run_id=@repair_panel AND season=2025 AND week=1)
)
ORDER BY season, week, panel_run_id, id
"""
CANDIDATE_SQL: Final = f"""
SELECT panel_run_id, season, week, cand_ix, tag, players,
       score_artifact_uri, score_artifact_sha256
FROM `{CANDIDATE_TABLE}`
WHERE season IN UNNEST(@seasons) AND (
  (panel_run_id IN UNNEST(@source_panels)
   AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1))
  OR (panel_run_id=@repair_panel AND season=2025 AND week=1)
)
ORDER BY season, week, panel_run_id, cand_ix
"""

MAXIMUM_REQUEST_BYTES: Final = 2_000_000
MAXIMUM_LATER_SOURCE_BYTES: Final = 8_000_000
MAXIMUM_SNAPSHOT_BYTES: Final = 16_000_000
MAXIMUM_MANIFEST_BYTES: Final = 2_000_000
MAXIMUM_TASK_RESULT_BYTES: Final = 16_000_000
MAXIMUM_TERMINAL_BYTES: Final = 128_000_000
MAXIMUM_GRADE_BYTES: Final = 192_000_000
MAXIMUM_SMOKE_RECEIPT_BYTES: Final = 2_000_000
MAXIMUM_LAUNCH_AUTHORITY_BYTES: Final = 2_000_000
MAXIMUM_OUTCOME_LEASE_BYTES: Final = 16_384
MAXIMUM_CATALOG_COMPLETION_BYTES: Final = 2_000_000
HISTORICAL_OUTCOME_LEASE_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
CATALOG_OUTCOME_COMPLETION_SCHEMA: Final = (
    "corpus-r6-catalog-wide-outcome-completion/v1"
)
CATALOG_OUTCOME_ROOT: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-catalog-wide-realized"
)

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")


class RunCorpusR6BoomFirstAllocationV1Error(RuntimeError):
    """The bounded historical allocation operator failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6BoomFirstAllocationV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _canonical(value: object) -> bytes:
    try:
        return science.canonical_json_bytes_v1(value)
    except science.CorpusR6BoomFirstAllocationV1Error as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    return {**body, field: _hash(body)}


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc


def _strict_json(raw: bytes, *, label: str, maximum_bytes: int) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > maximum_bytes:
        _fail(f"{label} bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(
            f"{label} is not JSON"
        ) from exc
    body = _mapping(value, label=label)
    if _canonical(body) != raw:
        _fail(f"{label} is not canonical JSON")
    return body


def _scoped_source_measurement_v1() -> dict[str, object]:
    files: list[dict[str, object]] = []
    for relative in SCOPED_SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            _fail(f"boom-first scoped source is absent: {relative}")
        raw = path.read_bytes()
        files.append({
            "path": relative,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    return {
        "files": files,
        "scoped_source_sha256": _hash(files),
    }


def _build_source_provenance_v1(
    *, execution_mode: str, observed_source_commit: str,
    embedded_build_source_commit: str | None,
) -> dict[str, object]:
    measurement = _scoped_source_measurement_v1()
    body = {
        "schema_version": SOURCE_PROVENANCE_SCHEMA,
        "execution_mode": execution_mode,
        "observed_source_commit": observed_source_commit,
        "embedded_build_source_commit": embedded_build_source_commit,
        "scoped_source_files": measurement["files"],
        "scoped_source_sha256": measurement["scoped_source_sha256"],
        "python_version": ".".join(str(value) for value in sys.version_info[:3]),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "source_observation": (
            "clean-git-provider-observation"
            if execution_mode == "preflight-smoke"
            else "immutable-image-embedded-build-source-commit"
        ),
    }
    return _with_hash(body, field="source_provenance_sha256")


def _validate_source_provenance_v1(
    value: object, *, execution_mode: str, code_commit: str,
) -> dict[str, object]:
    provenance = _mapping(value, label="boom-first source provenance")
    expected_fields = {
        "schema_version", "execution_mode", "observed_source_commit",
        "embedded_build_source_commit", "scoped_source_files",
        "scoped_source_sha256", "python_version", "numpy_version",
        "scipy_version", "source_observation", "source_provenance_sha256",
    }
    body = {
        key: child for key, child in provenance.items()
        if key != "source_provenance_sha256"
    }
    files = _sequence(
        provenance.get("scoped_source_files"), label="scoped source files"
    )
    if (
        set(provenance) != expected_fields
        or provenance.get("schema_version") != SOURCE_PROVENANCE_SCHEMA
        or provenance.get("execution_mode") != execution_mode
        or provenance.get("source_provenance_sha256") != _hash(body)
        or provenance.get("observed_source_commit") != code_commit
        or provenance.get("scoped_source_sha256") != _hash(files)
        or [
            _mapping(row, label="scoped source file").get("path")
            for row in files
        ] != list(SCOPED_SOURCE_PATHS)
        or any(
            set(_mapping(row, label="scoped source file"))
            != {"path", "sha256", "bytes"}
            or re.fullmatch(
                r"[0-9a-f]{64}",
                str(_mapping(row, label="scoped source file").get("sha256")),
            ) is None
            or type(_mapping(row, label="scoped source file").get("bytes"))
            is not int
            or _mapping(row, label="scoped source file")["bytes"] < 1
            for row in files
        )
        or provenance.get("python_version") != "3.14.4"
        or provenance.get("numpy_version") != "2.5.1"
        or provenance.get("scipy_version") != "1.18.0"
    ):
        _fail("boom-first source/runtime provenance differs")
    if execution_mode == "preflight-smoke":
        if (
            provenance.get("embedded_build_source_commit") is not None
            or provenance.get("source_observation")
            != "clean-git-provider-observation"
        ):
            _fail("boom-first preflight source observation differs")
    elif execution_mode == "manifest-smoke":
        if (
            provenance.get("embedded_build_source_commit") != code_commit
            or provenance.get("source_observation")
            != "immutable-image-embedded-build-source-commit"
        ):
            _fail("boom-first image source observation differs")
    else:  # pragma: no cover - callers pass one fixed smoke mode
        _fail("boom-first source provenance mode differs")
    return provenance


def _provider_job_projection_from_configuration_v1(
    configuration: Mapping[str, object],
) -> dict[str, object]:
    env = _mapping(
        configuration["container_environment"], label="job environment"
    )
    env.pop(JOB_AUTHORITY_SHA_ENV, None)
    return {
        "job_name": configuration["reused_job_name"],
        "job_uid": configuration["reused_job_uid"],
        "service_account": configuration["service_account"],
        "project_id": configuration["project_id"],
        "region": configuration["region"],
        "image_digest": configuration["image_digest"],
        "immutable_image_uri": configuration["immutable_image_uri"],
        "source_commit": env["CODE_SHA"],
        "container_command": configuration["container_command"],
        "container_args": configuration["container_args"],
        "container_environment": env,
        "task_count": configuration["task_count"],
        "parallelism": configuration["parallelism"],
        "max_retries": configuration["max_retries"],
        "timeout_seconds": configuration["timeout_seconds"],
        "cpu": configuration["cpu"],
        "memory": configuration["memory"],
        "working_directory": configuration["working_directory"],
        "volumes": configuration["volumes"],
        "volume_mounts": configuration["volume_mounts"],
        "provider_observed": True,
    }


class GCloudRunProviderV1(transport.GCloudRunProviderV1):
    """Guarded adapter for one fixed reused UID and service account."""

    def describe_job_identity(self, job_name: str) -> dict[str, object]:
        raw = self._describe_job_raw(job_name)
        metadata = _mapping(raw.get("metadata", {}), label="job identity metadata")
        template = _mapping(
            raw.get("spec", {}).get("template", {}).get("spec", {})
            .get("template", {}).get("spec", {}),
            label="job identity template",
        )
        identity = {
            "job_name": metadata.get("name"),
            "job_uid": metadata.get("uid"),
            "service_account": template.get("serviceAccountName"),
            "project_id": FIXED_PROJECT,
            "region": FIXED_REGION,
            "provider_observed": True,
        }
        if identity != {
            "job_name": FIXED_REUSED_JOB_NAME,
            "job_uid": FIXED_REUSED_JOB_UID,
            "service_account": FIXED_SERVICE_ACCOUNT,
            "project_id": FIXED_PROJECT,
            "region": FIXED_REGION,
            "provider_observed": True,
        }:
            _fail("boom-first provider reused-job identity differs")
        return identity

    def describe_job(self, job_name: str) -> dict[str, object]:
        raw = self._describe_job_raw(job_name)
        metadata = _mapping(raw.get("metadata", {}), label="job metadata")
        template = _mapping(
            raw.get("spec", {}).get("template", {}).get("spec", {})
            .get("template", {}).get("spec", {}),
            label="job template",
        )
        containers = _sequence(template.get("containers", []), label="job containers")
        if len(containers) != 1:
            _fail("boom-first provider job container count differs")
        container = _mapping(containers[0], label="job container")
        env = {
            str(row["name"]): str(row.get("value", ""))
            for row in _sequence(container.get("env", []), label="job environment")
            if isinstance(row, Mapping) and "name" in row
        }
        authority_sha = env.pop(JOB_AUTHORITY_SHA_ENV, "")
        observation = {
            "job_name": metadata.get("name"),
            "job_uid": metadata.get("uid"),
            "service_account": template.get("serviceAccountName"),
            "project_id": FIXED_PROJECT,
            "region": FIXED_REGION,
            "image_digest": str(container.get("image", "")).split("@")[-1],
            "immutable_image_uri": container.get("image"),
            "source_commit": env.get("CODE_SHA"),
            "container_command": container.get("command", []),
            "container_args": container.get("args", []),
            "container_environment": env,
            "task_count": raw.get("spec", {}).get("template", {})
            .get("spec", {}).get("taskCount"),
            "parallelism": raw.get("spec", {}).get("template", {})
            .get("spec", {}).get("parallelism"),
            "max_retries": template.get("maxRetries"),
            "timeout_seconds": int(
                str(template.get("timeoutSeconds", "0s")).rstrip("s")
            ),
            "cpu": str(container.get("resources", {}).get("limits", {}).get("cpu")),
            "memory": container.get("resources", {}).get("limits", {}).get("memory"),
            "working_directory": container.get("workingDir", ""),
            "volumes": template.get("volumes", []),
            "volume_mounts": container.get("volumeMounts", []),
            "provider_observed": True,
        }
        if authority_sha != _hash(observation):
            _fail("boom-first provider job authority environment differs")
        return observation

    def update_existing_job(self, desired: Mapping[str, object]) -> None:
        if (
            desired.get("reused_job_name") != FIXED_REUSED_JOB_NAME
            or desired.get("reused_job_uid") != FIXED_REUSED_JOB_UID
            or desired.get("service_account") != FIXED_SERVICE_ACCOUNT
            or desired.get("new_job_creation_allowed") is not False
        ):
            _fail("boom-first provider refuses nonfixed job mutation")
        environment = "^|^" + "|".join(
            f"{key}={value}"
            for key, value in desired["container_environment"].items()
        )
        subprocess.run([
            "gcloud", "run", "jobs", "update", FIXED_REUSED_JOB_NAME,
            "--project", FIXED_PROJECT, "--region", FIXED_REGION,
            "--image", str(desired["immutable_image_uri"]),
            "--tasks", str(desired["task_count"]),
            "--parallelism", str(desired["parallelism"]),
            "--max-retries", str(desired["max_retries"]),
            "--task-timeout", f"{desired['timeout_seconds']}s",
            "--cpu", str(desired["cpu"]), "--memory", str(desired["memory"]),
            "--service-account", FIXED_SERVICE_ACCOUNT,
            "--command", str(desired["container_command"][0]),
            f"--args={','.join(desired['container_args'])}",
            "--set-env-vars", environment, "--clear-volumes", "--quiet",
        ], check=True)

    def describe_execution(self, execution_id: str) -> dict[str, object]:
        raw = self._json([
            "gcloud", "run", "jobs", "executions", "describe", execution_id,
            "--project", FIXED_PROJECT, "--region", FIXED_REGION,
            "--format=json",
        ])
        metadata = _mapping(raw.get("metadata", {}), label="execution metadata")
        labels = _mapping(metadata.get("labels", {}), label="execution labels")
        owners = _sequence(metadata.get("ownerReferences", []), label="execution owners")
        owner = _mapping(
            owners[0] if len(owners) == 1 else {}, label="execution owner"
        )
        actual_execution = str(metadata.get("name", "")).split("/")[-1]
        actual_job = labels.get("run.googleapis.com/job") or owner.get("name")
        actual_uid = owner.get("uid")
        spec = _mapping(raw.get("spec", {}), label="execution spec")
        execution_template = _mapping(
            spec.get("template", {}).get("spec", {}), label="execution template"
        )
        containers = _sequence(
            execution_template.get("containers", []), label="execution containers"
        )
        if len(containers) != 1:
            _fail("boom-first provider execution container count differs")
        container = _mapping(containers[0], label="execution container")
        execution_env = {
            str(row["name"]): str(row.get("value", ""))
            for row in _sequence(
                container.get("env", []), label="execution environment"
            )
            if isinstance(row, Mapping) and "name" in row
        }
        authority_sha = execution_env.pop(JOB_AUTHORITY_SHA_ENV, "")
        execution_projection = {
            "job_name": actual_job,
            "job_uid": actual_uid,
            "service_account": execution_template.get("serviceAccountName"),
            "project_id": FIXED_PROJECT,
            "region": FIXED_REGION,
            "image_digest": str(container.get("image", "")).split("@")[-1],
            "immutable_image_uri": container.get("image"),
            "source_commit": execution_env.get("CODE_SHA"),
            "container_command": container.get("command", []),
            "container_args": container.get("args", []),
            "container_environment": execution_env,
            "task_count": spec.get("taskCount"),
            "parallelism": spec.get("parallelism"),
            "max_retries": execution_template.get("maxRetries"),
            "timeout_seconds": int(
                str(execution_template.get("timeoutSeconds", "0s")).rstrip("s")
            ),
            "cpu": str(container.get("resources", {}).get("limits", {}).get("cpu")),
            "memory": container.get("resources", {}).get("limits", {}).get("memory"),
            "working_directory": container.get("workingDir", ""),
            "volumes": execution_template.get("volumes", []),
            "volume_mounts": container.get("volumeMounts", []),
            "provider_observed": True,
        }
        job_observation = self.describe_job(str(actual_job))
        without_uri = lambda value: {  # noqa: E731
            key: child for key, child in value.items()
            if key != "immutable_image_uri"
        }
        if (
            actual_execution != execution_id
            or authority_sha != _hash(job_observation)
            or without_uri(execution_projection) != without_uri(job_observation)
            or not transport._execution_image_matches_job_image_v1(
                execution_uri=execution_projection["immutable_image_uri"],
                job_uri=job_observation["immutable_image_uri"],
                expected_digest=job_observation["image_digest"],
            )
        ):
            _fail("boom-first execution template differs from job authority")
        status = _mapping(raw.get("status", {}), label="execution status")
        return {
            "execution_id": actual_execution,
            "job_name": actual_job,
            "job_uid": actual_uid,
            "service_account": execution_template.get("serviceAccountName"),
            "project_id": FIXED_PROJECT,
            "region": FIXED_REGION,
            "task_count": spec.get("taskCount"),
            "succeeded_count": status.get("succeededCount", 0),
            "failed_count": status.get("failedCount", 0),
            "cancelled_count": status.get("cancelledCount", 0),
            "running_count": status.get("runningCount", 0),
            "terminal": status.get("completionTime") is not None,
            "provider_observed": True,
            "job_observation": job_observation,
        }


class GCSExactTransportV1(transport.GCSExactTransportV1):
    """Exact transport with a non-idempotent atomic launch claim.

    Ordinary scientific objects retain the repository's resumable
    create-once-or-exact-prior behavior.  A provider launch is different:
    accepting an exact prior claim and continuing would authorize a second
    54-task execution.  This one method therefore rejects every pre-existing
    generation, including byte-identical claims.
    """

    def claim_launch_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("boom-first launch claim bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                timeout=transport.hard_operator.GCS_IO_TIMEOUT_SECONDS,
                retry=self._retry,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ in {"Conflict", "PreconditionFailed"}:
                raise RunCorpusR6BoomFirstAllocationV1Error(
                    "boom-first launch claim already exists; automatic "
                    "relaunch is forbidden"
                ) from exc
            raise
        if blob.generation is None:
            _fail("boom-first launch claim lacks a generation")
        identity = _identity({
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="boom-first launch claim")
        if self.read_exact(identity) != raw:
            _fail("boom-first launch claim exact reopen differs")
        return identity


def _read_json(
    identity_value: object, *, store: object, label: str, maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    raw = store.read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read identity differs")
    return _strict_json(raw, label=label, maximum_bytes=maximum_bytes), identity


def _publish_json(
    *, uri: str, value: Mapping[str, object], maximum_bytes: int, store: object,
) -> dict[str, object]:
    raw = _canonical(value)
    if not raw or len(raw) > maximum_bytes:
        _fail("publication exceeds its exact byte ceiling")
    identity = _identity(
        store.publish_create_once(uri, raw), label="published object"
    )
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
        or store.read_exact(identity) != raw
    ):
        _fail("create-once publication exact reopen differs")
    return identity


def _publish_fresh_launch_claim_v1(
    *, uri: str, value: Mapping[str, object], store: object,
) -> dict[str, object]:
    raw = _canonical(value)
    if not raw or len(raw) > MAXIMUM_LAUNCH_AUTHORITY_BYTES:
        _fail("boom-first launch claim exceeds its exact byte ceiling")
    claim = getattr(store, "claim_launch_once", None)
    if not callable(claim):
        _fail("boom-first transport lacks atomic fresh-launch claiming")
    identity = _identity(claim(uri, raw), label="boom-first launch claim")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
        or store.read_exact(identity) != raw
    ):
        _fail("boom-first fresh launch claim exact reopen differs")
    return identity


def _output_prefix(value: object) -> str:
    marker = "/research/corpus-r6-boom-first-allocation/"
    if (
        type(value) is not str
        or not value.startswith(
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
        )
        or marker not in value
        or not value.endswith("/")
        or "//" in value[5:]
    ):
        _fail("boom-first output prefix differs")
    return value


def _snapshot_uri(prefix: str, ordinal: int, slate_id: str) -> str:
    return f"{_output_prefix(prefix)}inputs/{ordinal:02d}-{slate_id}.json"


def _result_uri(prefix: str, ordinal: int, slate_id: str) -> str:
    return f"{_output_prefix(prefix)}slates/{ordinal:02d}-{slate_id}.json"


def _manifest_uri(prefix: str) -> str:
    return f"{_output_prefix(prefix)}manifest.json"


def _terminal_uri(prefix: str) -> str:
    return f"{_output_prefix(prefix)}full-54/terminal.json"


def _grade_uri(prefix: str) -> str:
    return f"{_output_prefix(prefix)}full-54/descriptive-realized-grade.json"


def _launch_claim_uri(prefix: str) -> str:
    return f"{_output_prefix(prefix)}authorities/provider-launch-claim.json"


def _launch_receipt_uri(prefix: str) -> str:
    return f"{_output_prefix(prefix)}authorities/provider-launch-receipt.json"


def _json_scalar(value: object) -> object:
    if value is None:
        return None
    try:
        missing = bool(pd.isna(value))
    except (TypeError, ValueError):
        missing = False
    if missing:
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _query_parameters():
    from google.cloud import bigquery

    return [
        bigquery.ArrayQueryParameter("seasons", "INT64", [2023, 2024, 2025]),
        bigquery.ArrayQueryParameter(
            "source_panels", "STRING", list(science.SOURCE_PANELS)
        ),
        bigquery.ScalarQueryParameter(
            "r3_panel", "STRING", science.SOURCE_PANELS[3]
        ),
        bigquery.ScalarQueryParameter(
            "repair_panel", "STRING", science.REPAIR_PANEL
        ),
    ]


def _run_score_blind_query(
    client: object, sql: str, *, job_id: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    from google.cloud import bigquery

    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(query_parameters=_query_parameters()),
        location="US",
        job_id=job_id,
    )
    frame = job.result().to_dataframe()
    receipt = {
        "job_id": str(job.job_id),
        "location": str(job.location or "US"),
        "sql_sha256": sha256(sql.encode("utf-8")).hexdigest(),
        "selected_columns": list(frame.columns.astype(str)),
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "cache_hit": bool(job.cache_hit),
        "error_result": job.error_result,
    }
    if job.error_result is not None:
        _fail("score-blind generation query failed")
    return frame, receipt


def _player_rows(frame: pd.DataFrame, *, panel: str, season: int, week: int):
    rows = frame[
        frame.panel_run_id.astype(str).eq(panel)
        & frame.season.astype(int).eq(season)
        & frame.week.astype(int).eq(week)
    ]
    return [
        {field: _json_scalar(row[field]) for field in science.PLAYER_FIELDS}
        for _, row in rows.sort_values("id", kind="stable").iterrows()
    ]


def _candidate_rows(frame: pd.DataFrame, *, panel: str, season: int, week: int):
    rows = frame[
        frame.panel_run_id.astype(str).eq(panel)
        & frame.season.astype(int).eq(season)
        & frame.week.astype(int).eq(week)
    ]
    result = []
    for _, row in rows.sort_values("cand_ix", kind="stable").iterrows():
        roster = [value for value in str(row["players"]).split(",") if value]
        result.append({
            "panel_run_id": str(row["panel_run_id"]),
            "season": int(row["season"]),
            "week": int(row["week"]),
            "cand_ix": int(row["cand_ix"]),
            "tag": str(row["tag"]),
            "player_ids": sorted(str(value) for value in roster),
            "score_artifact_uri": str(row["score_artifact_uri"]),
            "score_artifact_sha256": str(row["score_artifact_sha256"]),
        })
    return result


def build_manifest_v1(
    *, later_source_identity: object, later_source_freeze_sha256: str,
    terminal_build_receipt: Mapping[str, object],
    terminal_build_receipt_identity: object,
    code_commit: str, image_digest: str,
    immutable_image_uri: str, output_prefix: str,
    snapshot_descriptors: Sequence[Mapping[str, object]],
    preflight_smoke_sha256: str,
    preflight_scoped_source_sha256: str,
) -> dict[str, object]:
    source = _identity(later_source_identity, label="later source")
    build_identity = _identity(
        terminal_build_receipt_identity, label="terminal build receipt"
    )
    build_receipt = _mapping(
        terminal_build_receipt, label="terminal build receipt"
    )
    prefix = _output_prefix(output_prefix)
    experiment_run_id = prefix.rstrip("/").rsplit("/", 1)[-1]
    descriptors = [_mapping(row, label="snapshot descriptor") for row in snapshot_descriptors]
    if (
        _COMMIT.fullmatch(code_commit) is None
        or _IMAGE.fullmatch(image_digest) is None
        or type(immutable_image_uri) is not str
        or not immutable_image_uri.endswith(f"@{image_digest}")
        or re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", experiment_run_id) is None
        or type(later_source_freeze_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", later_source_freeze_sha256) is None
        or re.fullmatch(r"[0-9a-f]{64}", preflight_smoke_sha256) is None
        or re.fullmatch(
            r"[0-9a-f]{64}", preflight_scoped_source_sha256
        ) is None
        or build_receipt.get("source_commit") != code_commit
        or build_receipt.get("image_digest") != image_digest
        or len(descriptors) != science.TASK_COUNT
    ):
        _fail("boom-first manifest authority/lattice differs")
    tasks: list[dict[str, object]] = []
    for ordinal, row in enumerate(descriptors):
        slate_id = science.expected_slate_id_v1(ordinal)
        identity = _identity(row.get("snapshot_identity"), label="generation snapshot")
        if (
            row.get("source_ordinal") != ordinal
            or row.get("slate_id") != slate_id
            or _IMAGE.fullmatch(
                "sha256:" + str(row.get("generation_snapshot_sha256"))
            ) is None
            or identity["uri"] != _snapshot_uri(prefix, ordinal, slate_id)
        ):
            _fail("generation snapshot descriptor differs")
        tasks.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "snapshot_identity": identity,
            "generation_snapshot_sha256": row["generation_snapshot_sha256"],
            "result_uri": _result_uri(prefix, ordinal, slate_id),
        })
    body: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "adapter_id": science.ADAPTER_ID,
        "experiment_run_id": experiment_run_id,
        "later_source_identity": source,
        "later_source_freeze_sha256": later_source_freeze_sha256,
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": _hash(build_receipt),
        "terminal_build_id": build_receipt["build_id"],
        "code_commit": code_commit,
        "image_digest": image_digest,
        "immutable_image_uri": immutable_image_uri,
        "output_prefix": prefix,
        "manifest_uri": _manifest_uri(prefix),
        "terminal_uri": _terminal_uri(prefix),
        "grade_uri": _grade_uri(prefix),
        "task_count": science.TASK_COUNT,
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "task_bindings": tasks,
        "task_bindings_sha256": _hash(tasks),
        "launch_shape": {
            "project": FIXED_PROJECT,
            "region": FIXED_REGION,
            "reused_job_name": FIXED_REUSED_JOB_NAME,
            "reused_job_uid": FIXED_REUSED_JOB_UID,
            "service_account": FIXED_SERVICE_ACCOUNT,
            "tasks": FIXED_TASK_COUNT,
            "parallelism": FIXED_PARALLELISM,
            "cpu": FIXED_CPU,
            "memory": FIXED_MEMORY,
            "timeout_seconds": FIXED_TIMEOUT_SECONDS,
            "max_retries": FIXED_MAX_RETRIES,
            "command": list(EXPECTED_TASK_COMMAND),
            "manifest_identity_environment": MANIFEST_IDENTITY_ENV,
            "task0_smoke_sha256_environment": TASK0_SMOKE_SHA_ENV,
            "new_job_creation_allowed": False,
        },
        "construction_preset": science.construction_preset_v1(),
        "generation_snapshot_law": {
            "source_table": PLAYER_TABLE,
            "capture_time": "prepare-command",
            "create_once_per_slate": True,
            "objective_field": "proj_tourney",
            "exact_control_roster_and_world_total_reproduction_required_per_seed": True,
            "postlock_columns_selected": [],
        },
        "model_ensemble": 1,
        "control_allocation": {"leverage": 160, "boom": 40, "role": 12},
        "treatment_allocation": {"leverage": 40, "boom": 160, "role": 12},
        "equal_requested_core_work": True,
        "equal_unique_population_required": False,
        "entry_budget": science.ENTRY_BUDGET,
        "tail_line": science.TAIL_LINE,
        "preflight_smoke_sha256": preflight_smoke_sha256,
        "preflight_scoped_source_sha256": preflight_scoped_source_sha256,
        "real_artifact_preflight_smoke_required_before_prepare": True,
        "manifest_bound_task0_smoke_required_before_launch": True,
        "target_slate_outcome_columns": [],
        "uses_realized_outcomes": False,
        "descriptive_only": True,
        "production_change_licensed": False,
    }
    return _with_hash(body, field="manifest_sha256")


def validate_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="boom-first manifest")
    digest = manifest.get("manifest_sha256")
    body = {key: child for key, child in manifest.items() if key != "manifest_sha256"}
    if type(digest) is not str or digest != _hash(body):
        _fail("boom-first manifest hash differs")
    expected_fields = {
        "schema_version", "adapter_id", "experiment_run_id",
        "later_source_identity", "later_source_freeze_sha256",
        "terminal_build_receipt_identity", "terminal_build_receipt_sha256",
        "terminal_build_id", "code_commit",
        "image_digest", "immutable_image_uri", "output_prefix", "manifest_uri",
        "terminal_uri", "grade_uri", "task_count", "task_bindings",
        "reused_job_name", "reused_job_uid", "service_account",
        "task_bindings_sha256", "launch_shape", "construction_preset",
        "generation_snapshot_law",
        "model_ensemble", "control_allocation", "treatment_allocation",
        "equal_requested_core_work", "equal_unique_population_required",
        "entry_budget", "tail_line",
        "preflight_smoke_sha256", "preflight_scoped_source_sha256",
        "real_artifact_preflight_smoke_required_before_prepare",
        "manifest_bound_task0_smoke_required_before_launch",
        "target_slate_outcome_columns",
        "uses_realized_outcomes", "descriptive_only",
        "production_change_licensed", "manifest_sha256",
    }
    expected_launch = {
        "project": FIXED_PROJECT,
        "region": FIXED_REGION,
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "tasks": FIXED_TASK_COUNT,
        "parallelism": FIXED_PARALLELISM,
        "cpu": FIXED_CPU,
        "memory": FIXED_MEMORY,
        "timeout_seconds": FIXED_TIMEOUT_SECONDS,
        "max_retries": FIXED_MAX_RETRIES,
        "command": list(EXPECTED_TASK_COMMAND),
        "manifest_identity_environment": MANIFEST_IDENTITY_ENV,
        "task0_smoke_sha256_environment": TASK0_SMOKE_SHA_ENV,
        "new_job_creation_allowed": False,
    }
    expected_snapshot_law = {
        "source_table": PLAYER_TABLE,
        "capture_time": "prepare-command",
        "create_once_per_slate": True,
        "objective_field": "proj_tourney",
        "exact_control_roster_and_world_total_reproduction_required_per_seed": True,
        "postlock_columns_selected": [],
    }
    image_digest = manifest.get("image_digest")
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("adapter_id") != science.ADAPTER_ID
        or re.fullmatch(
            r"[a-z0-9][a-z0-9-]{2,80}", str(manifest.get("experiment_run_id"))
        ) is None
        or _COMMIT.fullmatch(str(manifest.get("code_commit"))) is None
        or _IMAGE.fullmatch(str(image_digest)) is None
        or type(manifest.get("immutable_image_uri")) is not str
        or not str(manifest["immutable_image_uri"]).endswith(f"@{image_digest}")
        or manifest.get("launch_shape") != expected_launch
        or manifest.get("generation_snapshot_law") != expected_snapshot_law
        or manifest.get("task_count") != science.TASK_COUNT
        or manifest.get("reused_job_name") != FIXED_REUSED_JOB_NAME
        or manifest.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or manifest.get("service_account") != FIXED_SERVICE_ACCOUNT
        or manifest.get("model_ensemble") != 1
        or manifest.get("construction_preset") != science.construction_preset_v1()
        or manifest.get("control_allocation") != {"leverage": 160, "boom": 40, "role": 12}
        or manifest.get("treatment_allocation") != {"leverage": 40, "boom": 160, "role": 12}
        or manifest.get("equal_requested_core_work") is not True
        or manifest.get("equal_unique_population_required") is not False
        or manifest.get("entry_budget") != science.ENTRY_BUDGET
        or manifest.get("tail_line") != science.TAIL_LINE
        or any(
            re.fullmatch(r"[0-9a-f]{64}", str(manifest.get(field))) is None
            for field in (
                "preflight_smoke_sha256", "preflight_scoped_source_sha256",
            )
        )
        or manifest.get("real_artifact_preflight_smoke_required_before_prepare")
        is not True
        or manifest.get("manifest_bound_task0_smoke_required_before_launch")
        is not True
        or manifest.get("target_slate_outcome_columns") != []
        or manifest.get("uses_realized_outcomes") is not False
        or manifest.get("descriptive_only") is not True
        or manifest.get("production_change_licensed") is not False
    ):
        _fail("boom-first manifest fixed law differs")
    _identity(manifest.get("later_source_identity"), label="manifest later source")
    _identity(
        manifest.get("terminal_build_receipt_identity"),
        label="manifest terminal build receipt",
    )
    for field in (
        "later_source_freeze_sha256", "terminal_build_receipt_sha256",
    ):
        if re.fullmatch(r"[0-9a-f]{64}", str(manifest.get(field))) is None:
            _fail(f"boom-first manifest {field} differs")
    if type(manifest.get("terminal_build_id")) is not str or not manifest[
        "terminal_build_id"
    ]:
        _fail("boom-first manifest build ID differs")
    prefix = _output_prefix(manifest.get("output_prefix"))
    if (
        manifest.get("manifest_uri") != _manifest_uri(prefix)
        or manifest.get("terminal_uri") != _terminal_uri(prefix)
        or manifest.get("grade_uri") != _grade_uri(prefix)
        or manifest.get("task_bindings_sha256") != _hash(manifest.get("task_bindings"))
    ):
        _fail("boom-first manifest topology differs")
    tasks = _sequence(manifest.get("task_bindings"), label="manifest tasks")
    if len(tasks) != science.TASK_COUNT:
        _fail("boom-first manifest is not exact 54")
    for ordinal, raw in enumerate(tasks):
        task = _mapping(raw, label=f"manifest task[{ordinal}]")
        slate_id = science.expected_slate_id_v1(ordinal)
        snapshot_identity = _identity(task.get("snapshot_identity"), label="snapshot")
        if (
            task.get("source_ordinal") != ordinal
            or task.get("slate_id") != slate_id
            or _IMAGE.fullmatch(
                "sha256:" + str(task.get("generation_snapshot_sha256"))
            ) is None
            or snapshot_identity["uri"] != _snapshot_uri(prefix, ordinal, slate_id)
            or task.get("result_uri") != _result_uri(prefix, ordinal, slate_id)
        ):
            _fail("boom-first manifest task binding differs")
    return manifest


_SMOKE_RECEIPT_FIELDS: Final = frozenset({
    "schema_version", "execution_mode", "later_source_identity",
    "later_source_freeze_sha256", "code_commit", "manifest_identity",
    "manifest_sha256", "terminal_build_receipt_identity", "image_digest",
    "immutable_image_uri", "source_ordinal", "slate_id",
    "generation_snapshot_identity", "generation_snapshot_sha256",
    "query_receipts_sha256", "task_result_sha256",
    "runtime_authority_sha256", "normalized_slate_sha256",
    "source_provenance",
    "arm_science_sha256", "control_reproductions_sha256",
    "control_reproduction_count", "all_five_control_books_reproduced",
    "selected_book_counts", "both_arms_exact_80",
    "publication_performed", "outcome_columns_read",
    "uses_realized_outcomes", "complete", "smoke_sha256",
})


def _validate_smoke_receipt_base_v1(
    value: object, *, schema_version: str, execution_mode: str,
) -> dict[str, object]:
    receipt = _mapping(value, label=f"boom-first {execution_mode} receipt")
    body = {key: child for key, child in receipt.items() if key != "smoke_sha256"}
    selected_counts = _mapping(
        receipt.get("selected_book_counts"), label="smoke selected-book counts"
    )
    provenance = _validate_source_provenance_v1(
        receipt.get("source_provenance"), execution_mode=execution_mode,
        code_commit=str(receipt.get("code_commit")),
    )
    if (
        set(receipt) != _SMOKE_RECEIPT_FIELDS
        or receipt.get("schema_version") != schema_version
        or receipt.get("execution_mode") != execution_mode
        or receipt.get("smoke_sha256") != _hash(body)
        or receipt.get("source_ordinal") != 0
        or receipt.get("slate_id") != science.expected_slate_id_v1(0)
        or _COMMIT.fullmatch(str(receipt.get("code_commit"))) is None
        or any(
            re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(field))) is None
            for field in (
                "later_source_freeze_sha256", "generation_snapshot_sha256",
                "query_receipts_sha256", "task_result_sha256",
                "runtime_authority_sha256", "normalized_slate_sha256",
                "arm_science_sha256", "control_reproductions_sha256",
            )
        )
        or receipt.get("control_reproduction_count") != len(science.BLOCK_ORDER)
        or receipt.get("all_five_control_books_reproduced") is not True
        or selected_counts != {
            "control": science.ENTRY_BUDGET,
            "treatment": science.ENTRY_BUDGET,
        }
        or receipt.get("both_arms_exact_80") is not True
        or receipt.get("publication_performed") is not False
        or receipt.get("outcome_columns_read") != []
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("complete") is not True
    ):
        _fail(f"boom-first {execution_mode} receipt differs")
    _identity(receipt.get("later_source_identity"), label="smoke later source")
    return receipt


def _validate_preflight_smoke_receipt_v1(
    value: object, *, later_source_identity: object,
    later_source_freeze_sha256: str, code_commit: str,
) -> dict[str, object]:
    receipt = _validate_smoke_receipt_base_v1(
        value, schema_version=PREFLIGHT_SMOKE_SCHEMA,
        execution_mode="preflight-smoke",
    )
    expected_source = _identity(later_source_identity, label="preflight later source")
    current_scoped_source = _scoped_source_measurement_v1()
    if (
        receipt.get("later_source_identity") != expected_source
        or receipt.get("later_source_freeze_sha256")
        != later_source_freeze_sha256
        or receipt.get("code_commit") != code_commit
        or receipt["source_provenance"].get("scoped_source_sha256")
        != current_scoped_source["scoped_source_sha256"]
        or any(receipt.get(field) is not None for field in (
            "manifest_identity", "manifest_sha256",
            "terminal_build_receipt_identity", "image_digest",
            "immutable_image_uri", "generation_snapshot_identity",
        ))
    ):
        _fail("boom-first preflight smoke authority differs")
    return receipt


def _validate_manifest_smoke_receipt_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
) -> dict[str, object]:
    receipt = _validate_smoke_receipt_base_v1(
        value, schema_version=MANIFEST_SMOKE_SCHEMA,
        execution_mode="manifest-smoke",
    )
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="smoke manifest")
    binding = _mapping(retained["task_bindings"][0], label="smoke task binding")
    provenance = _mapping(
        receipt["source_provenance"], label="manifest smoke source provenance"
    )
    if (
        receipt.get("manifest_identity") != identity
        or receipt.get("manifest_sha256") != retained["manifest_sha256"]
        or receipt.get("later_source_identity") != retained["later_source_identity"]
        or receipt.get("later_source_freeze_sha256")
        != retained["later_source_freeze_sha256"]
        or receipt.get("terminal_build_receipt_identity")
        != retained["terminal_build_receipt_identity"]
        or receipt.get("code_commit") != retained["code_commit"]
        or receipt.get("image_digest") != retained["image_digest"]
        or receipt.get("immutable_image_uri") != retained["immutable_image_uri"]
        or receipt.get("generation_snapshot_identity")
        != binding["snapshot_identity"]
        or receipt.get("generation_snapshot_sha256")
        != binding["generation_snapshot_sha256"]
        or provenance.get("scoped_source_sha256")
        != retained["preflight_scoped_source_sha256"]
    ):
        _fail("boom-first manifest smoke authority differs")
    return receipt


def _build_snapshot_from_frames_v1(
    *, source_ordinal: int, frozen_source: Mapping[str, object],
    source_identity: Mapping[str, object], player_frame: pd.DataFrame,
    candidate_frame: pd.DataFrame, query_receipts: Mapping[str, object],
) -> dict[str, object]:
    season, week = science.SLATE_KEYS[source_ordinal]
    players: dict[str, list[dict[str, object]]] = {}
    candidates: dict[str, list[dict[str, object]]] = {}
    for block in science.BLOCK_ORDER:
        panel = science.candidate_source_panel_v1(season, week, block)
        players[block] = _player_rows(
            player_frame, panel=panel, season=season, week=week
        )
        candidates[block] = _candidate_rows(
            candidate_frame, panel=panel, season=season, week=week
        )
    return science.build_generation_snapshot_v1(
        source_ordinal=source_ordinal,
        later_source_identity=source_identity,
        later_source_freeze_sha256=str(frozen_source["freeze_sha256"]),
        later_slate=frozen_source["slates"][source_ordinal],
        player_rows_by_block=players,
        candidate_rows_by_block=candidates,
        query_receipts=query_receipts,
    )


def prepare_from_request_v1(
    request: object, *, store: object, bq_client: object, provider: object,
) -> dict[str, object]:
    item = _mapping(request, label="boom-first prepare request")
    if set(item) != {
        "later_source_identity", "terminal_build_receipt_identity",
        "preflight_smoke_receipt", "code_commit", "image_digest",
        "immutable_image_uri", "output_prefix",
    }:
        _fail("boom-first prepare request fields differ")
    source, source_identity = _read_json(
        item["later_source_identity"], store=store, label="later source freeze",
        maximum_bytes=MAXIMUM_LATER_SOURCE_BYTES,
    )
    try:
        frozen = later_source.validate_source_freeze(
            source, expected_freeze_sha256=str(source["freeze_sha256"])
        )
    except later_source.LR8LaterSourceError as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    if source_identity != _identity(
        item["later_source_identity"], label="requested later source"
    ):
        _fail("boom-first later-source identity differs")
    preflight = _validate_preflight_smoke_receipt_v1(
        item["preflight_smoke_receipt"],
        later_source_identity=source_identity,
        later_source_freeze_sha256=str(frozen["freeze_sha256"]),
        code_commit=str(item["code_commit"]),
    )
    build_identity = _identity(
        item["terminal_build_receipt_identity"], label="terminal build receipt"
    )
    build_raw = store.read_exact(build_identity)
    if (
        type(build_raw) is not bytes
        or len(build_raw) != build_identity["bytes"]
        or sha256(build_raw).hexdigest() != build_identity["sha256"]
    ):
        _fail("boom-first terminal build receipt exact bytes differ")
    try:
        raw_build_receipt = _mapping(
            json.loads(build_raw), label="terminal build receipt"
        )
        transport._validate_provider_build_attestation_v1(
            receipt=raw_build_receipt,
            provider_build=provider.describe_build(str(raw_build_receipt["build_id"])),
        )
        build_receipt, retained_build_identity = (
            l2b_panel._read_terminal_build_receipt(
                build_identity,
                source_commit_sha=str(item["code_commit"]),
                immutable_image_digest=str(item["image_digest"]),
                read_exact=store.read_exact,
                label="boom-first terminal build receipt",
            )
        )
    except (
        UnicodeDecodeError, json.JSONDecodeError, KeyError,
        l2b_panel.CorpusR6L2BPanelCloudV1Error,
        transport.RunCorpusR6CombinedPopulationAllBlockV1Error,
    ) as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    if retained_build_identity != build_identity or build_receipt != raw_build_receipt:
        _fail("boom-first terminal build receipt exact replay differs")
    prefix = _output_prefix(item["output_prefix"])
    query_namespace = sha256(prefix.encode("utf-8")).hexdigest()[:20]
    player_frame, player_receipt = _run_score_blind_query(
        bq_client, PLAYER_SQL,
        job_id=f"boom_first_k1_{query_namespace}_players",
    )
    candidate_frame, candidate_receipt = _run_score_blind_query(
        bq_client, CANDIDATE_SQL,
        job_id=f"boom_first_k1_{query_namespace}_candidates",
    )
    query_receipts = {
        "player_generation_snapshot": player_receipt,
        "candidate_generation_snapshot": candidate_receipt,
        "queried_at_prepare": True,
        "postlock_columns_selected": [],
    }
    descriptors: list[dict[str, object]] = []
    for ordinal in range(science.TASK_COUNT):
        snapshot = _build_snapshot_from_frames_v1(
            source_ordinal=ordinal, frozen_source=frozen,
            source_identity=source_identity, player_frame=player_frame,
            candidate_frame=candidate_frame, query_receipts=query_receipts,
        )
        slate_id = str(snapshot["slate_id"])
        identity = _publish_json(
            uri=_snapshot_uri(prefix, ordinal, slate_id), value=snapshot,
            maximum_bytes=MAXIMUM_SNAPSHOT_BYTES, store=store,
        )
        descriptors.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "snapshot_identity": identity,
            "generation_snapshot_sha256": snapshot["generation_snapshot_sha256"],
        })
    manifest = build_manifest_v1(
        later_source_identity=source_identity,
        later_source_freeze_sha256=str(frozen["freeze_sha256"]),
        terminal_build_receipt=build_receipt,
        terminal_build_receipt_identity=build_identity,
        code_commit=str(item["code_commit"]),
        image_digest=str(item["image_digest"]),
        immutable_image_uri=str(item["immutable_image_uri"]),
        output_prefix=prefix,
        snapshot_descriptors=descriptors,
        preflight_smoke_sha256=str(preflight["smoke_sha256"]),
        preflight_scoped_source_sha256=str(
            preflight["source_provenance"]["scoped_source_sha256"]
        ),
    )
    manifest_identity = _publish_json(
        uri=str(manifest["manifest_uri"]), value=manifest,
        maximum_bytes=MAXIMUM_MANIFEST_BYTES, store=store,
    )
    return {
        "schema_version": PREPARE_RESULT_SCHEMA,
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "later_source_identity": source_identity,
        "terminal_build_receipt_identity": build_identity,
        "preflight_smoke_sha256": preflight["smoke_sha256"],
        "preflight_scoped_source_sha256": preflight[
            "source_provenance"
        ]["scoped_source_sha256"],
        "generation_snapshot_count": len(descriptors),
        "task_count": science.TASK_COUNT,
        "launch_shape": manifest["launch_shape"],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _open_manifest(identity_value: object, *, store: object):
    manifest, identity = _read_json(
        identity_value, store=store, label="boom-first manifest",
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    retained = validate_manifest_v1(manifest)
    if identity["uri"] != retained["manifest_uri"]:
        _fail("boom-first manifest URI differs")
    source, source_identity = _read_json(
        retained["later_source_identity"], store=store,
        label="boom-first retained later source",
        maximum_bytes=MAXIMUM_LATER_SOURCE_BYTES,
    )
    try:
        frozen = later_source.validate_source_freeze(
            source,
            expected_freeze_sha256=str(retained["later_source_freeze_sha256"]),
        )
        build_receipt, build_identity = l2b_panel._read_terminal_build_receipt(
            retained["terminal_build_receipt_identity"],
            source_commit_sha=str(retained["code_commit"]),
            immutable_image_digest=str(retained["image_digest"]),
            read_exact=store.read_exact,
            label="boom-first retained terminal build receipt",
        )
    except (
        later_source.LR8LaterSourceError,
        l2b_panel.CorpusR6L2BPanelCloudV1Error,
    ) as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    if (
        source_identity != retained["later_source_identity"]
        or frozen["freeze_sha256"] != retained["later_source_freeze_sha256"]
        or build_identity != retained["terminal_build_receipt_identity"]
        or _hash(build_receipt) != retained["terminal_build_receipt_sha256"]
        or build_receipt["build_id"] != retained["terminal_build_id"]
    ):
        _fail("boom-first manifest retained source/build authority differs")
    return retained, identity


def _build_job_configuration_from_smoke_sha_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    task0_smoke_sha256: str,
) -> dict[str, object]:
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="provider manifest")
    if re.fullmatch(r"[0-9a-f]{64}", task0_smoke_sha256) is None:
        _fail("boom-first task-0 smoke SHA-256 differs")
    body: dict[str, object] = {
        "schema_version": JOB_CONFIGURATION_SCHEMA,
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "task_manifest_identity": identity,
        "task_manifest_sha256": retained["manifest_sha256"],
        "task0_smoke_sha256": task0_smoke_sha256,
        "terminal_build_receipt_identity": retained[
            "terminal_build_receipt_identity"
        ],
        "terminal_build_receipt_sha256": retained[
            "terminal_build_receipt_sha256"
        ],
        "image_digest": retained["image_digest"],
        "immutable_image_uri": retained["immutable_image_uri"],
        "container_command": [EXPECTED_TASK_COMMAND[0]],
        "container_args": list(EXPECTED_TASK_COMMAND[1:]),
        "container_environment": {
            SELECTION_ENABLE_ENV: SELECTION_ENABLE_VALUE,
            MANIFEST_IDENTITY_ENV: _canonical(identity).decode("utf-8"),
            TASK0_SMOKE_SHA_ENV: task0_smoke_sha256,
            "GOOGLE_CLOUD_PROJECT": FIXED_PROJECT,
            "CODE_SHA": retained["code_commit"],
            "ANALYSIS_IMAGE": retained["immutable_image_uri"],
            "R6_RUNTIME_IMAGE_DIGEST": retained["image_digest"],
        },
        "task_count": FIXED_TASK_COUNT,
        "parallelism": FIXED_PARALLELISM,
        "max_retries": FIXED_MAX_RETRIES,
        "timeout_seconds": FIXED_TIMEOUT_SECONDS,
        "cpu": FIXED_CPU,
        "memory": FIXED_MEMORY,
        "working_directory": "",
        "volumes": [],
        "volume_mounts": [],
        "new_job_creation_allowed": False,
    }
    projection = _provider_job_projection_from_configuration_v1(body)
    body["container_environment"][JOB_AUTHORITY_SHA_ENV] = _hash(projection)
    return _with_hash(body, field="job_configuration_sha256")


def build_job_configuration_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    smoke_receipt: object,
) -> dict[str, object]:
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="provider manifest")
    smoke = _validate_manifest_smoke_receipt_v1(
        smoke_receipt, manifest=retained, manifest_identity=identity
    )
    return _build_job_configuration_from_smoke_sha_v1(
        manifest=retained, manifest_identity=identity,
        task0_smoke_sha256=str(smoke["smoke_sha256"]),
    )


def expected_provider_job_observation_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    smoke_receipt: object,
) -> dict[str, object]:
    return _provider_job_projection_from_configuration_v1(
        build_job_configuration_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            smoke_receipt=smoke_receipt,
        )
    )


def validate_provider_job_observation_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    smoke_receipt: object,
) -> dict[str, object]:
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="provider manifest")
    smoke = _validate_manifest_smoke_receipt_v1(
        smoke_receipt, manifest=retained, manifest_identity=identity
    )
    return _validate_provider_job_observation_from_smoke_sha_v1(
        value, manifest=retained, manifest_identity=identity,
        task0_smoke_sha256=str(smoke["smoke_sha256"]),
    )


def _validate_provider_job_observation_from_smoke_sha_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    task0_smoke_sha256: str,
) -> dict[str, object]:
    observed = _mapping(value, label="boom-first provider job observation")
    expected = _provider_job_projection_from_configuration_v1(
        _build_job_configuration_from_smoke_sha_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            task0_smoke_sha256=task0_smoke_sha256,
        )
    )
    without_uri = lambda row: {  # noqa: E731
        key: child for key, child in row.items() if key != "immutable_image_uri"
    }
    if (
        without_uri(observed) != without_uri(expected)
        or not transport._execution_image_matches_job_image_v1(
            execution_uri=observed.get("immutable_image_uri"),
            job_uri=expected.get("immutable_image_uri"),
            expected_digest=expected.get("image_digest"),
        )
    ):
        _fail("boom-first provider job observation differs")
    return observed


def configure_existing_job_v1(
    *, manifest_identity: object, smoke_receipt: object,
    store: object, provider: object,
) -> dict[str, object]:
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    current_identity = provider.describe_job_identity(FIXED_REUSED_JOB_NAME)
    if current_identity != {
        "job_name": FIXED_REUSED_JOB_NAME,
        "job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "provider_observed": True,
    }:
        _fail("boom-first reusable job identity differs")
    configuration = build_job_configuration_v1(
        manifest=manifest, manifest_identity=retained_identity,
        smoke_receipt=smoke_receipt,
    )
    provider.update_existing_job(configuration)
    observation = validate_provider_job_observation_v1(
        provider.describe_job(FIXED_REUSED_JOB_NAME),
        manifest=manifest, manifest_identity=retained_identity,
        smoke_receipt=smoke_receipt,
    )
    return {
        "schema_version": "corpus-r6-boom-first-allocation-configure-result/v1",
        "manifest_identity": retained_identity,
        "job_configuration_sha256": configuration["job_configuration_sha256"],
        "job_observation": observation,
        "job_observation_sha256": _hash(observation),
        "task0_smoke_sha256": _mapping(
            smoke_receipt, label="configure smoke receipt"
        )["smoke_sha256"],
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "new_job_created": False,
        "complete": True,
    }


def _build_launch_claim_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    smoke_receipt: object, job_observation: Mapping[str, object],
) -> dict[str, object]:
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="launch-claim manifest")
    smoke = _validate_manifest_smoke_receipt_v1(
        smoke_receipt, manifest=retained, manifest_identity=identity
    )
    observation = validate_provider_job_observation_v1(
        job_observation, manifest=retained, manifest_identity=identity,
        smoke_receipt=smoke,
    )
    return _with_hash({
        "schema_version": LAUNCH_CLAIM_SCHEMA,
        "manifest_identity": identity,
        "manifest_sha256": retained["manifest_sha256"],
        "task0_smoke_sha256": smoke["smoke_sha256"],
        "job_observation_sha256": _hash(observation),
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "task_count": FIXED_TASK_COUNT,
        "parallelism": FIXED_PARALLELISM,
        "provider_launch_call_budget": 1,
        "automatic_relaunch_allowed": False,
        "receipt_absence_requires_explicit_reconciliation": True,
        "complete": True,
    }, field="launch_claim_sha256")


def _validate_launch_claim_from_smoke_sha_v1(
    value: object, *, manifest: Mapping[str, object],
    manifest_identity: object, task0_smoke_sha256: str,
) -> dict[str, object]:
    claim = _mapping(value, label="boom-first launch claim")
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="launch-claim manifest")
    if re.fullmatch(r"[0-9a-f]{64}", task0_smoke_sha256) is None:
        _fail("boom-first launch-claim smoke hash differs")
    expected_fields = {
        "schema_version", "manifest_identity", "manifest_sha256",
        "task0_smoke_sha256", "job_observation_sha256",
        "reused_job_name", "reused_job_uid", "service_account",
        "task_count", "parallelism", "provider_launch_call_budget",
        "automatic_relaunch_allowed",
        "receipt_absence_requires_explicit_reconciliation", "complete",
        "launch_claim_sha256",
    }
    body = {
        key: child for key, child in claim.items()
        if key != "launch_claim_sha256"
    }
    if (
        set(claim) != expected_fields
        or claim.get("schema_version") != LAUNCH_CLAIM_SCHEMA
        or claim.get("launch_claim_sha256") != _hash(body)
        or claim.get("manifest_identity") != identity
        or claim.get("manifest_sha256") != retained["manifest_sha256"]
        or claim.get("task0_smoke_sha256") != task0_smoke_sha256
        or re.fullmatch(
            r"[0-9a-f]{64}", str(claim.get("job_observation_sha256"))
        ) is None
        or claim.get("reused_job_name") != FIXED_REUSED_JOB_NAME
        or claim.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or claim.get("service_account") != FIXED_SERVICE_ACCOUNT
        or claim.get("task_count") != FIXED_TASK_COUNT
        or claim.get("parallelism") != FIXED_PARALLELISM
        or claim.get("provider_launch_call_budget") != 1
        or claim.get("automatic_relaunch_allowed") is not False
        or claim.get(
            "receipt_absence_requires_explicit_reconciliation"
        ) is not True
        or claim.get("complete") is not True
    ):
        _fail("boom-first launch claim authority differs")
    return claim


def _validate_launch_claim_v1(
    value: object, *, manifest: Mapping[str, object],
    manifest_identity: object, smoke_receipt: object,
) -> dict[str, object]:
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="launch-claim manifest")
    smoke = _validate_manifest_smoke_receipt_v1(
        smoke_receipt, manifest=retained, manifest_identity=identity
    )
    return _validate_launch_claim_from_smoke_sha_v1(
        value, manifest=retained, manifest_identity=identity,
        task0_smoke_sha256=str(smoke["smoke_sha256"]),
    )


def _build_launch_receipt_v1(
    *, claim: Mapping[str, object], claim_identity: object,
    execution_id: str,
) -> dict[str, object]:
    identity = _identity(claim_identity, label="launch claim")
    if type(execution_id) is not str or not execution_id:
        _fail("boom-first provider launch returned no execution ID")
    return _with_hash({
        "schema_version": LAUNCH_RECEIPT_SCHEMA,
        "launch_claim_identity": identity,
        "launch_claim_sha256": claim["launch_claim_sha256"],
        "manifest_identity": claim["manifest_identity"],
        "manifest_sha256": claim["manifest_sha256"],
        "task0_smoke_sha256": claim["task0_smoke_sha256"],
        "execution_id": execution_id,
        "job_observation_sha256": claim["job_observation_sha256"],
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "provider_launch_call_count": 1,
        "new_job_created": False,
        "complete": True,
    }, field="launch_receipt_sha256")


def _validate_launch_receipt_v1(
    value: object, *, claim: Mapping[str, object], claim_identity: object,
) -> dict[str, object]:
    receipt = _mapping(value, label="boom-first launch receipt")
    identity = _identity(claim_identity, label="launch claim")
    expected_fields = {
        "schema_version", "launch_claim_identity", "launch_claim_sha256",
        "manifest_identity", "manifest_sha256", "task0_smoke_sha256",
        "execution_id", "job_observation_sha256", "reused_job_name",
        "reused_job_uid", "service_account", "provider_launch_call_count",
        "new_job_created", "complete", "launch_receipt_sha256",
    }
    body = {
        key: child for key, child in receipt.items()
        if key != "launch_receipt_sha256"
    }
    if (
        set(receipt) != expected_fields
        or receipt.get("schema_version") != LAUNCH_RECEIPT_SCHEMA
        or receipt.get("launch_receipt_sha256") != _hash(body)
        or receipt.get("launch_claim_identity") != identity
        or receipt.get("launch_claim_sha256") != claim["launch_claim_sha256"]
        or receipt.get("manifest_identity") != claim["manifest_identity"]
        or receipt.get("manifest_sha256") != claim["manifest_sha256"]
        or receipt.get("task0_smoke_sha256") != claim["task0_smoke_sha256"]
        or receipt.get("job_observation_sha256")
        != claim["job_observation_sha256"]
        or type(receipt.get("execution_id")) is not str
        or not receipt["execution_id"]
        or receipt.get("reused_job_name") != FIXED_REUSED_JOB_NAME
        or receipt.get("reused_job_uid") != FIXED_REUSED_JOB_UID
        or receipt.get("service_account") != FIXED_SERVICE_ACCOUNT
        or receipt.get("provider_launch_call_count") != 1
        or receipt.get("new_job_created") is not False
        or receipt.get("complete") is not True
    ):
        _fail("boom-first launch receipt authority differs")
    return receipt


def _open_launch_receipt_v1(
    identity_value: object, *, manifest: Mapping[str, object],
    manifest_identity: object, store: object,
    smoke_receipt: object | None = None,
    task0_smoke_sha256: str | None = None,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if (smoke_receipt is None) == (task0_smoke_sha256 is None):
        _fail("boom-first launch receipt requires exactly one smoke authority")
    retained_manifest = validate_manifest_v1(manifest)
    retained_manifest_identity = _identity(
        manifest_identity, label="launch-receipt manifest"
    )
    receipt, receipt_identity = _read_json(
        identity_value, store=store, label="boom-first launch receipt",
        maximum_bytes=MAXIMUM_LAUNCH_AUTHORITY_BYTES,
    )
    prefix = str(retained_manifest["output_prefix"])
    if receipt_identity["uri"] != _launch_receipt_uri(prefix):
        _fail("boom-first launch receipt URI differs")
    raw_claim_identity = _mapping(
        receipt.get("launch_claim_identity"), label="launch claim identity"
    )
    claim, claim_identity = _read_json(
        raw_claim_identity, store=store, label="boom-first launch claim",
        maximum_bytes=MAXIMUM_LAUNCH_AUTHORITY_BYTES,
    )
    if claim_identity["uri"] != _launch_claim_uri(prefix):
        _fail("boom-first launch claim URI differs")
    if smoke_receipt is not None:
        retained_claim = _validate_launch_claim_v1(
            claim, manifest=retained_manifest,
            manifest_identity=retained_manifest_identity,
            smoke_receipt=smoke_receipt,
        )
    else:
        retained_claim = _validate_launch_claim_from_smoke_sha_v1(
            claim, manifest=retained_manifest,
            manifest_identity=retained_manifest_identity,
            task0_smoke_sha256=str(task0_smoke_sha256),
        )
    retained_receipt = _validate_launch_receipt_v1(
        receipt, claim=retained_claim, claim_identity=claim_identity,
    )
    return retained_receipt, receipt_identity, retained_claim


def launch_existing_job_v1(
    *, manifest_identity: object, smoke_receipt: object,
    store: object, provider: object,
) -> dict[str, object]:
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    smoke = _validate_manifest_smoke_receipt_v1(
        smoke_receipt, manifest=manifest, manifest_identity=retained_identity
    )
    observation = validate_provider_job_observation_v1(
        provider.describe_job(FIXED_REUSED_JOB_NAME),
        manifest=manifest, manifest_identity=retained_identity,
        smoke_receipt=smoke,
    )
    claim = _build_launch_claim_v1(
        manifest=manifest, manifest_identity=retained_identity,
        smoke_receipt=smoke, job_observation=observation,
    )
    claim_identity = _publish_fresh_launch_claim_v1(
        uri=_launch_claim_uri(str(manifest["output_prefix"])),
        value=claim, store=store,
    )
    # This is the sole provider-launch call in the operator.  The fresh
    # create-only claim above makes replay fail before this boundary.  If the
    # process dies after claiming, operators must reconcile the provider
    # explicitly; automatic relaunch is intentionally impossible.
    execution_id = provider.launch_existing_job(FIXED_REUSED_JOB_NAME)
    receipt = _build_launch_receipt_v1(
        claim=claim, claim_identity=claim_identity, execution_id=execution_id,
    )
    receipt_identity = _publish_json(
        uri=_launch_receipt_uri(str(manifest["output_prefix"])), value=receipt,
        maximum_bytes=MAXIMUM_LAUNCH_AUTHORITY_BYTES, store=store,
    )
    return {
        "schema_version": "corpus-r6-boom-first-allocation-launch-result/v2",
        "manifest_identity": retained_identity,
        "execution_id": execution_id,
        "launch_claim_identity": claim_identity,
        "launch_claim_sha256": claim["launch_claim_sha256"],
        "launch_receipt_identity": receipt_identity,
        "launch_receipt_sha256": receipt["launch_receipt_sha256"],
        "job_observation_sha256": _hash(observation),
        "task0_smoke_sha256": smoke["smoke_sha256"],
        "reused_job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "provider_launch_call_count": 1,
        "automatic_relaunch_allowed": False,
        "new_job_created": False,
        "complete": True,
    }


def build_provider_terminal_execution_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    smoke_receipt: object, launch_receipt: Mapping[str, object],
    launch_receipt_identity: object,
) -> dict[str, object]:
    raw = _mapping(value, label="boom-first provider execution")
    expected_fields = {
        "execution_id", "job_name", "job_uid", "service_account", "project_id",
        "region", "task_count", "succeeded_count", "failed_count",
        "cancelled_count", "running_count", "terminal", "provider_observed",
        "job_observation",
    }
    job = validate_provider_job_observation_v1(
        raw.get("job_observation"), manifest=manifest,
        manifest_identity=manifest_identity, smoke_receipt=smoke_receipt,
    )
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="provider manifest")
    retained_launch_identity = _identity(
        launch_receipt_identity, label="provider launch receipt"
    )
    if (
        set(raw) != expected_fields
        or raw.get("job_name") != FIXED_REUSED_JOB_NAME
        or raw.get("job_uid") != FIXED_REUSED_JOB_UID
        or raw.get("service_account") != FIXED_SERVICE_ACCOUNT
        or raw.get("project_id") != FIXED_PROJECT
        or raw.get("region") != FIXED_REGION
        or type(raw.get("execution_id")) is not str
        or not raw["execution_id"]
        or raw.get("task_count") != FIXED_TASK_COUNT
        or raw.get("succeeded_count") != FIXED_TASK_COUNT
        or raw.get("failed_count") != 0
        or raw.get("cancelled_count") != 0
        or raw.get("running_count") != 0
        or raw.get("terminal") is not True
        or raw.get("provider_observed") is not True
        or raw.get("execution_id") != launch_receipt.get("execution_id")
        or launch_receipt.get("manifest_identity") != identity
        or launch_receipt.get("manifest_sha256") != retained["manifest_sha256"]
        or launch_receipt.get("task0_smoke_sha256")
        != _mapping(smoke_receipt, label="provider smoke receipt").get(
            "smoke_sha256"
        )
        or launch_receipt.get("job_observation_sha256") != _hash(job)
    ):
        _fail("boom-first provider execution is not exact 54/54 terminal")
    proof = _with_hash({
        "schema_version": science.PROVIDER_TERMINAL_SCHEMA,
        "manifest_identity": identity,
        "manifest_sha256": retained["manifest_sha256"],
        "launch_claim_identity": launch_receipt["launch_claim_identity"],
        "launch_receipt_identity": retained_launch_identity,
        "launch_receipt_sha256": launch_receipt["launch_receipt_sha256"],
        **raw,
        "job_observation_sha256": _hash(job),
    }, field="provider_terminal_execution_sha256")
    try:
        return science.validate_provider_terminal_execution_v1(proof)
    except science.CorpusR6BoomFirstAllocationV1Error as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc


def status_existing_execution_v1(
    *, manifest_identity: object, launch_receipt_identity: object,
    smoke_receipt: object,
    store: object, provider: object,
) -> dict[str, object]:
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    launch_receipt, retained_launch_identity, _launch_claim = (
        _open_launch_receipt_v1(
            launch_receipt_identity, manifest=manifest,
            manifest_identity=retained_identity, smoke_receipt=smoke_receipt,
            store=store,
        )
    )
    execution_id = str(launch_receipt["execution_id"])
    raw = provider.describe_execution(execution_id)
    if raw.get("execution_id") != execution_id:
        _fail("boom-first provider status execution ID differs")
    return build_provider_terminal_execution_v1(
        raw, manifest=manifest, manifest_identity=retained_identity,
        smoke_receipt=smoke_receipt, launch_receipt=launch_receipt,
        launch_receipt_identity=retained_launch_identity,
    )


def _artifact_arrays(receipt: Mapping[str, object], raw: bytes):
    try:
        later_source.load_artifact_worlds(receipt, raw)
    except later_source.LR8LaterSourceError as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    try:
        with np.load(BytesIO(raw), allow_pickle=False) as artifact:
            return {
                "cand_ix": np.asarray(artifact["cand_ix"]),
                "totals": np.asarray(artifact["totals"]),
                "tail_line": np.asarray(artifact["tail_line"]),
                "player_ids": np.asarray(artifact["player_ids"]).astype(str),
                "player_draws": np.asarray(artifact["player_draws"], dtype=np.float64),
            }
    except Exception as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(
            "boom-first world artifact cannot be reconstructed"
        ) from exc


def _native_frame(rows: Sequence[Mapping[str, object]]) -> pd.DataFrame:
    return pd.DataFrame([{
        "panel_run_id": row["panel_run_id"],
        "season": row["season"],
        "week": row["week"],
        "cand_ix": row["cand_ix"],
        "tag": row["tag"],
        "players": ",".join(row["player_ids"]),
        "player_ids": list(row["player_ids"]),
        "score_artifact_uri": row["score_artifact_uri"],
        "score_artifact_sha256": row["score_artifact_sha256"],
    } for row in rows])


def _observed_command_v1(raw_cmdline: bytes | None = None) -> list[str]:
    if raw_cmdline is None:
        raw_cmdline = Path("/proc/self/cmdline").read_bytes()
    if type(raw_cmdline) is not bytes or not raw_cmdline.endswith(b"\x00"):
        _fail("boom-first process command is unavailable")
    try:
        command = [part.decode("utf-8") for part in raw_cmdline[:-1].split(b"\x00")]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(
            "boom-first process command is not UTF-8"
        ) from exc
    if command != list(EXPECTED_TASK_COMMAND):
        _fail("boom-first process command differs")
    return command


def _seal_runtime_wall_v1(
    runtime: Mapping[str, object], *, wall_seconds: float,
) -> dict[str, object]:
    body = {
        key: child for key, child in runtime.items()
        if key not in {
            "generation_and_selection_wall_seconds", "runtime_authority_sha256",
        }
    }
    body["generation_and_selection_wall_seconds"] = float(wall_seconds)
    sealed = _with_hash(body, field="runtime_authority_sha256")
    try:
        return science.validate_runtime_identity_v1(sealed)
    except science.CorpusR6BoomFirstAllocationV1Error as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc


def _runtime_identity(
    manifest: Mapping[str, object], *, manifest_identity: object,
    environment: Mapping[str, str], observed_command: Sequence[str],
):
    identity = _identity(manifest_identity, label="runtime manifest")
    index_text = str(environment.get("CLOUD_RUN_TASK_INDEX", ""))
    count_text = str(environment.get("CLOUD_RUN_TASK_COUNT", ""))
    attempt_text = str(environment.get("CLOUD_RUN_TASK_ATTEMPT", ""))
    code = str(environment.get("CODE_SHA", ""))
    image = str(environment.get("ANALYSIS_IMAGE", ""))
    execution_id = str(environment.get("CLOUD_RUN_EXECUTION", ""))
    command = [str(value) for value in observed_command]
    if (
        not index_text.isdecimal()
        or not count_text.isdecimal()
        or int(count_text) != science.TASK_COUNT
        or not 0 <= int(index_text) < int(count_text)
        or attempt_text != "0"
        or not execution_id
        or environment.get("CLOUD_RUN_JOB") != FIXED_REUSED_JOB_NAME
        or environment.get("GOOGLE_CLOUD_PROJECT") != FIXED_PROJECT
        or environment.get(SELECTION_ENABLE_ENV) != SELECTION_ENABLE_VALUE
        or environment.get(MANIFEST_IDENTITY_ENV)
        != _canonical(identity).decode("utf-8")
        or environment.get(TASK0_SMOKE_SHA_ENV, "") == ""
        or code != manifest["code_commit"]
        or image != manifest["immutable_image_uri"]
        or environment.get("R6_RUNTIME_IMAGE_DIGEST") != manifest["image_digest"]
        or command != list(EXPECTED_TASK_COMMAND)
    ):
        _fail("boom-first task runtime identity differs")
    return _seal_runtime_wall_v1({
        "schema_version": science.RUNTIME_AUTHORITY_SCHEMA,
        "execution_mode": "provider-task",
        "source_ordinal": int(index_text),
        "task_count": int(count_text),
        "task_attempt": 0,
        "execution_id": execution_id,
        "job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "manifest_identity": identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "terminal_build_receipt_identity": manifest[
            "terminal_build_receipt_identity"
        ],
        "code_commit": code,
        "image_digest": manifest["image_digest"],
        "immutable_image_uri": image,
        "task0_smoke_sha256": str(environment[TASK0_SMOKE_SHA_ENV]),
        "observed_command": command,
        "authority_source": (
            "reserved-cloud-run-metadata-and-exact-process-command"
        ),
    }, wall_seconds=0.0)


def _validate_task_against_manifest_v1(
    *, result: object, result_identity: object, manifest: Mapping[str, object],
    manifest_identity: object, snapshot: Mapping[str, object], ordinal: int,
    expected_execution_id: str, expected_task0_smoke_sha256: str,
) -> dict[str, object]:
    retained = science.validate_task_result_v1(result)
    identity = _identity(result_identity, label=f"task result[{ordinal}]")
    retained_manifest = validate_manifest_v1(manifest)
    retained_manifest_identity = _identity(
        manifest_identity, label="task result manifest"
    )
    frozen = science.validate_generation_snapshot_v1(snapshot)
    binding = _mapping(
        retained_manifest["task_bindings"][ordinal],
        label=f"task binding[{ordinal}]",
    )
    runtime = science.validate_runtime_identity_v1(
        retained["runtime_identity"], expected_source_ordinal=ordinal
    )
    if (
        binding.get("source_ordinal") != ordinal
        or identity["uri"] != binding["result_uri"]
        or identity["sha256"] != sha256(_canonical(retained)).hexdigest()
        or identity["bytes"] != len(_canonical(retained))
        or retained["source_ordinal"] != ordinal
        or retained["slate_id"] != binding["slate_id"]
        or retained["generation_snapshot_sha256"]
        != binding["generation_snapshot_sha256"]
        or frozen["generation_snapshot_sha256"]
        != binding["generation_snapshot_sha256"]
        or frozen["source_ordinal"] != ordinal
        or retained["later_source_identity"]
        != retained_manifest["later_source_identity"]
        or frozen["later_source_identity"]
        != retained_manifest["later_source_identity"]
        or runtime["execution_mode"] != "provider-task"
        or runtime["execution_id"] != expected_execution_id
        or runtime["job_name"] != FIXED_REUSED_JOB_NAME
        or runtime["reused_job_uid"] != FIXED_REUSED_JOB_UID
        or runtime["service_account"] != FIXED_SERVICE_ACCOUNT
        or runtime["project_id"] != FIXED_PROJECT
        or runtime["region"] != FIXED_REGION
        or runtime["manifest_identity"] != retained_manifest_identity
        or runtime["manifest_sha256"] != retained_manifest["manifest_sha256"]
        or runtime["terminal_build_receipt_identity"]
        != retained_manifest["terminal_build_receipt_identity"]
        or runtime["code_commit"] != retained_manifest["code_commit"]
        or runtime["image_digest"] != retained_manifest["image_digest"]
        or runtime["immutable_image_uri"]
        != retained_manifest["immutable_image_uri"]
        or runtime["task0_smoke_sha256"]
        != expected_task0_smoke_sha256
        or runtime["observed_command"] != list(EXPECTED_TASK_COMMAND)
    ):
        _fail("boom-first task result/manifest/runtime binding differs")
    return retained


def _recover_existing_task_v1(
    *, binding: Mapping[str, object], snapshot: Mapping[str, object],
    manifest: Mapping[str, object], manifest_identity: Mapping[str, object],
    current_runtime: Mapping[str, object], store: object,
) -> tuple[dict[str, object], dict[str, object]] | None:
    """Return a same-input create-once result, or None when it is absent."""

    try:
        result, identity = _open_known_json(
            str(binding["result_uri"]), store=store,
            label="existing task result", maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        )
    except Exception as exc:  # provider NotFound is the only absence signal
        if exc.__class__.__name__ == "NotFound":
            return None
        raise
    retained = _validate_task_against_manifest_v1(
        result=result, result_identity=identity, manifest=manifest,
        manifest_identity=manifest_identity, snapshot=snapshot,
        ordinal=int(binding["source_ordinal"]),
        expected_execution_id=str(current_runtime["execution_id"]),
        expected_task0_smoke_sha256=str(current_runtime["task0_smoke_sha256"]),
    )
    return retained, identity


def _generate_with_frozen_construction_v1(
    slate: pd.DataFrame, draws: np.ndarray, environment: Mapping[str, str],
    *, role_identities: Sequence[frozenset[str]],
):
    """Generate one native book with the named incumbent construction.

    The historical ATLAS helper predates the legality-only optimizer defaults.
    Reusing its implicit ``StackRules`` construction would therefore make the
    experiment depend on whichever defaults happen to be loaded in the image.
    This narrow adapter retains the proven generator call while passing the
    incumbent stack and its full receipt explicitly.
    """

    run_env = {str(key): str(value) for key, value in environment.items()}
    run_env["N_EPISTEMIC"] = "0"
    if run_env.get("BOOM_UNIQUE_FILL") != "0":
        _fail("boom-first generation requires natural boom deduplication")
    construction_receipt = science.construction_preset_v1()[
        "named_construction_preset"
    ]
    expected_construction_env = _mapping(
        construction_receipt["optimizer_environment"],
        label="boom-first incumbent construction environment",
    )
    mismatched = {
        key: (run_env.get(key), value)
        for key, value in expected_construction_env.items()
        if run_env.get(key) != value
    }
    if mismatched:
        _fail(
            "boom-first generation construction environment differs: "
            f"{sorted(mismatched)}"
        )
    captured: list[object] = []
    previous = {
        key: os.environ.get(key)
        for key in set(run_env) | {"ATLAS_BOOM_WORLD_RANKING"}
    }
    os.environ.update(run_env)
    os.environ.pop("ATLAS_BOOM_WORLD_RANKING", None)
    try:
        stack = StackRules(**_mapping(
            construction_receipt["stack"],
            label="boom-first incumbent stack",
        ))
        lineups = atlas.tail_select_lineups(
            slate, slate.to_dict("records"), draws,
            science.TAIL_LINE, science.ENTRY_BUDGET, stack,
            "proj_tourney",
            candidate_multiple=int(run_env.get("CAND_MULT", "2")),
            n_boom_solves=int(run_env.get("N_BOOM", "40")),
            n_game_stacks=int(run_env.get("N_GAMESTACK", "4")),
            contest=atlas.gpp(), sharp_fraction=0.0, cand_log_table=None,
            policy_env=run_env, candidate_capture=captured.append,
            preseeded_role_identities=role_identities,
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if len(captured) != 1 or not lineups:
        _fail("boom-first generation did not capture exactly one native book")
    batch = captured[0]
    return replace(batch, metadata={
        **dict(batch.metadata),
        "construction_preset_receipt": construction_receipt,
    })


def _run_score_blind_task_v1(
    *, frozen_snapshot: Mapping[str, object],
    runtime_identity: Mapping[str, object], store: object,
) -> dict[str, object]:
    """Run one full matched task in memory; this helper never publishes."""

    frozen = science.validate_generation_snapshot_v1(frozen_snapshot)
    runtime = science.validate_runtime_identity_v1(
        runtime_identity, expected_source_ordinal=int(frozen["source_ordinal"])
    )
    atlas.validate_frozen_inputs()
    generation_started = perf_counter()
    controls: dict[str, object] = {}
    treatments: dict[str, object] = {}
    prepared: list[dict[str, object]] = []
    grid = json.loads(atlas.SOURCE_GRID.read_text(encoding="utf-8"))
    for block, seed in zip(science.BLOCK_ORDER, frozen["seeds"], strict=True):
        receipt = seed["artifact_receipt"]
        artifact_identity = _identity(
            {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
            label=f"{block} world artifact",
        )
        artifact = _artifact_arrays(receipt, store.read_exact(artifact_identity))
        snapshot_frame = pd.DataFrame(seed["player_rows"])
        slate = atlas._slate_frame(snapshot_frame, artifact["player_ids"])
        draws = artifact["player_draws"]
        if draws.shape != (len(slate), science.WORLDS_PER_BLOCK):
            _fail("boom-first player-world shape differs")
        dst = slate["pos"].astype(str).str.upper().eq("DST").to_numpy()
        if not dst.any() or float(draws[dst].std(axis=1).max()) != 0.0:
            _fail("boom-first DST world rows differ")
        natives = _native_frame(seed["candidate_rows"])
        role_identities = [
            frozenset(row["player_ids"])
            for _, row in natives[natives.tag.astype(str).eq("epi")].iterrows()
        ]
        block_index = science.BLOCK_ORDER.index(block)
        cell = atlas._grid_cell(
            grid, science.SOURCE_PANELS[block_index],
            int(frozen["season"]), int(frozen["week"]),
        )
        source_env = atlas._generation_env(
            block_index, int(frozen["season"]), str(runtime["code_commit"])
        )
        atlas._validate_lever_env(cell, source_env)
        envs = science.arm_environments_v1(
            source_env, code_sha=str(runtime["code_commit"])
        )
        prepared.append({
            "block": block, "slate": slate, "draws": draws,
            "artifact": artifact, "natives": natives,
            "role_identities": role_identities, "envs": envs,
        })

    # Preserve the proven solver-state reproduction order: all controls first.
    for item in prepared:
        generated = _generate_with_frozen_construction_v1(
            item["slate"], item["draws"], item["envs"]["control"],
            role_identities=item["role_identities"],
        )
        control = science.inject_frozen_role12_v1(
            generated, native_rows=item["natives"], slate=item["slate"],
            artifact_totals=item["artifact"]["totals"],
        )
        reproduction = atlas._reproduction_check(
            control, item["natives"], item["artifact"]
        )
        control = replace(control, metadata={
            **dict(control.metadata), "control_reproduction": reproduction,
        })
        controls[str(item["block"])] = control
    for item in prepared:
        generated = _generate_with_frozen_construction_v1(
            item["slate"], item["draws"], item["envs"]["treatment"],
            role_identities=item["role_identities"],
        )
        treatments[str(item["block"])] = science.inject_frozen_role12_v1(
            generated, native_rows=item["natives"], slate=item["slate"],
            artifact_totals=item["artifact"]["totals"],
        )
    sealed_runtime = _seal_runtime_wall_v1(
        runtime,
        wall_seconds=float(perf_counter() - generation_started),
    )
    return science.build_task_result_v1(
        snapshot=frozen,
        books_by_arm={"control": controls, "treatment": treatments},
        runtime_identity=sealed_runtime,
    )


def execute_task_v1(
    *, manifest_identity: object, environment: Mapping[str, str], store: object,
) -> dict[str, object]:
    manifest, retained_manifest_identity = _open_manifest(
        manifest_identity, store=store
    )
    runtime = _runtime_identity(
        manifest, manifest_identity=retained_manifest_identity,
        environment=environment, observed_command=_observed_command_v1(),
    )
    ordinal = int(runtime["source_ordinal"])
    binding = manifest["task_bindings"][ordinal]
    snapshot, snapshot_identity = _read_json(
        binding["snapshot_identity"], store=store, label="generation snapshot",
        maximum_bytes=MAXIMUM_SNAPSHOT_BYTES,
    )
    frozen = science.validate_generation_snapshot_v1(snapshot)
    if (
        snapshot_identity != binding["snapshot_identity"]
        or frozen["source_ordinal"] != ordinal
        or frozen["generation_snapshot_sha256"]
        != binding["generation_snapshot_sha256"]
        or frozen["later_source_identity"] != manifest["later_source_identity"]
    ):
        _fail("boom-first task snapshot binding differs")
    recovered = _recover_existing_task_v1(
        binding=binding, snapshot=frozen, manifest=manifest,
        manifest_identity=retained_manifest_identity,
        current_runtime=runtime, store=store,
    )
    if recovered is not None:
        result, result_identity = recovered
        return {
            "schema_version": "corpus-r6-boom-first-task-execution/v1",
            "manifest_identity": retained_manifest_identity,
            "source_ordinal": ordinal,
            "slate_id": result["slate_id"],
            "task_result_identity": result_identity,
            "task_result_sha256": result["task_result_sha256"],
            "same_input_create_once_recovery": True,
            "uses_realized_outcomes": False,
            "complete": True,
        }
    result = _run_score_blind_task_v1(
        frozen_snapshot=frozen, runtime_identity=runtime, store=store,
    )
    result_identity = _publish_json(
        uri=str(binding["result_uri"]), value=result,
        maximum_bytes=MAXIMUM_TASK_RESULT_BYTES, store=store,
    )
    return {
        "schema_version": "corpus-r6-boom-first-task-execution/v1",
        "manifest_identity": retained_manifest_identity,
        "source_ordinal": ordinal,
        "slate_id": result["slate_id"],
        "task_result_identity": result_identity,
        "task_result_sha256": result["task_result_sha256"],
        "same_input_create_once_recovery": False,
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _preflight_runtime_v1(*, code_commit: str) -> dict[str, object]:
    return _seal_runtime_wall_v1({
        "schema_version": science.RUNTIME_AUTHORITY_SCHEMA,
        "execution_mode": "preflight-smoke",
        "source_ordinal": 0,
        "task_count": science.TASK_COUNT,
        "task_attempt": 0,
        "execution_id": "preflight-smoke",
        "job_name": None,
        "reused_job_uid": None,
        "service_account": None,
        "project_id": FIXED_PROJECT,
        "region": "US",
        "manifest_identity": None,
        "manifest_sha256": None,
        "terminal_build_receipt_identity": None,
        "code_commit": code_commit,
        "image_digest": None,
        "immutable_image_uri": None,
        "task0_smoke_sha256": None,
        "observed_command": ["preflight-smoke"],
        "authority_source": (
            "score-blind-real-artifact-preflight-no-publication"
        ),
    }, wall_seconds=0.0)


def _manifest_smoke_runtime_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
) -> dict[str, object]:
    retained = validate_manifest_v1(manifest)
    identity = _identity(manifest_identity, label="manifest-smoke manifest")
    return _seal_runtime_wall_v1({
        "schema_version": science.RUNTIME_AUTHORITY_SCHEMA,
        "execution_mode": "manifest-smoke",
        "source_ordinal": 0,
        "task_count": science.TASK_COUNT,
        "task_attempt": 0,
        "execution_id": "manifest-smoke",
        "job_name": FIXED_REUSED_JOB_NAME,
        "reused_job_uid": FIXED_REUSED_JOB_UID,
        "service_account": FIXED_SERVICE_ACCOUNT,
        "project_id": FIXED_PROJECT,
        "region": FIXED_REGION,
        "manifest_identity": identity,
        "manifest_sha256": retained["manifest_sha256"],
        "terminal_build_receipt_identity": retained[
            "terminal_build_receipt_identity"
        ],
        "code_commit": retained["code_commit"],
        "image_digest": retained["image_digest"],
        "immutable_image_uri": retained["immutable_image_uri"],
        "task0_smoke_sha256": None,
        "observed_command": ["manifest-smoke"],
        "authority_source": (
            "manifest-bound-real-artifact-smoke-no-publication"
        ),
    }, wall_seconds=0.0)


def _smoke_receipt_from_result_v1(
    *, schema_version: str, execution_mode: str,
    result: Mapping[str, object], snapshot: Mapping[str, object],
    generation_snapshot_identity: Mapping[str, object] | None,
    manifest: Mapping[str, object] | None,
    manifest_identity: Mapping[str, object] | None,
    source_provenance: Mapping[str, object],
) -> dict[str, object]:
    retained = science.validate_task_result_v1(result)
    frozen = science.validate_generation_snapshot_v1(snapshot)
    runtime = science.validate_runtime_identity_v1(
        retained["runtime_identity"], expected_source_ordinal=0
    )
    if (
        retained["source_ordinal"] != 0
        or frozen["source_ordinal"] != 0
        or retained["generation_snapshot_sha256"]
        != frozen["generation_snapshot_sha256"]
        or retained["later_source_identity"] != frozen["later_source_identity"]
        or runtime["execution_mode"] != execution_mode
    ):
        _fail("boom-first smoke task binding differs")
    arm_science = _mapping(retained["arm_science"], label="smoke arm science")
    control_books = _sequence(
        _mapping(arm_science["control"], label="smoke control science")[
            "native_books"
        ],
        label="smoke control native books",
    )
    reproductions = [
        _mapping(row, label="smoke control book")["control_reproduction"]
        for row in control_books
    ]
    selected_counts = {
        str(_mapping(row, label="smoke selected book")["coordinate"]["arm"]):
        len(_sequence(
            _mapping(row, label="smoke selected book")["selected_lineup_ids"],
            label="smoke selected lineup IDs",
        ))
        for row in _sequence(
            retained["normalized_slate"]["books"], label="smoke selected books"
        )
    }
    if (
        len(reproductions) != len(science.BLOCK_ORDER)
        or selected_counts != {
            "control": science.ENTRY_BUDGET,
            "treatment": science.ENTRY_BUDGET,
        }
    ):
        _fail("boom-first smoke reproduction/book lattice differs")
    retained_manifest = validate_manifest_v1(manifest) if manifest is not None else None
    retained_manifest_identity = (
        _identity(manifest_identity, label="smoke manifest")
        if manifest_identity is not None else None
    )
    provenance = _validate_source_provenance_v1(
        source_provenance, execution_mode=execution_mode,
        code_commit=str(runtime["code_commit"]),
    )
    body = {
        "schema_version": schema_version,
        "execution_mode": execution_mode,
        "later_source_identity": frozen["later_source_identity"],
        "later_source_freeze_sha256": frozen["later_source_freeze_sha256"],
        "code_commit": runtime["code_commit"],
        "manifest_identity": retained_manifest_identity,
        "manifest_sha256": (
            retained_manifest["manifest_sha256"] if retained_manifest else None
        ),
        "terminal_build_receipt_identity": (
            retained_manifest["terminal_build_receipt_identity"]
            if retained_manifest else None
        ),
        "image_digest": retained_manifest["image_digest"] if retained_manifest else None,
        "immutable_image_uri": (
            retained_manifest["immutable_image_uri"] if retained_manifest else None
        ),
        "source_ordinal": 0,
        "slate_id": retained["slate_id"],
        "generation_snapshot_identity": generation_snapshot_identity,
        "generation_snapshot_sha256": frozen["generation_snapshot_sha256"],
        "query_receipts_sha256": _hash(frozen["query_receipts"]),
        "task_result_sha256": retained["task_result_sha256"],
        "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        "normalized_slate_sha256": retained["normalized_slate_sha256"],
        "source_provenance": provenance,
        "arm_science_sha256": _hash(arm_science),
        "control_reproductions_sha256": _hash(reproductions),
        "control_reproduction_count": len(reproductions),
        "all_five_control_books_reproduced": True,
        "selected_book_counts": selected_counts,
        "both_arms_exact_80": True,
        "publication_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }
    return _with_hash(body, field="smoke_sha256")


def preflight_smoke_from_request_v1(
    request: object, *, store: object, bq_client: object, provider: object,
) -> dict[str, object]:
    """Run the full task-0 path on live score-blind inputs before build freeze."""

    item = _mapping(request, label="boom-first preflight smoke request")
    if set(item) != {"later_source_identity", "code_commit"}:
        _fail("boom-first preflight smoke request fields differ")
    code_commit = str(item["code_commit"])
    observed_source_commit = provider.current_source_commit()
    if (
        _COMMIT.fullmatch(code_commit) is None
        or observed_source_commit != code_commit
    ):
        _fail("boom-first preflight smoke code commit differs")
    source_provenance = _build_source_provenance_v1(
        execution_mode="preflight-smoke",
        observed_source_commit=str(observed_source_commit),
        embedded_build_source_commit=None,
    )
    source, source_identity = _read_json(
        item["later_source_identity"], store=store,
        label="preflight later source freeze",
        maximum_bytes=MAXIMUM_LATER_SOURCE_BYTES,
    )
    try:
        frozen = later_source.validate_source_freeze(
            source, expected_freeze_sha256=str(source["freeze_sha256"])
        )
    except later_source.LR8LaterSourceError as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    namespace = sha256(
        _canonical({"source": source_identity, "code": code_commit})
    ).hexdigest()[:20]
    player_frame, player_receipt = _run_score_blind_query(
        bq_client, PLAYER_SQL, job_id=f"boom_first_preflight_{namespace}_players"
    )
    candidate_frame, candidate_receipt = _run_score_blind_query(
        bq_client, CANDIDATE_SQL,
        job_id=f"boom_first_preflight_{namespace}_candidates",
    )
    query_receipts = {
        "player_generation_snapshot": player_receipt,
        "candidate_generation_snapshot": candidate_receipt,
        "queried_at_preflight": True,
        "postlock_columns_selected": [],
    }
    snapshot = _build_snapshot_from_frames_v1(
        source_ordinal=0, frozen_source=frozen, source_identity=source_identity,
        player_frame=player_frame, candidate_frame=candidate_frame,
        query_receipts=query_receipts,
    )
    result = _run_score_blind_task_v1(
        frozen_snapshot=snapshot,
        runtime_identity=_preflight_runtime_v1(code_commit=code_commit),
        store=store,
    )
    receipt = _smoke_receipt_from_result_v1(
        schema_version=PREFLIGHT_SMOKE_SCHEMA,
        execution_mode="preflight-smoke", result=result, snapshot=snapshot,
        generation_snapshot_identity=None, manifest=None,
        manifest_identity=None,
        source_provenance=source_provenance,
    )
    return _validate_preflight_smoke_receipt_v1(
        receipt, later_source_identity=source_identity,
        later_source_freeze_sha256=str(frozen["freeze_sha256"]),
        code_commit=code_commit,
    )


def smoke_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    """Run the exact manifest task-0 input in memory without publication."""

    item = _mapping(request, label="boom-first manifest smoke request")
    if set(item) != {"manifest_identity"}:
        _fail("boom-first manifest smoke request fields differ")
    manifest, manifest_identity = _open_manifest(
        item["manifest_identity"], store=store
    )
    embedded_source_commit = os.environ.get(BUILD_SOURCE_COMMIT_ENV, "")
    if embedded_source_commit != manifest["code_commit"]:
        _fail("boom-first manifest smoke embedded source commit differs")
    source_provenance = _build_source_provenance_v1(
        execution_mode="manifest-smoke",
        observed_source_commit=embedded_source_commit,
        embedded_build_source_commit=embedded_source_commit,
    )
    binding = _mapping(manifest["task_bindings"][0], label="smoke task binding")
    snapshot, snapshot_identity = _read_json(
        binding["snapshot_identity"], store=store,
        label="smoke generation snapshot", maximum_bytes=MAXIMUM_SNAPSHOT_BYTES,
    )
    frozen = science.validate_generation_snapshot_v1(snapshot)
    if (
        snapshot_identity != binding["snapshot_identity"]
        or frozen["source_ordinal"] != 0
        or frozen["generation_snapshot_sha256"]
        != binding["generation_snapshot_sha256"]
        or frozen["later_source_identity"] != manifest["later_source_identity"]
    ):
        _fail("boom-first manifest smoke snapshot binding differs")
    result = _run_score_blind_task_v1(
        frozen_snapshot=frozen,
        runtime_identity=_manifest_smoke_runtime_v1(
            manifest=manifest, manifest_identity=manifest_identity
        ),
        store=store,
    )
    receipt = _smoke_receipt_from_result_v1(
        schema_version=MANIFEST_SMOKE_SCHEMA,
        execution_mode="manifest-smoke", result=result, snapshot=frozen,
        generation_snapshot_identity=snapshot_identity, manifest=manifest,
        manifest_identity=manifest_identity,
        source_provenance=source_provenance,
    )
    return _validate_manifest_smoke_receipt_v1(
        receipt, manifest=manifest, manifest_identity=manifest_identity
    )


def _open_known_json(
    uri: str, *, store: object, label: str, maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, raw_identity = store.open_known(uri, maximum_bytes)
    identity = _identity(raw_identity, label=f"{label} identity")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} known-object identity differs")
    return _strict_json(raw, label=label, maximum_bytes=maximum_bytes), identity


def _open_bound_task_result_v1(
    *, manifest: Mapping[str, object], manifest_identity: Mapping[str, object],
    ordinal: int, execution_id: str, task0_smoke_sha256: str, store: object,
) -> tuple[dict[str, object], dict[str, object]]:
    binding = _mapping(
        manifest["task_bindings"][ordinal], label=f"task binding[{ordinal}]"
    )
    snapshot, snapshot_identity = _read_json(
        binding["snapshot_identity"], store=store,
        label=f"generation snapshot[{ordinal}]",
        maximum_bytes=MAXIMUM_SNAPSHOT_BYTES,
    )
    if snapshot_identity != binding["snapshot_identity"]:
        _fail("boom-first task snapshot exact identity differs")
    result, identity = _open_known_json(
        str(binding["result_uri"]), store=store,
        label=f"task result[{ordinal}]", maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
    )
    retained = _validate_task_against_manifest_v1(
        result=result, result_identity=identity, manifest=manifest,
        manifest_identity=manifest_identity, snapshot=snapshot, ordinal=ordinal,
        expected_execution_id=execution_id,
        expected_task0_smoke_sha256=task0_smoke_sha256,
    )
    return retained, identity


def collect_from_request_v1(
    request: object, *, store: object, provider: object,
) -> dict[str, object]:
    item = _mapping(request, label="boom-first collect request")
    if set(item) != {
        "manifest_identity", "launch_receipt_identity", "smoke_receipt",
    }:
        _fail("boom-first collect request fields differ")
    manifest, manifest_identity = _open_manifest(item["manifest_identity"], store=store)
    smoke = _validate_manifest_smoke_receipt_v1(
        item["smoke_receipt"], manifest=manifest,
        manifest_identity=manifest_identity,
    )
    provider_terminal = status_existing_execution_v1(
        manifest_identity=manifest_identity,
        launch_receipt_identity=item["launch_receipt_identity"],
        smoke_receipt=smoke,
        store=store, provider=provider,
    )
    results: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    for ordinal in range(science.TASK_COUNT):
        retained, identity = _open_bound_task_result_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            ordinal=ordinal, execution_id=str(provider_terminal["execution_id"]),
            task0_smoke_sha256=str(smoke["smoke_sha256"]), store=store,
        )
        results.append(retained)
        identities.append(identity)
    terminal = science.build_terminal_v1(
        task_results=results, task_result_identities=identities,
        manifest_identity=manifest_identity,
        manifest_sha256=str(manifest["manifest_sha256"]),
        provider_terminal_execution=provider_terminal,
    )
    terminal_identity = _publish_json(
        uri=str(manifest["terminal_uri"]), value=terminal,
        maximum_bytes=MAXIMUM_TERMINAL_BYTES, store=store,
    )
    return {
        "schema_version": COLLECT_RESULT_SCHEMA,
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "manifest_identity": manifest_identity,
        "execution_id": provider_terminal["execution_id"],
        "launch_receipt_identity": provider_terminal[
            "launch_receipt_identity"
        ],
        "provider_terminal_execution_sha256": provider_terminal[
            "provider_terminal_execution_sha256"
        ],
        "task0_smoke_sha256": smoke["smoke_sha256"],
        "source_slate_count": science.TASK_COUNT,
        "all_task_results_exact_opened_before_terminal": True,
        "provider_exact_54_of_54_terminal_validated_before_terminal": True,
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _reopen_terminal_and_tasks(identity_value: object, *, store: object):
    terminal, terminal_identity = _read_json(
        identity_value, store=store, label="boom-first terminal",
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
    )
    retained = science.validate_terminal_v1(terminal)
    manifest, manifest_identity = _open_manifest(
        retained["manifest_identity"], store=store
    )
    provider_terminal = science.validate_provider_terminal_execution_v1(
        retained["provider_terminal_execution"]
    )
    launch_receipt, launch_receipt_identity, launch_claim = (
        _open_launch_receipt_v1(
            provider_terminal["launch_receipt_identity"], manifest=manifest,
            manifest_identity=manifest_identity, store=store,
            task0_smoke_sha256=str(retained["task0_smoke_sha256"]),
        )
    )
    if (
        terminal_identity["uri"] != manifest["terminal_uri"]
        or manifest_identity != retained["manifest_identity"]
        or manifest["manifest_sha256"] != retained["manifest_sha256"]
        or provider_terminal["manifest_identity"] != manifest_identity
        or provider_terminal["manifest_sha256"] != manifest["manifest_sha256"]
        or provider_terminal["execution_id"] != retained["execution_id"]
        or provider_terminal["job_name"] != FIXED_REUSED_JOB_NAME
        or provider_terminal["job_uid"] != FIXED_REUSED_JOB_UID
        or provider_terminal["service_account"] != FIXED_SERVICE_ACCOUNT
        or provider_terminal["project_id"] != FIXED_PROJECT
        or provider_terminal["region"] != FIXED_REGION
        or launch_receipt_identity
        != provider_terminal["launch_receipt_identity"]
        or launch_receipt["launch_receipt_sha256"]
        != provider_terminal["launch_receipt_sha256"]
        or launch_receipt["launch_claim_identity"]
        != provider_terminal["launch_claim_identity"]
        or launch_claim["launch_claim_sha256"]
        != launch_receipt["launch_claim_sha256"]
        or launch_receipt["execution_id"] != retained["execution_id"]
    ):
        _fail("boom-first terminal manifest/provider binding differs")
    _validate_provider_job_observation_from_smoke_sha_v1(
        provider_terminal["job_observation"], manifest=manifest,
        manifest_identity=manifest_identity,
        task0_smoke_sha256=str(retained["task0_smoke_sha256"]),
    )
    results: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    for ordinal, descriptor in enumerate(retained["task_results"]):
        result, identity = _open_bound_task_result_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            ordinal=ordinal, execution_id=str(retained["execution_id"]),
            task0_smoke_sha256=str(retained["task0_smoke_sha256"]), store=store,
        )
        if (
            identity != descriptor["task_result_identity"]
            or result["task_result_sha256"] != descriptor["task_result_sha256"]
            or result["generation_snapshot_sha256"]
            != descriptor["generation_snapshot_sha256"]
            or result["runtime_identity"]["runtime_authority_sha256"]
            != descriptor["runtime_authority_sha256"]
            or result["source_ordinal"] != ordinal
        ):
            _fail("boom-first terminal task exact replay differs")
        results.append(result)
        identities.append(identity)
    rebuilt = science.build_terminal_v1(
        task_results=results, task_result_identities=identities,
        manifest_identity=manifest_identity,
        manifest_sha256=str(manifest["manifest_sha256"]),
        provider_terminal_execution=provider_terminal,
    )
    if _canonical(rebuilt) != _canonical(retained):
        _fail("boom-first terminal canonical task replay differs")
    return retained, terminal_identity, manifest


def _paired_allocation_summary_v1(
    slate_grades: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if len(slate_grades) != science.TASK_COUNT:
        _fail("paired allocation summary requires exact 54 slate grades")
    weekly: list[dict[str, object]] = []
    for ordinal, raw in enumerate(slate_grades):
        slate = _mapping(raw, label=f"paired slate grade[{ordinal}]")
        by_arm: dict[str, Mapping[str, object]] = {}
        for raw_metric in _sequence(slate.get("metrics"), label="paired metrics"):
            metric = _mapping(raw_metric, label="paired metric")
            coordinate = _mapping(metric.get("coordinate"), label="paired coordinate")
            arm = coordinate.get("arm")
            if coordinate.get("adapter_id") == science.ADAPTER_ID and arm in (
                "control", "treatment"
            ):
                if str(arm) in by_arm:
                    _fail("paired slate grade repeats an allocation arm")
                by_arm[str(arm)] = metric
        if set(by_arm) != {"control", "treatment"}:
            _fail("paired slate grade lacks one allocation arm")
        control = int(by_arm["control"]["selected_weekly_maximum_micro"])
        treatment = int(by_arm["treatment"]["selected_weekly_maximum_micro"])
        season, week = science.SLATE_KEYS[ordinal]
        weekly.append({
            "source_ordinal": ordinal,
            "season": season,
            "week": week,
            "slate_id": science.expected_slate_id_v1(ordinal),
            "control_weekly_maximum_micro": control,
            "treatment_weekly_maximum_micro": treatment,
            "paired_delta_micro": treatment - control,
            "control_population_ceiling_micro": int(
                by_arm["control"]["population_ceiling_micro"]
            ),
            "treatment_population_ceiling_micro": int(
                by_arm["treatment"]["population_ceiling_micro"]
            ),
            "control_selector_regret_micro": int(
                by_arm["control"]["population_ceiling_regret_micro"]
            ),
            "treatment_selector_regret_micro": int(
                by_arm["treatment"]["population_ceiling_regret_micro"]
            ),
            "thresholds": {
                arm: [{
                    "threshold_dk": row["threshold_dk"],
                    "selected_produced_at_least_one_hit": row[
                        "selected_produced_at_least_one_hit"
                    ],
                    "population_produced_at_least_one_hit": row[
                        "population_produced_at_least_one_hit"
                    ],
                } for row in by_arm[arm]["thresholds"]]
                for arm in ("control", "treatment")
            },
        })

    def aggregate(label: str, rows: Sequence[Mapping[str, object]]):
        if not rows:
            _fail("paired summary aggregate is empty")
        count = len(rows)
        control_sum = sum(int(row["control_weekly_maximum_micro"]) for row in rows)
        treatment_sum = sum(
            int(row["treatment_weekly_maximum_micro"]) for row in rows
        )
        threshold_values = [
            int(row["threshold_dk"]) for row in rows[0]["thresholds"]["control"]
        ]
        thresholds = []
        for index, threshold in enumerate(threshold_values):
            thresholds.append({
                "threshold_dk": threshold,
                "control_selected_slates_with_hit": sum(
                    bool(row["thresholds"]["control"][index][
                        "selected_produced_at_least_one_hit"
                    ]) for row in rows
                ),
                "treatment_selected_slates_with_hit": sum(
                    bool(row["thresholds"]["treatment"][index][
                        "selected_produced_at_least_one_hit"
                    ]) for row in rows
                ),
                "control_population_slates_with_hit": sum(
                    bool(row["thresholds"]["control"][index][
                        "population_produced_at_least_one_hit"
                    ]) for row in rows
                ),
                "treatment_population_slates_with_hit": sum(
                    bool(row["thresholds"]["treatment"][index][
                        "population_produced_at_least_one_hit"
                    ]) for row in rows
                ),
            })
        return {
            "label": label,
            "slate_count": count,
            "control_mean_weekly_maximum_micro": {
                "numerator": control_sum, "denominator": count,
            },
            "treatment_mean_weekly_maximum_micro": {
                "numerator": treatment_sum, "denominator": count,
            },
            "paired_mean_delta_micro": {
                "numerator": treatment_sum - control_sum,
                "denominator": count,
            },
            "treatment_win_count": sum(
                int(row["paired_delta_micro"] > 0) for row in rows
            ),
            "tie_count": sum(int(row["paired_delta_micro"] == 0) for row in rows),
            "control_win_count": sum(
                int(row["paired_delta_micro"] < 0) for row in rows
            ),
            "control_mean_population_ceiling_regret_micro": {
                "numerator": sum(
                    int(row["control_selector_regret_micro"]) for row in rows
                ),
                "denominator": count,
            },
            "treatment_mean_population_ceiling_regret_micro": {
                "numerator": sum(
                    int(row["treatment_selector_regret_micro"]) for row in rows
                ),
                "denominator": count,
            },
            "thresholds": thresholds,
        }

    aggregates = [aggregate("all-54", weekly)]
    for season in (2023, 2024, 2025):
        aggregates.append(aggregate(
            str(season), [row for row in weekly if row["season"] == season]
        ))
    body = {
        "weekly_rows": weekly,
        "weekly_rows_sha256": _hash(weekly),
        "aggregates": aggregates,
        "aggregates_sha256": _hash(aggregates),
        "primary_coordinate": {
            "model_ensemble": 1,
            "entry_budget": science.ENTRY_BUDGET,
            "tail_line": science.TAIL_LINE,
        },
        "season_2025_already_informed_descriptive_only": True,
    }
    return _with_hash(body, field="paired_summary_sha256")


def _strict_lease_json_v1(raw: bytes) -> dict[str, object]:
    if (
        type(raw) is not bytes
        or not raw.endswith(b"\n")
        or raw.endswith(b"\n\n")
        or len(raw) > MAXIMUM_OUTCOME_LEASE_BYTES
    ):
        _fail("historical-outcome lease bytes differ")
    body_raw = raw[:-1]
    if not body_raw:
        _fail("historical-outcome lease is empty")
    try:
        value = json.loads(body_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(
            "historical-outcome lease is not UTF-8 JSON"
        ) from exc
    body = _mapping(value, label="historical-outcome lease")
    if _canonical(body) != body_raw:
        _fail("historical-outcome lease is not canonical JSON plus newline")
    return body


def _open_live_outcome_lease_v1(
    *, expected_identity: object, catalog_run_id: str, store: object,
) -> tuple[dict[str, object], dict[str, object]]:
    expected = _identity(expected_identity, label="historical-outcome lease")
    if expected["uri"] != HISTORICAL_OUTCOME_LEASE_URI:
        _fail("historical-outcome lease URI differs")
    raw, observed_value = store.open_known(
        HISTORICAL_OUTCOME_LEASE_URI, MAXIMUM_OUTCOME_LEASE_BYTES
    )
    observed = _identity(observed_value, label="live historical-outcome lease")
    if (
        observed != expected
        or len(raw) != observed["bytes"]
        or sha256(raw).hexdigest() != observed["sha256"]
    ):
        _fail("historical-outcome lease is not the requested live generation")
    body = _strict_lease_json_v1(raw)
    if set(body) != {
        "version", "run_id", "job", "code_sha", "image", "acquired_at",
    }:
        _fail("historical-outcome lease body fields differ")
    try:
        acquired_at = datetime.fromisoformat(str(body.get("acquired_at")))
    except ValueError as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(
            "historical-outcome lease timestamp differs"
        ) from exc
    if (
        body.get("version") != "historical-outcome-active-v1"
        or body.get("run_id") != catalog_run_id
        or type(body.get("job")) is not str
        or not body["job"]
        or _COMMIT.fullmatch(str(body.get("code_sha"))) is None
        or type(body.get("image")) is not str
        or not body["image"]
        or acquired_at.tzinfo is None
        or acquired_at.utcoffset() is None
    ):
        _fail("historical-outcome lease body authority differs")
    return body, observed


def _open_catalog_outcome_completion_v1(
    *, completion_identity: object, outcome_snapshot_identity: object,
    historical_outcome_lease_identity: object, store: object,
) -> tuple[dict[str, object], dict[str, object]]:
    completion, identity = _read_json(
        completion_identity, store=store, label="catalog outcome completion",
        maximum_bytes=MAXIMUM_CATALOG_COMPLETION_BYTES,
    )
    expected_fields = {
        "schema_version", "run_id", "outcome_key_projection_identity",
        "registered_request_identity", "query_evidence_identity",
        "realized_source_identity", "outcome_snapshot_identity",
        "historical_outcome_lease_identity", "source_snapshot_at",
        "source_slate_count", "outcome_key_count", "delta_query_key_count",
        "one_historical_outcome_read", "one_exact_query_job",
        "historical_outcome_lease_release_required", "lease_release_owner",
        "lineup_scoring_performed", "graph_mutation_licensed",
        "production_change_licensed", "decision_authority", "complete",
        "completion_sha256",
    }
    body = {
        key: child for key, child in completion.items()
        if key != "completion_sha256"
    }
    run_id = completion.get("run_id")
    expected_uri = f"{CATALOG_OUTCOME_ROOT}/{run_id}/completion.json"
    snapshot_identity = _identity(
        outcome_snapshot_identity, label="requested catalog outcome snapshot"
    )
    lease_identity = _identity(
        historical_outcome_lease_identity,
        label="requested catalog historical-outcome lease",
    )
    if (
        set(completion) != expected_fields
        or completion.get("schema_version") != CATALOG_OUTCOME_COMPLETION_SCHEMA
        or type(run_id) is not str
        or re.fullmatch(r"[a-z0-9][a-z0-9-]{2,100}", run_id) is None
        or identity["uri"] != expected_uri
        or completion.get("completion_sha256") != _hash(body)
        or completion.get("source_slate_count") != science.TASK_COUNT
        or completion.get("outcome_key_count") != 29_605
        or completion.get("delta_query_key_count") != 15_358
        or completion.get("outcome_snapshot_identity") != snapshot_identity
        or completion.get("historical_outcome_lease_identity") != lease_identity
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("one_exact_query_job") is not True
        or completion.get("historical_outcome_lease_release_required") is not True
        or completion.get("lease_release_owner") != "external-launcher-watcher"
        or any(completion.get(field) is not False for field in (
            "lineup_scoring_performed", "graph_mutation_licensed",
            "production_change_licensed", "decision_authority",
        ))
        or completion.get("complete") is not True
    ):
        _fail("catalog outcome completion authority differs")
    for field in (
        "outcome_key_projection_identity", "registered_request_identity",
        "query_evidence_identity", "realized_source_identity",
        "outcome_snapshot_identity", "historical_outcome_lease_identity",
    ):
        _identity(completion.get(field), label=f"catalog completion {field}")
    return completion, identity


def grade_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="boom-first grade request")
    if set(item) != {
        "terminal_identity", "outcome_snapshot_identity",
        "catalog_outcome_completion_identity",
        "historical_outcome_lease_identity",
    }:
        _fail("boom-first grade request fields differ")
    terminal, terminal_identity, manifest = _reopen_terminal_and_tasks(
        item["terminal_identity"], store=store
    )
    catalog_completion, catalog_completion_identity = (
        _open_catalog_outcome_completion_v1(
            completion_identity=item["catalog_outcome_completion_identity"],
            outcome_snapshot_identity=item["outcome_snapshot_identity"],
            historical_outcome_lease_identity=item[
                "historical_outcome_lease_identity"
            ],
            store=store,
        )
    )
    lease_body_before, lease_identity_before = _open_live_outcome_lease_v1(
        expected_identity=catalog_completion["historical_outcome_lease_identity"],
        catalog_run_id=str(catalog_completion["run_id"]), store=store,
    )
    try:
        _snapshot, outcome_identity, player_scores, slate_keys = (
            grader.open_outcome_snapshot_surface_v1(
                outcome_snapshot_identity=item["outcome_snapshot_identity"],
                read_outcome_exact=store.read_exact,
            )
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    normalized = terminal["normalized_slates"]
    if (
        outcome_identity != catalog_completion["outcome_snapshot_identity"]
        or terminal["later_source_identity"]
        != _snapshot["later_source_freeze_identity"]
        or len(slate_keys) != science.TASK_COUNT
        or any(
            slate_keys[ordinal][2] != normalized[ordinal]["slate_id"]
            for ordinal in range(science.TASK_COUNT)
        )
    ):
        _fail("boom-first terminal/outcome source or slate binding differs")
    try:
        slate_grades = grader.score_normalized_slates_v1(
            slates=normalized, player_scores=player_scores
        )
        aggregates = grader.aggregate_normalized_slate_grades_v1(slate_grades)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    paired_summary = _paired_allocation_summary_v1(slate_grades)
    lease_body_after, lease_identity_after = _open_live_outcome_lease_v1(
        expected_identity=lease_identity_before,
        catalog_run_id=str(catalog_completion["run_id"]), store=store,
    )
    if (
        lease_identity_after != lease_identity_before
        or _canonical(lease_body_after) != _canonical(lease_body_before)
    ):
        _fail("historical-outcome lease changed during boom-first grade")
    grade = _with_hash({
        "schema_version": science.GRADE_SCHEMA,
        "adapter_id": science.ADAPTER_ID,
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "outcome_snapshot_identity": outcome_identity,
        "outcome_snapshot_sha256": _snapshot["outcome_snapshot_sha256"],
        "catalog_outcome_completion_identity": catalog_completion_identity,
        "catalog_outcome_completion_sha256": catalog_completion[
            "completion_sha256"
        ],
        "later_source_identity": terminal["later_source_identity"],
        "historical_outcome_lease_identity": lease_identity_before,
        "historical_outcome_lease_body_sha256": _hash(lease_body_before),
        "historical_outcome_lease_unchanged_during_grade": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "source_slate_count": science.TASK_COUNT,
        "slate_grades": slate_grades,
        "slate_grades_sha256": _hash(slate_grades),
        "aggregate_results": aggregates,
        "aggregate_results_sha256": _hash(aggregates),
        "paired_allocation_summary": paired_summary,
        "score_free_terminal_and_all_tasks_validated_before_outcome_open": True,
        "uses_realized_outcomes": True,
        "additional_historical_outcome_read": False,
        "retry_authority": False,
        "retune_authority": False,
        "graph_mutation_authority": False,
        "season_2025_already_informed_descriptive_only": True,
        "automatic_promotion": False,
        "production_change_licensed": False,
        "complete": True,
    }, field="grade_sha256")
    grade_identity = _publish_json(
        uri=str(manifest["grade_uri"]), value=grade,
        maximum_bytes=MAXIMUM_GRADE_BYTES, store=store,
    )
    return {
        "schema_version": GRADE_RESULT_SCHEMA,
        "grade_identity": grade_identity,
        "grade_sha256": grade["grade_sha256"],
        "historical_outcome_lease_identity": lease_identity_before,
        "catalog_outcome_completion_identity": catalog_completion_identity,
        "catalog_outcome_completion_sha256": catalog_completion[
            "completion_sha256"
        ],
        "historical_outcome_lease_body_sha256": _hash(lease_body_before),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "uses_realized_outcomes": True,
        "source_slate_count": science.TASK_COUNT,
        "complete": True,
    }


def _load_request(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail(f"{label} must be one existing absolute file")
    return _strict_json(path.read_bytes(), label=label, maximum_bytes=MAXIMUM_REQUEST_BYTES)


def _manifest_identity_from_environment() -> dict[str, object]:
    raw = os.environ.get(MANIFEST_IDENTITY_ENV, "")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunCorpusR6BoomFirstAllocationV1Error(
            "boom-first manifest identity environment is not JSON"
        ) from exc
    identity = _identity(parsed, label="runtime manifest")
    if raw.encode("utf-8") != _canonical(identity):
        _fail("runtime manifest identity environment is not canonical JSON")
    return identity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "preflight-smoke", "prepare", "smoke", "configure", "launch",
        "status", "collect", "grade", "validate",
    ):
        child = commands.add_parser(name)
        child.add_argument("--request", type=Path, required=True)
        child.add_argument("--execute", action="store_true")
    task = commands.add_parser("task")
    task.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute:
        _fail("boom-first execution requires --execute")
    if args.command == "grade":
        if os.environ.get(GRADE_ENABLE_ENV) != GRADE_ENABLE_VALUE:
            _fail(f"grade requires {GRADE_ENABLE_ENV}={GRADE_ENABLE_VALUE}")
    elif os.environ.get(SELECTION_ENABLE_ENV) != SELECTION_ENABLE_VALUE:
        _fail(f"selection requires {SELECTION_ENABLE_ENV}={SELECTION_ENABLE_VALUE}")
    store = GCSExactTransportV1()
    provider = GCloudRunProviderV1()
    if args.command == "preflight-smoke":
        from google.cloud import bigquery

        result = preflight_smoke_from_request_v1(
            _load_request(args.request, label="preflight smoke request"),
            store=store, bq_client=bigquery.Client(project=FIXED_PROJECT),
            provider=provider,
        )
    elif args.command == "prepare":
        from google.cloud import bigquery

        result = prepare_from_request_v1(
            _load_request(args.request, label="prepare request"), store=store,
            bq_client=bigquery.Client(project=FIXED_PROJECT),
            provider=provider,
        )
    elif args.command == "task":
        result = execute_task_v1(
            manifest_identity=_manifest_identity_from_environment(),
            environment=os.environ, store=store,
        )
    elif args.command == "smoke":
        result = smoke_from_request_v1(
            _load_request(args.request, label="manifest smoke request"),
            store=store,
        )
    elif args.command == "configure":
        request = _load_request(args.request, label="configure request")
        if set(request) != {"manifest_identity", "smoke_receipt"}:
            _fail("configure request fields differ")
        result = configure_existing_job_v1(
            manifest_identity=request["manifest_identity"],
            smoke_receipt=request["smoke_receipt"], store=store,
            provider=provider,
        )
    elif args.command == "launch":
        request = _load_request(args.request, label="launch request")
        if set(request) != {"manifest_identity", "smoke_receipt"}:
            _fail("launch request fields differ")
        result = launch_existing_job_v1(
            manifest_identity=request["manifest_identity"],
            smoke_receipt=request["smoke_receipt"], store=store,
            provider=provider,
        )
    elif args.command == "status":
        request = _load_request(args.request, label="status request")
        if set(request) != {
            "manifest_identity", "launch_receipt_identity", "smoke_receipt",
        }:
            _fail("status request fields differ")
        result = status_existing_execution_v1(
            manifest_identity=request["manifest_identity"],
            launch_receipt_identity=request["launch_receipt_identity"],
            smoke_receipt=request["smoke_receipt"], store=store,
            provider=provider,
        )
    elif args.command == "collect":
        result = collect_from_request_v1(
            _load_request(args.request, label="collect request"), store=store,
            provider=provider,
        )
    elif args.command == "grade":
        result = grade_from_request_v1(
            _load_request(args.request, label="grade request"), store=store
        )
    elif args.command == "validate":
        request = _load_request(args.request, label="validate request")
        if set(request) == {"manifest_identity"}:
            value, identity = _open_manifest(request["manifest_identity"], store=store)
            result = {"kind": "manifest", "identity": identity,
                      "sha256": value["manifest_sha256"], "valid": True}
        elif set(request) == {"terminal_identity"}:
            value, identity, _manifest = _reopen_terminal_and_tasks(
                request["terminal_identity"], store=store
            )
            result = {"kind": "terminal", "identity": identity,
                      "sha256": value["terminal_sha256"], "valid": True}
        else:
            _fail("validate request fields differ")
    else:  # pragma: no cover
        _fail("unknown boom-first command")
    sys.stdout.buffer.write(_canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6BoomFirstAllocationV1Error,
        science.CorpusR6BoomFirstAllocationV1Error,
        grader.CorpusR6NovelRosterRealizedGraderV1Error,
        later_source.LR8LaterSourceError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
