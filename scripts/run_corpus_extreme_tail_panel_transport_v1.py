#!/usr/bin/env python3
"""Default-off production transport for the outcome-blind T230 panel.

The scientific CLI remains the only producer of manifests, results,
acceptances and the final release.  This wrapper fixes the production prefix,
materializes digest-postdated evidence, supplies a real Git checkout, journals
every create-once publication by known URI, exposes only mechanics identities,
and never lists GCS or prints support/rank/book fields.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import re
import sys
import tempfile
import time
from typing import Final

from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch

import run_corpus_extreme_tail_panel_v1 as core_cli


ENABLE_ENV: Final = "FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED"


class GCSJournalBackend:
    """Known-object GCS client; this class intentionally has no list method."""

    def __init__(self, client: object) -> None:
        self._client = client

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not isinstance(uri, str) or not uri.startswith("gs://"):
            raise transport.T230TransportError("GCS URI differs")
        bucket, marker, name = uri[5:].partition("/")
        if not marker or not bucket or not name or name.endswith("/") or "//" in name:
            raise transport.T230TransportError("GCS URI differs")
        return bucket, name

    @staticmethod
    def _collision_types() -> tuple[type[BaseException], ...]:
        try:
            from google.api_core.exceptions import AlreadyExists, PreconditionFailed
        except ImportError as exc:  # pragma: no cover - production dependency
            raise transport.T230TransportError(
                "google-api-core is required for GCS transport"
            ) from exc
        return (AlreadyExists, PreconditionFailed)

    def read(self, identity: Mapping[str, object]) -> bytes:
        retained = batch.normalize_object_identity(identity, label="GCS pinned read")
        bucket, name = self._parts(str(retained["uri"]))
        generation = int(str(retained["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        raw = blob.download_as_bytes(if_generation_match=generation)
        if (
            not isinstance(raw, bytes)
            or len(raw) != retained["bytes"]
            or sha256(raw).hexdigest() != retained["sha256"]
        ):
            raise transport.T230TransportError("GCS pinned read differs")
        return raw

    def read_known_uri(self, uri: str) -> tuple[Mapping[str, object], bytes]:
        """Resolve only one predeclared name, then immediately pin generation."""
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.reload()
        except Exception as exc:
            try:
                from google.api_core.exceptions import NotFound
            except ImportError:  # pragma: no cover
                NotFound = ()  # type: ignore[assignment,misc]
            if NotFound and isinstance(exc, NotFound):
                raise FileNotFoundError(uri) from exc
            raise
        if blob.generation is None:
            raise transport.T230TransportError("known GCS object lacks generation")
        generation = int(blob.generation)
        pinned = self._client.bucket(bucket).blob(name, generation=generation)
        raw = pinned.download_as_bytes(if_generation_match=generation)
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        return identity, raw

    def create(self, uri: str, raw: bytes) -> Mapping[str, object]:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type=(
                    "text/plain; charset=utf-8"
                    if uri.endswith(".txt")
                    else "application/json"
                ),
                if_generation_match=0,
            )
        except self._collision_types() as exc:
            raise transport.JournalObjectExists(uri) from exc
        if blob.generation is None:
            raise transport.T230TransportError("GCS create lacks generation")
        generation = int(blob.generation)
        pinned = self._client.bucket(bucket).blob(name, generation=generation)
        retained = pinned.download_as_bytes(if_generation_match=generation)
        if retained != raw:
            raise transport.T230TransportError("GCS create differs on pinned reopen")
        return {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


class JournaledCoreStore:
    """Core CLI store whose every target has an intent and completion."""

    def __init__(
        self,
        backend: GCSJournalBackend,
        *,
        transport_contract_sha256: str,
        transition_prefix: str,
    ) -> None:
        self._backend = backend
        self._publisher = transport.RecoverablePublisher(
            backend, transport_contract_sha256
        )
        self._transition_prefix = transition_prefix

    def read(self, identity: Mapping[str, object]) -> bytes:
        return self._backend.read(identity)

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> Mapping[str, object]:
        suffix = sha256(uri.encode("utf-8")).hexdigest()[:16]
        recovered = self._publisher.publish(
            target_uri=uri,
            raw=raw,
            transition_id=f"{self._transition_prefix}-{suffix}",
        )
        return recovered["target_identity"]


def _identity_from_args(args: argparse.Namespace, stem: str) -> dict[str, object]:
    return batch.normalize_object_identity({
        "uri": getattr(args, f"{stem}_uri"),
        "generation": getattr(args, f"{stem}_generation"),
        "sha256": getattr(args, f"{stem}_sha256"),
        "bytes": getattr(args, f"{stem}_bytes"),
    }, label=stem.replace("_", " "))


def _image_from_arg(value: str) -> dict[str, str]:
    uri, marker, digest = value.rpartition("@")
    if not marker or not uri:
        raise transport.T230TransportError(
            "immutable image must be one URI@sha256:digest"
        )
    return batch.normalize_image_identity(
        {"uri": value, "digest": digest}, label="immutable image"
    )


def _add_identity(
    parser: argparse.ArgumentParser, stem: str, *, required: bool = True
) -> None:
    option = stem.replace("_", "-")
    parser.add_argument(f"--{option}-uri", required=required)
    parser.add_argument(f"--{option}-generation", required=required)
    parser.add_argument(f"--{option}-sha256", required=required)
    parser.add_argument(f"--{option}-bytes", required=required, type=int)


def _write_once(path: Path, raw: bytes) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise transport.T230TransportError("output must be one absolute non-symlink path")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if not path.is_file() or path.is_symlink() or path.read_bytes() != raw:
            raise transport.T230TransportError("create-once local output differs")


def _load(path: Path, *, label: str) -> dict[str, object]:
    return transport.strict_json(path.read_bytes(), label=label)


def _prefreeze_expected_from_files(
    *, source_snapshot_path: Path, immutable_image: str, g0_preflight_path: Path
) -> tuple[dict[str, object], dict[str, str], dict[str, object]]:
    snapshot = transport.validate_source_snapshot_v1(
        _load(source_snapshot_path, label="prefreeze source snapshot")
    )
    image = _image_from_arg(immutable_image)
    preflight = _load(g0_preflight_path, label="prefreeze G0 preflight")
    panel_identity = batch.normalize_object_identity(
        preflight.get("panel_object_identity"),
        label="prefreeze G0 panel object",
    )
    if (
        preflight.get("g0_preflight_passed") is not True
        or preflight.get("source_commit_sha") != snapshot["source_commit_sha"]
        or preflight.get("accepted_slate_count")
        != transport.execution.AUTHORITATIVE_SLATE_COUNT
        or preflight.get("lane_count") != 2
        or panel_identity["uri"] != transport.execution.FROZEN_G0_PANEL_URI
    ):
        raise transport.T230TransportError(
            "prefreeze G0/source snapshot binding differs"
        )
    return snapshot, image, panel_identity


def _acceptances_from_lane_files(
    *,
    backend: GCSJournalBackend,
    contract_hash: str,
    lane_files: Sequence[Path],
) -> list[dict[str, object]]:
    if len(lane_files) != 2:
        raise transport.T230TransportError(
            "finish-panel requires two ordered lane ledger files"
        )
    acceptances: list[dict[str, object]] = []
    for lane_ordinal, path in enumerate(lane_files):
        lane_identity = batch.normalize_object_identity(
            _load(path, label=f"lane ledger identity[{lane_ordinal}]"),
            label="lane ledger identity",
        )
        ledger = transport.reopen_lane_ledger_v1(
            lane_ledger_identity=lane_identity,
            transport_contract_sha256=contract_hash,
            lane_ordinal=lane_ordinal,
            read_exact=backend.read,
        )
        acceptances.extend(
            dict(row["acceptance_identity"])
            for row in ledger["ordered_stage_rows"]
        )
    return acceptances


def _require_execute(args: argparse.Namespace) -> None:
    if args.execute is not True or os.environ.get(ENABLE_ENV) != "1":
        raise transport.T230TransportError(
            f"--execute and {ENABLE_ENV}=1 are required"
        )


def _configure_core_git(snapshot: Mapping[str, object]) -> None:
    adapter = transport.SnapshotGitAdapter(transport.REPOSITORY_ROOT, snapshot)
    # The adapter still calls real Git for HEAD/blob/status; it adds an exact
    # baked-source comparison and cannot turn a manifest into a Git surrogate.
    core_cli.REPOSITORY_ROOT = transport.REPOSITORY_ROOT
    core_cli._git_head = adapter.git_head
    core_cli._git_blob = adapter.git_blob
    core_cli._git_status = adapter.git_status


def _identity_file(directory: Path, name: str, value: Mapping[str, object]) -> Path:
    path = directory / f"{name}.json"
    path.write_bytes(transport.canonical_json(dict(value)) + b"\n")
    return path


def _core_args(
    *,
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int | None,
    identities: Mapping[str, object],
    directory: Path,
) -> list[str]:
    if operation == "prepare":
        evidence = _identity_file(
            directory, "image-evidence", identities["image_evidence_identity"]
        )
        return [
            "prepare", "--image-evidence-identity", str(evidence),
            "--output-prefix", transport.OUTPUT_PREFIX, "--execute",
        ]
    authority = _identity_file(
        directory, "execution-authority", identities["execution_authority_identity"]
    )
    if operation == "run-slate":
        return [
            "run-slate", "--execution-authority-identity", str(authority),
            "--source-ordinal", str(source_ordinal),
            "--runtime-attempt-ordinal", str(runtime_attempt_ordinal), "--execute",
        ]
    if operation == "verify-slate":
        result = _identity_file(directory, "result", identities["result_identity"])
        return [
            "verify-slate", "--execution-authority-identity", str(authority),
            "--source-ordinal", str(source_ordinal),
            "--runtime-attempt-ordinal", str(runtime_attempt_ordinal),
            "--result-identity", str(result), "--execute",
        ]
    if operation == "finish-panel":
        result = [
            "finish-panel", "--execution-authority-identity", str(authority),
            "--runtime-attempt-ordinal", str(runtime_attempt_ordinal),
        ]
        acceptances = identities.get("acceptance_identities")
        if not isinstance(acceptances, Sequence) or len(acceptances) != 54:
            raise transport.T230TransportError("finalizer needs exactly 54 acceptances")
        for ordinal, identity in enumerate(acceptances):
            path = _identity_file(directory, f"acceptance-{ordinal:02d}", identity)
            result.extend(("--acceptance-identity", str(path)))
        result.append("--execute")
        return result
    raise transport.T230TransportError("unknown core operation")


def _runtime_kwargs(backend: GCSJournalBackend) -> dict[str, object]:
    return {
        "read_exact": backend.read,
        "repository_root": transport.REPOSITORY_ROOT,
        "git_head": core_cli._git_head,
        "git_blob": core_cli._git_blob,
        "git_status": core_cli._git_status,
    }


def _authority_context(
    backend: GCSJournalBackend, authority_identity: Mapping[str, object]
) -> object:
    return core_cli.execution._reopen_authority_context(
        execution_authority_identity=authority_identity,
        **_runtime_kwargs(backend),
    )


def _published_authority_context(
    backend: GCSJournalBackend, authority_identity: Mapping[str, object]
) -> object:
    return core_cli.execution._reopen_published_authority_context(
        execution_authority_identity=authority_identity,
        read_exact=backend.read,
    )


def _member_target_uri(
    *,
    backend: GCSJournalBackend,
    authority_identity: Mapping[str, object],
    source_ordinal: int,
    field: str,
) -> str:
    context = _published_authority_context(backend, authority_identity)
    member, _panel_member = core_cli.execution._source_member(
        context.execution, source_ordinal=source_ordinal
    )
    retained = member.get(field)
    if not isinstance(retained, str):
        raise transport.T230TransportError("core member target URI differs")
    return retained


def _recover_core_terminal(
    *,
    backend: GCSJournalBackend,
    contract: Mapping[str, object],
    contract_hash: str,
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int,
    launch_request_identity: Mapping[str, object],
    launch_publication_proof: Mapping[str, object],
    predecessor_identities: Sequence[Mapping[str, object]],
    identities: Mapping[str, object],
) -> dict[str, object] | None:
    authority_identity = identities.get("execution_authority_identity")
    if operation == "prepare":
        target_uri = core_cli.execution.authority_uri_for_output_prefix(
            transport.OUTPUT_PREFIX
        )
    elif operation == "finish-panel":
        target_uri = core_cli.execution.panel_release_uri_for_output_prefix(
            transport.OUTPUT_PREFIX
        )
    else:
        if not isinstance(authority_identity, Mapping) or type(source_ordinal) is not int:
            raise transport.T230TransportError("core recovery authority/member differs")
        target_uri = _member_target_uri(
            backend=backend,
            authority_identity=authority_identity,
            source_ordinal=source_ordinal,
            field="result_uri" if operation == "run-slate" else "acceptance_uri",
        )
    try:
        target_identity, target_raw = transport.recover_or_complete_publication(
            backend=backend,
            target_uri=target_uri,
            publication_binding_sha256=contract_hash,
        )
    except FileNotFoundError:
        return None
    body = transport.strict_json(target_raw, label=f"recovered core {operation}")
    try:
        if operation == "prepare":
            authority = core_cli.execution.reopen_published_t230_execution_authority_v1(
                execution_authority_identity=target_identity,
                read_exact=backend.read,
            )
            recovered_authority = authority
            exposed = {
                "execution_authority_identity": target_identity,
                "manifest_identity": authority["manifest_identity"],
            }
            intent_uri = transport._journal_uri(
                target_uri, str(target_identity["sha256"]), "intent"
            )
            intent_identity_raw, intent_raw = backend.read_known_uri(intent_uri)
            intent_identity = batch.normalize_object_identity(
                intent_identity_raw, label="prepare recovery intent"
            )
            if backend.read(intent_identity) != intent_raw:
                raise transport.T230TransportError(
                    "prepare recovery intent differs on pinned reopen"
                )
            intent = transport.strict_json(
                intent_raw, label="prepare recovery intent"
            )
            transition = intent.get("transition_id")
            if (
                intent.get("publication_binding_sha256") != contract_hash
                or not isinstance(transition, str)
            ):
                raise transport.T230TransportError(
                    "prepare recovery intent binding differs"
                )
            match = re.fullmatch(
                r"prepare-panel-a([0-7])-[0-9a-f]{16}", transition
            )
            if match is None:
                raise transport.T230TransportError(
                    "prepare recovery attempt cannot be derived"
                )
            recovered_attempt = int(match.group(1))
        elif operation == "run-slate":
            context = _published_authority_context(backend, authority_identity)
            recovered_authority = context.authority
            worker_identity, worker = core_cli.execution._runtime_from_binding(
                body.get("worker_runtime_binding"),
                role="worker",
                source_ordinal=source_ordinal,
                authority_context=context,
                read_exact=backend.read,
            )
            core_cli.execution._validate_t230_slate_result_structure(
                body,
                authority_context=context,
                worker_runtime_identity=worker_identity,
                worker_runtime_receipt=worker,
                source_ordinal=int(source_ordinal),
            )
            exposed = {
                "worker_runtime_measurement_identity": worker_identity,
                "result_identity": target_identity,
            }
            recovered_attempt = int(worker["runtime_attempt_ordinal"])
        elif operation == "verify-slate":
            context = _published_authority_context(backend, authority_identity)
            recovered_authority = context.authority
            acceptance = core_cli.execution._validate_acceptance_structure(
                body,
                authority_context=context,
                source_ordinal=int(source_ordinal),
                read_exact=backend.read,
                require_science_recomputation=False,
            )
            verifier_identity = acceptance["verifier_runtime_binding"][
                "runtime_measurement_identity"
            ]
            exposed = {
                "verifier_runtime_measurement_identity": verifier_identity,
                "acceptance_identity": target_identity,
            }
            recovered_attempt = int(
                acceptance["verifier_runtime_binding"]["runtime_attempt_ordinal"]
            )
        else:
            acceptance_identities = identities.get("acceptance_identities")
            if not isinstance(authority_identity, Mapping) or not isinstance(
                acceptance_identities, Sequence
            ):
                raise transport.T230TransportError("release recovery inputs differ")
            finalizer_binding = body.get("finalizer_runtime_binding")
            if not isinstance(finalizer_binding, Mapping):
                raise transport.T230TransportError("release finalizer binding differs")
            finalizer_identity = finalizer_binding.get(
                "runtime_measurement_identity"
            )
            core_cli.execution.validate_published_t230_panel_release_v1(
                body,
                execution_authority_identity=authority_identity,
                acceptance_identities=acceptance_identities,
                read_exact=backend.read,
            )
            recovered_authority = (
                core_cli.execution.reopen_published_t230_execution_authority_v1(
                    execution_authority_identity=authority_identity,
                    read_exact=backend.read,
                )
            )
            exposed = {
                "finalizer_runtime_measurement_identity": finalizer_identity,
                "panel_release_identity": target_identity,
            }
            recovered_attempt = int(
                finalizer_binding["runtime_attempt_ordinal"]
            )
        if (
            recovered_authority.get("output_prefix") != transport.OUTPUT_PREFIX
            or recovered_authority.get("source_commit_sha")
            != contract.get("source_commit_sha")
            or recovered_authority.get("immutable_image")
            != contract.get("immutable_image")
            or recovered_authority.get("image_evidence_identity")
            != contract.get("image_evidence_identity")
        ):
            raise transport.T230TransportError(
                "recovered core authority differs from the transport contract"
            )
    except Exception as exc:
        raise transport.T230TransportError(
            f"recovered core {operation} failed structural replay: {exc}"
        ) from exc
    start_uri = transport.stage_start_uri(
        operation, source_ordinal, recovered_attempt
    )
    start_identity, start_raw = transport.recover_or_complete_publication(
        backend=backend,
        target_uri=start_uri,
        publication_binding_sha256=contract_hash,
    )
    start = transport.strict_json(start_raw, label="recovered stage start")
    origin_execution = str(start.get("cloud_execution_name", ""))
    normalized_predecessors = [
        batch.normalize_object_identity(
            value, label=f"recovered predecessor[{ordinal}]"
        )
        for ordinal, value in enumerate(predecessor_identities)
    ]
    reopened_start = transport.reopen_stage_launch_authority_v1(
        stage_start=start,
        transport_contract_sha256=contract_hash,
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=recovered_attempt,
        cloud_execution_name=origin_execution,
        read_exact=backend.read,
    )["stage_start"]
    if (
        recovered_attempt != runtime_attempt_ordinal
        or start.get("runtime_image") != contract.get("immutable_image")
        or reopened_start.get("launch_request_identity")
        != launch_request_identity
        or reopened_start.get("launch_publication_proof")
        != launch_publication_proof
        or reopened_start.get("predecessor_identities")
        != normalized_predecessors
    ):
        raise transport.T230TransportError(
            "recovered core stage differs from the frozen attempt/image"
        )
    if operation == "finish-panel":
        transport.validate_finalizer_execution_distinct_v1(
            transport_contract_sha256=contract_hash,
            finalizer_cloud_execution_name=origin_execution,
            lane_ledger_identities=normalized_predecessors,
            read_exact=backend.read,
        )
    else:
        transport.validate_stage_predecessor_inputs_v1(
            transport_contract_sha256=contract_hash,
            operation=operation,
            source_ordinal=source_ordinal,
            predecessor_identities=normalized_predecessors,
            read_exact=backend.read,
        )
    return {
        "runtime_attempt_ordinal": recovered_attempt,
        "cloud_execution_name": origin_execution,
        "stage_start_identity": start_identity,
        "core_workflow_receipt": {
            "operation": operation,
            "recovered_after_core_terminal_create": True,
            "core_terminal_identity": target_identity,
            "science_recomputation_performed": False,
        },
        "exposed_identities": exposed,
    }


def _publish_recovered_stage(
    *,
    backend: GCSJournalBackend,
    contract_hash: str,
    operation: str,
    source_ordinal: int | None,
    recovered_core: Mapping[str, object],
) -> dict[str, object]:
    stage = transport.build_stage_receipt_v1(
        transport_contract_sha256=contract_hash,
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=int(recovered_core["runtime_attempt_ordinal"]),
        cloud_execution_name=str(recovered_core["cloud_execution_name"]),
        stage_start_identity=recovered_core["stage_start_identity"],
        core_workflow_receipt=recovered_core["core_workflow_receipt"],
        exposed_identities=recovered_core["exposed_identities"],
        wall_time_millis=None,
        peak_rss_kib=None,
    )
    publication = transport.RecoverablePublisher(
        backend, contract_hash
    ).publish(
        target_uri=transport._stage_uri(operation, source_ordinal),
        raw=transport.canonical_json(stage),
        transition_id=(
            f"stage-{operation}-"
            f"{source_ordinal if source_ordinal is not None else 'panel'}"
        ),
    )
    return {
        **stage,
        "stage_receipt_identity": publication["target_identity"],
    }


def run_core_stage(
    *,
    backend: GCSJournalBackend,
    transport_contract_identity: Mapping[str, object],
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int | None,
    cloud_execution_name: str,
    cloud_job: str,
    cloud_task_index: int,
    cloud_task_attempt: int,
    cloud_task_count: int,
    runtime_image: Mapping[str, object],
    launch_request_identity: Mapping[str, object],
    launch_request_intent_identity: Mapping[str, object],
    launch_request_completion_identity: Mapping[str, object],
    predecessor_identities: Sequence[Mapping[str, object]],
    identities: Mapping[str, object],
) -> dict[str, object]:
    if runtime_attempt_ordinal != 0:
        raise transport.T230TransportError(
            "production run-stage requires the sole fixed attempt ordinal zero"
        )
    contract_raw = backend.read(transport_contract_identity)
    contract = transport.validate_transport_contract_against_baked_snapshot_v1(
        transport.strict_json(contract_raw, label="transport contract")
    )
    if os.geteuid() != 0:
        raise transport.T230TransportError(
            "production run-stage must retain root for the root-owned 0400 evidence"
        )
    if contract["immutable_image"] != runtime_image:
        raise transport.T230TransportError(
            "runtime image differs from the digest-pinned transport contract"
        )
    contract_hash = str(contract["transport_contract_sha256"])
    recovered_launch_proof, recovered_launch_raw = (
        transport.recover_publication_proof_v1(
            backend=backend,
            target_uri=transport.launch_request_uri(
                operation, source_ordinal
            ),
            publication_binding_sha256=contract_hash,
        )
    )
    supplied_launch_proof = {
        "intent_identity": batch.normalize_object_identity(
            launch_request_intent_identity,
            label="supplied launch intent",
        ),
        "target_identity": batch.normalize_object_identity(
            launch_request_identity,
            label="supplied launch request",
        ),
        "completion_identity": batch.normalize_object_identity(
            launch_request_completion_identity,
            label="supplied launch completion",
        ),
    }
    if (
        recovered_launch_proof != supplied_launch_proof
        or backend.read(supplied_launch_proof["target_identity"])
        != recovered_launch_raw
    ):
        raise transport.T230TransportError(
            "runtime launch request differs from its completed journal"
        )
    transport.reopen_launch_request_v1(
        launch_request_identity=launch_request_identity,
        transport_contract_identity=transport_contract_identity,
        transport_contract=contract,
        operation=operation,
        source_ordinal=source_ordinal,
        predecessor_identities=predecessor_identities,
        read_exact=backend.read,
    )
    if operation == "finish-panel":
        transport.validate_finalizer_execution_distinct_v1(
            transport_contract_sha256=str(
                contract["transport_contract_sha256"]
            ),
            finalizer_cloud_execution_name=cloud_execution_name,
            lane_ledger_identities=predecessor_identities,
            read_exact=backend.read,
        )
    else:
        transport.validate_stage_predecessor_inputs_v1(
            transport_contract_sha256=str(
                contract["transport_contract_sha256"]
            ),
            operation=operation,
            source_ordinal=source_ordinal,
            predecessor_identities=predecessor_identities,
            read_exact=backend.read,
        )
    snapshot = transport.validate_source_snapshot_v1(
        transport.strict_json(
            transport.SOURCE_SNAPSHOT_PATH.read_bytes(), label="baked source snapshot"
        )
    )
    _configure_core_git(snapshot)
    evidence_identity = contract["image_evidence_identity"]
    evidence_raw = backend.read(evidence_identity)
    transport.materialize_image_evidence_v1(
        raw=evidence_raw, identity=evidence_identity
    )
    stage_uri = transport._stage_uri(operation, source_ordinal)
    try:
        recovered_identity, recovered_raw = transport.recover_or_complete_publication(
            backend=backend,
            target_uri=stage_uri,
            publication_binding_sha256=str(
                contract["transport_contract_sha256"]
            ),
        )
    except FileNotFoundError:
        recovered_identity = None
        recovered_raw = None
    if recovered_identity is not None and recovered_raw is not None:
        recovered_stage = transport.validate_stage_receipt_v1(
            transport.strict_json(recovered_raw, label="recovered stage receipt"),
            transport_contract_sha256=str(contract["transport_contract_sha256"]),
            operation=operation,
            source_ordinal=source_ordinal,
        )
        return {
            **recovered_stage,
            "stage_receipt_identity": recovered_identity,
        }

    recovered_core = _recover_core_terminal(
        backend=backend,
        contract=contract,
        contract_hash=str(contract["transport_contract_sha256"]),
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=runtime_attempt_ordinal,
        launch_request_identity=launch_request_identity,
        launch_publication_proof=recovered_launch_proof,
        predecessor_identities=predecessor_identities,
        identities=identities,
    )
    if recovered_core is not None:
        return _publish_recovered_stage(
            backend=backend,
            contract_hash=str(contract["transport_contract_sha256"]),
            operation=operation,
            source_ordinal=source_ordinal,
            recovered_core=recovered_core,
        )
    stage_start = transport.build_stage_start_v1(
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=runtime_attempt_ordinal,
        cloud_execution_name=cloud_execution_name,
        cloud_job=cloud_job,
        cloud_task_index=cloud_task_index,
        cloud_task_attempt=cloud_task_attempt,
        cloud_task_count=cloud_task_count,
        runtime_image=runtime_image,
        launch_request_identity=launch_request_identity,
        launch_publication_proof=recovered_launch_proof,
        predecessor_identities=predecessor_identities,
    )
    start_publication = transport.RecoverablePublisher(
        backend, str(contract["transport_contract_sha256"])
    ).publish(
        target_uri=str(stage_start["stage_start_uri"]),
        raw=transport.canonical_json(stage_start),
        transition_id=(
            f"stage-start-{operation}-"
            f"{source_ordinal if source_ordinal is not None else 'panel'}-"
            f"a{runtime_attempt_ordinal}"
        ),
    )
    stage_start_identity = start_publication["target_identity"]

    core_store = JournaledCoreStore(
        backend,
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        transition_prefix=(
            f"{operation}-{source_ordinal if source_ordinal is not None else 'panel'}-"
            f"a{runtime_attempt_ordinal if runtime_attempt_ordinal is not None else 0}"
        ),
    )
    core_identities = dict(identities)
    core_identities.setdefault("image_evidence_identity", evidence_identity)
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.monotonic_ns()
    with tempfile.TemporaryDirectory(prefix="foundry-t230-") as raw_directory:
        arguments = _core_args(
            operation=operation,
            source_ordinal=source_ordinal,
            runtime_attempt_ordinal=runtime_attempt_ordinal,
            identities=core_identities,
            directory=Path(raw_directory),
        )
        core_receipt = core_cli.run(arguments, store=core_store)
    elapsed = (time.monotonic_ns() - started + 999_999) // 1_000_000
    peak = max(before, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    exposed_names = {
        "prepare": ("execution_authority_identity", "manifest_identity"),
        "run-slate": ("worker_runtime_measurement_identity", "result_identity"),
        "verify-slate": ("verifier_runtime_measurement_identity", "acceptance_identity"),
        "finish-panel": ("finalizer_runtime_measurement_identity", "panel_release_identity"),
    }[operation]
    exposed = {name: core_receipt[name] for name in exposed_names}
    stage = transport.build_stage_receipt_v1(
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=runtime_attempt_ordinal,
        cloud_execution_name=cloud_execution_name,
        stage_start_identity=stage_start_identity,
        core_workflow_receipt=core_receipt,
        exposed_identities=exposed,
        wall_time_millis=int(elapsed),
        peak_rss_kib=int(peak),
    )
    publication = transport.RecoverablePublisher(
        backend, str(contract["transport_contract_sha256"])
    ).publish(
        target_uri=stage_uri,
        raw=transport.canonical_json(stage),
        transition_id=(
            f"stage-{operation}-"
            f"{source_ordinal if source_ordinal is not None else 'panel'}"
        ),
    )
    # The small terminal output contains mechanics and identities only.
    return {
        **stage,
        "stage_receipt_identity": publication["target_identity"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frozen Foundry T230 transport")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("parked")

    snapshot = commands.add_parser("build-source-snapshot")
    snapshot.add_argument("--source-commit", required=True)
    snapshot.add_argument("--repository-root", type=Path, required=True)
    snapshot.add_argument("--output", type=Path, required=True)

    evidence = commands.add_parser("build-image-evidence")
    evidence.add_argument("--source-snapshot", type=Path, required=True)
    evidence.add_argument("--immutable-image", required=True)
    evidence.add_argument("--output", type=Path, required=True)

    publish_evidence = commands.add_parser("publish-image-evidence")
    publish_evidence.add_argument("--source-snapshot", type=Path, required=True)
    publish_evidence.add_argument("--image-evidence", type=Path, required=True)
    publish_evidence.add_argument("--immutable-image", required=True)
    publish_evidence.add_argument("--g0-preflight", type=Path, required=True)
    publish_evidence.add_argument("--execute", action="store_true", required=True)

    contract = commands.add_parser("build-transport-contract")
    contract.add_argument("--source-snapshot", type=Path, required=True)
    contract.add_argument("--immutable-image", required=True)
    _add_identity(contract, "image_evidence")
    contract.add_argument("--prefreeze-release-gate", type=Path, required=True)
    contract.add_argument("--output", type=Path, required=True)

    publish_prefreeze_smoke = commands.add_parser("publish-prefreeze-smoke")
    publish_prefreeze_smoke.add_argument(
        "--smoke-receipt", type=Path, required=True
    )
    publish_prefreeze_smoke.add_argument(
        "--execute", action="store_true", required=True
    )

    assert_prefreeze_absent = commands.add_parser(
        "assert-prefreeze-smoke-absent"
    )
    assert_prefreeze_absent.add_argument(
        "--execute", action="store_true", required=True
    )

    publish_prefreeze_launch = commands.add_parser(
        "publish-prefreeze-smoke-launch"
    )
    publish_prefreeze_launch.add_argument(
        "--source-snapshot", type=Path, required=True
    )
    publish_prefreeze_launch.add_argument("--immutable-image", required=True)
    publish_prefreeze_launch.add_argument(
        "--g0-preflight", type=Path, required=True
    )
    publish_prefreeze_launch.add_argument("--service-account", required=True)
    publish_prefreeze_launch.add_argument(
        "--execute", action="store_true", required=True
    )

    publish_prefreeze_time = commands.add_parser(
        "publish-prefreeze-smoke-time-v"
    )
    _add_identity(publish_prefreeze_time, "smoke_receipt")
    publish_prefreeze_time.add_argument(
        "--smoke-receipt", type=Path, required=True
    )
    publish_prefreeze_time.add_argument("--raw-time-v", type=Path, required=True)
    publish_prefreeze_time.add_argument(
        "--execute", action="store_true", required=True
    )

    recover_prefreeze = commands.add_parser(
        "recover-prefreeze-smoke-inputs"
    )
    recover_prefreeze.add_argument("--source-snapshot", type=Path, required=True)
    recover_prefreeze.add_argument("--immutable-image", required=True)
    recover_prefreeze.add_argument("--g0-preflight", type=Path, required=True)
    recover_prefreeze.add_argument("--receipt-identity-output", type=Path, required=True)
    recover_prefreeze.add_argument("--receipt-body-output", type=Path, required=True)
    recover_prefreeze.add_argument("--time-identity-output", type=Path, required=True)
    recover_prefreeze.add_argument("--time-body-output", type=Path, required=True)
    recover_prefreeze.add_argument(
        "--execute", action="store_true", required=True
    )

    recover_prefreeze_receipt = commands.add_parser(
        "recover-prefreeze-smoke-receipt"
    )
    recover_prefreeze_receipt.add_argument(
        "--source-snapshot", type=Path, required=True
    )
    recover_prefreeze_receipt.add_argument("--immutable-image", required=True)
    recover_prefreeze_receipt.add_argument(
        "--g0-preflight", type=Path, required=True
    )
    recover_prefreeze_receipt.add_argument("--output", type=Path, required=True)
    recover_prefreeze_receipt.add_argument(
        "--execute", action="store_true", required=True
    )

    publish_prefreeze_execution = commands.add_parser(
        "publish-prefreeze-smoke-execution"
    )
    publish_prefreeze_execution.add_argument(
        "--source-snapshot", type=Path, required=True
    )
    publish_prefreeze_execution.add_argument("--immutable-image", required=True)
    publish_prefreeze_execution.add_argument(
        "--g0-preflight", type=Path, required=True
    )
    publish_prefreeze_execution.add_argument(
        "--observed-execution", type=Path, required=True
    )
    publish_prefreeze_execution.add_argument(
        "--execute", action="store_true", required=True
    )

    resolve_prefreeze_gate = commands.add_parser(
        "resolve-prefreeze-release-gate"
    )
    resolve_prefreeze_gate.add_argument(
        "--source-snapshot", type=Path, required=True
    )
    resolve_prefreeze_gate.add_argument("--immutable-image", required=True)
    resolve_prefreeze_gate.add_argument("--g0-preflight", type=Path, required=True)
    resolve_prefreeze_gate.add_argument("--output", type=Path, required=True)
    resolve_prefreeze_gate.add_argument(
        "--execute", action="store_true", required=True
    )

    publish_contract = commands.add_parser("publish-transport-contract")
    publish_contract.add_argument("--transport-contract", type=Path, required=True)
    publish_contract.add_argument("--source-snapshot", type=Path, required=True)
    publish_contract.add_argument("--execute", action="store_true", required=True)

    materialize = commands.add_parser("materialize-image-evidence")
    _add_identity(materialize, "image_evidence")
    materialize.add_argument("--execute", action="store_true", required=True)

    bootstrap = commands.add_parser("resolve-transport-contract")
    bootstrap.add_argument("--contract-output", type=Path, required=True)
    bootstrap.add_argument("--evidence-output", type=Path, required=True)
    bootstrap.add_argument("--image-output", type=Path, required=True)
    bootstrap.add_argument("--execute", action="store_true", required=True)

    preflight_g0 = commands.add_parser("preflight-g0")
    preflight_g0.add_argument("--repository-root", type=Path, required=True)
    preflight_g0.add_argument("--execute", action="store_true", required=True)

    lane = commands.add_parser("build-lane-ledger")
    lane.add_argument("--lane-ordinal", type=int, required=True)
    lane.add_argument(
        "--stage-receipt-identity", type=Path, action="append", default=[]
    )
    _add_identity(lane, "transport_contract")
    lane.add_argument("--output", type=Path, required=True)
    lane.add_argument("--execute", action="store_true", required=True)

    publish_lane = commands.add_parser("publish-lane-ledger")
    publish_lane.add_argument("--lane-ordinal", type=int, required=True)
    publish_lane.add_argument("--lane-ledger", type=Path, required=True)
    _add_identity(publish_lane, "transport_contract")
    publish_lane.add_argument("--execute", action="store_true", required=True)

    publish_job_config = commands.add_parser("publish-job-config")
    _add_identity(publish_job_config, "transport_contract")
    publish_job_config.add_argument(
        "--job", required=True,
        choices=(transport.LANE_A_JOB, transport.LANE_B_JOB),
    )
    publish_job_config.add_argument("--observed-config", type=Path, required=True)
    publish_job_config.add_argument("--execute", action="store_true", required=True)

    benchmark = commands.add_parser("build-benchmark")
    _add_identity(benchmark, "transport_contract")
    _add_identity(benchmark, "worker_stage_receipt")
    _add_identity(benchmark, "benchmark_disposition")
    _add_identity(benchmark, "raw_time_v")
    benchmark.add_argument("--output", type=Path, required=True)
    benchmark.add_argument("--execute", action="store_true", required=True)

    raw_time = commands.add_parser("publish-raw-time-v")
    _add_identity(raw_time, "transport_contract")
    _add_identity(raw_time, "worker_stage_receipt")
    raw_time.add_argument("--raw-time-v", type=Path, required=True)
    raw_time.add_argument("--execute", action="store_true", required=True)

    publish_benchmark = commands.add_parser("publish-benchmark")
    _add_identity(publish_benchmark, "transport_contract")
    publish_benchmark.add_argument("--benchmark", type=Path, required=True)
    publish_benchmark.add_argument("--execute", action="store_true", required=True)

    publish_execution_terminal = commands.add_parser(
        "publish-benchmark-execution-terminal"
    )
    _add_identity(publish_execution_terminal, "transport_contract")
    _add_identity(publish_execution_terminal, "worker_stage_receipt")
    publish_execution_terminal.add_argument(
        "--observed-terminal", type=Path, required=True
    )
    publish_execution_terminal.add_argument(
        "--execute", action="store_true", required=True
    )

    abort_benchmark = commands.add_parser("publish-benchmark-terminal-abort")
    _add_identity(abort_benchmark, "transport_contract")
    _add_identity(abort_benchmark, "worker_stage_receipt")
    _add_identity(abort_benchmark, "benchmark_execution_terminal")
    abort_benchmark.add_argument("--execute", action="store_true", required=True)

    resume_benchmark = commands.add_parser("resume-benchmark-transaction")
    _add_identity(resume_benchmark, "transport_contract")
    resume_benchmark.add_argument("--execute", action="store_true", required=True)

    compute = commands.add_parser("publish-compute-release")
    _add_identity(compute, "transport_contract")
    _add_identity(compute, "benchmark")
    compute.add_argument("--execute", action="store_true", required=True)

    resolve_compute = commands.add_parser("resolve-compute-release")
    _add_identity(resolve_compute, "transport_contract")
    resolve_compute.add_argument("--output", type=Path, required=True)
    resolve_compute.add_argument("--execute", action="store_true", required=True)

    resolve_stage = commands.add_parser("resolve-stage-receipt")
    _add_identity(resolve_stage, "transport_contract")
    resolve_stage.add_argument(
        "--operation", required=True,
        choices=("prepare", "run-slate", "verify-slate", "finish-panel"),
    )
    resolve_stage.add_argument("--source-ordinal", type=int)
    resolve_stage.add_argument("--output", type=Path, required=True)
    resolve_stage.add_argument("--body-output", type=Path)
    resolve_stage.add_argument("--execute", action="store_true", required=True)

    launch = commands.add_parser("publish-launch-request")
    _add_identity(launch, "transport_contract")
    launch.add_argument(
        "--operation", required=True,
        choices=("prepare", "run-slate", "verify-slate", "finish-panel"),
    )
    launch.add_argument("--source-ordinal", type=int)
    launch.add_argument(
        "--predecessor-identity", action="append", type=Path, default=[]
    )
    launch.add_argument("--job-config-identity", type=Path, required=True)
    launch.add_argument("--execute", action="store_true", required=True)

    resolve_launch = commands.add_parser("resolve-launch-request")
    _add_identity(resolve_launch, "transport_contract")
    resolve_launch.add_argument(
        "--operation", required=True,
        choices=("prepare", "run-slate", "verify-slate", "finish-panel"),
    )
    resolve_launch.add_argument("--source-ordinal", type=int)
    resolve_launch.add_argument(
        "--predecessor-identity", action="append", type=Path, default=[]
    )
    resolve_launch.add_argument("--output", type=Path, required=True)
    resolve_launch.add_argument("--execute", action="store_true", required=True)

    recover_stage = commands.add_parser("recover-stage-after-core-terminal")
    _add_identity(recover_stage, "transport_contract")
    recover_stage.add_argument(
        "--operation", required=True,
        choices=("prepare", "run-slate", "verify-slate", "finish-panel"),
    )
    recover_stage.add_argument("--source-ordinal", type=int)
    _add_identity(recover_stage, "execution_authority", required=False)
    recover_stage.add_argument(
        "--lane-ledger", action="append", type=Path, default=[]
    )
    recover_stage.add_argument(
        "--predecessor-identity", action="append", type=Path, default=[]
    )
    recover_stage.add_argument("--output", type=Path, required=True)
    recover_stage.add_argument("--body-output", type=Path)
    recover_stage.add_argument("--execute", action="store_true", required=True)

    stage = commands.add_parser("run-stage")
    stage.add_argument(
        "--operation",
        required=True,
        choices=("prepare", "run-slate", "verify-slate", "finish-panel"),
    )
    stage.add_argument("--source-ordinal", type=int)
    stage.add_argument("--runtime-attempt-ordinal", type=int, required=True)
    stage.add_argument("--cloud-execution-name", required=True)
    stage.add_argument("--cloud-job", required=True)
    stage.add_argument("--cloud-task-index", type=int, required=True)
    stage.add_argument("--cloud-task-attempt", type=int, required=True)
    stage.add_argument("--cloud-task-count", type=int, required=True)
    stage.add_argument("--runtime-image", required=True)
    _add_identity(stage, "transport_contract")
    _add_identity(stage, "launch_request")
    _add_identity(stage, "launch_request_intent")
    _add_identity(stage, "launch_request_completion")
    _add_identity(stage, "execution_authority", required=False)
    _add_identity(stage, "result", required=False)
    _add_identity(stage, "compute_release", required=False)
    stage.add_argument("--lane-ledger", action="append", type=Path, default=[])
    stage.add_argument(
        "--predecessor-identity", action="append", type=Path, default=[]
    )
    stage.add_argument("--execute", action="store_true", required=True)
    return parser


def run(argv: Sequence[str], *, backend: GCSJournalBackend | None = None) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    if args.command == "parked":
        return {
            "state": "parked", "default_off": True, "client_constructed": False,
            "output_prefix": transport.OUTPUT_PREFIX,
        }
    if args.command == "build-source-snapshot":
        value = transport.build_source_snapshot_v1(
            repository_root=args.repository_root,
            source_commit_sha=args.source_commit,
        )
        _write_once(args.output, transport.canonical_json(value) + b"\n")
        return value
    if args.command == "build-image-evidence":
        value = transport.build_image_evidence_v1(
            repository_root=transport.REPOSITORY_ROOT,
            source_snapshot=_load(args.source_snapshot, label="source snapshot"),
            immutable_image=_image_from_arg(args.immutable_image),
        )
        _write_once(args.output, transport.canonical_json(value) + b"\n")
        return value
    if args.command == "build-transport-contract":
        value = transport.build_transport_contract_v1(
            source_snapshot=_load(args.source_snapshot, label="source snapshot"),
            immutable_image=_image_from_arg(args.immutable_image),
            image_evidence_identity=_identity_from_args(args, "image_evidence"),
            prefreeze_release_gate=_load(
                args.prefreeze_release_gate,
                label="prefreeze release gate",
            ),
        )
        _write_once(args.output, transport.canonical_json(value) + b"\n")
        return value
    if backend is None:
        try:
            from google.cloud import storage
        except ImportError as exc:  # pragma: no cover
            raise transport.T230TransportError(
                "google-cloud-storage is required for execute mode"
            ) from exc
        backend = GCSJournalBackend(storage.Client(project=transport.PROJECT))
    _require_execute(args)
    if args.command == "preflight-g0":
        repository_root = args.repository_root.resolve()
        if not repository_root.is_dir():
            raise transport.T230TransportError(
                "G0 preflight repository root is absent"
            )
        publication_relative = (
            core_cli.execution.FROZEN_G0_PUBLICATION_RECEIPT_PATH.relative_to(
                transport.REPOSITORY_ROOT
            )
        )
        lane_relatives = tuple(
            path.relative_to(transport.REPOSITORY_ROOT)
            for path in core_cli.execution.FROZEN_G0_LANE_RECEIPT_PATHS
        )
        lock_relative = core_cli.execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH
        core_cli.execution.FROZEN_G0_PUBLICATION_RECEIPT_PATH = (
            repository_root / publication_relative
        )
        core_cli.execution.FROZEN_G0_LANE_RECEIPT_PATHS = tuple(
            repository_root / path for path in lane_relatives
        )
        core_cli.execution.FROZEN_G0_AUTHORITY_LOCK_PATH = (
            repository_root / lock_relative
        )
        _receipt, _panel, published_panel, lanes, binding = (
            core_cli.execution.replay_published_v12_panel_v1(
                repository_root=repository_root,
                read_exact=backend.read,
                git_head=core_cli._git_head,
                git_blob=core_cli._git_blob,
                git_status=core_cli._git_status,
            )
        )
        return {
            "g0_preflight_passed": True,
            "source_commit_sha": binding["source_commit_sha"],
            "panel_id": published_panel["panel_id"],
            "panel_object_identity": _panel["panel_object_identity"],
            "accepted_slate_count": published_panel["accepted_slate_count"],
            "lane_count": len(lanes),
            "image_push_precondition_satisfied": True,
            "production_execution_licensed": False,
        }
    if args.command == "publish-prefreeze-smoke":
        receipt = _load(args.smoke_receipt, label="prefreeze smoke receipt")
        retained = core_cli.execution.validate_t230_prefreeze_smoke_receipt_v1(
            receipt,
            expected_panel_object_identity=receipt.get(
                "panel_object_identity", {}
            ),
            expected_source_commit_sha=str(receipt.get("source_commit_sha", "")),
            expected_immutable_candidate_image=receipt.get(
                "immutable_candidate_image", {}
            ),
            require_release_runtime=True,
        )
        baked_snapshot = transport.validate_runtime_source_snapshot_v1(
            transport.strict_json(
                transport.SOURCE_SNAPSHOT_PATH.read_bytes(),
                label="baked prefreeze source snapshot",
            ),
            repository_root=transport.REPOSITORY_ROOT,
        )
        if retained["source_commit_sha"] != baked_snapshot["source_commit_sha"]:
            raise transport.T230TransportError(
                "prefreeze smoke receipt differs from baked candidate source"
            )
        launch = transport.recover_prefreeze_smoke_launch_v1(
            backend=backend,
            expected_panel_object_identity=retained["panel_object_identity"],
            expected_source_commit_sha=str(retained["source_commit_sha"]),
            expected_immutable_candidate_image=retained[
                "immutable_candidate_image"
            ],
        )
        publication = transport.RecoverablePublisher(
            backend, str(retained["prefreeze_smoke_receipt_sha256"])
        ).publish(
            target_uri=transport.PREFREEZE_SMOKE_RECEIPT_URI,
            raw=transport.canonical_json(retained),
            transition_id="publish-prefreeze-rule1-smoke",
        )
        return {
            "smoke_launch_identity": launch["smoke_launch_identity"],
            "prefreeze_smoke_receipt": retained,
            **publication,
        }
    if args.command == "assert-prefreeze-smoke-absent":
        try:
            backend.read_known_uri(transport.PREFREEZE_SMOKE_RECEIPT_URI)
        except FileNotFoundError:
            return {
                "prefreeze_smoke_receipt_absent": True,
                "science_launch_allowed_once": True,
            }
        raise transport.T230TransportError(
            "a prefreeze smoke receipt already exists; science relaunch forbidden"
        )
    if args.command == "publish-prefreeze-smoke-launch":
        snapshot, image, panel_identity = _prefreeze_expected_from_files(
            source_snapshot_path=args.source_snapshot,
            immutable_image=args.immutable_image,
            g0_preflight_path=args.g0_preflight,
        )
        launch = transport.build_prefreeze_smoke_launch_v1(
            panel_object_identity=panel_identity,
            source_commit_sha=str(snapshot["source_commit_sha"]),
            immutable_candidate_image=image,
            service_account=args.service_account,
        )
        publication = transport.RecoverablePublisher(
            backend, str(launch["prefreeze_smoke_launch_sha256"])
        ).publish(
            target_uri=transport.PREFREEZE_SMOKE_LAUNCH_URI,
            raw=transport.canonical_json(launch),
            transition_id="claim-prefreeze-rule1-smoke-launch",
        )
        return {"prefreeze_smoke_launch": launch, **publication}
    if args.command == "publish-prefreeze-smoke-time-v":
        receipt = _load(args.smoke_receipt, label="prefreeze smoke receipt")
        receipt_identity = _identity_from_args(args, "smoke_receipt")
        receipt_raw = transport.canonical_json(receipt)
        if backend.read(receipt_identity) != receipt_raw:
            raise transport.T230TransportError(
                "prefreeze time-v receipt exact read differs"
            )
        raw_time_v = args.raw_time_v.read_bytes()
        binding = transport.build_prefreeze_smoke_time_binding_v1(
            smoke_receipt_identity=receipt_identity,
            smoke_receipt=receipt,
            raw_time_v=raw_time_v,
        )
        publication = transport.RecoverablePublisher(
            backend,
            str(binding["prefreeze_smoke_time_binding_sha256"]),
        ).publish(
            target_uri=transport.PREFREEZE_SMOKE_TIME_V_URI,
            raw=raw_time_v,
            transition_id="publish-prefreeze-rule1-smoke-time-v",
        )
        return {"prefreeze_smoke_time_binding": binding, **publication}
    if args.command in {
        "recover-prefreeze-smoke-inputs",
        "recover-prefreeze-smoke-receipt",
        "publish-prefreeze-smoke-execution",
        "resolve-prefreeze-release-gate",
    }:
        snapshot, image, panel_identity = _prefreeze_expected_from_files(
            source_snapshot_path=args.source_snapshot,
            immutable_image=args.immutable_image,
            g0_preflight_path=args.g0_preflight,
        )
        if args.command == "recover-prefreeze-smoke-inputs":
            inputs = transport.recover_prefreeze_smoke_inputs_v1(
                backend=backend,
                expected_panel_object_identity=panel_identity,
                expected_source_commit_sha=str(snapshot["source_commit_sha"]),
                expected_immutable_candidate_image=image,
            )
            _write_once(
                args.receipt_identity_output,
                transport.canonical_json(inputs["smoke_receipt_identity"])
                + b"\n",
            )
            _write_once(
                args.receipt_body_output,
                transport.canonical_json(inputs["smoke_receipt"]) + b"\n",
            )
            _write_once(
                args.time_identity_output,
                transport.canonical_json(inputs["smoke_time_v_identity"])
                + b"\n",
            )
            _write_once(args.time_body_output, inputs["smoke_time_v"])
            return {
                "smoke_receipt_identity": inputs["smoke_receipt_identity"],
                "smoke_time_v_identity": inputs["smoke_time_v_identity"],
                "immutable_candidate_image": image,
            }
        if args.command == "recover-prefreeze-smoke-receipt":
            retained = transport.recover_prefreeze_smoke_receipt_v1(
                backend=backend,
                expected_panel_object_identity=panel_identity,
                expected_source_commit_sha=str(snapshot["source_commit_sha"]),
                expected_immutable_candidate_image=image,
            )
            _write_once(
                args.output,
                transport.canonical_json(retained["smoke_receipt"]) + b"\n",
            )
            return retained
        if args.command == "publish-prefreeze-smoke-execution":
            launch = transport.recover_prefreeze_smoke_launch_v1(
                backend=backend,
                expected_panel_object_identity=panel_identity,
                expected_source_commit_sha=str(snapshot["source_commit_sha"]),
                expected_immutable_candidate_image=image,
            )
            inputs = transport.recover_prefreeze_smoke_inputs_v1(
                backend=backend,
                expected_panel_object_identity=panel_identity,
                expected_source_commit_sha=str(snapshot["source_commit_sha"]),
                expected_immutable_candidate_image=image,
            )
            projection = transport.build_prefreeze_smoke_execution_v1(
                smoke_launch_identity=launch["smoke_launch_identity"],
                smoke_launch=launch["smoke_launch"],
                smoke_receipt_identity=inputs["smoke_receipt_identity"],
                smoke_receipt=inputs["smoke_receipt"],
                smoke_time_v_identity=inputs["smoke_time_v_identity"],
                smoke_time_v=inputs["smoke_time_v"],
                observed_execution=_load(
                    args.observed_execution,
                    label="observed prefreeze smoke execution",
                ),
            )
            publication = transport.RecoverablePublisher(
                backend, str(projection["prefreeze_smoke_execution_sha256"])
            ).publish(
                target_uri=transport.PREFREEZE_SMOKE_EXECUTION_URI,
                raw=transport.canonical_json(projection),
                transition_id="publish-prefreeze-rule1-smoke-execution",
            )
            return {"prefreeze_smoke_execution": projection, **publication}
        retained = transport.resolve_prefreeze_release_gate_v1(
            backend=backend,
            expected_panel_object_identity=panel_identity,
            expected_source_commit_sha=str(snapshot["source_commit_sha"]),
            expected_immutable_candidate_image=image,
        )
        _write_once(
            args.output,
            transport.canonical_json(retained["prefreeze_release_gate"])
            + b"\n",
        )
        return retained
    if args.command == "resolve-transport-contract":
        known_identity_raw, known_raw = backend.read_known_uri(
            transport.TRANSPORT_CONTRACT_URI
        )
        known_identity = batch.normalize_object_identity(
            known_identity_raw, label="bootstrap transport contract"
        )
        if backend.read(known_identity) != known_raw:
            raise transport.T230TransportError(
                "bootstrap contract differs on generation-pinned reopen"
            )
        contract = transport.validate_transport_contract_v1(
            transport.strict_json(known_raw, label="bootstrap transport contract")
        )
        transport.reopen_contract_prefreeze_release_gate_v1(
            transport_contract=contract, backend=backend
        )
        contract_hash = str(contract["transport_contract_sha256"])
        recovered_identity, recovered_raw = (
            transport.recover_or_complete_publication(
                backend=backend,
                target_uri=transport.TRANSPORT_CONTRACT_URI,
                publication_binding_sha256=contract_hash,
            )
        )
        if recovered_identity != known_identity or recovered_raw != known_raw:
            raise transport.T230TransportError(
                "bootstrap contract journal recovery differs"
            )
        evidence_identity = batch.normalize_object_identity(
            contract["image_evidence_identity"],
            label="bootstrap image evidence",
        )
        evidence_raw = backend.read(evidence_identity)
        evidence = transport._validate_image_evidence_structural_v1(
            transport.strict_json(
                evidence_raw, label="bootstrap image evidence"
            )
        )
        if (
            evidence.get("immutable_image") != contract["immutable_image"]
            or evidence.get("source_commit_sha") != contract["source_commit_sha"]
        ):
            raise transport.T230TransportError(
                "bootstrap image evidence source/image differs"
            )
        _write_once(
            args.contract_output,
            transport.canonical_json(known_identity) + b"\n",
        )
        _write_once(
            args.evidence_output,
            transport.canonical_json(evidence_identity) + b"\n",
        )
        _write_once(
            args.image_output,
            transport.canonical_json(contract["immutable_image"]) + b"\n",
        )
        return {
            "transport_contract_identity": known_identity,
            "image_evidence_identity": evidence_identity,
            "immutable_image": contract["immutable_image"],
        }
    if args.command == "publish-image-evidence":
        snapshot = _load(args.source_snapshot, label="source snapshot")
        evidence_body = _load(args.image_evidence, label="image evidence")
        validated_snapshot, validated_image, panel_identity = (
            _prefreeze_expected_from_files(
                source_snapshot_path=args.source_snapshot,
                immutable_image=args.immutable_image,
                g0_preflight_path=args.g0_preflight,
            )
        )
        gate = transport.resolve_prefreeze_release_gate_v1(
            backend=backend,
            expected_panel_object_identity=panel_identity,
            expected_source_commit_sha=str(
                validated_snapshot["source_commit_sha"]
            ),
            expected_immutable_candidate_image=validated_image,
        )["prefreeze_release_gate"]
        binding = transport.build_image_evidence_publication_binding_v1(
            source_snapshot=snapshot,
            immutable_image=_image_from_arg(args.immutable_image),
            image_evidence=evidence_body,
        )
        publication = transport.RecoverablePublisher(
            backend,
            str(binding["image_evidence_publication_binding_sha256"]),
        ).publish(
            target_uri=str(binding["target_uri"]),
            raw=transport.canonical_json(evidence_body),
            transition_id="publish-post-digest-image-evidence",
        )
        return {"prefreeze_release_gate": gate, "binding": binding, **publication}
    if args.command == "publish-transport-contract":
        body = _load(args.transport_contract, label="transport contract")
        snapshot = _load(args.source_snapshot, label="source snapshot")
        expected = transport.build_transport_contract_v1(
            source_snapshot=snapshot,
            immutable_image=body.get("immutable_image"),
            image_evidence_identity=body.get("image_evidence_identity", {}),
            prefreeze_release_gate=body.get("prefreeze_release_gate", {}),
        )
        if transport.canonical_json(body) != transport.canonical_json(expected):
            raise transport.T230TransportError(
                "transport contract differs from supplied exact source snapshot"
            )
        transport.reopen_contract_prefreeze_release_gate_v1(
            transport_contract=body, backend=backend
        )
        evidence_identity = batch.normalize_object_identity(
            body["image_evidence_identity"],
            label="contract publication image evidence",
        )
        evidence_raw = backend.read(evidence_identity)
        evidence = transport._validate_image_evidence_structural_v1(
            transport.strict_json(
                evidence_raw, label="contract publication image evidence"
            )
        )
        if (
            evidence.get("source_commit_sha") != body["source_commit_sha"]
            or evidence.get("immutable_image") != body["immutable_image"]
        ):
            raise transport.T230TransportError(
                "contract publication image evidence source/image differs"
            )
        evidence_binding = (
            transport.build_image_evidence_publication_binding_v1(
                source_snapshot=snapshot,
                immutable_image=body["immutable_image"],
                image_evidence=evidence,
            )
        )
        recovered_evidence_identity, recovered_evidence_raw = (
            transport.recover_or_complete_publication(
                backend=backend,
                target_uri=str(evidence_binding["target_uri"]),
                publication_binding_sha256=str(
                    evidence_binding[
                        "image_evidence_publication_binding_sha256"
                    ]
                ),
            )
        )
        if (
            recovered_evidence_identity != evidence_identity
            or recovered_evidence_raw != evidence_raw
        ):
            raise transport.T230TransportError(
                "contract publication image evidence journal differs"
            )
        publication = transport.RecoverablePublisher(
            backend, str(body["transport_contract_sha256"])
        ).publish(
            target_uri=transport.TRANSPORT_CONTRACT_URI,
            raw=transport.canonical_json(body),
            transition_id="publish-transport-contract",
        )
        return {"transport_contract": body, **publication}
    if args.command == "materialize-image-evidence":
        identity = _identity_from_args(args, "image_evidence")
        binding = transport.materialize_image_evidence_v1(
            raw=backend.read(identity), identity=identity
        )
        return {"materialized": True, "binding": binding}
    if args.command in {
        "build-lane-ledger", "publish-lane-ledger", "build-benchmark",
        "publish-compute-release", "publish-raw-time-v", "publish-benchmark",
        "publish-benchmark-execution-terminal",
        "publish-benchmark-terminal-abort",
        "resume-benchmark-transaction",
        "resolve-compute-release", "resolve-stage-receipt",
        "publish-launch-request", "resolve-launch-request", "publish-job-config",
        "recover-stage-after-core-terminal",
    }:
        contract_identity = _identity_from_args(args, "transport_contract")
        contract = transport.validate_transport_contract_v1(
            transport.strict_json(
                backend.read(contract_identity), label="transport contract"
            )
        )
        contract_hash = str(contract["transport_contract_sha256"])
        if args.command == "publish-job-config":
            body = transport.build_job_config_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                observed_config=_load(
                    args.observed_config, label="observed Cloud Run job config"
                ),
                job=args.job,
            )
            publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.job_config_uri(args.job),
                raw=transport.canonical_json(body),
                transition_id=f"publish-job-config-{args.job}",
            )
            return {"job_config": body, **publication}
        if args.command == "recover-stage-after-core-terminal":
            predecessors = [
                batch.normalize_object_identity(
                    _load(path, label="recovery predecessor identity"),
                    label="recovery predecessor identity",
                )
                for path in args.predecessor_identity
            ]
            transport.validate_stage_predecessor_inputs_v1(
                transport_contract_sha256=contract_hash,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                predecessor_identities=predecessors,
                read_exact=backend.read,
            )
            launch_proof, _launch_raw = transport.recover_publication_proof_v1(
                backend=backend,
                target_uri=transport.launch_request_uri(
                    args.operation, args.source_ordinal
                ),
                publication_binding_sha256=contract_hash,
            )
            launch_identity = launch_proof["target_identity"]
            transport.reopen_launch_request_v1(
                launch_request_identity=launch_identity,
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                predecessor_identities=predecessors,
                read_exact=backend.read,
            )
            recovery_identities: dict[str, object] = {}
            if args.operation != "prepare":
                recovery_identities["execution_authority_identity"] = (
                    _identity_from_args(args, "execution_authority")
                )
            if args.operation == "finish-panel":
                recovery_identities["acceptance_identities"] = (
                    _acceptances_from_lane_files(
                        backend=backend,
                        contract_hash=contract_hash,
                        lane_files=args.lane_ledger,
                    )
                )
            recovered_core = _recover_core_terminal(
                backend=backend,
                contract=contract,
                contract_hash=contract_hash,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                runtime_attempt_ordinal=0,
                launch_request_identity=launch_identity,
                launch_publication_proof=launch_proof,
                predecessor_identities=predecessors,
                identities=recovery_identities,
            )
            if recovered_core is None:
                raise transport.T230TransportError(
                    "core terminal is absent; recovery cannot launch science"
                )
            stage = _publish_recovered_stage(
                backend=backend,
                contract_hash=contract_hash,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                recovered_core=recovered_core,
            )
            _write_once(
                args.output,
                transport.canonical_json(stage["stage_receipt_identity"]) + b"\n",
            )
            if args.body_output is not None:
                _write_once(
                    args.body_output, transport.canonical_json(stage) + b"\n"
                )
            return stage
        if args.command == "build-lane-ledger":
            identities = [
                batch.normalize_object_identity(
                    _load(path, label="stage receipt identity"),
                    label="stage receipt identity",
                )
                for path in args.stage_receipt_identity
            ]
            ledger = transport.build_lane_ledger_v1(
                transport_contract_sha256=contract_hash,
                lane_ordinal=args.lane_ordinal,
                stage_receipt_identities=identities,
                read_exact=backend.read,
            )
            _write_once(args.output, transport.canonical_json(ledger) + b"\n")
            return ledger
        if args.command == "publish-launch-request":
            predecessors = [
                batch.normalize_object_identity(
                    _load(path, label="launch predecessor identity"),
                    label="launch predecessor identity",
                )
                for path in args.predecessor_identity
            ]
            transport.validate_stage_predecessor_inputs_v1(
                transport_contract_sha256=contract_hash,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                predecessor_identities=predecessors,
                read_exact=backend.read,
            )
            request = transport.build_launch_request_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                predecessor_identities=predecessors,
                job_config_identity=batch.normalize_object_identity(
                    _load(
                        args.job_config_identity,
                        label="launch job-config identity",
                    ),
                    label="launch job-config identity",
                ),
                read_exact=backend.read,
            )
            publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.launch_request_uri(
                    args.operation, args.source_ordinal
                ),
                raw=transport.canonical_json(request),
                transition_id=(
                    f"launch-{args.operation}-"
                    f"{args.source_ordinal if args.source_ordinal is not None else 'panel'}"
                ),
            )
            return {"launch_request": request, **publication}
        if args.command == "resolve-launch-request":
            predecessors = [
                batch.normalize_object_identity(
                    _load(path, label="resolved launch predecessor identity"),
                    label="resolved launch predecessor identity",
                )
                for path in args.predecessor_identity
            ]
            transport.validate_stage_predecessor_inputs_v1(
                transport_contract_sha256=contract_hash,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                predecessor_identities=predecessors,
                read_exact=backend.read,
            )
            proof, _request_raw = transport.recover_publication_proof_v1(
                backend=backend,
                target_uri=transport.launch_request_uri(
                    args.operation, args.source_ordinal
                ),
                publication_binding_sha256=contract_hash,
            )
            request = transport.reopen_launch_request_v1(
                launch_request_identity=proof["target_identity"],
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                predecessor_identities=predecessors,
                read_exact=backend.read,
            )
            _write_once(
                args.output,
                transport.canonical_json(proof["target_identity"]) + b"\n",
            )
            return {
                "launch_request": request,
                "launch_publication_proof": proof,
            }
        if args.command == "resolve-stage-receipt":
            target_uri = transport._stage_uri(
                args.operation, args.source_ordinal
            )
            identity, raw = transport.recover_or_complete_publication(
                backend=backend,
                target_uri=target_uri,
                publication_binding_sha256=contract_hash,
            )
            body = transport.validate_stage_receipt_v1(
                transport.strict_json(raw, label="resolved stage receipt"),
                transport_contract_sha256=contract_hash,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
            )
            start_identity = batch.normalize_object_identity(
                body["stage_start_identity"], label="resolved stage start"
            )
            start_body = transport.strict_json(
                backend.read(start_identity), label="resolved stage start"
            )
            transport.reopen_stage_launch_authority_v1(
                stage_start=start_body,
                transport_contract_sha256=contract_hash,
                operation=args.operation,
                source_ordinal=args.source_ordinal,
                runtime_attempt_ordinal=int(body["runtime_attempt_ordinal"]),
                cloud_execution_name=str(body["cloud_execution_name"]),
                read_exact=backend.read,
            )
            _write_once(args.output, transport.canonical_json(identity) + b"\n")
            if args.body_output is not None:
                _write_once(
                    args.body_output, transport.canonical_json(body) + b"\n"
                )
            return identity
        if args.command == "publish-lane-ledger":
            body = _load(args.lane_ledger, label="lane ledger")
            # Rebuild from its exact stage identities before publication.
            rows = body.get("ordered_stage_rows")
            if not isinstance(rows, list):
                raise transport.T230TransportError("lane ledger rows differ")
            stage_identities: list[Mapping[str, object]] = []
            for row in rows:
                if not isinstance(row, Mapping):
                    raise transport.T230TransportError("lane ledger row differs")
                stage_identities.extend((
                    row.get("worker_stage_receipt_identity", {}),
                    row.get("verifier_stage_receipt_identity", {}),
                ))
            expected = transport.build_lane_ledger_v1(
                transport_contract_sha256=contract_hash,
                lane_ordinal=args.lane_ordinal,
                stage_receipt_identities=stage_identities,
                read_exact=backend.read,
            )
            if transport.canonical_json(body) != transport.canonical_json(expected):
                raise transport.T230TransportError("lane ledger exact replay differs")
            publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.lane_ledger_uri(args.lane_ordinal),
                raw=transport.canonical_json(expected),
                transition_id=f"publish-lane-{args.lane_ordinal}-ledger",
            )
            return {"lane_ledger": expected, **publication}
        if args.command == "publish-benchmark-execution-terminal":
            terminal = transport.build_benchmark_execution_terminal_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=_identity_from_args(
                    args, "worker_stage_receipt"
                ),
                observed_terminal=_load(
                    args.observed_terminal,
                    label="benchmark execution terminal projection",
                ),
                read_exact=backend.read,
            )
            publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.BENCHMARK_EXECUTION_TERMINAL_URI,
                raw=transport.canonical_json(terminal),
                transition_id="publish-benchmark-execution-terminal",
            )
            return {"benchmark_execution_terminal": terminal, **publication}
        if args.command == "build-benchmark":
            raw_identity = _identity_from_args(args, "raw_time_v")
            benchmark = transport.build_benchmark_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=_identity_from_args(
                    args, "worker_stage_receipt"
                ),
                benchmark_disposition_identity=_identity_from_args(
                    args, "benchmark_disposition"
                ),
                raw_time_v_identity=raw_identity,
                raw_time_v=backend.read(raw_identity),
                read_exact=backend.read,
            )
            _write_once(
                args.output, transport.canonical_json(benchmark) + b"\n"
            )
            return benchmark
        if args.command == "resume-benchmark-transaction":
            worker_identity, _worker_raw = (
                transport.recover_or_complete_publication(
                    backend=backend,
                    target_uri=transport._stage_uri("run-slate", 0),
                    publication_binding_sha256=contract_hash,
                )
            )
            disposition_identity, disposition_raw = (
                transport.recover_or_complete_publication(
                    backend=backend,
                    target_uri=transport.BENCHMARK_DISPOSITION_URI,
                    publication_binding_sha256=contract_hash,
                )
            )
            retained_disposition = transport.strict_json(
                disposition_raw, label="resumed benchmark disposition"
            )
            if retained_disposition.get("state") != "raw-ready":
                raise transport.T230TransportError(
                    "benchmark disposition is terminal-abort; resume is forbidden"
                )
            retained_raw_text = retained_disposition.get("raw_time_v_utf8")
            if not isinstance(retained_raw_text, str):
                raise transport.T230TransportError(
                    "raw-ready disposition lacks retained mechanics bytes"
                )
            raw = retained_raw_text.encode("utf-8")
            try:
                raw_identity, recovered_raw = (
                    transport.recover_or_complete_publication(
                        backend=backend,
                        target_uri=transport.RAW_TIME_V_URI,
                        publication_binding_sha256=contract_hash,
                    )
                )
            except FileNotFoundError:
                raw_publication = transport.RecoverablePublisher(
                    backend, contract_hash
                ).publish(
                    target_uri=transport.RAW_TIME_V_URI,
                    raw=raw,
                    transition_id="publish-benchmark-raw-time-v",
                )
                raw_identity = raw_publication["target_identity"]
                recovered_raw = backend.read(raw_identity)
            if recovered_raw != raw:
                raise transport.T230TransportError(
                    "resumed raw time-v differs from its prior disposition"
                )
            expected_disposition = transport.build_benchmark_disposition_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=worker_identity,
                state="raw-ready",
                raw_time_v_binding={
                    "uri": raw_identity["uri"],
                    "sha256": raw_identity["sha256"],
                    "bytes": raw_identity["bytes"],
                },
                raw_time_v=raw,
                benchmark_execution_terminal_identity=None,
                read_exact=backend.read,
            )
            if disposition_raw != transport.canonical_json(expected_disposition):
                raise transport.T230TransportError(
                    "resumed raw-ready disposition differs"
                )
            benchmark = transport.build_benchmark_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=worker_identity,
                benchmark_disposition_identity=disposition_identity,
                raw_time_v_identity=raw_identity,
                raw_time_v=raw,
                read_exact=backend.read,
            )
            benchmark_publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.BENCHMARK_URI,
                raw=transport.canonical_json(benchmark),
                transition_id="publish-benchmark",
            )
            release = transport.build_compute_release_v1(
                benchmark_identity=benchmark_publication["target_identity"],
                benchmark=benchmark,
                read_exact=backend.read,
            )
            compute_publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.COMPUTE_RELEASE_URI,
                raw=transport.canonical_json(release),
                transition_id="publish-compute-release",
            )
            return {
                "benchmark_identity": benchmark_publication["target_identity"],
                "compute_release_identity": compute_publication["target_identity"],
                "resumed_without_science_relaunch": True,
            }
        if args.command == "publish-raw-time-v":
            raw = args.raw_time_v.read_bytes()
            transport.parse_gnu_time_v_v1(raw)
            worker_identity = _identity_from_args(args, "worker_stage_receipt")
            raw_binding = {
                "uri": transport.RAW_TIME_V_URI,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            disposition = transport.build_benchmark_disposition_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=worker_identity,
                state="raw-ready",
                raw_time_v_binding=raw_binding,
                raw_time_v=raw,
                benchmark_execution_terminal_identity=None,
                read_exact=backend.read,
            )
            disposition_publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.BENCHMARK_DISPOSITION_URI,
                raw=transport.canonical_json(disposition),
                transition_id="benchmark-disposition-raw-ready",
            )
            publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.RAW_TIME_V_URI,
                raw=raw,
                transition_id="publish-benchmark-raw-time-v",
            )
            published_raw = publication["target_identity"]
            if {
                "uri": published_raw["uri"],
                "sha256": published_raw["sha256"],
                "bytes": published_raw["bytes"],
            } != raw_binding:
                raise transport.T230TransportError(
                    "published raw time-v differs from prior disposition"
                )
            return {
                "raw_time_v_identity": publication["target_identity"],
                "benchmark_disposition_identity": disposition_publication[
                    "target_identity"
                ],
            }
        if args.command == "publish-benchmark":
            benchmark = transport.validate_benchmark_v1(
                _load(args.benchmark, label="benchmark")
            )
            if benchmark["transport_contract_identity"] != contract_identity:
                raise transport.T230TransportError(
                    "benchmark differs from the publication contract identity"
                )
            raw_identity = batch.normalize_object_identity(
                benchmark["raw_time_v_identity"], label="benchmark raw time-v"
            )
            expected = transport.build_benchmark_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=batch.normalize_object_identity(
                    benchmark["worker_stage_receipt_identity"],
                    label="benchmark worker stage",
                ),
                benchmark_disposition_identity=batch.normalize_object_identity(
                    benchmark["benchmark_disposition_identity"],
                    label="benchmark disposition",
                ),
                raw_time_v_identity=raw_identity,
                raw_time_v=backend.read(raw_identity),
                read_exact=backend.read,
            )
            if transport.canonical_json(benchmark) != transport.canonical_json(
                expected
            ):
                raise transport.T230TransportError(
                    "benchmark differs from exact contract/stage replay"
                )
            publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.BENCHMARK_URI,
                raw=transport.canonical_json(benchmark),
                transition_id="publish-benchmark",
            )
            return {"benchmark": benchmark, **publication}
        if args.command == "publish-benchmark-terminal-abort":
            try:
                backend.read_known_uri(transport.COMPUTE_RELEASE_URI)
            except FileNotFoundError:
                pass
            else:
                raise transport.T230TransportError(
                    "compute release exists; benchmark abort is forbidden"
                )
            for recoverable_uri in (
                transport.RAW_TIME_V_URI, transport.BENCHMARK_URI
            ):
                try:
                    backend.read_known_uri(recoverable_uri)
                except FileNotFoundError:
                    continue
                raise transport.T230TransportError(
                    "recoverable benchmark evidence exists; terminal abort is forbidden"
                )
            worker_identity = _identity_from_args(args, "worker_stage_receipt")
            terminal_identity = _identity_from_args(
                args, "benchmark_execution_terminal"
            )
            disposition = transport.build_benchmark_disposition_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=worker_identity,
                state="terminal-abort",
                raw_time_v_binding=None,
                raw_time_v=None,
                benchmark_execution_terminal_identity=terminal_identity,
                read_exact=backend.read,
            )
            disposition_publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.BENCHMARK_DISPOSITION_URI,
                raw=transport.canonical_json(disposition),
                transition_id="benchmark-disposition-terminal-abort",
            )
            abort = transport.build_benchmark_terminal_abort_v1(
                transport_contract_identity=contract_identity,
                transport_contract=contract,
                worker_stage_receipt_identity=worker_identity,
                benchmark_disposition_identity=disposition_publication[
                    "target_identity"
                ],
                benchmark_execution_terminal_identity=terminal_identity,
                read_exact=backend.read,
            )
            publication = transport.RecoverablePublisher(
                backend, contract_hash
            ).publish(
                target_uri=transport.BENCHMARK_ABORT_URI,
                raw=transport.canonical_json(abort),
                transition_id="benchmark-terminal-abort",
            )
            return {"benchmark_terminal_abort": abort, **publication}
        if args.command == "resolve-compute-release":
            identity, raw = transport.recover_or_complete_publication(
                backend=backend,
                target_uri=transport.COMPUTE_RELEASE_URI,
                publication_binding_sha256=contract_hash,
            )
            compute_release = transport.reopen_compute_release_v1(
                compute_release_identity=identity,
                read_exact=backend.read,
            )
            if compute_release["transport_contract_identity"] != contract_identity:
                raise transport.T230TransportError(
                    "resolved compute release contract differs"
                )
            _write_once(args.output, transport.canonical_json(identity) + b"\n")
            return identity
        benchmark_identity = _identity_from_args(args, "benchmark")
        benchmark_body = transport.strict_json(
            backend.read(benchmark_identity), label="benchmark"
        )
        release = transport.build_compute_release_v1(
            benchmark_identity=benchmark_identity,
            benchmark=benchmark_body,
            read_exact=backend.read,
        )
        if release["transport_contract_identity"] != contract_identity:
            raise transport.T230TransportError(
                "compute publication contract differs"
            )
        publication = transport.RecoverablePublisher(
            backend, contract_hash
        ).publish(
            target_uri=transport.COMPUTE_RELEASE_URI,
            raw=transport.canonical_json(release),
            transition_id="publish-compute-release",
        )
        return {"compute_release": release, **publication}
    if args.command == "run-stage":
        contract_identity = _identity_from_args(args, "transport_contract")
        predecessor_identities = [
            batch.normalize_object_identity(
                _load(path, label="stage predecessor identity"),
                label="stage predecessor identity",
            )
            for path in args.predecessor_identity
        ]
        compute_required = not (
            args.operation == "prepare"
            or (args.operation == "run-slate" and args.source_ordinal == 0)
        )
        if compute_required:
            if args.compute_release_uri is None:
                raise transport.T230TransportError(
                    "post-benchmark stage requires the exact compute release"
                )
            compute_identity = _identity_from_args(args, "compute_release")
            compute_release = transport.reopen_compute_release_v1(
                compute_release_identity=compute_identity,
                read_exact=backend.read,
            )
            if compute_release["transport_contract_identity"] != contract_identity:
                raise transport.T230TransportError(
                    "compute release differs from the run-stage transport contract"
                )
        elif args.compute_release_uri is not None:
            raise transport.T230TransportError(
                "prepare/benchmark worker cannot consume a compute release"
            )
        identities: dict[str, object] = {}
        if args.operation != "prepare":
            identities["execution_authority_identity"] = _identity_from_args(
                args, "execution_authority"
            )
        if args.operation == "verify-slate":
            identities["result_identity"] = _identity_from_args(args, "result")
        if args.operation == "finish-panel":
            if len(args.lane_ledger) != 2:
                raise transport.T230TransportError(
                    "finish-panel requires two ordered lane ledger files"
                )
            contract_raw = backend.read(contract_identity)
            contract_body = transport.strict_json(
                contract_raw, label="transport contract"
            )
            contract_hash = str(contract_body["transport_contract_sha256"])
            acceptances: list[dict[str, object]] = []
            for lane_ordinal, path in enumerate(args.lane_ledger):
                lane_identity = batch.normalize_object_identity(
                    _load(path, label=f"lane ledger identity[{lane_ordinal}]"),
                    label="lane ledger identity",
                )
                ledger = transport.reopen_lane_ledger_v1(
                    lane_ledger_identity=lane_identity,
                    transport_contract_sha256=contract_hash,
                    lane_ordinal=lane_ordinal,
                    read_exact=backend.read,
                )
                acceptances.extend(
                    dict(row["acceptance_identity"])
                    for row in ledger["ordered_stage_rows"]
                )
            identities["acceptance_identities"] = acceptances
        return run_core_stage(
            backend=backend,
            transport_contract_identity=contract_identity,
            operation=args.operation,
            source_ordinal=args.source_ordinal,
            runtime_attempt_ordinal=args.runtime_attempt_ordinal,
            cloud_execution_name=args.cloud_execution_name,
            cloud_job=args.cloud_job,
            cloud_task_index=args.cloud_task_index,
            cloud_task_attempt=args.cloud_task_attempt,
            cloud_task_count=args.cloud_task_count,
            runtime_image=_image_from_arg(args.runtime_image),
            launch_request_identity=_identity_from_args(
                args, "launch_request"
            ),
            launch_request_intent_identity=_identity_from_args(
                args, "launch_request_intent"
            ),
            launch_request_completion_identity=_identity_from_args(
                args, "launch_request_completion"
            ),
            predecessor_identities=predecessor_identities,
            identities=identities,
        )
    raise transport.T230TransportError("unknown T230 transport command")


def main(argv: Sequence[str] | None = None) -> int:
    result = run(sys.argv[1:] if argv is None else argv)
    sys.stdout.buffer.write(transport.canonical_json(result) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
