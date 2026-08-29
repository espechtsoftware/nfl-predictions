#!/usr/bin/env python3
"""Run, collect, and grade the fixed 54-slate combined-population test.

``prepare``, ``task``, and ``collect`` are outcome-blind.  ``grade`` first
exact-reopens the create-last terminal, its manifest, and all 54 task results;
only after that replay succeeds may it open the already-published catalog-wide
outcome snapshot.  The operator never generates a population and never runs a
warehouse query.
"""

from __future__ import annotations

from collections.abc import Mapping
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
for _import_path in (ROOT, ROOT / "src"):
    if str(_import_path) not in sys.path:
        sys.path.insert(0, str(_import_path))

from nfl_dfs.research import (
    corpus_r6_combined_population_all_block_execution_v1 as execution,
)
from nfl_dfs.research import (
    corpus_r6_combined_population_all_block_v1 as combined,
)
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as full_freeze
from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as hard_bridge
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as l2b_panel
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader
from nfl_dfs.research import corpus_r6_population_crossed_cloud_v1 as crossed
try:
    from scripts import run_corpus_r6_hard230_selector_bridge_v1 as hard_operator
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    import run_corpus_r6_hard230_selector_bridge_v1 as hard_operator


ENABLE_ENV = "R6_COMBINED_POPULATION_ALL_BLOCK_ENABLE"
ENABLE_VALUE = "I_UNDERSTAND_HISTORICAL_FINALIST_CONFIRMATION_V1"
MANIFEST_IDENTITY_ENV = "R6_COMBINED_POPULATION_ALL_BLOCK_MANIFEST_IDENTITY"
TASK_INDEX_ENV = "CLOUD_RUN_TASK_INDEX"
TASK_COUNT_ENV = "CLOUD_RUN_TASK_COUNT"
MAXIMUM_REQUEST_BYTES = 256_000
MAXIMUM_MANIFEST_BYTES = 16_000_000
MAXIMUM_PROFILE_RESULT_BYTES = crossed.MAXIMUM_SLATE_RESULT_BYTES
MAXIMUM_HARD_TERMINAL_BYTES = hard_operator.MAXIMUM_TERMINAL_BYTES
MAXIMUM_SOURCE_MEMBER_BYTES = 2_000_000
MAXIMUM_TASK_RESULT_BYTES = 256_000_000
MAXIMUM_TERMINAL_BYTES = 512_000
MAXIMUM_GRADE_BYTES = 160_000_000


