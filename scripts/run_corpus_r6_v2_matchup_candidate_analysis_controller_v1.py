#!/usr/bin/env python3
"""Guarded one-job operator for the canonical outcome-blind R6-v2 release.

Host commands separate provider mutation from observation:

* ``snapshot`` (mutating GCS only) freezes the exact reused-job/export and
  controller manifest before the job is changed;
* ``launch`` creates a fresh configuration claim, updates the existing UID,
  creates a fresh execution claim, then launches exactly one phase;
* ``status`` is provider/GCS read-only;
* ``accept`` publishes a phase receipt only after provider and scientific
  gates pass;
* ``reopen`` is a fully read-only independent replay; and
* ``restore`` replaces the reused job from its generation-pinned export and
  proves the stable configuration and UID are exact.

``dispatch`` is the only container entrypoint.  It derives source ordinals
strictly from ``CLOUD_RUN_TASK_INDEX`` and calls the canonical release core;
it accepts no caller-supplied commit, image, ordinal, outcome or score input.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_controller_v1 as controller,
)
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_release_v2 as release,
)
from nfl_dfs.research.corpus_neo4j_transport import (
    ExactObjectStore,
    GoogleCloudObjectStore,
    ObjectIdentity,
)


CLOUD_RUN_TASK_INDEX: Final = "CLOUD_RUN_TASK_INDEX"
_TASK_INDEX = re.compile(r"(?:0|[1-9][0-9]*)")
_PROJECT = re.compile(r"[a-z][a-z0-9-]{4,62}")
_REGION = re.compile(r"[a-z]+-[a-z]+[0-9]")
_JOB = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]")
_EXECUTION = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]")
MAX_PROVIDER_STDOUT_BYTES: Final = 64 * 1024 * 1024
MAX_PROVIDER_STDERR_BYTES: Final = 2 * 1024 * 1024


class RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(RuntimeError):
    """The guarded host/container operator failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or "\x00" in value:
        _fail(f"{label} differs")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(str(exc)) from exc


def _object_identity(value: object, *, label: str) -> ObjectIdentity:
    row = _identity(value, label=label)
    return ObjectIdentity(
        uri=str(row["uri"]), generation=str(row["generation"]),
        sha256=str(row["sha256"]), bytes=int(row["bytes"]),
    )


