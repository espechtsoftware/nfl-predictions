from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from nfl_dfs.research import (
    corpus_r6_construction_allocation_cross_operator_v1 as operator,
)
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross
from nfl_dfs.research import corpus_r6_construction_allocation_shard_v1 as shard
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as fixed_panel
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter


def _identity(uri: str, raw: bytes, generation: str = "17") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _Store:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, bytes]] = {}
        self.writes: list[str] = []

    def prime(self, identity: dict[str, object], raw: bytes) -> None:
        assert len(raw) == identity["bytes"]
        assert hashlib.sha256(raw).hexdigest() == identity["sha256"]
        self.rows[str(identity["uri"])] = (str(identity["generation"]), raw)

    def read(self, identity: dict[str, object]) -> bytes:
        generation, raw = self.rows[str(identity["uri"])]
        assert generation == str(identity["generation"])
        return raw

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        assert uri not in self.rows
        generation = str(10_000 + len(self.writes))
        self.rows[uri] = (generation, raw)
        self.writes.append(uri)
        return {
            **_identity(uri, raw, generation),
            "create_once": True,
        }


def _authority_fixture(*, arbitrary_lock: bool = False):
    receipts = {
        role: {
            "sha256": hashlib.sha256(role.encode("ascii")).hexdigest(),
            "bytes": len(role),
            "rows": 1,
            "columns": ["fixture"],
        }
        for role in (
            "mixed_walk_forward_panel",
            "prelock_dst_projection",
            "common_lock_market_points",
            "tabpfn_marginals",
        )
    }
    lock = operator.common_lock_authority_v1(
        slate_id="2023-w01",
        input_frame_receipts=receipts,
        lock_id="fixture-lock-v1",
    )
    lock_raw = b"lock" if arbitrary_lock else cross.canonical_json_bytes(lock)
    lock_identity = _identity("gs://fixture/common-lock.json", lock_raw, "20")
    audit = operator.audit_bank_placeholder_v1(
        slate_id="2023-w01",
        placeholder_id="fixture-unconsumed-audit-v1",
    )
    audit_raw = cross.canonical_json_bytes(audit)
    audit_identity = _identity("gs://fixture/audit-bank.json", audit_raw, "21")
    source = cross.source_manifest_v1(
        season=2023,
        week=1,
        slate_id="2023-w01",
        input_frame_receipts=receipts,
        lock_identity=lock_identity,
        audit_bank_identity=audit_identity,
    )
    source_raw = cross.canonical_json_bytes(source)
    source_identity = _identity("gs://fixture/source.json", source_raw, "22")
    _, descriptor = cross._source_document_descriptor_v1(
        source,
        source_identity=source_identity,
        season=2023,
        week=1,
        slate_id="2023-w01",
        audit_bank_identity=audit_identity,
    )
    code_sha = "a" * 40
    image_digest = "sha256:" + "b" * 64
    runtime = operator.runtime_build_attestation_v1(
        build_id="fixture-build-1",
        source_repository="https://github.com/example/nfl-predictions.git",
        requested_source_commit=code_sha,
        resolved_source_commit=code_sha,
        image_tag="us-central1-docker.pkg.dev/example/repo/image:fixture",
        image_digest=image_digest,
        provider_observed_at="2026-08-30T12:00:00Z",
    )
    runtime_raw = cross.canonical_json_bytes(runtime)
    runtime_identity = _identity(
        "gs://fixture/runtime-build-attestation.json", runtime_raw, "23"
    )
    selection = {
        "receipt_sha256": "c" * 64,
        "scientific_sha256": "d" * 64,
        "code_sha": code_sha,
        "image_digest": image_digest,
        "panel_authority": {
            "identity": dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
        },
        "seed_labels": ["R0", "R1", "R2", "R3", "R4"],
        "worlds_per_block": 3,
        "slates": [{
            "season": 2023,
            "week": 1,
            "slate_id": "2023-w01",
            "source_identity": source_identity,
            "source_descriptor": descriptor,
            "lock_identity": lock_identity,
            "audit_bank_identity": audit_identity,
        }],
    }
    store = _Store()
    for identity, raw in (
        (source_identity, source_raw),
        (lock_identity, lock_raw),
        (audit_identity, audit_raw),
        (runtime_identity, runtime_raw),
    ):
        store.prime(identity, raw)
    return selection, runtime_identity, store


