from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from nfl_dfs.research import (
    corpus_r6_construction_allocation_cross_operator_v1 as operator,
)
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross
from scripts import (
    run_corpus_r6_construction_allocation_snapshot_shard_v1 as subject,
)


CODE = "a" * 40
IMAGE = "sha256:" + "b" * 64
RUN_ID = "construction-cross-fixture-v1"
OUTPUT_PREFIX = subject.OUTPUT_ROOT


class _MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}
        self.read_calls: list[str] = []
        self.publish_calls: list[str] = []
        self.resolve_calls: list[str] = []

    def seed_raw(
        self, uri: str, raw: bytes, *, generation: str = "7",
    ) -> dict[str, object]:
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return identity

    def seed_document(
        self, uri: str, value: Mapping[str, object], *, newline: bool = False,
    ) -> dict[str, object]:
        raw = subject._canonical(value) + (b"\n" if newline else b"")
        return self.seed_raw(uri, raw)

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        uri = str(identity["uri"])
        self.read_calls.append(uri)
        raw, retained = self.objects[uri]
        assert {key: identity[key] for key in ("uri", "generation", "sha256", "bytes")} == retained
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        self.publish_calls.append(uri)
        if uri in self.objects:
            prior, retained = self.objects[uri]
            assert prior == raw
        else:
            retained = self.seed_raw(uri, raw, generation="11")
        return {**retained, "create_once": True}

    def resolve_known(self, uri: str, maximum_bytes: int) -> dict[str, object]:
        self.resolve_calls.append(uri)
        raw, retained = self.objects[uri]
        assert len(raw) <= maximum_bytes
        return dict(retained)


class _Provider:
    def __init__(
        self, *, mutate: bool = False, mutate_execution: bool = False,
    ) -> None:
        self.calls: list[str] = []
        self.execution_calls: list[str] = []
        self.mutate = mutate
        self.mutate_execution = mutate_execution

    def observe_runtime_build(
        self, expected_attestation: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.calls.append(str(expected_attestation["build_id"]))
        result = dict(expected_attestation)
        if self.mutate:
            result["image_digest"] = "sha256:" + "c" * 64
        return result

    def observe_runtime_execution(
        self, expected_attestation: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.execution_calls.append(str(expected_attestation["execution_name"]))
        result = dict(expected_attestation)
        if self.mutate_execution:
            result["succeeded_count"] = 53
        return result


def _attestation() -> dict[str, object]:
    return operator.runtime_build_attestation_v1(
        build_id="build-fixture-20260830",
        source_repository="github.com/example/nfl-predictions",
        requested_source_commit=CODE,
        resolved_source_commit=CODE,
        image_tag="us-central1-docker.pkg.dev/p/r/i:fixture",
        image_digest=IMAGE,
        provider_observed_at="2026-08-30T12:00:00Z",
    )


def _execution_attestation() -> dict[str, object]:
    return operator.runtime_execution_attestation_v1(
        project_id="nfl-predictions-503414",
        region="us-central1",
        job_name="fixture-reused-job",
        job_generation="12",
        execution_name="fixture-execution-54",
        execution_uid="11111111-2222-3333-4444-555555555555",
        task_count=len(cross.EXPECTED_SLATE_IDS),
        succeeded_count=len(cross.EXPECTED_SLATE_IDS),
        failed_count=0,
        cancelled_count=0,
        running_count=0,
        code_sha=CODE,
        image_digest=IMAGE,
        provider_observed_at="2026-08-30T14:00:00Z",
    )


def _provider_build_metadata(*, direct_git: bool) -> dict[str, object]:
    attestation = _attestation()
    requested_source = {
        "url": attestation["source_repository"],
        "revision": CODE,
    }
    if direct_git:
        source = {"gitSource": requested_source}
        provenance = {"resolvedGitSource": requested_source}
    else:
        source = {
            "storageSource": {
                "bucket": str(attestation["source_repository"]),
                "object": CODE,
            }
        }
        provenance = {
            "resolvedStorageSource": {
                "bucket": str(attestation["source_repository"]),
                "object": CODE,
            }
        }
    return {
        "id": attestation["build_id"],
        "status": "SUCCESS",
        "source": source,
        "sourceProvenance": provenance,
        "substitutions": {
            "_CODE_SHA": CODE,
            "_BUILD_IMAGE": attestation["image_tag"],
        },
        "results": {"images": [{
            "name": attestation["image_tag"],
            "digest": IMAGE,
        }]},
    }


def test_cloud_build_provider_requires_exact_direct_git_source(monkeypatch):
    metadata = _provider_build_metadata(direct_git=True)
    monkeypatch.setattr(
        subject.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(metadata)),
    )
    attestation = _attestation()
    assert subject.GCloudBuildProviderV1().observe_runtime_build(
        attestation
    ) == attestation


def test_cloud_build_provider_rejects_storage_source_even_when_strings_match(
    monkeypatch,
):
    metadata = _provider_build_metadata(direct_git=False)
    monkeypatch.setattr(
        subject.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(metadata)),
    )
    with pytest.raises(
        subject.SnapshotShardRunnerError,
        match="Cloud Build.*source",
    ):
        subject.GCloudBuildProviderV1().observe_runtime_build(_attestation())


