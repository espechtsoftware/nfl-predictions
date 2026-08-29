#!/usr/bin/env python3
"""Guarded operator for fixed-G0 catalog recovery attempt three."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess
from typing import Final

from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as recovery
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter,
)


SUMMARY_SCHEMA: Final = "corpus-r6-fixed-g0-catalog-recovery-summary/v3"
REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
FOCUSED_TEST_ENV: Final = {
    "LC_ALL": "C.UTF-8",
    "PYTEST_ADDOPTS": "",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONPATH": "",
}
class RecoveryGCSBackendV1:
    """Generation transport plus metadata-only exact-prefix inventory."""

    def __init__(self, generation_backend: adapter.GCSGenerationBackendV1) -> None:
        self.generation_backend = generation_backend

    def transport(self) -> adapter.GenerationTransportV1:
        return self.generation_backend.transport()

    def list_prefix_inventory(self, prefix: str) -> list[dict[str, object]]:
        tail = prefix.removeprefix("gs://")
        bucket_name, marker, object_prefix = tail.partition("/")
        if (
            not prefix.startswith("gs://")
            or not marker
            or not bucket_name
            or not object_prefix
            or not prefix.endswith("/")
        ):
            _fail("catalog census prefix differs")
        client = self.generation_backend._client
        rows: list[dict[str, object]] = []
        for blob in client.list_blobs(bucket_name, prefix=object_prefix):
            generation = str(getattr(blob, "generation", ""))
            size = getattr(blob, "size", None)
            name = str(getattr(blob, "name", ""))
            relative_name = name.removeprefix(object_prefix)
            if (
                not name.startswith(object_prefix)
                or not relative_name
                or any(part in {"", ".", ".."} for part in relative_name.split("/"))
            ):
                _fail("catalog census blob name escapes the exact prefix")
            rows.append({
                "uri": f"gs://{bucket_name}/{name}",
                "generation": generation,
                "bytes": size,
            })
        return recovery.normalize_prefix_inventory_v1(
            sorted(rows, key=lambda row: str(row["uri"]))
        )


BackendFactory = Callable[[], RecoveryGCSBackendV1]


class RunCorpusR6FixedG0CatalogRecoveryV1Error(RuntimeError):
    """The guarded catalog recovery operator failed closed."""

    def __init__(
        self, message: str, *, partial_summary: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.partial_summary = None if partial_summary is None else dict(partial_summary)


def _fail(message: str) -> None:
    raise RunCorpusR6FixedG0CatalogRecoveryV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return adapter._normalized_identity(value, label=label)
    except Exception as exc:
        raise RunCorpusR6FixedG0CatalogRecoveryV1Error(str(exc)) from exc


def _default_backend_factory() -> RecoveryGCSBackendV1:
    return RecoveryGCSBackendV1(
        adapter.GCSGenerationBackendV1.from_default_client()
    )


def _clean_context() -> tuple[
    adapter.SubprocessGitRepositoryV1,
    str,
    list[dict[str, object]],
    dict[str, str],
]:
    repository = adapter.SubprocessGitRepositoryV1(REPOSITORY_ROOT)
    head = repository.require_current_clean_head()
    origins = recovery.verify_module_origins_v1(
        REPOSITORY_ROOT, runner_file=Path(__file__)
    )
    measurements = recovery.measure_implementation_v1(repository, head)
    return repository, head, measurements, origins


def _planned_source_audit_v1(
    *,
    base_transport: adapter.GenerationTransportV1,
    mode: str,
    task_ordinals: Sequence[int],
    fixed_outer_identity: Mapping[str, object] | None = None,
) -> recovery.TransportAuditV1:
    extras: list[dict[str, object]] = []
    if fixed_outer_identity is not None:
        normalized_outer = _identity(
            fixed_outer_identity, label="fixed outer read-plan identity"
        )
        if normalized_outer["uri"] != recovery.OUTER_ATTESTATION_URI:
            _fail("outer identity URI differs from the fixed recovery root")
        extras.append(normalized_outer)
    panel_identity = adapter._normalized_identity(
        adapter.FIXED_PINS.panel_identity, label="fixed source-plan panel"
    )
    audit = recovery.TransportAuditV1(
        base_transport,
        mode=mode,
        allowed_read_identities=[panel_identity],
        panel_task_ordinals=task_ordinals,
        planned_output_uris=(
            recovery.planned_inner_output_uris_v1()
            if mode == "publish"
            else ()
        ),
    )
    panel_raw = adapter.read_generation_exact_v1(
        panel_identity, transport=audit.transport()
    )
    audit.bind_planned_read_identities_v1(
        [
            *recovery.source_read_allowlist_v1(
                pins=adapter.FIXED_PINS,
                task_ordinals=task_ordinals,
                exact_panel_raw=panel_raw,
            ),
            *extras,
        ]
    )
    return audit


def run_smoke_v1(
    *,
    repository: adapter.SubprocessGitRepositoryV1,
    source_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    module_origins: Mapping[str, object],
    base_review: adapter.AdapterReviewBindingV1,
    base_transport: adapter.GenerationTransportV1,
) -> dict[str, object]:
    """Run task 0 through a transport that cannot resolve or create outputs."""
    audit = _planned_source_audit_v1(
        base_transport=base_transport, mode="read_only", task_ordinals=(0,)
    )
    try:
        inputs = adapter._derive_pinned_projection_inputs_v1(
            pins=adapter.FIXED_PINS,
            adapter_review=base_review,
            read_tracked=repository.read_tracked,
            transport=audit.transport(),
            task_evidence_ordinals=(0,),
        )
        evidence = recovery.build_smoke_evidence_v1(
            source_commit_sha=source_commit_sha,
            implementation_measurements=implementation_measurements,
            module_origins=module_origins,
            inputs=inputs,
            transport_audit=audit.snapshot_v1(),
        )
        return recovery.validate_smoke_evidence_v1(evidence)
    except Exception as exc:
        raise RunCorpusR6FixedG0CatalogRecoveryV1Error(
            f"read-only real task-0 recovery smoke failed: {exc}",
            partial_summary={
                "schema_version": SUMMARY_SCHEMA,
                "mode": "smoke",
                "transport_audit": audit.snapshot_v1(),
                "cloud_mutation_performed": False,
                "complete": False,
            },
        ) from exc


def run_smoke_production_v1(
    *, backend_factory: BackendFactory = _default_backend_factory,
) -> dict[str, object]:
    repository, head, measurements, origins = _clean_context()
    base_review = recovery.resolve_base_adapter_review_v1(repository)
    backend = backend_factory()
    return run_smoke_v1(
        repository=repository,
        source_commit_sha=head,
        implementation_measurements=measurements,
        module_origins=origins,
        base_review=base_review,
        base_transport=backend.transport(),
    )


def _reviewed_implementation_from_smoke_v1(
    *,
    repository: adapter.SubprocessGitRepositoryV1,
    current_head: str,
    smoke: Mapping[str, object],
) -> tuple[str, list[dict[str, object]]]:
    """Retain H0 evidence across later artifact-only descendant commits."""
    implementation_commit = str(smoke["source_commit_sha"])
    recovery.require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=implementation_commit,
        descendant_commit_sha=current_head,
        label="smoke-implementation-to-current-head",
    )
    measurements = recovery.reopen_implementation_v1(
        repository,
        implementation_commit_sha=implementation_commit,
        measurements=smoke["implementation_measurements"],
    )
    recovery.verify_current_implementation_v1(
        repository,
        current_head=current_head,
        reviewed_measurements=measurements,
    )
    return implementation_commit, measurements


def run_empty_prefix_census_production_v1(
    *,
    checked_at_utc: str,
    backend_factory: BackendFactory = _default_backend_factory,
) -> dict[str, object]:
    repository, head, _, _ = _clean_context()
    try:
        smoke_raw = repository.read_tracked(head, recovery.SMOKE_EVIDENCE_PATH)
    except Exception as exc:
        raise RunCorpusR6FixedG0CatalogRecoveryV1Error(
            "tracked recovery smoke is required before the prefix census"
        ) from exc
    smoke = recovery.validate_smoke_evidence_v1(
        recovery._parse_json(smoke_raw, label="tracked recovery smoke")
    )
    implementation_commit, measurements = (
        _reviewed_implementation_from_smoke_v1(
            repository=repository,
            current_head=head,
            smoke=smoke,
        )
    )
    backend = backend_factory()
    inventory = backend.list_prefix_inventory(adapter.FIXED_CATALOG_NAMESPACE)
    return recovery.validate_empty_prefix_evidence_v1(
        recovery.build_empty_prefix_evidence_v1(
            checked_at_utc=checked_at_utc,
            source_commit_sha=implementation_commit,
            implementation_measurements=measurements,
            observed_prefix_inventory=inventory,
        ),
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
    )


def run_focused_tests_production_v1() -> dict[str, object]:
    """Closed local runner: fixed argv, observed exit, invocation-owned JUnit."""
    repository, head, _, _ = _clean_context()
    smoke_raw = repository.read_tracked(head, recovery.SMOKE_EVIDENCE_PATH)
    smoke = recovery.validate_smoke_evidence_v1(
        recovery._parse_json(smoke_raw, label="tracked recovery smoke")
    )
    implementation_commit, measurements = (
        _reviewed_implementation_from_smoke_v1(
            repository=repository,
            current_head=head,
            smoke=smoke,
        )
    )
    junit_path = Path(recovery.FOCUSED_TEST_RUNTIME_JUNIT_PATH)
    frozen_junit_path = REPOSITORY_ROOT / recovery.FOCUSED_TEST_OUTPUT_PATH
    receipt_path = REPOSITORY_ROOT / recovery.FOCUSED_TEST_RECEIPT_PATH
    if receipt_path.exists() and not frozen_junit_path.exists():
        _fail("focused-test receipt exists without its frozen JUnit")
    if frozen_junit_path.exists():
        output_raw = frozen_junit_path.read_bytes()
        receipt = recovery.build_focused_test_receipt_v1(
            implementation_commit_sha=implementation_commit,
            implementation_measurements=measurements,
            output_file=recovery.file_binding(
                recovery.FOCUSED_TEST_OUTPUT_PATH, output_raw
            ),
            exact_output_raw=output_raw,
        )
        if receipt_path.exists():
            retained = recovery._parse_json(
                receipt_path.read_bytes(), label="existing focused-test receipt"
            )
            return recovery.validate_focused_test_receipt_v1(
                retained,
                implementation_commit_sha=implementation_commit,
                implementation_measurements=measurements,
                exact_output_raw=output_raw,
            )
        recovery.write_local_create_once_v1(
            repository_root=REPOSITORY_ROOT,
            relative_path=recovery.FOCUSED_TEST_RECEIPT_PATH,
            body=receipt,
        )
        return receipt
    if junit_path.exists():
        if junit_path.is_symlink() or not junit_path.is_file():
            _fail("focused-test runtime JUnit is not a regular owned file")
        junit_path.unlink()
    completed = subprocess.run(
        list(recovery.FOCUSED_TEST_COMMAND),
        cwd=REPOSITORY_ROOT,
        check=False,
        env=dict(FOCUSED_TEST_ENV),
    )
    if completed.returncode != 0 or not junit_path.is_file():
        _fail("closed focused-test invocation did not pass")
    output_raw = junit_path.read_bytes()
    receipt = recovery.build_focused_test_receipt_v1(
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        output_file=recovery.file_binding(
            recovery.FOCUSED_TEST_OUTPUT_PATH, output_raw
        ),
        exact_output_raw=output_raw,
    )
    recovery.write_local_raw_create_once_v1(
        repository_root=REPOSITORY_ROOT,
        relative_path=recovery.FOCUSED_TEST_OUTPUT_PATH,
        raw=output_raw,
    )
    recovery.write_local_create_once_v1(
        repository_root=REPOSITORY_ROOT,
        relative_path=recovery.FOCUSED_TEST_RECEIPT_PATH,
        body=receipt,
    )
    return receipt


def build_review_lock_production_v1(
    *,
    output_relative_path: str,
    independent_review_disposition: str,
    p0_open_count: int,
    p1_open_count: int,
    p2_open_count: int,
) -> dict[str, object]:
    if output_relative_path != recovery.REVIEW_LOCK_PATH:
        _fail("recovery review-lock output path differs")
    repository, head, _, _ = _clean_context()
    recovery.reopen_historical_evidence_v1(repository)
    try:
        smoke_raw = repository.read_tracked(head, recovery.SMOKE_EVIDENCE_PATH)
        empty_raw = repository.read_tracked(head, recovery.EMPTY_PREFIX_EVIDENCE_PATH)
        focused_receipt_raw = repository.read_tracked(
            head, recovery.FOCUSED_TEST_RECEIPT_PATH
        )
        focused_raw = repository.read_tracked(head, recovery.FOCUSED_TEST_OUTPUT_PATH)
    except Exception as exc:
        raise RunCorpusR6FixedG0CatalogRecoveryV1Error(
            "tracked smoke/empty-prefix/focused evidence is incomplete"
        ) from exc
    smoke = recovery.validate_smoke_evidence_v1(
        recovery._parse_json(smoke_raw, label="tracked recovery smoke")
    )
    implementation_commit = str(smoke["source_commit_sha"])
    measurements = recovery.reopen_implementation_v1(
        repository,
        implementation_commit_sha=implementation_commit,
        measurements=smoke["implementation_measurements"],
    )
    recovery.require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=implementation_commit,
        descendant_commit_sha=head,
        label="review-implementation-to-current-head",
    )
    recovery.verify_current_implementation_v1(
        repository,
        current_head=head,
        reviewed_measurements=measurements,
    )
    empty = recovery.validate_empty_prefix_evidence_v1(
        recovery._parse_json(empty_raw, label="tracked empty-prefix evidence"),
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
    )
    lock = recovery.build_review_lock_v1(
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        smoke_evidence_file=recovery.file_binding(recovery.SMOKE_EVIDENCE_PATH, smoke_raw),
        smoke_evidence=smoke,
        empty_prefix_evidence_file=recovery.file_binding(
            recovery.EMPTY_PREFIX_EVIDENCE_PATH, empty_raw
        ),
        empty_prefix_evidence=empty,
        focused_test_receipt_file=recovery.file_binding(
            recovery.FOCUSED_TEST_RECEIPT_PATH, focused_receipt_raw
        ),
        focused_test_receipt=recovery._parse_json(
            focused_receipt_raw, label="tracked focused-test receipt"
        ),
        focused_test_output_raw=focused_raw,
        independent_review_disposition=independent_review_disposition,
        p0_open_count=p0_open_count,
        p1_open_count=p1_open_count,
        p2_open_count=p2_open_count,
    )
    recovery.write_local_create_once_v1(
        repository_root=REPOSITORY_ROOT,
        relative_path=output_relative_path,
        body=lock,
    )
    return lock


def build_final_lock_production_v1(
    *, output_relative_path: str, publication_approved: bool,
) -> dict[str, object]:
    if output_relative_path != recovery.FINAL_LOCK_PATH or publication_approved is not True:
        _fail("recovery final-lock output/approval differs")
    repository, head, _, _ = _clean_context()
    review, review_file = recovery.resolve_review_lock_v1(
        repository,
        review_lock_commit_sha=head,
        current_head=head,
    )
    lock = recovery.build_final_lock_v1(
        review_lock_commit_sha=head,
        review_lock_file=review_file,
        review_lock=review,
        publication_approved=True,
    )
    recovery.write_local_create_once_v1(
        repository_root=REPOSITORY_ROOT,
        relative_path=output_relative_path,
        body=lock,
    )
    return lock


def build_attempt_marker_production_v1(
    *, output_relative_path: str,
) -> dict[str, object]:
    """Reserve attempt three durably before any cloud client can exist."""
    if output_relative_path != recovery.ATTEMPT_PATH:
        _fail("recovery attempt-marker output path differs")
    repository, head, _, _ = _clean_context()
    capability = recovery.resolve_final_capability_v1(
        repository,
        final_lock_commit_sha=head,
        current_head=head,
    )
    marker = recovery.build_attempt_marker_v1(
        capability=capability,
        require_final_lock_at_head=True,
    )
    recovery.write_local_create_once_v1(
        repository_root=REPOSITORY_ROOT,
        relative_path=output_relative_path,
        body=marker,
    )
    return marker


def _inner_result_exact_reopen(
    *,
    capability: recovery.PublicationCapabilityV1,
    repository: adapter.SubprocessGitRepositoryV1,
    transport: adapter.GenerationTransportV1,
    replay_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    reopened = adapter._reopen_pinned_replay_receipt_v1(
        pins=adapter.FIXED_PINS,
        adapter_review=capability.base_adapter_review,
        replay_receipt_identity=replay_receipt_identity,
        read_tracked=repository.read_tracked,
        transport=transport,
    )
    receipt = _mapping(reopened.get("replay_receipt"), label="reopened inner receipt")
    release = _mapping(reopened.get("catalog_release"), label="reopened inner release")
    if (
        receipt.get("task_count") != adapter.catalog.TASK_COUNT
        or release.get("task_count") != adapter.catalog.TASK_COUNT
        or receipt.get("outcome_columns_read") != []
        or receipt.get("uses_realized_outcomes") is not False
    ):
        _fail("reopened inner catalog chain differs")
    return reopened


def run_publish_v1() -> dict[str, object]:
    """Only mutation boundary; every authority-bearing dependency is fixed here."""
    if os.environ.get(recovery.ENABLE_ENV) != "1":
        _fail("fixed-G0 catalog recovery publication is parked")
    repository = adapter.SubprocessGitRepositoryV1(REPOSITORY_ROOT)
    head = repository.require_current_clean_head()
    recovery.verify_module_origins_v1(REPOSITORY_ROOT, runner_file=Path(__file__))
    recovery.measure_implementation_v1(repository, head)
    capability, attempt_binding = recovery.resolve_tracked_attempt_binding_v1(
        repository=repository,
        current_head=head,
    )
    validated_capability = recovery.validate_resolved_authority_v1(capability)
    validated_attempt = recovery.validate_tracked_attempt_binding_v1(
        attempt_binding, capability=validated_capability
    )
    attempt_marker = _mapping(
        validated_attempt.marker, label="tracked publication attempt marker"
    )
    attempt_marker_file = _mapping(
        validated_attempt.marker_file, label="tracked publication attempt file"
    )
    if os.environ.get(recovery.ENABLE_ENV) != "1":
        _fail("fixed-G0 catalog recovery publication is parked")
    backend = _default_backend_factory()
    preflight_inventory: list[dict[str, object]] | None = None
    try:
        preflight_inventory = backend.list_prefix_inventory(
            adapter.FIXED_CATALOG_NAMESPACE
        )
        allowed_output_uris = {
            *recovery.planned_inner_output_uris_v1(),
            recovery.OUTER_ATTESTATION_URI,
        }
        unexpected_preflight_uris = [
            str(row["uri"])
            for row in preflight_inventory
            if str(row["uri"]) not in allowed_output_uris
        ]
        if unexpected_preflight_uris:
            _fail("pre-write recovery output inventory contains an unplanned URI")
    except Exception as exc:
        raise RunCorpusR6FixedG0CatalogRecoveryV1Error(
            f"pre-write recovery output census failed: {exc}",
            partial_summary={
                "schema_version": SUMMARY_SCHEMA,
                "mode": "publish",
                "preflight_prefix_inventory": preflight_inventory,
                "cloud_mutation_performed": False,
                "outcome_columns_read": [],
                "uses_realized_outcomes": False,
                "complete": False,
            },
        ) from exc
    if (
        repository.require_current_clean_head() != head
        or os.environ.get(recovery.ENABLE_ENV) != "1"
    ):
        _fail("publication authority changed before the mutation boundary")
    all_task_ordinals = tuple(range(adapter.catalog.TASK_COUNT))
    audit = _planned_source_audit_v1(
        base_transport=backend.transport(),
        mode="publish",
        task_ordinals=all_task_ordinals,
    )
    transport = audit.transport()
    pre_root_inventory: list[dict[str, object]] | None = None
    terminal_inventory: list[dict[str, object]] | None = None
    outer_presence_state = "unknown"
    try:
        published = adapter._publish_pinned_projection_release_v1(
            pins=adapter.FIXED_PINS,
            adapter_review=validated_capability.base_adapter_review,
            read_tracked=repository.read_tracked,
            transport=transport,
            request_authoritative_publication=False,
        )
        reopened = _inner_result_exact_reopen(
            capability=validated_capability,
            repository=repository,
            transport=transport,
            replay_receipt_identity=_mapping(
                published.get("replay_receipt_identity"),
                label="published inner receipt identity",
            ),
        )
        if reopened["replay_receipt"] != published["replay_receipt"]:
            _fail("published inner receipt differs on explicit exact reopen")
        manifest = recovery.ordered_inner_object_manifest_v1(
            release_identity=reopened["catalog_release_identity"],
            release=reopened["catalog_release"],
            receipt_identity=reopened["replay_receipt_identity"],
        )
        if tuple(str(row["identity"]["uri"]) for row in manifest) != recovery.planned_inner_output_uris_v1():
            _fail("inner object manifest URI order differs from the fixed plan")
        expected_inner_inventory = recovery.prefix_inventory_from_identities_v1(
            [row["identity"] for row in manifest]
        )
        pre_root_inventory = backend.list_prefix_inventory(
            adapter.FIXED_CATALOG_NAMESPACE
        )
        outer_presence_state = (
            "confirmed-present"
            if any(
                row["uri"] == recovery.OUTER_ATTESTATION_URI
                for row in pre_root_inventory
            )
            else "confirmed-absent"
        )
        exact_inner_pre_root = pre_root_inventory == expected_inner_inventory
        pre_root_outer_rows = [
            row for row in pre_root_inventory
            if row["uri"] == recovery.OUTER_ATTESTATION_URI
        ]
        pre_root_inner_rows = [
            row for row in pre_root_inventory
            if row["uri"] != recovery.OUTER_ATTESTATION_URI
        ]
        resumable_outer_pre_root = (
            len(pre_root_inventory) == recovery.EXPECTED_TOTAL_OBJECT_COUNT
            and pre_root_inner_rows == expected_inner_inventory
            and len(pre_root_outer_rows) == 1
        )
        if not exact_inner_pre_root and not resumable_outer_pre_root:
            _fail("pre-root recovery output inventory differs")
        audit.activate_outer_after_pre_root_v1()
        outer = recovery.build_outer_attestation_v1(
            capability=validated_capability,
            attempt_binding=validated_attempt,
            release_identity=reopened["catalog_release_identity"],
            release=reopened["catalog_release"],
            replay_receipt_identity=reopened["replay_receipt_identity"],
            replay_receipt=reopened["replay_receipt"],
        )
        outer_identity = adapter.publish_create_once_resumable_v1(
            recovery.OUTER_ATTESTATION_URI,
            recovery.canonical_json_bytes(outer),
            transport=transport,
        )
        outer_presence_state = "confirmed-present"
        exact_outer = recovery._reopen_outer_structure_v1(
            outer_identity=outer_identity,
            capability=validated_capability,
            attempt_binding=validated_attempt,
            transport=transport,
        )
        if exact_outer["outer_attestation"] != outer:
            _fail("outer recovery attestation differs after exact reopen")
        expected_inventory = recovery.prefix_inventory_from_identities_v1([
            *(row["identity"] for row in manifest),
            outer_identity,
        ])
        terminal_inventory = backend.list_prefix_inventory(
            adapter.FIXED_CATALOG_NAMESPACE
        )
        snapshot = audit.snapshot_v1()
        if (
            terminal_inventory != expected_inventory
            or len(terminal_inventory) != recovery.EXPECTED_TOTAL_OBJECT_COUNT
        ):
            _fail("terminal recovery output inventory differs")
        return {
            "schema_version": SUMMARY_SCHEMA,
            "mode": "publish",
            "publication_commit_sha": validated_capability.current_clean_commit_sha,
            "implementation_commit_sha": validated_capability.implementation_commit_sha,
            "review_lock_file": dict(validated_capability.review_lock_file),
            "final_lock_file": dict(validated_capability.final_lock_file),
            "attempt_marker_file": dict(attempt_marker_file),
            "inner_catalog_release_identity": _identity(
                reopened["catalog_release_identity"], label="summary inner release"
            ),
            "inner_replay_receipt_identity": _identity(
                reopened["replay_receipt_identity"], label="summary inner receipt"
            ),
            "outer_attestation_identity": _identity(
                outer_identity, label="summary outer attestation"
            ),
            "outer_attestation_sha256": outer["recovery_attestation_sha256"],
            "inner_object_count": recovery.EXPECTED_INNER_OBJECT_COUNT,
            "total_object_count": recovery.EXPECTED_TOTAL_OBJECT_COUNT,
            "transport_audit": snapshot,
            "pre_root_prefix_inventory": pre_root_inventory,
            "pre_root_prefix_inventory_sha256": recovery.canonical_sha256(
                pre_root_inventory
            ),
            "terminal_prefix_inventory": terminal_inventory,
            "terminal_prefix_inventory_sha256": recovery.canonical_sha256(
                terminal_inventory
            ),
            "outer_published_last": True,
            "outer_presence_state": outer_presence_state,
            "pre_root_state": (
                "exact-110-inner-before-root"
                if exact_inner_pre_root
                else "exact-111-resume-existing-root"
            ),
            "inner_exact_reopen_complete": True,
            "downstream_pin_identity": _identity(
                outer_identity, label="downstream outer identity"
            ),
            "world_matrix_bodies_read": False,
            "world_schedule_bodies_read": False,
            "result_object_bodies_read": False,
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
            "graph_mutation_performed": False,
            "deployment_performed": False,
            "production_change_performed": False,
            "complete": True,
        }
    except Exception as exc:
        snapshot = audit.snapshot_v1()
        partial = {
            "schema_version": SUMMARY_SCHEMA,
            "mode": "publish",
            "publication_commit_sha": validated_capability.current_clean_commit_sha,
            "attempt_marker_file": dict(attempt_marker_file),
            "transport_audit": snapshot,
            "pre_root_prefix_inventory": pre_root_inventory,
            "terminal_prefix_inventory": terminal_inventory,
            "outer_presence_state": (
                "confirmed-present"
                if (
                    recovery.OUTER_ATTESTATION_URI in audit.created_uris
                    or recovery.OUTER_ATTESTATION_URI in audit.reopened_uris
                )
                else (
                    "unknown"
                    if (
                        recovery.OUTER_ATTESTATION_URI in audit.create_attempt_uris
                        or recovery.OUTER_ATTESTATION_URI in audit.current_resolution_uris
                        or recovery.OUTER_ATTESTATION_URI in audit.pending_created_uris
                        or recovery.OUTER_ATTESTATION_URI in audit.pending_reopened_uris
                    )
                    else outer_presence_state
                )
            ),
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
            "complete": False,
        }
        raise RunCorpusR6FixedG0CatalogRecoveryV1Error(
            f"fixed-G0 catalog recovery publication failed: {exc}",
            partial_summary=partial,
        ) from exc


def run_publish_production_v1(
) -> dict[str, object]:
    return run_publish_v1()


def run_reopen_v1(
    *,
    capability: recovery.PublicationCapabilityV1,
    attempt_binding: recovery.TrackedAttemptBindingV1,
    repository: adapter.SubprocessGitRepositoryV1,
    outer_identity: Mapping[str, object],
    backend: RecoveryGCSBackendV1,
) -> dict[str, object]:
    """Independently reopen the outer root and all 110 inner objects read-only."""
    normalized_requested_outer = _identity(
        outer_identity, label="requested recovery outer identity"
    )
    if normalized_requested_outer["uri"] != recovery.OUTER_ATTESTATION_URI:
        _fail("outer identity URI differs from the fixed recovery root")
    all_task_ordinals = tuple(range(adapter.catalog.TASK_COUNT))
    audit = _planned_source_audit_v1(
        base_transport=backend.transport(),
        mode="read_only",
        task_ordinals=all_task_ordinals,
        fixed_outer_identity=normalized_requested_outer,
    )
    transport = audit.transport()
    normalized_outer_identity = _identity(
        outer_identity, label="independent outer identity"
    )
    outer_raw = adapter.read_generation_exact_v1(
        normalized_outer_identity, transport=transport
    )
    validated_outer = recovery.validate_outer_attestation_v1(
        recovery._parse_json(outer_raw, label="independent outer bootstrap"),
        capability=capability,
        attempt_binding=attempt_binding,
    )
    audit.bind_attested_output_identities_v1(
        [row["identity"] for row in validated_outer["inner_object_manifest"]]
    )
    exact_outer = recovery._reopen_outer_structure_v1(
        outer_identity=outer_identity,
        capability=capability,
        attempt_binding=attempt_binding,
        transport=transport,
    )
    outer = _mapping(exact_outer["outer_attestation"], label="independently reopened outer")
    reopened = _inner_result_exact_reopen(
        capability=capability,
        repository=repository,
        transport=transport,
        replay_receipt_identity=_mapping(
            outer["inner_replay_receipt_identity"], label="outer inner receipt"
        ),
    )
    manifest = recovery.ordered_inner_object_manifest_v1(
        release_identity=reopened["catalog_release_identity"],
        release=reopened["catalog_release"],
        receipt_identity=reopened["replay_receipt_identity"],
    )
    if (
        outer["inner_catalog_release_identity"] != reopened["catalog_release_identity"]
        or outer["inner_catalog_release_sha256"]
        != reopened["catalog_release"]["release_sha256"]
        or outer["inner_replay_receipt_identity"] != reopened["replay_receipt_identity"]
        or outer["inner_replay_receipt_sha256"]
        != reopened["replay_receipt"]["replay_receipt_sha256"]
        or outer["inner_object_manifest"] != manifest
        or outer["inner_object_manifest_sha256"] != recovery.canonical_sha256(manifest)
    ):
        _fail("independent outer-to-inner exact replay differs")
    expected_inventory = recovery.prefix_inventory_from_identities_v1([
        *(row["identity"] for row in manifest),
        exact_outer["outer_identity"],
    ])
    terminal_inventory = backend.list_prefix_inventory(
        adapter.FIXED_CATALOG_NAMESPACE
    )
    if terminal_inventory != expected_inventory:
        _fail("independent exact-prefix inventory differs")
    snapshot = audit.snapshot_v1()
    if (
        snapshot["current_resolution_count"] != 0
        or snapshot["create_attempt_count"] != 0
        or snapshot["write_capability_enabled"] is not False
    ):
        _fail("independent reopen transport was not capability-read-only")
    return {
        "schema_version": SUMMARY_SCHEMA,
        "mode": "reopen",
        "publication_commit_sha": capability.current_clean_commit_sha,
        "implementation_commit_sha": capability.implementation_commit_sha,
        "outer_attestation_identity": exact_outer["outer_identity"],
        "outer_attestation_sha256": outer["recovery_attestation_sha256"],
        "inner_catalog_release_identity": reopened["catalog_release_identity"],
        "inner_replay_receipt_identity": reopened["replay_receipt_identity"],
        "inner_object_count": len(manifest),
        "transport_audit": snapshot,
        "terminal_prefix_inventory": terminal_inventory,
        "terminal_prefix_inventory_sha256": recovery.canonical_sha256(
            terminal_inventory
        ),
        "cloud_mutation_performed": False,
        "world_matrix_bodies_read": False,
        "world_schedule_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }


def run_reopen_production_v1(
    *,
    outer_identity: Mapping[str, object],
    backend_factory: BackendFactory = _default_backend_factory,
) -> dict[str, object]:
    normalized_outer = _identity(outer_identity, label="production recovery outer identity")
    if normalized_outer["uri"] != recovery.OUTER_ATTESTATION_URI:
        _fail("outer identity URI differs from the fixed recovery root")
    repository, head, _, _ = _clean_context()
    capability, attempt_binding = recovery.resolve_tracked_attempt_binding_v1(
        repository=repository,
        current_head=head,
    )
    backend = backend_factory()
    return run_reopen_v1(
        capability=capability,
        attempt_binding=attempt_binding,
        repository=repository,
        outer_identity=normalized_outer,
        backend=backend,
    )


def _outer_identity(args: argparse.Namespace) -> dict[str, object]:
    return _identity({
        "uri": args.outer_uri,
        "generation": args.outer_generation,
        "sha256": args.outer_sha256,
        "bytes": args.outer_bytes,
    }, label="CLI outer recovery attestation")


def _status() -> dict[str, object]:
    return {
        "schema_version": SUMMARY_SCHEMA,
        "default_state": "publication-parked",
        "first_landed_cloud_capability": "read-only-real-task0-smoke",
        "smoke_evidence_path": recovery.SMOKE_EVIDENCE_PATH,
        "empty_prefix_evidence_path": recovery.EMPTY_PREFIX_EVIDENCE_PATH,
        "focused_test_receipt_path": recovery.FOCUSED_TEST_RECEIPT_PATH,
        "review_lock_path": recovery.REVIEW_LOCK_PATH,
        "final_lock_path": recovery.FINAL_LOCK_PATH,
        "attempt_path": recovery.ATTEMPT_PATH,
        "outer_attestation_uri": recovery.OUTER_ATTESTATION_URI,
        "downstream_pin_required": "outer_attestation_identity",
        "uses_realized_outcomes": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reviewed fixed-G0 catalog recovery attempt three")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("smoke")
    census = subparsers.add_parser("census-empty-prefix")
    census.add_argument("--checked-at-utc", required=True)
    subparsers.add_parser("run-focused-tests")
    review = subparsers.add_parser("build-review-lock")
    review.add_argument("--output", required=True)
    review.add_argument("--review-disposition", choices=("approve", "reject"), required=True)
    review.add_argument("--p0-open-count", type=int, required=True)
    review.add_argument("--p1-open-count", type=int, required=True)
    review.add_argument("--p2-open-count", type=int, required=True)
    review.add_argument("--build", action="store_true", required=True)
    final = subparsers.add_parser("build-final-lock")
    final.add_argument("--output", required=True)
    final.add_argument("--publication-approved", action="store_true", required=True)
    final.add_argument("--build", action="store_true", required=True)
    attempt = subparsers.add_parser("build-attempt-marker")
    attempt.add_argument("--output", required=True)
    attempt.add_argument("--build", action="store_true", required=True)
    publish = subparsers.add_parser("publish")
    publish.add_argument("--execute", action="store_true", required=True)
    reopen = subparsers.add_parser("reopen")
    reopen.add_argument("--outer-uri", required=True)
    reopen.add_argument("--outer-generation", required=True)
    reopen.add_argument("--outer-sha256", required=True)
    reopen.add_argument("--outer-bytes", type=int, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "status":
        result = _status()
    elif args.command == "smoke":
        result = run_smoke_production_v1()
        recovery.write_local_create_once_v1(
            repository_root=REPOSITORY_ROOT,
            relative_path=recovery.SMOKE_EVIDENCE_PATH,
            body=result,
        )
    elif args.command == "census-empty-prefix":
        result = run_empty_prefix_census_production_v1(
            checked_at_utc=args.checked_at_utc
        )
        recovery.write_local_create_once_v1(
            repository_root=REPOSITORY_ROOT,
            relative_path=recovery.EMPTY_PREFIX_EVIDENCE_PATH,
            body=result,
        )
    elif args.command == "run-focused-tests":
        result = run_focused_tests_production_v1()
    elif args.command == "build-review-lock":
        result = build_review_lock_production_v1(
            output_relative_path=args.output,
            independent_review_disposition=args.review_disposition,
            p0_open_count=args.p0_open_count,
            p1_open_count=args.p1_open_count,
            p2_open_count=args.p2_open_count,
        )
    elif args.command == "build-final-lock":
        result = build_final_lock_production_v1(
            output_relative_path=args.output,
            publication_approved=args.publication_approved,
        )
    elif args.command == "build-attempt-marker":
        result = build_attempt_marker_production_v1(
            output_relative_path=args.output,
        )
    elif args.command == "publish":
        result = run_publish_production_v1()
    else:
        result = run_reopen_production_v1(outer_identity=_outer_identity(args))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