def _fake_panel_reopen(selection, *, read_exact):
    del read_exact
    slates = [str(row["slate_id"]) for row in selection["slates"]]
    return {
        "role": "fixed-g0-panel",
        "identity": dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
        "panel_id": cross.FOUNDRY_G0_PANEL_ID,
        "panel_index_sha256": adapter.FIXED_PANEL_INDEX_SHA256,
        "accepted_slate_ids_sha256": cross.canonical_sha256(slates),
        "accepted_slate_count": len(slates),
        "generation_exact_reopened": True,
        "schema_and_self_hash_validated": True,
    }


def test_execution_authority_replays_manifest_shard_and_runtime(monkeypatch) -> None:
    monkeypatch.setattr(cross, "EXPECTED_SLATE_IDS", ("2023-w01",))
    selection = {
        "panel_id": "fixture-cross-v1",
        "code_sha": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
    }
    monkeypatch.setattr(
        cross, "validate_score_blind_cross_v1", lambda value: dict(value)
    )
    shard_root = {
        "expected_slate_coordinate": {"ordinal": 0, "slate_id": "2023-w01"},
        "panel_id": selection["panel_id"],
        "code_sha": selection["code_sha"],
        "image_digest": selection["image_digest"],
        "shard_sha256": "1" * 64,
        "scientific_sha256": "2" * 64,
        "execution_observations": {
            "runtime_execution_coordinate": {
                "job_name": "fixture-reused-job",
                "execution_name": "fixture-execution-1",
                "task_index": 0,
                "task_count": 1,
                "task_attempt": 0,
            }
        },
    }
    monkeypatch.setattr(
        shard, "validate_score_blind_cross_shard_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        shard,
        "collect_score_blind_cross_shards_v1",
        lambda roots: dict(selection),
    )
    store = _Store()
    shard_raw = cross.canonical_json_bytes(shard_root) + b"\n"
    shard_identity = _identity("gs://fixture/shards/00.json", shard_raw, "31")
    store.prime(shard_identity, shard_raw)
    task_bindings = [{
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "shard_uri": shard_identity["uri"],
    }]
    manifest_body = {
        "schema_version": (
            "corpus-r6-construction-allocation-snapshot-shard-manifest/v1"
        ),
        "run_id": selection["panel_id"],
        "code_sha": selection["code_sha"],
        "image_digest": selection["image_digest"],
        "task_count": 1,
        "expected_slate_ids": ["2023-w01"],
        "task_bindings": task_bindings,
        "task_bindings_sha256": cross.canonical_sha256(task_bindings),
        "foundry_g0_panel_id": cross.FOUNDRY_G0_PANEL_ID,
        "foundry_g0_panel_identity": dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
        "uses_target_slate_outcomes": False,
        "target_slate_outcome_columns": [],
    }
    manifest = {
        **manifest_body,
        "manifest_sha256": cross.canonical_sha256(manifest_body),
    }
    manifest_raw = cross.canonical_json_bytes(manifest) + b"\n"
    manifest_identity = _identity(
        "gs://fixture/manifest.json", manifest_raw, "30"
    )
    store.prime(manifest_identity, manifest_raw)
    execution = operator.runtime_execution_attestation_v1(
        project_id="nfl-predictions-503414",
        region="us-central1",
        job_name="fixture-reused-job",
        job_generation="12",
        execution_name="fixture-execution-1",
        execution_uid="11111111-2222-3333-4444-555555555555",
        task_count=1,
        succeeded_count=1,
        failed_count=0,
        cancelled_count=0,
        running_count=0,
        code_sha=selection["code_sha"],
        image_digest=selection["image_digest"],
        provider_observed_at="2026-08-30T14:00:00Z",
    )
    execution_raw = cross.canonical_json_bytes(execution)
    execution_identity = _identity(
        "gs://fixture/execution.json", execution_raw, "32"
    )
    store.prime(execution_identity, execution_raw)
    authority = operator.selection_execution_authority_v1(
        input_manifest_identity=manifest_identity,
        input_manifest_sha256=manifest["manifest_sha256"],
        ordered_shard_identities=[shard_identity],
        runtime_execution_attestation_identity=execution_identity,
    )
    receipt = operator.verify_selection_execution_authority_v1(
        selection, execution_authority=authority, read_exact=store.read
    )
    assert receipt["all_shards_generation_exact_reopened"] is True
    assert receipt["selection_replayed_from_declared_shards"] is True
    assert receipt[
        "runtime_execution_provider_attestation_exact_reopened"
    ] is True

    forged = deepcopy(authority)
    forged["ordered_shard_identities"][0]["uri"] += ".forged"
    body = dict(forged)
    body.pop("execution_authority_sha256")
    forged["execution_authority_sha256"] = cross.canonical_sha256(body)
    with pytest.raises(operator.ConstructionAllocationCrossOperatorError):
        operator.verify_selection_execution_authority_v1(
            selection, execution_authority=forged, read_exact=store.read
        )