def _provider_execution_metadata() -> tuple[dict[str, object], dict[str, object]]:
    expected = _execution_attestation()
    job = {
        "metadata": {
            "name": expected["job_name"],
            "generation": expected["job_generation"],
        },
    }
    execution = {
        "metadata": {
            "name": expected["execution_name"],
            "uid": expected["execution_uid"],
            "labels": {
                "run.googleapis.com/job": expected["job_name"],
                "run.googleapis.com/jobGeneration": expected["job_generation"],
            },
        },
        "spec": {
            "taskCount": expected["task_count"],
            "template": {"spec": {"containers": [{
                "image": "us-central1-docker.pkg.dev/p/r/i@" + IMAGE,
                "env": [{"name": "CODE_SHA", "value": CODE}],
            }]}},
        },
        "status": {
            "completionTime": expected["provider_observed_at"],
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": expected["succeeded_count"],
            "failedCount": expected["failed_count"],
            "cancelledCount": expected["cancelled_count"],
            "runningCount": expected["running_count"],
        },
    }
    return job, execution


def _patch_provider_execution(
    monkeypatch: pytest.MonkeyPatch,
    job: Mapping[str, object],
    execution: Mapping[str, object],
) -> None:
    def run(command, **kwargs):
        del kwargs
        value = execution if "executions" in command else job
        return SimpleNamespace(stdout=json.dumps(value))

    monkeypatch.setattr(subject.subprocess, "run", run)


def test_cloud_run_provider_requires_structural_exact_execution(monkeypatch):
    job, execution = _provider_execution_metadata()
    _patch_provider_execution(monkeypatch, job, execution)
    expected = _execution_attestation()
    assert subject.GCloudBuildProviderV1().observe_runtime_execution(
        expected
    ) == expected


def test_cloud_run_provider_rejects_task_count_substring_false_positive(
    monkeypatch,
):
    job, execution = _provider_execution_metadata()
    forged = deepcopy(execution)
    forged["spec"]["taskCount"] = 1
    forged["irrelevant_caller_string"] = "54"
    _patch_provider_execution(monkeypatch, job, forged)
    with pytest.raises(
        subject.SnapshotShardRunnerError,
        match="Cloud Run provider observation differs",
    ):
        subject.GCloudBuildProviderV1().observe_runtime_execution(
            _execution_attestation()
        )


def _legacy_manifest(
    store: _MemoryStore,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    prefix = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-boom-first-allocation/fixture/"
    )
    snapshot_identities = []
    bindings = []
    for ordinal, slate_id in enumerate(cross.EXPECTED_SLATE_IDS):
        snapshot = {
            "schema_version": "fixture-generation-snapshot/v1",
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "generation_snapshot_sha256": format(ordinal + 1, "064x"),
        }
        identity = store.seed_document(
            f"{prefix}inputs/{ordinal:02d}-{slate_id}.json", snapshot
        )
        snapshot_identities.append(identity)
        bindings.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "snapshot_identity": identity,
            "generation_snapshot_sha256": format(ordinal + 1, "064x"),
            "result_uri": f"{prefix}slates/{ordinal:02d}-{slate_id}.json",
        })
    uri = f"{prefix}manifest.json"
    body = {
        "schema_version": subject.LEGACY_MANIFEST_SCHEMA,
        "manifest_uri": uri,
        "output_prefix": prefix,
        "task_count": len(bindings),
        "task_bindings": bindings,
        "task_bindings_sha256": subject._hash(bindings),
        "target_slate_outcome_columns": [],
        "uses_realized_outcomes": False,
    }
    manifest = subject._with_hash(body, field="manifest_sha256")
    identity = store.seed_document(uri, manifest)
    return manifest, identity, snapshot_identities