class RunCorpusR6CombinedPopulationAllBlockV1Error(RuntimeError):
    """The bounded combined-population operator failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6CombinedPopulationAllBlockV1Error(message)


class GCloudRunProviderV1:
    """Small guarded provider adapter; it can update only the fixed reused UID."""

    def _json(self, argv: list[str]) -> dict[str, object]:
        completed = subprocess.run(argv, check=True, capture_output=True)
        return _mapping(json.loads(completed.stdout), label="gcloud provider response")

    def current_source_commit(self) -> str:
        if subprocess.run(
            ["git", "status", "--porcelain"], check=True, capture_output=True
        ).stdout:
            _fail("combined build authority requires a clean committed source tree")
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()

    def resolve_image_digest(self, image_tag: str) -> str:
        value = self._json([
            "gcloud", "artifacts", "docker", "images", "describe", image_tag,
            "--project", execution.FIXED_GCP_PROJECT, "--format=json",
        ])
        digest = value.get("image_summary", {}).get("digest")
        return str(digest)

    def describe_build(self, build_id: str) -> dict[str, object]:
        return self._json([
            "gcloud", "builds", "describe", build_id,
            "--project", execution.FIXED_GCP_PROJECT, "--format=json",
        ])

    def _describe_job_raw(self, job_name: str) -> dict[str, object]:
        if job_name != execution.FIXED_REUSED_JOB_NAME:
            _fail("combined provider refuses non-fixed job")
        return self._json([
            "gcloud", "run", "jobs", "describe", job_name, "--project",
            execution.FIXED_GCP_PROJECT, "--region", execution.FIXED_REGION,
            "--format=json",
        ])

    def describe_job_identity(self, job_name: str) -> dict[str, object]:
        """Read only stable metadata so a legacy config can be replaced safely."""
        raw = self._describe_job_raw(job_name)
        metadata = _mapping(raw.get("metadata", {}), label="job identity metadata")
        identity = {
            "job_name": metadata.get("name"), "job_uid": metadata.get("uid"),
            "project_id": execution.FIXED_GCP_PROJECT,
            "region": execution.FIXED_REGION, "provider_observed": True,
        }
        if (
            identity["job_name"] != execution.FIXED_REUSED_JOB_NAME
            or identity["job_uid"] != execution.FIXED_REUSED_JOB_UID
        ):
            _fail("combined provider reused-job metadata identity differs")
        return identity

    def describe_job(self, job_name: str) -> dict[str, object]:
        raw = self._describe_job_raw(job_name)
        metadata = raw.get("metadata", {})
        template = raw.get("spec", {}).get("template", {}).get("spec", {}).get("template", {}).get("spec", {})
        container = (template.get("containers") or [{}])[0]
        env = {row["name"]: row.get("value", "") for row in container.get("env", [])}
        authority_sha = env.pop(execution.JOB_AUTHORITY_SHA_ENV, "")
        observation = {
            "job_name": metadata.get("name"), "job_uid": metadata.get("uid"),
            "project_id": execution.FIXED_GCP_PROJECT, "region": execution.FIXED_REGION,
            "image_digest": str(container.get("image", "")).split("@")[-1],
            "immutable_image_uri": container.get("image"),
            "source_commit": env.get("CODE_SHA"),
            "container_command": container.get("command", []),
            "container_args": container.get("args", []),
            "container_environment": env,
            "task_count": raw.get("spec", {}).get("template", {}).get("spec", {}).get("taskCount"),
            "parallelism": raw.get("spec", {}).get("template", {}).get("spec", {}).get("parallelism"),
            "max_retries": template.get("maxRetries"),
            "timeout_seconds": int(str(template.get("timeoutSeconds", "0s")).rstrip("s")),
            "cpu": str(container.get("resources", {}).get("limits", {}).get("cpu")),
            "memory": container.get("resources", {}).get("limits", {}).get("memory"),
            "working_directory": container.get("workingDir", ""),
            "volumes": template.get("volumes", []), "volume_mounts": container.get("volumeMounts", []),
            "provider_observed": True,
        }
        if authority_sha != _hash(observation):
            _fail("combined provider job authority environment differs")
        return observation

    def update_existing_job(self, desired: Mapping[str, object]) -> None:
        if desired["reused_job_name"] != execution.FIXED_REUSED_JOB_NAME:
            _fail("combined provider refuses new job")
        environment = "^|^" + "|".join(
            f"{key}={value}" for key, value in desired["container_environment"].items()
        )
        subprocess.run([
            "gcloud", "run", "jobs", "update", execution.FIXED_REUSED_JOB_NAME,
            "--project", execution.FIXED_GCP_PROJECT, "--region", execution.FIXED_REGION,
            "--image", str(desired["immutable_image_uri"]), "--tasks", str(desired["task_count"]),
            "--parallelism", str(desired["parallelism"]), "--max-retries", "0",
            "--task-timeout", f"{desired['timeout_seconds']}s", "--cpu", str(desired["cpu"]),
            "--memory", str(desired["memory"]), "--command", str(desired["container_command"][0]),
            f"--args={','.join(desired['container_args'])}", "--set-env-vars", environment,
            "--clear-volumes",
            "--quiet",
        ], check=True)

    def launch_existing_job(self, job_name: str) -> str:
        raw = self._json(["gcloud", "run", "jobs", "execute", job_name,
                          "--project", execution.FIXED_GCP_PROJECT, "--region", execution.FIXED_REGION,
                          "--async", "--format=json"])
        return str(raw.get("metadata", {}).get("name", "")).split("/")[-1]

    def describe_execution(self, execution_id: str) -> dict[str, object]:
        raw = self._json([
            "gcloud", "run", "jobs", "executions", "describe", execution_id,
            "--project", execution.FIXED_GCP_PROJECT, "--region", execution.FIXED_REGION,
            "--format=json",
        ])
        metadata = _mapping(raw.get("metadata", {}), label="execution metadata")
        labels = _mapping(metadata.get("labels", {}), label="execution labels")
        owners = metadata.get("ownerReferences", [])
        owner = _mapping(owners[0] if len(owners) == 1 else {}, label="execution owner")
        actual_execution = str(metadata.get("name", "")).split("/")[-1]
        actual_job = labels.get("run.googleapis.com/job") or owner.get("name")
        actual_uid = owner.get("uid")
        spec = _mapping(raw.get("spec", {}), label="execution spec")
        actual_task_count = spec.get("taskCount")
        status = raw.get("status", {})
        job_observation = self.describe_job(str(actual_job))
        execution_template = _mapping(
            spec.get("template", {}).get("spec", {}), label="execution template"
        )
        containers = execution_template.get("containers", [])
        if containers:
            container = _mapping(containers[0], label="execution container")
            execution_env = {
                row["name"]: row.get("value", "") for row in container.get("env", [])
            }
            authority_sha = execution_env.pop(execution.JOB_AUTHORITY_SHA_ENV, "")
            execution_projection = {
                "job_name": actual_job, "job_uid": actual_uid,
                "project_id": execution.FIXED_GCP_PROJECT,
                "region": execution.FIXED_REGION,
                "image_digest": str(container.get("image", "")).split("@")[-1],
                "immutable_image_uri": container.get("image"),
                "source_commit": execution_env.get("CODE_SHA"),
                "container_command": container.get("command", []),
                "container_args": container.get("args", []),
                "container_environment": execution_env,
                "task_count": actual_task_count,
                "parallelism": spec.get("parallelism"),
                "max_retries": execution_template.get("maxRetries"),
                "timeout_seconds": int(str(execution_template.get("timeoutSeconds", "0s")).rstrip("s")),
                "cpu": str(container.get("resources", {}).get("limits", {}).get("cpu")),
                "memory": container.get("resources", {}).get("limits", {}).get("memory"),
                "working_directory": container.get("workingDir", ""),
                "volumes": execution_template.get("volumes", []),
                "volume_mounts": container.get("volumeMounts", []),
                "provider_observed": True,
            }
            if authority_sha != _hash(execution_projection) or execution_projection != job_observation:
                _fail("provider execution template differs from exact job authority")
        if (
            actual_execution != execution_id
            or actual_job != job_observation.get("job_name")
            or actual_uid != job_observation.get("job_uid")
            or actual_task_count != job_observation.get("task_count")
            or not containers
        ):
            _fail("provider execution resource job/UID/task configuration differs")
        return {
            "execution_id": actual_execution,
            "job_name": actual_job,
            "job_uid": actual_uid,
            "task_count": actual_task_count,
            "succeeded_count": status.get("succeededCount", 0),
            "failed_count": status.get("failedCount", 0),
            "cancelled_count": status.get("cancelledCount", 0),
            "running_count": status.get("runningCount", 0),
            "terminal": status.get("completionTime") is not None,
            "provider_observed": True,
            "job_observation": job_observation,
        }


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _canonical(value: object) -> bytes:
    try:
        return grader.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _strict_json(raw: bytes, *, label: str, maximum_bytes: int) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > maximum_bytes:
        _fail(f"{label} byte size differs")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc


def _validate_provider_build_attestation_v1(
    *, receipt: Mapping[str, object], provider_build: Mapping[str, object]
) -> None:
    build = _mapping(provider_build, label="provider Cloud Build attestation")
    substitutions = _mapping(build.get("substitutions", {}), label="build substitutions")
    source = _mapping(build.get("source", {}), label="build source")
    repo_source = _mapping(source.get("repoSource", {}), label="build repo source")
    git_source = _mapping(source.get("gitSource", {}), label="build git source")
    provenance = _mapping(
        build.get("sourceProvenance", {}), label="build source provenance"
    )
    resolved_repo = _mapping(
        provenance.get("resolvedRepoSource", {}), label="resolved repo build source"
    )
    resolved_git = _mapping(
        provenance.get("resolvedGitSource", {}), label="resolved git build source"
    )
    repo_mode = bool(repo_source) or bool(resolved_repo)
    git_mode = bool(git_source) or bool(resolved_git)
    if (
        repo_mode == git_mode
        or bool(repo_source) != bool(resolved_repo)
        or bool(git_source) != bool(resolved_git)
    ):
        _fail("provider Cloud Build source mode differs")
    if repo_mode:
        requested_commit = repo_source.get("commitSha")
        resolved_commit = resolved_repo.get("commitSha")
        requested_repository = (
            repo_source.get("repoName") or repo_source.get("repository")
        )
        resolved_repository = (
            resolved_repo.get("repoName") or resolved_repo.get("repository")
        )
    else:
        requested_commit = git_source.get("revision")
        resolved_commit = resolved_git.get("revision")
        requested_repository = git_source.get("url")
        resolved_repository = resolved_git.get("url")
    if (
        re.fullmatch(r"[0-9a-f]{40}", str(requested_commit)) is None
        or requested_commit != resolved_commit
        or type(requested_repository) is not str
        or not requested_repository
        or requested_repository != resolved_repository
    ):
        _fail("provider Cloud Build requested/resolved source differs")
    corroborating_revisions = [
        value for value in (
            substitutions.get("COMMIT_SHA"), substitutions.get("REVISION_ID"),
            substitutions.get("_SOURCE_COMMIT"),
        ) if value not in (None, "")
    ]
    images = [
        _mapping(row, label="provider build image")
        for row in build.get("results", {}).get("images", [])
    ]
    if (
        build.get("id") != receipt.get("build_id")
        or build.get("status") != "SUCCESS"
        or resolved_commit != receipt.get("source_commit")
        or any(
            re.fullmatch(r"[0-9a-f]{40}", str(value)) is None
            or value != resolved_commit
            for value in corroborating_revisions
        )
        or not any(
            row.get("name") == receipt.get("image_tag")
            and row.get("digest") == receipt.get("image_digest")
            for row in images
        )
    ):
        _fail("provider Cloud Build attestation differs from receipt")


class GCSExactTransportV1(hard_operator.GCSExactTransportV1):
    """Use the existing 900-second exact transport plus known-name resolve."""

    def open_known(
        self, uri: str, maximum_bytes: int
    ) -> tuple[bytes, Mapping[str, object]]:
        if type(maximum_bytes) is not int or maximum_bytes < 1:
            _fail("known-object byte ceiling differs")
        bucket_name, object_name = self._parts(uri)
        metadata = self._client.bucket(bucket_name).blob(object_name)
        metadata.reload(
            timeout=hard_operator.GCS_IO_TIMEOUT_SECONDS,
            retry=self._retry,
        )
        if metadata.generation is None or metadata.size is None:
            _fail("known combined result lacks generation or size")
        size = int(metadata.size)
        generation = int(metadata.generation)
        if size < 1 or size > maximum_bytes:
            _fail("known combined result exceeds its byte ceiling")
        raw = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        ).download_as_bytes(
            if_generation_match=generation,
            timeout=hard_operator.GCS_IO_TIMEOUT_SECONDS,
            retry=self._retry,
        )
        if type(raw) is not bytes or len(raw) != size:
            _fail("known combined result generation-exact bytes differ")
        return raw, _identity({
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": size,
        }, label="known combined result")


def _read_json(
    identity_value: object,
    *,
    store: object,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=label)
    raw = store.read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read identity differs")
    return _strict_json(raw, label=label, maximum_bytes=maximum_bytes), identity


def _publish_json(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    store: object,
) -> dict[str, object]:
    raw = _canonical(value)
    if len(raw) > maximum_bytes:
        _fail("combined publication exceeds its byte ceiling")
    identity = _identity(
        store.publish_create_once(uri, raw), label="combined publication"
    )
    if (
        identity["uri"] != uri
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
        or store.read_exact(identity) != raw
    ):
        _fail("combined create-once exact reopen differs")
    return identity


def _read_hard_terminal(
    *, store: object
) -> tuple[dict[str, object], dict[str, object]]:
    body, identity = _read_json(
        execution.FIXED_HARD230_TERMINAL_IDENTITY,
        store=store,
        label="hard230 selector terminal",
        maximum_bytes=MAXIMUM_HARD_TERMINAL_BYTES,
    )
    try:
        terminal = hard_bridge.validate_hard230_selector_terminal_v1(body)
    except hard_bridge.CorpusR6Hard230SelectorBridgeV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    if identity["uri"] != terminal["terminal_uri"]:
        _fail("hard230 selector terminal outer URI differs")
    return terminal, identity


def prepare_from_request_v1(
    request: object, *, store: object, provider: object
) -> dict[str, object]:
    """Exact-open the three completed finalist roots, then publish a manifest."""
    item = _mapping(request, label="combined prepare request")
    if set(item) != {
        "incumbent_panel_freeze_identity", "profile_terminal_identity",
        "hard230_terminal_identity", "terminal_build_receipt_identity",
        "output_prefix",
    }:
        _fail("combined prepare request fields differ")
    if (
        _identity(item["incumbent_panel_freeze_identity"], label="incumbent")
        != execution.FIXED_INCUMBENT_PANEL_FREEZE_IDENTITY
        or _identity(item["profile_terminal_identity"], label="profiles")
        != execution.FIXED_PROFILE_TERMINAL_IDENTITY
        or _identity(item["hard230_terminal_identity"], label="hard230")
        != execution.FIXED_HARD230_TERMINAL_IDENTITY
    ):
        _fail("combined prepare source identity differs")
    try:
        incumbent, incumbent_identity = full_freeze.reopen_panel_freeze_v1(
            item["incumbent_panel_freeze_identity"], read_exact=store.read_exact
        )
        profile_root, profile_identity, profile_opened = (
            grader.reopen_terminal_experiment_v1(
                terminal_root_identity=item["profile_terminal_identity"],
                read_terminal_exact=store.read_exact,
            )
        )
    except (
        full_freeze.CorpusR6FullUnionPanelFreezeV1Error,
        grader.CorpusR6NovelRosterRealizedGraderV1Error,
    ) as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    hard_terminal, hard_identity = _read_hard_terminal(store=store)
    build_identity = _identity(
        item["terminal_build_receipt_identity"],
        label="combined terminal build receipt",
    )
    build_bytes = store.read_exact(build_identity)
    if (
        type(build_bytes) is not bytes
        or len(build_bytes) != build_identity["bytes"]
        or len(build_bytes) > l2b_panel.MAXIMUM_JSON_INPUT_BYTES
        or sha256(build_bytes).hexdigest() != build_identity["sha256"]
    ):
        _fail("combined terminal build receipt exact bytes differ")
    try:
        raw_build = _mapping(
            json.loads(build_bytes.decode("utf-8")),
            label="combined terminal build receipt",
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(
            "combined terminal build receipt is not UTF-8 JSON"
        ) from exc
    try:
        provider_build = provider.describe_build(str(raw_build["build_id"]))
        _validate_provider_build_attestation_v1(
            receipt=raw_build, provider_build=provider_build
        )
        build_receipt, verified_build_identity = l2b_panel._read_terminal_build_receipt(
            build_identity,
            source_commit_sha=str(raw_build["source_commit"]),
            immutable_image_digest=str(raw_build["image_digest"]),
            read_exact=store.read_exact,
            label="combined terminal build receipt",
        )
    except l2b_panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    if verified_build_identity != build_identity or build_receipt != raw_build:
        _fail("combined terminal build receipt exact replay differs")
    if profile_opened.adapter_id != grader.POPULATION_CROSSED_ADAPTER:
        _fail("combined profile terminal adapter differs")
    if not (
        profile_opened.later_source_identity
        == incumbent["later_source_freeze_identity"]
        == hard_terminal["later_source_identity"]
    ):
        _fail("combined finalist later-source identities differ")
    manifest = execution.build_task_manifest_v1(
        incumbent_panel_freeze=incumbent,
        incumbent_panel_freeze_identity=incumbent_identity,
        profile_terminal_root=profile_root,
        profile_terminal_identity=profile_identity,
        profile_task_manifest=profile_opened.task_manifest,
        profile_task_result_descriptors=profile_opened.task_result_descriptors,
        profile_task_results=profile_opened.task_results,
        hard230_terminal=hard_terminal,
        hard230_terminal_identity=hard_identity,
        terminal_build_receipt=build_receipt,
        terminal_build_receipt_identity=build_identity,
        output_prefix=str(item["output_prefix"]),
    )
    manifest_uri = f"{manifest['output_prefix']}task-manifest.json"
    manifest_identity = _publish_json(
        uri=manifest_uri,
        value=manifest,
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-population-all-block-prepare-result/v1",
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "task_count": execution.TASK_COUNT,
        "terminal_uri": manifest["terminal_uri"],
        "job_configuration": execution.build_job_configuration_v1(
            manifest=manifest, manifest_identity=manifest_identity
        ),
        "all_sources_exact_opened_before_manifest": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def configure_existing_job_v1(
    *, task_manifest_identity: object, store: object, provider: object
) -> dict[str, object]:
    manifest, identity = _open_manifest(task_manifest_identity, store=store)
    before = provider.describe_job_identity(execution.FIXED_REUSED_JOB_NAME)
    if (
        before.get("job_name") != execution.FIXED_REUSED_JOB_NAME
        or before.get("job_uid") != execution.FIXED_REUSED_JOB_UID
    ):
        _fail("combined configure refuses a different or new Cloud Run job")
    desired = execution.build_job_configuration_v1(
        manifest=manifest, manifest_identity=identity
    )
    provider.update_existing_job(desired)
    after = provider.describe_job(execution.FIXED_REUSED_JOB_NAME)
    execution.validate_provider_job_observation_v1(
        after, manifest=manifest, manifest_identity=identity
    )
    return {"job_observation": after, "job_configuration": desired, "complete": True}


def launch_existing_job_v1(
    *, task_manifest_identity: object, store: object, provider: object
) -> dict[str, object]:
    manifest, identity = _open_manifest(task_manifest_identity, store=store)
    observed = provider.describe_job(execution.FIXED_REUSED_JOB_NAME)
    execution.validate_provider_job_observation_v1(
        observed, manifest=manifest, manifest_identity=identity
    )
    execution_id = provider.launch_existing_job(execution.FIXED_REUSED_JOB_NAME)
    if type(execution_id) is not str or not execution_id:
        _fail("combined provider launch did not return one execution ID")
    return {"execution_id": execution_id, "job_uid": execution.FIXED_REUSED_JOB_UID,
            "new_job_created": False, "complete": True}


def status_existing_execution_v1(
    *, task_manifest_identity: object, execution_id: str,
    store: object, provider: object
) -> dict[str, object]:
    manifest, identity = _open_manifest(task_manifest_identity, store=store)
    status = provider.describe_execution(execution_id)
    return execution.validate_provider_terminal_execution_v1(
        status, manifest=manifest, manifest_identity=identity
    )


def _open_manifest(
    identity_value: object, *, store: object
) -> tuple[dict[str, object], dict[str, object]]:
    manifest, identity = _read_json(
        identity_value,
        store=store,
        label="combined task manifest",
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    try:
        retained = execution.validate_task_manifest_v1(manifest)
    except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    if identity["uri"] != f"{retained['output_prefix']}task-manifest.json":
        _fail("combined task manifest outer URI differs")
    try:
        build_receipt, build_identity = l2b_panel._read_terminal_build_receipt(
            retained["terminal_build_receipt_identity"],
            source_commit_sha=str(retained["code_commit"]),
            immutable_image_digest=str(retained["image_digest"]),
            read_exact=store.read_exact,
            label="combined retained build receipt",
        )
    except l2b_panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    if (
        build_identity != retained["terminal_build_receipt_identity"]
        or _hash(build_receipt) != retained["terminal_build_receipt_sha256"]
        or build_receipt["build_id"] != retained["terminal_build_id"]
    ):
        _fail("combined retained build receipt binding differs")
    return retained, identity


def _derive_science_v1(
    *, manifest: Mapping[str, object], task_index: int, store: object
) -> dict[str, object]:
    """Exact-reopen all frozen sources and recompute one eight-book slate."""
    if type(task_index) is not int or not 0 <= task_index < execution.TASK_COUNT:
        _fail("combined task index differs")
    binding = manifest["task_bindings"][task_index]
    try:
        leaf, incumbent_manifest, panel, members, incumbent_result, leaf_identity = (
            full_freeze.reopen_slate_freeze_v1(
                binding["incumbent_slate_freeze_identity"],
                read_exact=store.read_exact,
            )
        )
    except full_freeze.CorpusR6FullUnionPanelFreezeV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    if (
        leaf_identity != binding["incumbent_slate_freeze_identity"]
        or leaf["slate_freeze_sha256"]
        != binding["incumbent_slate_freeze_sha256"]
        or incumbent_result["task_result_sha256"]
        != binding["incumbent_task_result_sha256"]
        or leaf["source_ordinal"] != task_index
        or leaf["slate_id"] != binding["slate_id"]
    ):
        _fail("combined incumbent slate binding differs")
    incumbent_source = combined.project_incumbent_current_r6_source_v1(
        task_result=incumbent_result,
        panel_index_identity=incumbent_manifest["panel_index_identity"],
        panel_index_sha256=str(panel["panel_index_sha256"]),
        panel_member=members[task_index],
    )
    profile_result_body, profile_result_identity = _read_json(
        binding["profile_task_result_identity"],
        store=store,
        label="profile crossed task result",
        maximum_bytes=MAXIMUM_PROFILE_RESULT_BYTES,
    )
    try:
        profile_result = crossed.validate_slate_result_v1(profile_result_body)
        prepared, profile_bodies, profile_source = crossed._load_task_sources_v1(
            binding["profile_source_request"], read_exact=store.read_exact
        )
    except crossed.CorpusR6PopulationCrossedCloudV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    if (
        profile_result_identity != binding["profile_task_result_identity"]
        or profile_result["slate_result_sha256"]
        != binding["profile_task_result_sha256"]
        or profile_result["source_ordinal"] != task_index
        or profile_result["slate_id"] != binding["slate_id"]
        or profile_result["task_request_sha256"]
        != binding["profile_source_request_sha256"]
        or profile_result["projection_bundle_identity"]
        != binding["profile_source_request"]["projection_bundle_identity"]
        or profile_result["profile_lineup_identities"]
        != binding["profile_source_request"]["profile_lineup_identities"]
        or profile_source["later_source_identity"] != manifest["later_source_identity"]
    ):
        _fail("combined profile slate/source binding differs")
    profile_sources = combined.project_profile_sources_v1(
        profile_lineups_by_id=profile_bodies, players=prepared.players
    )
    hard_terminal, hard_identity = _read_hard_terminal(store=store)
    if (
        hard_identity != manifest["hard230_terminal_identity"]
        or hard_terminal["terminal_sha256"] != manifest["hard230_terminal_sha256"]
    ):
        _fail("combined hard230 terminal manifest binding differs")
    hard_slate = _mapping(
        hard_terminal["slate_results"][task_index], label="hard230 slate result"
    )
    if (
        hard_slate["source_ordinal"] != task_index
        or hard_slate["slate_id"] != binding["slate_id"]
        or hard_slate["slate_result_sha256"]
        != binding["hard230_slate_result_sha256"]
        or hard_slate["source_member_identity"]
        != binding["hard230_source_member_identity"]
    ):
        _fail("combined hard230 slate binding differs")
    source_member_identity = _mapping(
        hard_slate["source_member_identity"], label="hard230 source member identity"
    )
    source_member, _source_member_object = _read_json(
        source_member_identity["object_identity"],
        store=store,
        label="hard230 source member",
        maximum_bytes=MAXIMUM_SOURCE_MEMBER_BYTES,
    )
    hard_source = combined.project_hard230_challenger_source_v1(
        slate_result=hard_slate, source_member=source_member
    )
    return combined.run_combined_population_all_block_v1(
        slate={
            "season": prepared.season,
            "week": prepared.week,
            "slate_id": prepared.slate_id,
        },
        sources=(incumbent_source, *profile_sources, hard_source),
        players=prepared.players,
        player_draws=prepared.player_draws,
    )


def execute_task_v1(
    *,
    task_manifest_identity: object,
    runtime_authority: Mapping[str, object],
    store: object,
) -> dict[str, object]:
    """Run one score-free slate from immutable populations and worlds."""
    manifest, manifest_identity = _open_manifest(
        task_manifest_identity, store=store
    )
    try:
        retained_runtime = execution.validate_runtime_authority_v1(
            runtime_authority,
            manifest=manifest,
            manifest_identity=manifest_identity,
        )
    except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    task_index = int(retained_runtime["task_index"])
    binding = manifest["task_bindings"][task_index]
    science = _derive_science_v1(
        manifest=manifest, task_index=task_index, store=store
    )
    result = execution.build_task_result_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        source_ordinal=task_index,
        runtime_authority=retained_runtime,
        science_result=science,
    )
    result_identity = _publish_json(
        uri=binding["result_uri"],
        value=result,
        maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-population-all-block-task-completion/v1",
        "task_index": task_index,
        "source_ordinal": task_index,
        "slate_id": result["slate_id"],
        "task_manifest_identity": manifest_identity,
        "task_binding_sha256": binding["task_binding_sha256"],
        "runtime_authority_sha256": retained_runtime[
            "runtime_authority_sha256"
        ],
        "task_result_identity": result_identity,
        "task_result_sha256": result["task_result_sha256"],
        "union_lineup_count": result["union_lineup_count"],
        "book_count": result["book_count"],
        "entry_budget": result["entry_budget"],
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _open_known_task_results(
    *,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    store: object,
) -> list[tuple[dict[str, object], dict[str, object]]]:
    rows: list[tuple[dict[str, object], dict[str, object]]] = []
    for ordinal, binding in enumerate(manifest["task_bindings"]):
        raw, identity_value = store.open_known(
            binding["result_uri"], MAXIMUM_TASK_RESULT_BYTES
        )
        identity = _identity(identity_value, label=f"combined result[{ordinal}]")
        result = _strict_json(
            raw, label=f"combined result[{ordinal}]", maximum_bytes=MAXIMUM_TASK_RESULT_BYTES
        )
        try:
            retained = execution.validate_task_result_v1(
                result, manifest=manifest, manifest_identity=manifest_identity
            )
        except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
            raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
        if (
            identity["uri"] != binding["result_uri"]
            or identity["sha256"] != sha256(raw).hexdigest()
            or identity["bytes"] != len(raw)
            or retained["source_ordinal"] != ordinal
        ):
            _fail(f"combined known result[{ordinal}] binding differs")
        replayed = _derive_science_v1(
            manifest=manifest, task_index=ordinal, store=store
        )
        try:
            retained = execution.validate_exact_science_replay_v1(
                retained,
                replayed_science_result=replayed,
                manifest=manifest,
                manifest_identity=manifest_identity,
            )
        except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
            raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
        rows.append((retained, identity))
    return rows


def collect_from_request_v1(
    request: object, *, store: object, provider: object
) -> dict[str, object]:
    item = _mapping(request, label="combined collect request")
    if set(item) != {"task_manifest_identity", "execution_id"}:
        _fail("combined collect request fields differ")
    manifest, manifest_identity = _open_manifest(
        item["task_manifest_identity"], store=store
    )
    provider_terminal = status_existing_execution_v1(
        task_manifest_identity=manifest_identity,
        execution_id=str(item["execution_id"]), store=store, provider=provider,
    )
    if provider_terminal["execution_id"] != item["execution_id"]:
        _fail("combined collect execution ID differs")
    task_results = _open_known_task_results(
        manifest=manifest, manifest_identity=manifest_identity, store=store
    )
    try:
        terminal = execution.build_terminal_v1(
            manifest=manifest,
            manifest_identity=manifest_identity,
            task_results=task_results,
            provider_terminal_execution=provider_terminal,
        )
    except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    terminal_identity = _publish_json(
        uri=terminal["terminal_uri"],
        value=terminal,
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-population-all-block-collect-result/v1",
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "source_slate_count": execution.TASK_COUNT,
        "all_task_results_exact_opened_before_terminal": True,
        "generic_normalized_terminal_validated_before_terminal": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _reopen_terminal(
    identity_value: object, *, store: object
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    tuple[dict[str, object], ...],
]:
    terminal_body, terminal_identity = _read_json(
        identity_value,
        store=store,
        label="combined terminal",
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
    )
    try:
        terminal = execution.validate_terminal_envelope_v1(terminal_body)
    except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    if terminal_identity["uri"] != terminal["terminal_uri"]:
        _fail("combined terminal outer URI differs")
    manifest, manifest_identity = _open_manifest(
        terminal["task_manifest_identity"], store=store
    )
    if (
        manifest_identity != terminal["task_manifest_identity"]
        or manifest["task_manifest_sha256"] != terminal["task_manifest_sha256"]
    ):
        _fail("combined terminal manifest binding differs")
    task_results: list[tuple[dict[str, object], dict[str, object]]] = []
    for ordinal, descriptor in enumerate(terminal["task_results"]):
        result, identity = _read_json(
            descriptor["task_result_identity"],
            store=store,
            label=f"combined terminal task result[{ordinal}]",
            maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        )
        replayed = _derive_science_v1(
            manifest=manifest, task_index=ordinal, store=store
        )
        try:
            result = execution.validate_exact_science_replay_v1(
                result,
                replayed_science_result=replayed,
                manifest=manifest,
                manifest_identity=manifest_identity,
            )
        except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
            raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
        task_results.append((result, identity))
    try:
        validated, normalized = execution.validate_terminal_with_results_v1(
            terminal,
            manifest=manifest,
            task_results=task_results,
        )
    except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc
    return validated, terminal_identity, manifest, normalized


def grade_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="combined grade request")
    if set(item) != {"terminal_identity", "outcome_snapshot_identity"}:
        _fail("combined grade request fields differ")

    # This complete score-free replay intentionally precedes the first call
    # to the outcome reader below.
    terminal, terminal_identity, _manifest, normalized = _reopen_terminal(
        item["terminal_identity"], store=store
    )
    snapshot, snapshot_identity, player_scores, slate_keys = (
        grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=item["outcome_snapshot_identity"],
            read_outcome_exact=store.read_exact,
        )
    )
    if (
        snapshot.get("later_source_freeze_identity")
        != terminal["later_source_identity"]
        or set(slate_keys) != set(range(execution.TASK_COUNT))
        or any(
            slate_keys[ordinal][2] != normalized[ordinal]["slate_id"]
            for ordinal in range(execution.TASK_COUNT)
        )
    ):
        _fail("combined terminal/outcome source or slate binding differs")
    slate_grades = grader.score_normalized_slates_v1(
        slates=normalized, player_scores=player_scores
    )
    aggregates = grader.aggregate_normalized_slate_grades_v1(slate_grades)
    body = {
        "schema_version": "corpus-r6-combined-population-all-block-realized-grade/v1",
        "adapter_id": combined.ADAPTER_ID,
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "later_source_identity": terminal["later_source_identity"],
        "source_slate_count": execution.TASK_COUNT,
        "entry_budget": combined.ENTRY_BUDGET,
        "strategy_count": execution.BOOK_COUNT_PER_SLATE,
        "slate_grades": slate_grades,
        "slate_grades_sha256": _hash(slate_grades),
        "aggregate_cells": aggregates,
        "aggregate_cells_sha256": _hash(aggregates),
        "all_score_free_predecessors_validated_before_outcome_open": True,
        "outcome_source_and_slate_identity_bound": True,
        "historical_finalist_confirmation": True,
        "untouched_confirmatory_inference": False,
        "complete": True,
    }
    grade = {**body, "grade_sha256": _hash(body)}
    grade_identity = _publish_json(
        uri=execution.grade_uri_v1(output_prefix=str(terminal["output_prefix"])),
        value=grade,
        maximum_bytes=MAXIMUM_GRADE_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-combined-population-all-block-grade-result/v1",
        "grade_identity": grade_identity,
        "grade_sha256": grade["grade_sha256"],
        "aggregate_cell_count": len(aggregates),
        "historical_finalist_confirmation": True,
        "complete": True,
    }


def _load_request(path: str) -> dict[str, object]:
    return _strict_json(
        Path(path).read_bytes(),
        label="combined operator request",
        maximum_bytes=MAXIMUM_REQUEST_BYTES,
    )


def _task_manifest_identity_from_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    env = dict(os.environ if environment is None else environment)
    raw_identity = env.get(MANIFEST_IDENTITY_ENV, "")
    try:
        identity_value = json.loads(raw_identity)
    except (json.JSONDecodeError, TypeError) as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(
            "combined task environment differs"
        ) from exc
    return _identity(identity_value, label="task manifest")


def _observed_command_v1(raw_cmdline: bytes | None = None) -> list[str]:
    raw = Path("/proc/self/cmdline").read_bytes() if raw_cmdline is None else raw_cmdline
    try:
        values = [part.decode("utf-8") for part in raw.split(b"\0") if part]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(
            "combined observed process command is not UTF-8"
        ) from exc
    return values


def _runtime_authority_from_environment(
    *, manifest_identity: object, store: object,
    environment: Mapping[str, str] | None = None,
    observed_command: list[str] | None = None,
    observed_project_id: str | None = None,
) -> dict[str, object]:
    manifest, _retained_identity = _open_manifest(manifest_identity, store=store)
    try:
        return execution.build_runtime_authority_v1(
            manifest=manifest,
            manifest_identity=manifest_identity,
            environment=os.environ if environment is None else environment,
            observed_command=(
                _observed_command_v1() if observed_command is None
                else observed_command
            ),
            observed_project_id=(
                str(getattr(getattr(store, "_client", None), "project", ""))
                if observed_project_id is None else observed_project_id
            ),
        )
    except execution.CorpusR6CombinedPopulationAllBlockExecutionV1Error as exc:
        raise RunCorpusR6CombinedPopulationAllBlockV1Error(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "configure", "launch", "status", "collect", "grade"):
        child = subparsers.add_parser(command)
        child.add_argument("--request", required=True)
    subparsers.add_parser("task")
    args = parser.parse_args(argv)
    if os.environ.get(ENABLE_ENV) != ENABLE_VALUE:
        _fail(f"{ENABLE_ENV} is not exactly enabled")
    store = GCSExactTransportV1()
    provider = GCloudRunProviderV1()
    if args.command == "prepare":
        result = prepare_from_request_v1(_load_request(args.request), store=store, provider=provider)
    elif args.command == "configure":
        request = _load_request(args.request)
        result = configure_existing_job_v1(
            task_manifest_identity=request["task_manifest_identity"], store=store, provider=provider
        )
    elif args.command == "launch":
        request = _load_request(args.request)
        result = launch_existing_job_v1(
            task_manifest_identity=request["task_manifest_identity"], store=store, provider=provider
        )
    elif args.command == "status":
        request = _load_request(args.request)
        result = status_existing_execution_v1(
            task_manifest_identity=request["task_manifest_identity"],
            execution_id=str(request["execution_id"]), store=store, provider=provider
        )
    elif args.command == "task":
        manifest_identity = _task_manifest_identity_from_environment()
        runtime_authority = _runtime_authority_from_environment(
            manifest_identity=manifest_identity,
            store=store,
        )
        result = execute_task_v1(
            task_manifest_identity=manifest_identity,
            runtime_authority=runtime_authority,
            store=store,
        )
    elif args.command == "collect":
        result = collect_from_request_v1(_load_request(args.request), store=store, provider=provider)
    else:
        result = grade_from_request_v1(_load_request(args.request), store=store)
    sys.stdout.buffer.write(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