def test_fixed_g0_panel_authority_is_deep_reopened(monkeypatch) -> None:
    selection = {
        "panel_authority": {
            "identity": dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
        },
        "slates": [{"slate_id": slate_id} for slate_id in cross.EXPECTED_SLATE_IDS],
    }
    calls: list[dict[str, object]] = []

    def reopen(identity, *, read_exact):
        calls.append(dict(identity))
        del read_exact
        return (
            {
                "panel_id": cross.FOUNDRY_G0_PANEL_ID,
                "panel_index_sha256": adapter.FIXED_PANEL_INDEX_SHA256,
            },
            [{"slate_id": slate_id} for slate_id in cross.EXPECTED_SLATE_IDS],
            dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
        )

    monkeypatch.setattr(fixed_panel, "reopen_fixed_panel_v1", reopen)
    result = operator._reopen_fixed_g0_panel_v1(
        selection, read_exact=lambda _identity: b"unused"
    )
    assert calls == [cross.FOUNDRY_G0_PANEL_IDENTITY]
    assert result["generation_exact_reopened"] is True
    assert result["schema_and_self_hash_validated"] is True
    assert result["accepted_slate_count"] == 54
    assert result["panel_index_sha256"] == adapter.FIXED_PANEL_INDEX_SHA256
    assert result["panel_index_sha256"] != cross.FOUNDRY_G0_PANEL_ID.removeprefix(
        "v12:"
    )

    forged = deepcopy(selection)
    forged["panel_authority"]["identity"]["generation"] = "999"
    with pytest.raises(
        operator.ConstructionAllocationCrossOperatorError,
        match="fixed G0 panel identity differs",
    ):
        operator._reopen_fixed_g0_panel_v1(
            forged, read_exact=lambda _identity: b"unused"
        )
    assert len(calls) == 1


def test_typed_lock_audit_and_runtime_authorities_replace_arbitrary_bytes(
    monkeypatch,
) -> None:
    selection, runtime_identity, store = _authority_fixture()
    monkeypatch.setattr(
        cross, "validate_score_blind_cross_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        operator, "_reopen_fixed_g0_panel_v1", _fake_panel_reopen
    )
    receipt = operator.verify_upstream_authorities_v1(
        selection,
        runtime_build_attestation_identity=runtime_identity,
        read_exact=store.read,
    )
    assert receipt["exact_read_count"] == 5
    assert receipt["fixed_g0_panel_generation_exact_reopened"] is True
    assert receipt[
        "runtime_code_image_provider_attestation_exact_reopened"
    ] is True
    assert receipt["all_locks_schema_and_self_hash_validated"] is True
    assert receipt[
        "all_audit_authority_documents_schema_and_self_hash_validated"
    ] is True
    assert receipt["independent_audit_evaluation_authority_available"] is False
    assert receipt["unconsumed_audit_placeholder_count"] == 1
    assert receipt["audit_placeholders_have_evaluation_authority"] is False
    assert receipt["outcome_data_accessed"] is False

    bad_selection, bad_runtime, bad_store = _authority_fixture(
        arbitrary_lock=True
    )
    with pytest.raises(
        operator.ConstructionAllocationCrossOperatorError,
        match="common lock JSON differs",
    ):
        operator.verify_upstream_authorities_v1(
            bad_selection,
            runtime_build_attestation_identity=bad_runtime,
            read_exact=bad_store.read,
        )


def test_runtime_attestation_and_multiplicity_are_self_hashed_and_exact() -> None:
    code_sha = "a" * 40
    image = "sha256:" + "b" * 64
    attestation = operator.runtime_build_attestation_v1(
        build_id="build-1",
        source_repository="https://github.com/example/repo.git",
        requested_source_commit=code_sha,
        resolved_source_commit=code_sha,
        image_tag="us-central1-docker.pkg.dev/example/repo/image:tag",
        image_digest=image,
        provider_observed_at="2026-08-30T12:00:00Z",
    )
    assert operator.validate_runtime_build_attestation_v1(
        attestation, expected_code_sha=code_sha, expected_image_digest=image
    ) == attestation
    with pytest.raises(
        operator.ConstructionAllocationCrossOperatorError,
        match="selection code/image",
    ):
        operator.validate_runtime_build_attestation_v1(
            attestation,
            expected_code_sha="c" * 40,
            expected_image_digest=image,
        )
    forged = deepcopy(attestation)
    forged["provider_observed"] = False
    with pytest.raises(
        operator.ConstructionAllocationCrossOperatorError,
        match="self-hash differs",
    ):
        operator.validate_runtime_build_attestation_v1(
            forged, expected_code_sha=code_sha, expected_image_digest=image
        )

    family = operator.multiplicity_family_v1()
    assert operator.validate_multiplicity_family_v1(family) == family
    forged_family = deepcopy(family)
    forged_family["family_id"] = "another-family"
    with pytest.raises(
        operator.ConstructionAllocationCrossOperatorError,
        match="self-hash differs",
    ):
        operator.validate_multiplicity_family_v1(forged_family)