def _prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_MemoryStore, dict[str, object], dict[str, object], _Provider]:
    store = _MemoryStore()
    _legacy, legacy_identity, _snapshots = _legacy_manifest(store)
    monkeypatch.setattr(
        subject, "FROZEN_BOOM_FIRST_MANIFEST_IDENTITY", dict(legacy_identity)
    )
    attestation = _attestation()
    attestation_identity = store.seed_document(
        "gs://fixture/authorities/build.json", attestation
    )
    provider = _Provider()
    request = {
        "frozen_boom_first_manifest_identity": legacy_identity,
        "runtime_build_attestation_identity": attestation_identity,
        "panel_identity": dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
        "code_sha": CODE,
        "image_digest": IMAGE,
        "output_prefix": OUTPUT_PREFIX,
        "run_id": RUN_ID,
        "frozen_at": "2026-08-30T12:30:00Z",
    }
    result = subject.prepare_from_request_v1(
        request, store=store, provider=provider
    )
    manifest_identity = {
        key: result["manifest_identity"][key]
        for key in ("uri", "generation", "sha256", "bytes")
    }
    manifest, _, _ = subject.open_input_manifest_v1(
        manifest_identity, store=store
    )
    return store, manifest_identity, manifest, provider


def _environment(
    manifest_identity: Mapping[str, object], *, ordinal: int = 0,
) -> dict[str, str]:
    return {
        subject.ENABLE_ENV: subject.ENABLE_VALUE,
        subject.CODE_SHA_ENV: CODE,
        subject.IMAGE_DIGEST_ENV: IMAGE,
        subject.TASK_INDEX_ENV: str(ordinal),
        subject.TASK_COUNT_ENV: str(len(cross.EXPECTED_SLATE_IDS)),
        subject.TASK_ATTEMPT_ENV: "0",
        subject.CLOUD_RUN_JOB_ENV: "fixture-reused-job",
        subject.CLOUD_RUN_EXECUTION_ENV: "fixture-execution-54",
        subject.MANIFEST_IDENTITY_ENV: subject._canonical(
            dict(manifest_identity)
        ).decode("ascii"),
    }


def test_prepare_binds_exact_54_snapshot_and_placeholder_lattices(monkeypatch):
    store, manifest_identity, manifest, provider = _prepared(monkeypatch)
    assert manifest["task_count"] == 54
    assert manifest["expected_slate_ids"] == list(cross.EXPECTED_SLATE_IDS)
    assert manifest["foundry_g0_panel_identity"] == cross.FOUNDRY_G0_PANEL_IDENTITY
    assert manifest["runtime_build_attestation_identity"]["uri"] == (
        "gs://fixture/authorities/build.json"
    )
    assert manifest["selection_uri"] == f"{OUTPUT_PREFIX}{RUN_ID}/selection.json"
    assert manifest["terminal_uri"] == f"{OUTPUT_PREFIX}{RUN_ID}/terminal.json"
    assert provider.calls == ["build-fixture-20260830"]
    assert len([
        uri for uri in store.publish_calls if "/audit-placeholders/" in uri
    ]) == 54
    assert store.publish_calls[-1] == manifest_identity["uri"]
    assert store.resolve_calls == []
    assert manifest["execution_contract"]["automatic_launch_or_relaunch"] is False
    assert manifest["execution_contract"]["deployment_mutation"] is False
    assert subject.MAX_GENERATION_SNAPSHOT_BYTES > 2_672_191

    tampered = deepcopy(manifest)
    tampered["task_bindings"][0]["shard_uri"] += ".latest"
    tampered["task_bindings_sha256"] = subject._hash(tampered["task_bindings"])
    body = dict(tampered)
    body.pop("manifest_sha256")
    tampered["manifest_sha256"] = subject._hash(body)
    with pytest.raises(subject.SnapshotShardRunnerError, match=r"binding\[0\]"):
        subject.validate_input_manifest_v1(tampered)