def _canonical(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _load_identity(
    path: Path, *, label: str, carrier_fields: Sequence[str] = (),
) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        _fail(f"{label} path must be one absolute regular file")
    raw = path.read_bytes()
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if raw not in {canonical, canonical + b"\n"}:
        _fail(f"{label} file framing differs")
    try:
        value = batch.parse_canonical_json_bytes(canonical, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(str(exc)) from exc
    item = _mapping(value, label=label)
    present = [field for field in carrier_fields if field in item]
    if len(present) > 1:
        _fail(f"{label} carries multiple identities")
    return _identity(item[present[0]] if present else item, label=label)


def _read_json(
    storage: ExactObjectStore, identity: object, *, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _identity(identity, label=f"{label} identity")
    raw = storage.read_exact(_object_identity(retained, label=label))
    if (
        type(raw) is not bytes or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(str(exc)) from exc
    return retained, _mapping(value, label=label)


def _publish_raw(
    storage: ExactObjectStore, *, uri: str, raw: bytes, label: str,
) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} bytes differ")
    identity = storage.publish_create_once(uri, raw)
    if identity.uri != uri or storage.read_exact(identity) != raw:
        _fail(f"{label} create-once exact reopen differs")
    return identity.as_dict()


class FreshClaimGoogleCloudObjectStore(GoogleCloudObjectStore):
    """GCS adapter whose provider-mutation claims reject every prior object."""

    def claim_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        if type(raw) is not bytes or not raw:
            _fail("fresh provider mutation claim bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ in {"PreconditionFailed", "Conflict"}:
                raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(
                    "fresh provider-mutation claim already exists; automatic "
                    "retry is forbidden"
                ) from exc
            raise
        blob.reload()
        if blob.generation is None:
            _fail("fresh provider-mutation claim lacks a generation")
        identity = ObjectIdentity(
            uri=uri, generation=str(blob.generation),
            sha256=sha256(raw).hexdigest(), bytes=len(raw),
        )
        if self.read_exact(identity) != raw:
            _fail("fresh provider-mutation claim exact reopen differs")
        return identity


class GCloudRunOneJobProviderV1:
    """Thin gcloud adapter; all scientific/provider validation stays pure."""

    def __init__(self, *, project: str, region: str) -> None:
        if _PROJECT.fullmatch(project) is None or _REGION.fullmatch(region) is None:
            _fail("provider project or region differs")
        self.project = project
        self.region = region

    @staticmethod
    def _run(argv: Sequence[str], *, stdout_limit: int = MAX_PROVIDER_STDOUT_BYTES) -> bytes:
        retained = [_string(token, label="provider argv") for token in argv]
        try:
            result = subprocess.run(
                retained, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(
                "provider subprocess could not start"
            ) from exc
        if (
            len(result.stdout) > stdout_limit
            or len(result.stderr) > MAX_PROVIDER_STDERR_BYTES
            or result.returncode != 0
        ):
            _fail("provider subprocess failed or exceeded its output envelope")
        return result.stdout

    @classmethod
    def _json(cls, argv: Sequence[str]) -> object:
        raw = cls._run(argv)
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(
                "provider returned malformed JSON"
            ) from exc

    def describe_job(self, job_name: str) -> dict[str, object]:
        if _JOB.fullmatch(job_name) is None:
            _fail("provider job name differs")
        return _mapping(self._json([
            "gcloud", "run", "jobs", "describe", job_name,
            "--project", self.project, "--region", self.region, "--format=json",
        ]), label="provider job description")

    def export_job(self, job_name: str) -> bytes:
        if _JOB.fullmatch(job_name) is None:
            _fail("provider export job differs")
        return self._run([
            "gcloud", "run", "jobs", "describe", job_name,
            "--project", self.project, "--region", self.region,
            "--format=export",
        ])

    def list_executions(self, job_name: str) -> list[object]:
        if _JOB.fullmatch(job_name) is None:
            _fail("provider execution census job differs")
        value = self._json([
            "gcloud", "run", "jobs", "executions", "list", "--job", job_name,
            "--project", self.project, "--region", self.region, "--format=json",
        ])
        return _sequence(value, label="provider execution census")

    def scheduler_census_all_regions(self) -> tuple[list[object], bool]:
        locations = _sequence(self._json([
            "gcloud", "scheduler", "locations", "list",
            "--project", self.project, "--format=json",
        ]), label="scheduler location census")
        rows: list[object] = []
        seen: set[str] = set()
        for raw in locations:
            row = _mapping(raw, label="scheduler location")
            name = _string(row.get("locationId") or str(row.get("name", "")).rsplit("/", 1)[-1], label="scheduler location id")
            if name in seen:
                _fail("scheduler location census repeats a region")
            seen.add(name)
            values = self._json([
                "gcloud", "scheduler", "jobs", "list", "--location", name,
                "--project", self.project, "--format=json",
            ])
            rows.extend(_sequence(values, label=f"scheduler jobs[{name}]"))
        return rows, True

    def observe_cloud_build_image(
        self, *, build_id: str, immutable_image: str, source_commit_sha: str,
    ) -> dict[str, object]:
        """Build one observation solely from authenticated Cloud Build data."""
        build_id = _string(build_id, label="runtime build id")
        if (
            re.fullmatch(r"[0-9A-Za-z-]{8,128}", build_id) is None
            or re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", immutable_image) is None
            or re.fullmatch(r"[0-9a-f]{40}", source_commit_sha) is None
        ):
            _fail("runtime build/image/commit request differs")
        raw = _mapping(self._json([
            "gcloud", "builds", "describe", build_id,
            "--project", self.project, "--format=json",
        ]), label="runtime Cloud Build observation")
        if raw.get("id") != build_id or raw.get("status") != "SUCCESS":
            _fail("runtime Cloud Build is not exact terminal success")
        expected_name, expected_digest = immutable_image.rsplit("@", 1)
        images = _sequence(
            _mapping(raw.get("results", {}), label="build results").get("images", []),
            label="build result images",
        )
        image_match = False
        for raw_image in images:
            row = _mapping(raw_image, label="build result image")
            name = str(row.get("name", ""))
            digest = str(row.get("digest", ""))
            if digest != expected_digest:
                continue
            names = {name, name.rsplit("@", 1)[0], name.rsplit(":", 1)[0]}
            if expected_name in names:
                image_match = True
        substitutions = _mapping(
            raw.get("substitutions", {}), label="build substitutions"
        )
        observed_commits = {
            str(value) for key, value in substitutions.items()
            if str(key) in {
                "COMMIT_SHA", "REVISION_ID", "SOURCE_COMMIT_SHA",
                "_SOURCE_COMMIT_SHA",
            }
        }
        repo_source = raw.get("source", {})
        if isinstance(repo_source, Mapping):
            nested = repo_source.get("repoSource", {})
            if isinstance(nested, Mapping) and nested.get("commitSha"):
                observed_commits.add(str(nested["commitSha"]))
        resource_name = str(raw.get("name", ""))
        if not resource_name.endswith(f"/builds/{build_id}"):
            resource_name = f"projects/{self.project}/builds/{build_id}"
        if not image_match or source_commit_sha not in observed_commits:
            _fail("authenticated Cloud Build image/commit observation differs")
        return {
            "schema_version": release.PROVIDER_IMAGE_OBSERVATION_SCHEMA,
            "provider": "google-cloud-build",
            "observation_kind": "cloud-build-image",
            "resource_name": resource_name,
            "build_id": build_id,
            "job_name": None,
            "job_uid": None,
            "execution_id": None,
            "source_commit_sha": source_commit_sha,
            "immutable_image": immutable_image,
            "provider_observed": True,
        }

    def authenticate_runtime_image_authority(
        self, authority: Mapping[str, object],
    ) -> dict[str, object]:
        """Re-observe the immutable image from authenticated Cloud Build data.

        A schema-valid JSON supplied by a caller is not provider evidence.  The
        controller therefore accepts an initial authority only when its nested
        build observation can be reconstructed from ``gcloud builds describe``.
        Job and execution image observations are made again after each update
        and launch by the phase validators.
        """
        retained = release.validate_provider_runtime_image_authority_v1(authority)
        observation = _mapping(
            retained["provider_observation"], label="provider image observation"
        )
        if (
            observation.get("provider") != "google-cloud-build"
            or observation.get("observation_kind") != "cloud-build-image"
            or any(observation.get(key) is not None for key in (
                "job_name", "job_uid", "execution_id",
            ))
        ):
            _fail("initial runtime authority must be a Cloud Build image observation")
        observed = self.observe_cloud_build_image(
            build_id=str(observation["build_id"]),
            immutable_image=str(observation["immutable_image"]),
            source_commit_sha=str(observation["source_commit_sha"]),
        )
        if observed != observation:
            _fail("authenticated Cloud Build observation differs from authority")
        return observed

    @staticmethod
    def _environment_flag(environment: Mapping[str, object]) -> str:
        for key, value in environment.items():
            if "|" in str(key) or "|" in str(value) or "=" in str(key):
                _fail("provider environment cannot be encoded safely")
        return "^|^" + "|".join(
            f"{key}={value}" for key, value in sorted(environment.items())
        )

    def update_job(self, projection: Mapping[str, object]) -> dict[str, object]:
        job = _string(projection.get("job_name"), label="configured job")
        if _JOB.fullmatch(job) is None:
            _fail("configured job differs")
        command = _sequence(projection.get("command"), label="job command")
        args = _sequence(projection.get("args"), label="job args")
        if len(command) != 1:
            _fail("configured job command differs")
        self._run([
            "gcloud", "run", "jobs", "update", job,
            "--project", self.project, "--region", self.region,
            "--image", str(projection["immutable_image"]),
            "--tasks", str(projection["task_count"]),
            "--parallelism", str(projection["parallelism"]),
            "--max-retries", "0",
            "--task-timeout", f"{projection['timeout_seconds']}s",
            "--cpu", str(projection["cpu"]),
            "--memory", str(projection["memory"]),
            "--service-account", str(projection["service_account"]),
            "--command", str(command[0]),
            f"--args={','.join(str(value) for value in args)}",
            "--set-env-vars", self._environment_flag(
                _mapping(projection.get("environment"), label="job environment")
            ),
            "--clear-volumes", "--quiet", "--format=json",
        ])
        return self.describe_job(job)

    def execute_job(self, job_name: str) -> str:
        if _JOB.fullmatch(job_name) is None:
            _fail("executed job differs")
        raw = self._run([
            "gcloud", "run", "jobs", "execute", job_name,
            "--project", self.project, "--region", self.region,
            "--async", "--format=value(metadata.name)",
        ], stdout_limit=1024)
        execution = raw.decode("utf-8").strip().rsplit("/", 1)[-1]
        if _EXECUTION.fullmatch(execution) is None or not execution.startswith(
            f"{job_name}-"
        ):
            _fail("provider execution submission response differs")
        return execution

    def describe_execution(self, execution: str) -> dict[str, object]:
        if _EXECUTION.fullmatch(execution) is None:
            _fail("described execution differs")
        return _mapping(self._json([
            "gcloud", "run", "jobs", "executions", "describe", execution,
            "--project", self.project, "--region", self.region, "--format=json",
        ]), label="provider execution description")

    def describe_task(self, execution: str, task_index: int) -> dict[str, object]:
        if _EXECUTION.fullmatch(execution) is None or type(task_index) is not int or task_index < 0:
            _fail("described task differs")
        task = f"{execution}-task{task_index}"
        return _mapping(self._json([
            "gcloud", "run", "jobs", "executions", "tasks", "describe", task,
            "--project", self.project, "--region", self.region, "--format=json",
        ]), label="provider task description")

    def restore_job(self, exported_job: bytes) -> dict[str, object]:
        if type(exported_job) is not bytes or not exported_job:
            _fail("restored export bytes differ")
        with tempfile.TemporaryDirectory(prefix="r6-v2-job-restore-") as raw:
            path = Path(raw) / "job-before.export.yaml"
            path.write_bytes(exported_job)
            self._run([
                "gcloud", "run", "jobs", "replace", str(path),
                "--project", self.project, "--region", self.region,
                "--quiet", "--format=json",
            ])
        try:
            parsed = exported_job.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(
                "restored export is not UTF-8"
            ) from exc
        match = re.search(r"(?m)^\s*name:\s*([a-z][a-z0-9-]{1,62})\s*$", parsed)
        if match is None:
            _fail("restored export does not name one job")
        return self.describe_job(match.group(1))


def _encode_identity(value: object) -> str:
    raw = _canonical(_identity(value, label="encoded identity"))
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_identity(value: object) -> dict[str, object]:
    text = _string(value, label="encoded controller manifest identity")
    try:
        raw = base64.b64decode(text, altchars=b"-_", validate=True)
        parsed = batch.parse_canonical_json_bytes(raw, label="controller identity")
    except Exception as exc:
        raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(
            "encoded controller manifest identity differs"
        ) from exc
    return _identity(parsed, label="controller manifest identity")


def _on_image_runtime_authority(
    *, repository_root: Path, expected: Mapping[str, object],
) -> dict[str, object]:
    """Load the fixed build-overlay receipt; GCS/caller substitutes are illegal."""
    try:
        root = repository_root.resolve(strict=True)
        path = root / controller.ON_IMAGE_RUNTIME_AUTHORITY_RELATIVE_PATH
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(
            "fixed on-image runtime authority is absent"
        ) from exc
    if resolved != path or not resolved.is_file() or resolved.is_symlink():
        _fail("fixed on-image runtime authority path differs")
    raw = resolved.read_bytes()
    if not raw:
        _fail("fixed on-image runtime authority framing differs")
    try:
        value = batch.parse_canonical_json_bytes(
            raw, label="fixed on-image runtime authority"
        )
    except batch.CorpusParametricBatchError as exc:
        raise RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error(str(exc)) from exc
    retained = release.validate_embedded_runtime_authority_v1(value)
    if raw != batch.canonical_json_bytes(retained):
        _fail("fixed on-image runtime authority must be exact canonical JSON")
    expected_retained = release.validate_embedded_runtime_authority_v1(expected)
    if retained != expected_retained:
        _fail("fixed on-image runtime authority differs from provider authority")
    return retained


def _analysis_manifest(
    storage: ExactObjectStore, manifest: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    uri = f"{manifest['analysis_output_prefix']}execution-manifest.json"
    resolved = storage.resolve_optional(uri)
    if resolved is None:
        _fail("canonical analysis manifest is absent")
    return release.reopen_manifest_v2(
        storage=storage, manifest_identity=resolved[0].as_dict()
    )


def _resolve_required(
    storage: ExactObjectStore, uri: str, *, label: str,
) -> dict[str, object]:
    resolved = storage.resolve_optional(uri)
    if resolved is None:
        _fail(f"{label} is absent")
    return resolved[0].as_dict()


def science_gate_v1(
    *, storage: ExactObjectStore, manifest: Mapping[str, object], phase: str,
) -> dict[str, object]:
    """Exact-open the phase's canonical outcome-blind scientific artifact."""
    retained = controller.validate_controller_manifest_v1(manifest)
    analysis_identity, analysis, _, _ = _analysis_manifest(storage, retained)
    members = _sequence(analysis["source_members"], label="analysis source members")
    if phase == "prepare":
        detail = {
            "analysis_manifest_identity": analysis_identity,
            "execution_manifest_sha256": analysis["execution_manifest_sha256"],
            "source_slate_count": len(members),
        }
    elif phase in {"task0-worker", "full-workers"}:
        ordinals = [0] if phase == "task0-worker" else list(range(54))
        workers: list[dict[str, object]] = []
        worker_processes: list[tuple[object, ...]] = []
        for ordinal in ordinals:
            member = _mapping(members[ordinal], label=f"source member[{ordinal}]")
            identity = _resolve_required(
                storage, str(member["worker_result_uri"]),
                label=f"worker[{ordinal}]",
            )
            worker_identity, worker = release._reopen_worker_result(  # noqa: SLF001
                storage=storage, identity=identity,
                manifest_identity=analysis_identity, manifest=analysis,
                source_ordinal=ordinal,
            )
            worker_processes.append(
                release._process_instance_key(  # noqa: SLF001
                    release._validate_process_runtime(  # noqa: SLF001
                        worker["worker_process_runtime"], role="ordinal-worker"
                    )
                )
            )
            workers.append({
                "source_ordinal": ordinal, "worker_result_identity": worker_identity,
                "worker_result_sha256": worker["worker_result_sha256"],
            })
        if len(worker_processes) != len(set(worker_processes)):
            _fail("worker phase reused a measured process instance")
        detail = {
            "analysis_manifest_identity": analysis_identity,
            "worker_count": len(workers), "workers_sha256": batch.canonical_sha256(workers),
            "worker_processes_pairwise_distinct": True,
        }
    elif phase in {"task0-verifier", "full-verifiers"}:
        ordinals = [0] if phase == "task0-verifier" else list(range(54))
        acceptances: list[dict[str, object]] = []
        verifier_processes: list[tuple[object, ...]] = []
        for ordinal in ordinals:
            member = _mapping(members[ordinal], label=f"source member[{ordinal}]")
            identity = _resolve_required(
                storage, str(member["acceptance_uri"]),
                label=f"acceptance[{ordinal}]",
            )
            acceptance_identity, acceptance, _, _ = release._reopen_acceptance(  # noqa: SLF001
                storage=storage, identity=identity,
                manifest_identity=analysis_identity, manifest=analysis,
                source_ordinal=ordinal,
            )
            verifier_processes.append(
                release._process_instance_key(  # noqa: SLF001
                    release._validate_process_runtime(  # noqa: SLF001
                        acceptance["verifier_process_runtime"],
                        role="independent-verifier",
                    )
                )
            )
            acceptances.append({
                "source_ordinal": ordinal,
                "acceptance_identity": acceptance_identity,
                "slate_acceptance_sha256": acceptance["slate_acceptance_sha256"],
            })
        if len(verifier_processes) != len(set(verifier_processes)):
            _fail("verifier phase reused a measured process instance")
        detail = {
            "analysis_manifest_identity": analysis_identity,
            "accepted_slate_count": len(acceptances),
            "acceptances_sha256": batch.canonical_sha256(acceptances),
            "worker_verifier_processes_distinct": True,
            "verifier_processes_pairwise_distinct": True,
        }
    elif phase == "finish":
        root_identity = _resolve_required(
            storage, str(analysis["terminal_root_uri"]), label="terminal root"
        )
        retained_root, root = release.reopen_terminal_root_v2(
            storage=storage, terminal_root_identity=root_identity,
        )
        detail = {
            "analysis_manifest_identity": analysis_identity,
            "terminal_root_identity": retained_root,
            "accepted_root_sha256": root["accepted_root_sha256"],
            "accepted_slate_count": root["accepted_slate_count"],
            "rank_80_book_count": root["rank_80_book_count"],
            "prefix_count": root["prefix_count"],
        }
    else:
        _fail("science gate phase differs")
    gate = {
        "schema_version": "corpus-r6-v2-one-job-phase-science-gate/v1",
        "phase": phase,
        "passed": True,
        **detail,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "automatic_retry_licensed": False,
    }
    controller.reject_outcome_carriers_v1(gate, label="science gate")
    gate["science_gate_sha256"] = batch.canonical_sha256(gate)
    return gate


def publish_runtime_authority_v1(
    *, storage: ExactObjectStore, provider: GCloudRunOneJobProviderV1,
    controller_output_prefix: str, source_embedded_identity: object,
    build_id: str, immutable_image: str, source_commit_sha: str,
) -> dict[str, object]:
    """Construct authority only from an authenticated provider observation."""
    prefix = controller.output_prefix_v1(controller_output_prefix)
    _, embedded = _read_json(
        storage, source_embedded_identity,
        label="source embedded runtime authority",
    )
    embedded = release.validate_embedded_runtime_authority_v1(embedded)
    if embedded["source_commit_sha"] != source_commit_sha:
        _fail("source embedded runtime authority commit differs")
    observation = provider.observe_cloud_build_image(
        build_id=build_id, immutable_image=immutable_image,
        source_commit_sha=source_commit_sha,
    )
    authority = release.build_provider_runtime_image_authority_v1(
        provider_observation=observation,
        embedded_runtime_authority=embedded,
    )
    # Controlled namespace publication: snapshot accepts no authority URI other
    # than these exact two names.
    embedded_identity = controller.publish_json_v1(
        storage=storage,
        uri=f"{prefix}runtime/embedded-runtime-authority.json",
        value=embedded, label="controlled embedded runtime authority",
    )
    authority_identity = controller.publish_json_v1(
        storage=storage,
        uri=f"{prefix}runtime/provider-image-authority.json",
        value=authority, label="controlled provider image authority",
    )
    authenticated = provider.authenticate_runtime_image_authority(authority)
    if authenticated != observation:
        _fail("published provider runtime authority authentication differs")
    return {
        "schema_version": "corpus-r6-v2-provider-runtime-authority-published/v1",
        "provider_runtime_image_authority_identity": authority_identity,
        "provider_runtime_image_authority_sha256": authority[
            "provider_runtime_image_authority_sha256"
        ],
        "embedded_runtime_authority_identity": embedded_identity,
        "embedded_runtime_authority_sha256": embedded[
            "runtime_authority_sha256"
        ],
        "authenticated_provider_observation_sha256": batch.canonical_sha256(
            observation
        ),
        "provider_observation_constructed_by_controller": True,
        "caller_provider_observation_accepted": False,
        "provider_job_mutation_performed": False,
        "uses_realized_outcomes": False,
        "automatic_retry_licensed": False,
    }


def _phase_acceptance(
    *, storage: ExactObjectStore, manifest: Mapping[str, object], phase: str,
) -> tuple[dict[str, object], dict[str, object]]:
    uri = controller.phase_uri_v1(manifest, phase, "acceptance.json")
    resolved = storage.resolve_optional(uri)
    if resolved is None:
        _fail(f"controller phase {phase} is not accepted")
    identity, value = _read_json(
        storage, resolved[0].as_dict(), label=f"phase {phase} acceptance"
    )
    body = dict(value)
    digest = body.pop("phase_acceptance_sha256", None)
    status = _mapping(value.get("phase_status"), label=f"{phase} phase status")
    status_body = dict(status)
    status_digest = status_body.pop("phase_status_sha256", None)
    gate = _mapping(value.get("science_gate"), label=f"{phase} science gate")
    if (
        value.get("schema_version") != controller.PHASE_ACCEPTANCE_SCHEMA
        or value.get("publication_mode") != controller.PUBLICATION_MODE
        or value.get("status") != "accepted"
        or value.get("phase") != phase or value.get("accepted") is not True
        or digest != batch.canonical_sha256(body)
        or value.get("run_id") != manifest["run_id"]
        or value.get("controller_manifest_sha256")
        != manifest["controller_manifest_sha256"]
        or status_digest != batch.canonical_sha256(status_body)
        or value.get("phase_status_sha256") != status_digest
        or value.get("science_gate_sha256") != batch.canonical_sha256(gate)
        or value.get("provider_mutation_complete") is not True
        or value.get("provider_observed_immutable_image") is not True
        or value.get("zero_retries_verified") is not True
        or value.get("automatic_retry_licensed") is not False
        or value.get("uses_realized_outcomes") is not False
        or value.get("outcome_authority") is not False
        or value.get("historical_scoring_licensed") is not False
    ):
        _fail(f"controller phase {phase} acceptance differs")
    return identity, value


def _predecessor_acceptance(
    *, storage: ExactObjectStore, manifest: Mapping[str, object], phase: str,
) -> dict[str, object] | None:
    ordinal = controller.PHASES.index(phase)
    if ordinal == 0:
        return None
    identity, acceptance = _phase_acceptance(
        storage=storage, manifest=manifest, phase=controller.PHASES[ordinal - 1],
    )
    expected_gate = science_gate_v1(
        storage=storage, manifest=manifest, phase=controller.PHASES[ordinal - 1],
    )
    if acceptance.get("science_gate") != expected_gate:
        _fail("predecessor phase science gate replay differs")
    return identity


def snapshot_controller_v1(
    *, storage: ExactObjectStore, provider: GCloudRunOneJobProviderV1,
    run_id: str, controller_output_prefix: str, analysis_output_prefix: str,
    job_name: str, job_uid: str, panel_index_identity: object,
    lane_terminal_identities: Sequence[object],
    matchup_source_release_identity: object,
    runtime_image_authority_identity: object,
    embedded_runtime_authority_identity: object,
) -> dict[str, object]:
    prefix = controller.output_prefix_v1(controller_output_prefix)
    _, image_authority = _read_json(
        storage, runtime_image_authority_identity,
        label="provider runtime image authority",
    )
    observed = provider.authenticate_runtime_image_authority(image_authority)
    if observed != image_authority.get("provider_observation"):
        _fail("authenticated runtime image observation differs from authority")
    _, embedded_authority = _read_json(
        storage, embedded_runtime_authority_identity,
        label="embedded runtime authority",
    )
    job = provider.describe_job(job_name)
    exported = provider.export_job(job_name)
    executions = provider.list_executions(job_name)
    schedulers, complete = provider.scheduler_census_all_regions()
    snapshot = controller.build_job_snapshot_v1(
        job=job, exported_job=exported, executions=executions,
        schedulers=schedulers, all_regions_complete=complete,
        job_name=job_name, job_uid=job_uid,
    )
    snapshot_identity = controller.publish_json_v1(
        storage=storage, uri=f"{prefix}job-before.json", value=snapshot,
        label="job snapshot",
    )
    export_identity = _publish_raw(
        storage, uri=f"{prefix}job-before.export.yaml", raw=exported,
        label="job export",
    )
    manifest = controller.build_controller_manifest_v1(
        run_id=run_id, controller_output_prefix=prefix,
        analysis_output_prefix=analysis_output_prefix,
        project_id=provider.project, region=provider.region,
        job_snapshot_identity=snapshot_identity, job_snapshot=snapshot,
        job_export_identity=export_identity,
        panel_index_identity=panel_index_identity,
        lane_terminal_identities=lane_terminal_identities,
        matchup_source_release_identity=matchup_source_release_identity,
        runtime_image_authority_identity=runtime_image_authority_identity,
        runtime_image_authority=image_authority,
        embedded_runtime_authority_identity=embedded_runtime_authority_identity,
        embedded_runtime_authority=embedded_authority,
    )
    manifest_identity = controller.publish_json_v1(
        storage=storage, uri=f"{prefix}controller-manifest.json",
        value=manifest, label="controller manifest",
    )
    controller.reopen_controller_manifest_v1(
        storage=storage, manifest_identity=manifest_identity,
    )
    return {
        "schema_version": "corpus-r6-v2-one-job-controller-prepared/v1",
        "controller_manifest_identity": manifest_identity,
        "controller_manifest_sha256": manifest["controller_manifest_sha256"],
        "job_snapshot_identity": snapshot_identity,
        "job_export_identity": export_identity,
        "provider_job_mutation_performed": False,
        "uses_realized_outcomes": False,
        "automatic_retry_licensed": False,
    }


def launch_phase_v1(
    *, storage: controller.FreshClaimStore,
    provider: GCloudRunOneJobProviderV1, manifest_identity: object,
    phase: str,
) -> dict[str, object]:
    retained_identity, manifest = controller.reopen_controller_manifest_v1(
        storage=storage, manifest_identity=manifest_identity,
    )
    if phase not in controller.PHASES:
        _fail("launched phase differs")
    predecessor = _predecessor_acceptance(
        storage=storage, manifest=manifest, phase=phase,
    )
    if storage.resolve_optional(
        controller.phase_uri_v1(manifest, phase, "execution-binding.json")
    ) is not None:
        _fail("phase already has an execution binding; relaunch is forbidden")
    controller.validate_no_active_executions_v1(
        provider.list_executions(str(manifest["job_name"])),
        job_name=str(manifest["job_name"]),
    )
    encoded = _encode_identity(retained_identity)
    projection = controller.phase_job_projection_v1(
        manifest=manifest, manifest_identity_b64=encoded, phase=phase,
    )
    configure_claim = controller.build_mutation_claim_v1(
        manifest=manifest, manifest_identity=retained_identity, phase=phase,
        operation="configure", predecessor_acceptance_identity=predecessor,
    )
    configure_claim_identity = controller.publish_fresh_claim_v1(
        storage=storage,
        uri=controller.phase_uri_v1(manifest, phase, "configure-claim.json"),
        value=configure_claim, label=f"{phase} configure claim",
    )
    configured = provider.update_job(projection)
    controller.validate_phase_job_observation_v1(
        configured, manifest=manifest, manifest_identity_b64=encoded, phase=phase,
    )
    launch_claim = controller.build_mutation_claim_v1(
        manifest=manifest, manifest_identity=retained_identity, phase=phase,
        operation="launch", predecessor_acceptance_identity=predecessor,
    )
    launch_claim_identity = controller.publish_fresh_claim_v1(
        storage=storage,
        uri=controller.phase_uri_v1(manifest, phase, "launch-claim.json"),
        value=launch_claim, label=f"{phase} launch claim",
    )
    execution_name = provider.execute_job(str(manifest["job_name"]))
    execution = provider.describe_execution(execution_name)
    binding = controller.build_execution_binding_v1(
        manifest=manifest, manifest_identity=retained_identity, phase=phase,
        configure_claim_identity=configure_claim_identity,
        launch_claim_identity=launch_claim_identity, configured_job=configured,
        execution=execution,
        manifest_identity_b64=encoded,
    )
    binding_identity = controller.publish_json_v1(
        storage=storage,
        uri=controller.phase_uri_v1(manifest, phase, "execution-binding.json"),
        value=binding, label=f"{phase} execution binding",
    )
    return {
        "schema_version": "corpus-r6-v2-one-job-phase-launched/v1",
        "phase": phase, "execution_name": execution_name,
        "execution_binding_identity": binding_identity,
        "task_count": controller.PHASE_TASK_COUNTS[phase],
        "maximum_task_retries": 0,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
    }


def phase_status_v1(
    *, storage: ExactObjectStore, provider: GCloudRunOneJobProviderV1,
    manifest_identity: object, phase: str,
) -> dict[str, object]:
    retained_identity, manifest = controller.reopen_controller_manifest_v1(
        storage=storage, manifest_identity=manifest_identity,
    )
    binding_uri = controller.phase_uri_v1(
        manifest, phase, "execution-binding.json"
    )
    binding_identity = _resolve_required(storage, binding_uri, label="execution binding")
    _, binding = _read_json(storage, binding_identity, label="execution binding")
    execution_name = _string(binding.get("execution_name"), label="bound execution")
    execution = provider.describe_execution(execution_name)
    tasks = [
        provider.describe_task(execution_name, ordinal)
        for ordinal in range(controller.PHASE_TASK_COUNTS[phase])
    ]
    return controller.build_phase_status_v1(
        manifest=manifest, manifest_identity=retained_identity, phase=phase,
        binding_identity=binding_identity, binding=binding,
        execution=execution, task_observations=tasks,
        manifest_identity_b64=_encode_identity(retained_identity),
    )


def accept_phase_v1(
    *, storage: ExactObjectStore, provider: GCloudRunOneJobProviderV1,
    manifest_identity: object, phase: str,
) -> dict[str, object]:
    retained_identity, manifest = controller.reopen_controller_manifest_v1(
        storage=storage, manifest_identity=manifest_identity,
    )
    predecessor = _predecessor_acceptance(
        storage=storage, manifest=manifest, phase=phase,
    )
    status = phase_status_v1(
        storage=storage, provider=provider,
        manifest_identity=retained_identity, phase=phase,
    )
    gate = science_gate_v1(storage=storage, manifest=manifest, phase=phase)
    acceptance = controller.build_phase_acceptance_v1(
        manifest=manifest, manifest_identity=retained_identity,
        phase_status=status, predecessor_identity=predecessor,
        science_gate=gate,
    )
    identity = controller.publish_json_v1(
        storage=storage,
        uri=controller.phase_uri_v1(manifest, phase, "acceptance.json"),
        value=acceptance, label=f"{phase} acceptance",
    )
    return {
        "schema_version": "corpus-r6-v2-one-job-phase-accepted/v1",
        "phase": phase, "phase_acceptance_identity": identity,
        "phase_acceptance_sha256": acceptance["phase_acceptance_sha256"],
        "science_gate_sha256": gate["science_gate_sha256"],
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
    }


def independent_reopen_v1(
    *, storage: ExactObjectStore, manifest_identity: object,
) -> dict[str, object]:
    retained_identity, manifest = controller.reopen_controller_manifest_v1(
        storage=storage, manifest_identity=manifest_identity,
    )
    predecessor: dict[str, object] | None = None
    acceptances: list[dict[str, object]] = []
    execution_names: list[str] = []
    encoded = _encode_identity(retained_identity)
    for phase in controller.PHASES:
        identity, acceptance = _phase_acceptance(
            storage=storage, manifest=manifest, phase=phase,
        )
        gate = science_gate_v1(storage=storage, manifest=manifest, phase=phase)
        status = _mapping(acceptance.get("phase_status"), label="phase status")
        binding_identity = _identity(
            status.get("binding_identity"), label="execution binding"
        )
        retained_binding_identity, binding = _read_json(
            storage, binding_identity, label=f"{phase} execution binding",
        )
        if retained_binding_identity != binding_identity:
            _fail(f"independent execution binding identity differs at {phase}")
        binding = controller.validate_execution_binding_v1(
            binding, manifest=manifest, manifest_identity=retained_identity,
            phase=phase, manifest_identity_b64=encoded,
        )
        for operation, field in (
            ("configure", "configure_claim_identity"),
            ("launch", "launch_claim_identity"),
        ):
            claim_identity = _identity(
                binding.get(field), label=f"{phase} {operation} claim"
            )
            if claim_identity["uri"] != controller.phase_uri_v1(
                manifest, phase, f"{operation}-claim.json"
            ):
                _fail(f"independent {operation} claim URI differs at {phase}")
            retained_claim_identity, claim = _read_json(
                storage, claim_identity, label=f"{phase} {operation} claim",
            )
            if retained_claim_identity != claim_identity:
                _fail(f"independent {operation} claim identity differs at {phase}")
            controller.validate_mutation_claim_v1(
                claim, manifest=manifest, manifest_identity=retained_identity,
                phase=phase, operation=operation,
                predecessor_acceptance_identity=predecessor,
            )
        status = controller.validate_phase_status_v1(
            status, manifest=manifest, manifest_identity=retained_identity,
            phase=phase, binding=binding, binding_identity=binding_identity,
            manifest_identity_b64=encoded,
        )
        if (
            acceptance.get("manifest_identity") != retained_identity
            or acceptance.get("predecessor_acceptance_identity") != predecessor
            or acceptance.get("phase_status_sha256")
            != status["phase_status_sha256"]
            or acceptance.get("science_gate") != gate
            or acceptance.get("science_gate_sha256")
            != batch.canonical_sha256(gate)
            or acceptance.get("zero_retries_verified") is not True
            or acceptance.get("provider_observed_immutable_image") is not True
        ):
            _fail(f"independent phase replay differs at {phase}")
        execution_names.append(str(binding["execution_name"]))
        acceptances.append({
            "phase": phase, "acceptance_identity": identity,
            "phase_acceptance_sha256": acceptance["phase_acceptance_sha256"],
            "science_gate_sha256": gate["science_gate_sha256"],
        })
        predecessor = identity
    if len(execution_names) != len(set(execution_names)):
        _fail("independent replay found a reused phase execution")
    finish_gate = science_gate_v1(
        storage=storage, manifest=manifest, phase="finish"
    )
    result = {
        "schema_version": controller.REOPEN_SCHEMA,
        "complete": True,
        "status": "independently-reopened",
        "manifest_identity": retained_identity,
        "controller_manifest_sha256": manifest["controller_manifest_sha256"],
        "phase_count": len(acceptances),
        "ordered_phase_acceptances": acceptances,
        "ordered_phase_acceptances_sha256": batch.canonical_sha256(acceptances),
        "terminal_root_identity": finish_gate["terminal_root_identity"],
        "accepted_root_sha256": finish_gate["accepted_root_sha256"],
        "accepted_slate_count": finish_gate["accepted_slate_count"],
        "rank_80_book_count": finish_gate["rank_80_book_count"],
        "prefix_count": finish_gate["prefix_count"],
        "provider_job_mutation_performed": False,
        "provider_status_read_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "automatic_retry_licensed": False,
    }
    result["independent_reopen_sha256"] = batch.canonical_sha256(result)
    return result


def restore_job_v1(
    *, storage: controller.FreshClaimStore,
    provider: GCloudRunOneJobProviderV1, manifest_identity: object,
) -> dict[str, object]:
    retained_identity, manifest = controller.reopen_controller_manifest_v1(
        storage=storage, manifest_identity=manifest_identity,
    )
    reopened = independent_reopen_v1(
        storage=storage, manifest_identity=retained_identity,
    )
    controller.validate_no_active_executions_v1(
        provider.list_executions(str(manifest["job_name"])),
        job_name=str(manifest["job_name"]),
    )
    _, snapshot = _read_json(
        storage, manifest["job_snapshot_identity"], label="job snapshot"
    )
    _, exported = controller._read_raw(  # noqa: SLF001
        storage, manifest["job_export_identity"], label="job export"
    )
    current = provider.describe_job(str(manifest["job_name"]))
    _, metadata, _, _ = controller._job_parts(  # noqa: SLF001
        current, expected_job=str(manifest["job_name"]),
        expected_uid=str(manifest["job_uid"]),
    )
    claim = controller.build_mutation_claim_v1(
        manifest=manifest, manifest_identity=retained_identity,
        phase="restore", operation="restore",
        predecessor_acceptance_identity=reopened[
            "ordered_phase_acceptances"
        ][-1]["acceptance_identity"],
    )
    claim_identity = controller.publish_fresh_claim_v1(
        storage=storage,
        uri=controller.phase_uri_v1(manifest, "restore", "restore-claim.json"),
        value=claim, label="job restore claim",
    )
    restored = provider.restore_job(exported)
    proof = controller.validate_restored_job_v1(
        snapshot=snapshot, restored_job=restored,
    )
    receipt = {
        "schema_version": controller.RESTORATION_SCHEMA,
        "status": "restored",
        "restored": True,
        "manifest_identity": retained_identity,
        "controller_manifest_sha256": manifest["controller_manifest_sha256"],
        "restore_claim_identity": claim_identity,
        "independent_reopen_sha256": reopened["independent_reopen_sha256"],
        "job_before_uid": snapshot["job_uid"],
        "job_uid_before_restore": metadata["uid"],
        "restored_job": proof,
        "exact_job_uid_preserved": True,
        "exact_stable_configuration_restored": True,
        "provider_mutation_claim_created_before_restore": True,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
    }
    receipt["restoration_sha256"] = batch.canonical_sha256(receipt)
    identity = controller.publish_json_v1(
        storage=storage,
        uri=controller.phase_uri_v1(manifest, "restore", "restoration.json"),
        value=receipt, label="job restoration",
    )
    return {**receipt, "restoration_identity": identity}


def dispatch_v1(
    *, storage: ExactObjectStore, environment: Mapping[str, str],
    repository_root: Path,
) -> dict[str, object]:
    """Execute exactly one provider-bound phase task inside Cloud Run."""
    manifest_identity = _decode_identity(
        environment.get(controller.MANIFEST_IDENTITY_ENV)
    )
    phase = _string(environment.get(controller.PHASE_ENV), label="dispatch phase")
    retained_identity, manifest = controller.reopen_controller_manifest_v1(
        storage=storage, manifest_identity=manifest_identity,
    )
    if phase not in controller.PHASES:
        _fail("dispatch phase differs")
    raw_index = environment.get(CLOUD_RUN_TASK_INDEX)
    if type(raw_index) is not str or _TASK_INDEX.fullmatch(raw_index) is None:
        _fail("CLOUD_RUN_TASK_INDEX must be one canonical decimal integer")
    task_index = int(raw_index)
    count = controller.PHASE_TASK_COUNTS[phase]
    if not 0 <= task_index < count:
        _fail("CLOUD_RUN_TASK_INDEX lies outside the exact phase task lattice")
    if phase in {"prepare", "task0-worker", "task0-verifier", "finish"} and task_index != 0:
        _fail("single-task controller phase must execute task index zero")
    _, provider_authority = _read_json(
        storage, manifest["runtime_image_authority_identity"],
        label="provider runtime image authority",
    )
    provider_authority = release.validate_provider_runtime_image_authority_v1(
        provider_authority
    )
    embedded = _on_image_runtime_authority(
        repository_root=repository_root,
        expected=_mapping(
            provider_authority["embedded_runtime_authority"],
            label="provider embedded runtime authority",
        ),
    )
    if phase == "prepare":
        return release.prepare_release_v2(
            storage=storage,
            panel_index_identity=manifest["panel_index_identity"],
            lane_terminal_identities=manifest["lane_terminal_identities"],
            matchup_source_release_identity=manifest[
                "matchup_source_release_identity"
            ],
            runtime_image_authority_identity=manifest[
                "runtime_image_authority_identity"
            ],
            output_prefix=str(manifest["analysis_output_prefix"]),
        )
    analysis_identity, _, _, _ = _analysis_manifest(storage, manifest)
    if phase in {"task0-worker", "full-workers"}:
        source_ordinal = 0 if phase == "task0-worker" else task_index
        return release.run_worker_v2(
            storage=storage, manifest_identity=analysis_identity,
            source_ordinal=source_ordinal, repository_root=repository_root,
        )
    if phase in {"task0-verifier", "full-verifiers"}:
        source_ordinal = 0 if phase == "task0-verifier" else task_index
        return release.verify_worker_v2(
            storage=storage, manifest_identity=analysis_identity,
            source_ordinal=source_ordinal, repository_root=repository_root,
        )
    if phase == "finish":
        return release.finish_release_v2(
            storage=storage, manifest_identity=analysis_identity,
        )
    _fail("dispatch phase is unregistered")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--region")
    commands = parser.add_subparsers(dest="command", required=True)

    runtime = commands.add_parser("publish-runtime-authority")
    runtime.add_argument("--controller-output-prefix", required=True)
    runtime.add_argument(
        "--source-embedded-runtime-authority-identity", type=Path, required=True
    )
    runtime.add_argument("--build-id", required=True)
    runtime.add_argument("--immutable-image", required=True)
    runtime.add_argument("--source-commit", required=True)
    runtime.add_argument("--execute", action="store_true")

    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--run-id", required=True)
    snapshot.add_argument("--controller-output-prefix", required=True)
    snapshot.add_argument("--analysis-output-prefix", required=True)
    snapshot.add_argument("--job-name", required=True)
    snapshot.add_argument("--job-uid", required=True)
    snapshot.add_argument("--panel-index-identity", type=Path, required=True)
    snapshot.add_argument(
        "--lane-terminal-identity", type=Path, action="append", required=True
    )
    snapshot.add_argument(
        "--matchup-source-release-identity", type=Path, required=True
    )
    snapshot.add_argument(
        "--runtime-image-authority-identity", type=Path, required=True
    )
    snapshot.add_argument(
        "--embedded-runtime-authority-identity", type=Path, required=True
    )
    snapshot.add_argument("--execute", action="store_true")

    for name in ("launch", "status", "accept", "reopen", "restore"):
        command = commands.add_parser(name)
        command.add_argument("--controller-manifest-identity", type=Path, required=True)
        if name in {"launch", "status", "accept"}:
            command.add_argument("--phase", choices=controller.PHASES, required=True)
        if name in {"launch", "accept", "restore"}:
            command.add_argument("--execute", action="store_true")

    dispatch = commands.add_parser("dispatch")
    dispatch.add_argument("--repository-root", type=Path, default=Path("/app"))
    dispatch.add_argument("--execute", action="store_true")
    return parser


def _require_execute(args: argparse.Namespace) -> None:
    if getattr(args, "execute", False) is not True:
        _fail(f"{args.command} requires explicit --execute")


def run(
    argv: Sequence[str], *, storage: ExactObjectStore | None = None,
    provider: GCloudRunOneJobProviderV1 | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    environ = os.environ if environment is None else environment
    if args.command == "dispatch":
        _require_execute(args)
        store = storage or FreshClaimGoogleCloudObjectStore(project=args.project)
        return dispatch_v1(
            storage=store, environment=environ,
            repository_root=args.repository_root.resolve(strict=True),
        )
    if args.project is None or args.region is None:
        _fail("host command requires --project and --region")
    if args.command in {
        "publish-runtime-authority", "snapshot", "launch", "accept", "restore",
    }:
        _require_execute(args)
    prepared: dict[str, object] = {}
    if args.command == "publish-runtime-authority":
        prepared["source_embedded_identity"] = _load_identity(
            args.source_embedded_runtime_authority_identity,
            label="source embedded runtime authority",
        )
    elif args.command == "snapshot":
        if len(args.lane_terminal_identity) != 2:
            _fail("snapshot requires exactly two lane terminal identities")
        prepared = {
            "panel_index_identity": _load_identity(
                args.panel_index_identity, label="panel index",
                carrier_fields=("panel_object_identity", "panel_index_identity"),
            ),
            "lane_terminal_identities": [
                _load_identity(
                    path, label=f"lane terminal[{ordinal}]",
                    carrier_fields=("terminal_receipt_identity",),
                )
                for ordinal, path in enumerate(args.lane_terminal_identity)
            ],
            "matchup_source_release_identity": _load_identity(
                args.matchup_source_release_identity,
                label="matchup source release", carrier_fields=("release_identity",),
            ),
            "runtime_image_authority_identity": _load_identity(
                args.runtime_image_authority_identity,
                label="provider runtime image authority",
            ),
            "embedded_runtime_authority_identity": _load_identity(
                args.embedded_runtime_authority_identity,
                label="embedded runtime authority",
            ),
        }
    else:
        prepared["manifest_identity"] = _load_identity(
            args.controller_manifest_identity, label="controller manifest",
            carrier_fields=("controller_manifest_identity",),
        )
    live_provider = provider or GCloudRunOneJobProviderV1(
        project=args.project, region=args.region,
    )
    store = storage or FreshClaimGoogleCloudObjectStore(project=args.project)
    if args.command == "publish-runtime-authority":
        return publish_runtime_authority_v1(
            storage=store, provider=live_provider,
            controller_output_prefix=args.controller_output_prefix,
            source_embedded_identity=prepared["source_embedded_identity"],
            build_id=args.build_id, immutable_image=args.immutable_image,
            source_commit_sha=args.source_commit,
        )
    if args.command == "snapshot":
        return snapshot_controller_v1(
            storage=store, provider=live_provider, run_id=args.run_id,
            controller_output_prefix=args.controller_output_prefix,
            analysis_output_prefix=args.analysis_output_prefix,
            job_name=args.job_name, job_uid=args.job_uid,
            panel_index_identity=prepared["panel_index_identity"],
            lane_terminal_identities=prepared["lane_terminal_identities"],
            matchup_source_release_identity=prepared[
                "matchup_source_release_identity"
            ],
            runtime_image_authority_identity=prepared[
                "runtime_image_authority_identity"
            ],
            embedded_runtime_authority_identity=prepared[
                "embedded_runtime_authority_identity"
            ],
        )
    manifest_identity = prepared["manifest_identity"]
    if args.command == "launch":
        return launch_phase_v1(
            storage=store, provider=live_provider,
            manifest_identity=manifest_identity, phase=args.phase,
        )
    if args.command == "status":
        return phase_status_v1(
            storage=store, provider=live_provider,
            manifest_identity=manifest_identity, phase=args.phase,
        )
    if args.command == "accept":
        return accept_phase_v1(
            storage=store, provider=live_provider,
            manifest_identity=manifest_identity, phase=args.phase,
        )
    if args.command == "reopen":
        return independent_reopen_v1(
            storage=store, manifest_identity=manifest_identity,
        )
    if args.command == "restore":
        return restore_job_v1(
            storage=store, provider=live_provider,
            manifest_identity=manifest_identity,
        )
    _fail("unregistered controller command")


def main(argv: Sequence[str] | None = None) -> int:
    result = run(sys.argv[1:] if argv is None else argv)
    sys.stdout.buffer.write(_canonical(result) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