@pytest.mark.parametrize(
    "schema",
    [
        operator.INDEPENDENT_DRAW_BANK_ROOT_SCHEMA,
        operator.INDEPENDENT_BANK_PLAN_SCHEMA,
    ],
)
def test_independent_audit_contracts_fail_closed_in_placeholder_only_release(
    schema: str,
) -> None:
    document = {"schema_version": schema}
    raw = cross.canonical_json_bytes(document)
    identity = _identity("gs://fixture/unsupported-audit-bank.json", raw)
    with pytest.raises(
        operator.ConstructionAllocationCrossOperatorError,
        match="unavailable in the placeholder-only release",
    ):
        operator._validate_audit_bank_v1(
            raw,
            identity=identity,
            slate_id="2023-w01",
            world_blocks=["R0", "R1", "R2", "R3", "R4"],
            worlds_per_block=3,
            read_exact=lambda _identity: b"unused",
        )


def test_publication_reopens_all_authorities_before_first_write_and_root_last(
    monkeypatch,
) -> None:
    selection, runtime_identity, store = _authority_fixture()
    monkeypatch.setattr(
        cross, "validate_score_blind_cross_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        cross, "EXPECTED_SLATE_IDS", ("2023-w01",)
    )
    monkeypatch.setattr(
        operator, "_reopen_fixed_g0_panel_v1", _fake_panel_reopen
    )
    execution_identity = _identity(
        "gs://fixture/runtime-execution-attestation.json",
        b'{"fixture":true}',
        "24",
    )
    execution_authority = {
        "execution_authority_sha256": "e" * 64,
        "runtime_execution_attestation_identity": execution_identity,
    }
    execution_reopen = {
        "receipt_sha256": "f" * 64,
        "all_shards_generation_exact_reopened": True,
        "selection_replayed_from_declared_shards": True,
        "runtime_execution_provider_attestation_exact_reopened": True,
        "uses_target_slate_outcomes": False,
    }
    monkeypatch.setattr(
        operator,
        "validate_selection_execution_authority_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        operator,
        "verify_selection_execution_authority_v1",
        lambda selection, *, execution_authority, read_exact: dict(
            execution_reopen
        ),
    )
    ready = operator.prepare_create_once_bundle_v1(
        selection,
        run_id="fixture-cross-v1",
        output_prefix="gs://fixture/output",
        frozen_at="2026-08-30T12:00:00Z",
        runtime_build_attestation_identity=runtime_identity,
        execution_authority=execution_authority,
    )
    envelope = operator.publish_create_once_bundle_v1(
        ready, publish_create_once=store.publish, read_exact=store.read
    )
    assert store.writes == [ready["selection_uri"], ready["terminal_uri"]]
    reopened = operator.reopen_terminal_bundle_v1(
        envelope, read_exact=store.read
    )
    assert reopened["selection"] == selection
    assert reopened["multiplicity_family"]["family_id"] == (
        operator.MULTIPLICITY_FAMILY_ID
    )
    assert reopened["outcome_data_accessed"] is False

    bad_selection, bad_runtime, bad_store = _authority_fixture(
        arbitrary_lock=True
    )
    bad_ready = operator.prepare_create_once_bundle_v1(
        bad_selection,
        run_id="fixture-bad-cross-v1",
        output_prefix="gs://fixture/output",
        frozen_at="2026-08-30T12:00:00Z",
        runtime_build_attestation_identity=bad_runtime,
        execution_authority=execution_authority,
    )
    with pytest.raises(operator.ConstructionAllocationCrossOperatorError):
        operator.publish_create_once_bundle_v1(
            bad_ready,
            publish_create_once=bad_store.publish,
            read_exact=bad_store.read,
        )
    assert bad_store.writes == []