def test_task_is_default_off_exact_ordinal_and_reads_snapshot_worlds_placeholder(
    monkeypatch,
):
    store, manifest_identity, manifest, _provider = _prepared(monkeypatch)
    artifact_identities = [
        store.seed_raw(f"gs://fixture/world/{block}.npz", block.encode("ascii"))
        for block in cross.SEED_LABELS
    ]
    monkeypatch.setattr(
        subject.snapshot_adapter.frozen_allocation,
        "validate_generation_snapshot_v1",
        lambda value: dict(value),
    )

    class _FakeBuilder:
        def __init__(self, bindings, *, read_exact, require_exact_panel):
            assert len(bindings) == 1
            assert require_exact_panel is False
            self.binding = bindings[0]
            # Model the real adapter's one snapshot plus R0--R4 exact reads.
            read_exact(self.binding.snapshot_identity)
            for identity in artifact_identities:
                read_exact(identity)

        def cross_slates(self):
            return (SimpleNamespace(
                slate_id="2023-w01", season=2023, week=1,
            ),)

    def fake_build(slate, builder, **kwargs):
        return {
            "expected_slate_coordinate": {
                "ordinal": kwargs["expected_slate_ordinal"],
                "slate_id": slate.slate_id,
            },
            "panel_id": kwargs["panel_id"],
            "code_sha": kwargs["code_sha"],
            "image_digest": kwargs["image_digest"],
            "uses_target_slate_outcomes": False,
            "scientific_sha256": "1" * 64,
            "shard_sha256": "2" * 64,
        }

    monkeypatch.setattr(
        subject.snapshot_adapter,
        "FrozenSnapshotConstructionNativeBookBuilder",
        _FakeBuilder,
    )
    monkeypatch.setattr(
        subject.shard_science, "build_score_blind_cross_shard_v1", fake_build
    )
    monkeypatch.setattr(
        subject.shard_science,
        "validate_score_blind_cross_shard_v1",
        lambda value: dict(value),
    )
    environment = _environment(manifest_identity)
    disabled = dict(environment)
    disabled.pop(subject.ENABLE_ENV)
    reads_before_disabled = len(store.read_calls)
    with pytest.raises(subject.SnapshotShardRunnerError, match="requires"):
        subject.execute_task_v1(
            manifest_identity=manifest_identity,
            environment=disabled,
            store=store,
        )
    assert len(store.read_calls) == reads_before_disabled

    stale = dict(environment)
    stale[subject.IMAGE_DIGEST_ENV] = "sha256:" + "c" * 64
    with pytest.raises(subject.SnapshotShardRunnerError, match="code/image"):
        subject.execute_task_v1(
            manifest_identity=manifest_identity,
            environment=stale,
            store=store,
        )

    placeholder_uri = manifest["task_bindings"][0][
        "audit_placeholder_identity"
    ]["uri"]
    placeholder_reads_before = store.read_calls.count(placeholder_uri)
    result = subject.execute_task_v1(
        manifest_identity=manifest_identity,
        environment=environment,
        store=store,
    )
    assert result["source_ordinal"] == 0
    assert result["slate_id"] == "2023-w01"
    assert result["publication_performed"] is True
    assert result["shard_identity"]["uri"] == manifest["task_bindings"][0][
        "shard_uri"
    ]
    assert store.read_calls.count(
        manifest["task_bindings"][0]["snapshot_identity"]["uri"]
    ) == 1
    assert all(store.read_calls.count(identity["uri"]) == 1 for identity in artifact_identities)
    assert store.read_calls.count(placeholder_uri) == placeholder_reads_before + 1

    smoke = subject.task0_smoke_v1(
        manifest_identity=manifest_identity,
        environment=environment,
        store=store,
    )
    assert smoke["schema_version"] == subject.SMOKE_RESULT_SCHEMA
    assert smoke["publication_performed"] is False
    assert smoke["shard_identity"] is None


def test_task_rejects_placeholder_that_claims_evaluation_authority(monkeypatch):
    store, manifest_identity, manifest, _provider = _prepared(monkeypatch)
    monkeypatch.setattr(
        subject.snapshot_adapter.frozen_allocation,
        "validate_generation_snapshot_v1",
        lambda value: dict(value),
    )
    placeholder_identity = manifest["task_bindings"][0][
        "audit_placeholder_identity"
    ]
    raw, _ = store.objects[str(placeholder_identity["uri"])]
    value = json.loads(raw)
    value["evaluation_authority"] = True
    body = dict(value)
    body.pop("audit_placeholder_sha256")
    value["audit_placeholder_sha256"] = cross.canonical_sha256(body)
    tampered_raw = subject._canonical(value)
    tampered_identity = store.seed_raw(
        str(placeholder_identity["uri"]), tampered_raw,
        generation=str(placeholder_identity["generation"]),
    )
    # Rebind only the manifest so the exact read reaches semantic validation.
    changed = deepcopy(manifest)
    changed["task_bindings"][0]["audit_placeholder_identity"] = tampered_identity
    changed["task_bindings_sha256"] = subject._hash(changed["task_bindings"])
    body = dict(changed)
    body.pop("manifest_sha256")
    changed["manifest_sha256"] = subject._hash(body)
    changed_raw = subject._document(changed)
    changed_identity = store.seed_raw(
        str(manifest_identity["uri"]), changed_raw,
        generation=str(manifest_identity["generation"]),
    )
    environment = _environment(changed_identity)
    with pytest.raises(subject.SnapshotShardRunnerError, match="evaluation authority"):
        subject.execute_task_v1(
            manifest_identity=changed_identity,
            environment=environment,
            store=store,
        )


def test_collect_resolves_all_known_names_and_delegates_hardened_terminal(
    monkeypatch,
):
    store, manifest_identity, manifest, _prepare_provider = _prepared(monkeypatch)
    execution_attestation_identity = store.seed_document(
        "gs://fixture/authorities/execution.json", _execution_attestation()
    )
    roots = []
    for ordinal, binding in enumerate(manifest["task_bindings"]):
        root = {
            "expected_slate_coordinate": {
                "ordinal": ordinal,
                "slate_id": binding["slate_id"],
            },
            "panel_id": RUN_ID,
            "code_sha": CODE,
            "image_digest": IMAGE,
            "scientific_sha256": format(ordinal + 1, "064x"),
            "shard_sha256": format(ordinal + 101, "064x"),
        }
        roots.append(root)
        store.seed_raw(str(binding["shard_uri"]), subject._document(root))

    selection = {
        "panel_id": RUN_ID,
        "code_sha": CODE,
        "image_digest": IMAGE,
        "receipt_sha256": "d" * 64,
    }
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        subject.shard_science,
        "validate_score_blind_cross_shard_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        subject.shard_science,
        "collect_score_blind_cross_shards_v1",
        lambda values: (seen.setdefault("roots", list(values)), dict(selection))[1],
    )

    def fake_prepare(value, **kwargs):
        seen["selection"] = value
        seen["prepare"] = kwargs
        return {
            "selection_uri": manifest["selection_uri"],
            "terminal_uri": manifest["terminal_uri"],
        }

    monkeypatch.setattr(subject.operator, "prepare_create_once_bundle_v1", fake_prepare)
    monkeypatch.setattr(
        subject.operator,
        "publish_create_once_bundle_v1",
        lambda ready, **kwargs: {
            "schema_version": "fixture-terminal-envelope/v1",
            "envelope_sha256": "e" * 64,
        },
    )
    monkeypatch.setattr(
        subject.operator,
        "reopen_terminal_bundle_v1",
        lambda envelope, **kwargs: {
            "complete": True,
            "execution_reopen_receipt": {
                "all_shards_generation_exact_reopened": True,
                "selection_replayed_from_declared_shards": True,
                "all_shards_match_runtime_execution": True,
                "runtime_execution_provider_attestation_exact_reopened": True,
                "uses_target_slate_outcomes": False,
            },
            "upstream_reopen_receipt": {
                "fixed_g0_panel_generation_exact_reopened": True,
                "runtime_code_image_provider_attestation_exact_reopened": True,
                "all_sources_generation_exact_reopened": True,
                "all_locks_generation_exact_reopened": True,
                "all_audit_authority_documents_generation_exact_reopened": True,
                "unconsumed_audit_placeholder_count": 54,
                "independent_audit_evaluation_authority_available": False,
                "audit_placeholders_have_evaluation_authority": False,
                "outcome_data_accessed": False,
            },
        },
    )
    provider = _Provider()
    result = subject.collect_v1(
        manifest_identity=manifest_identity,
        runtime_execution_attestation_identity=execution_attestation_identity,
        environment=_environment(manifest_identity),
        store=store,
        provider=provider,
    )
    assert result["shard_count"] == 54
    assert result["all_shards_resolved_by_deterministic_name_without_listing"] is True
    assert result["selection_published_before_terminal_root"] is True
    assert result["outcome_data_accessed"] is False
    assert store.resolve_calls == [
        str(binding["shard_uri"]) for binding in manifest["task_bindings"]
    ]
    assert len(seen["roots"]) == 54
    assert seen["prepare"]["runtime_build_attestation_identity"] == manifest[
        "runtime_build_attestation_identity"
    ]
    assert provider.calls == ["build-fixture-20260830"]
    assert provider.execution_calls == ["fixture-execution-54"]

    missing = str(manifest["task_bindings"][17]["shard_uri"])
    del store.objects[missing]
    with pytest.raises(subject.SnapshotShardRunnerError, match="missing or mutable"):
        subject.collect_v1(
            manifest_identity=manifest_identity,
            runtime_execution_attestation_identity=(
                execution_attestation_identity
            ),
            environment=_environment(manifest_identity),
            store=store,
            provider=provider,
        )


def test_prepare_and_collect_fail_closed_on_provider_drift(monkeypatch):
    store = _MemoryStore()
    _legacy, legacy_identity, _ = _legacy_manifest(store)
    monkeypatch.setattr(
        subject, "FROZEN_BOOM_FIRST_MANIFEST_IDENTITY", dict(legacy_identity)
    )
    attestation = _attestation()
    attestation_identity = store.seed_document(
        "gs://fixture/authorities/build.json", attestation
    )
    request = {
        "frozen_boom_first_manifest_identity": legacy_identity,
        "runtime_build_attestation_identity": attestation_identity,
        "panel_identity": dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
        "code_sha": CODE,
        "image_digest": IMAGE,
        "output_prefix": OUTPUT_PREFIX,
        "run_id": RUN_ID,
        "frozen_at": "2026-08-30T12:30:00Z",
    }
    with pytest.raises(subject.SnapshotShardRunnerError, match="provider build"):
        subject.prepare_from_request_v1(
            request, store=store, provider=_Provider(mutate=True)
        )
    # Provider validation precedes the first create-once write.
    assert store.publish_calls == []


def test_gcs_known_name_resolution_pins_generation_without_listing():
    raw = b'{"fixed":true}\n'

    class _Blob:
        generation = "91"
        size = len(raw)

        def __init__(self) -> None:
            self.reload_calls = 0
            self.download_generations: list[int] = []

        def reload(self, *, timeout):
            assert timeout == subject.GCS_TIMEOUT_SECONDS
            self.reload_calls += 1

        def download_as_bytes(self, *, if_generation_match, timeout):
            assert timeout == subject.GCS_TIMEOUT_SECONDS
            self.download_generations.append(if_generation_match)
            return raw

    blob = _Blob()

    class _Bucket:
        def blob(self, name):
            assert name == "known/path.json"
            return blob

    class _Client:
        def bucket(self, name):
            assert name == "fixture-bucket"
            return _Bucket()

    store = subject.GCSExactKnownNameStoreV1(client=_Client())
    identity = store.resolve_known(
        "gs://fixture-bucket/known/path.json", 1_000
    )
    assert identity == {
        "uri": "gs://fixture-bucket/known/path.json",
        "generation": "91",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    assert blob.reload_calls == 1
    assert blob.download_generations == [91]
    assert store.read_exact(identity) == raw
    # Generation resolution seeds the exact-read cache, so collection does
    # not download every potentially large shard twice.
    assert blob.download_generations == [91]


def test_cli_routes_execution_attestation_only_to_collect(monkeypatch, capsys):
    manifest_identity = {
        "uri": "gs://fixture/manifest.json",
        "generation": "1",
        "sha256": "a" * 64,
        "bytes": 10,
    }
    execution_identity = {
        "uri": "gs://fixture/execution.json",
        "generation": "2",
        "sha256": "b" * 64,
        "bytes": 10,
    }
    monkeypatch.setenv(subject.ENABLE_ENV, subject.ENABLE_VALUE)
    monkeypatch.setattr(subject, "GCSExactKnownNameStoreV1", lambda: object())
    monkeypatch.setattr(subject, "GCloudBuildProviderV1", lambda: object())
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        subject,
        "task0_smoke_v1",
        lambda **kwargs: (seen.setdefault("smoke", kwargs), {"ok": "smoke"})[1],
    )
    monkeypatch.setattr(
        subject,
        "collect_v1",
        lambda **kwargs: (seen.setdefault("collect", kwargs), {"ok": "collect"})[1],
    )
    monkeypatch.setattr(
        subject,
        "_load_request",
        lambda path, *, label: {"manifest_identity": manifest_identity},
    )
    assert subject.main([
        "smoke", "--request", "/tmp/smoke.json", "--execute"
    ]) == 0
    assert "runtime_execution_attestation_identity" not in seen["smoke"]

    monkeypatch.setattr(
        subject,
        "_load_request",
        lambda path, *, label: {
            "manifest_identity": manifest_identity,
            "runtime_execution_attestation_identity": execution_identity,
        },
    )
    assert subject.main([
        "collect", "--request", "/tmp/collect.json", "--execute"
    ]) == 0
    assert seen["collect"]["runtime_execution_attestation_identity"] == (
        execution_identity
    )
    capsys.readouterr()
