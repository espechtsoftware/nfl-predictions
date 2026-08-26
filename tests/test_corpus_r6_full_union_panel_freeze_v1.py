from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from scripts import run_corpus_r6_full_union_panel_freeze_v1 as cli
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_release_v1 as release
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research.corpus_neo4j_transport import ObjectIdentity


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK0_RECEIPT = (
    REPO_ROOT
    / "reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index"
    / "panel-index-live/full-union-task0-smoke-2023-w01/receipt.json"
)


def _identity(tag: str, generation: int = 1) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "uri": f"gs://fixture/{tag}.json",
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _MemoryExact:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.current: dict[str, tuple[ObjectIdentity, bytes]] = {}
        self.generation = 0

    @staticmethod
    def _key(identity: object) -> tuple[str, str, str, int]:
        if isinstance(identity, ObjectIdentity):
            identity = identity.as_dict()
        assert isinstance(identity, dict)
        return (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )

    def add(self, uri: str, value: dict[str, Any]) -> dict[str, object]:
        raw = batch.canonical_json_bytes(value)
        return self.publish_create_once(uri, raw).as_dict()

    def read_exact(self, identity: object) -> bytes:
        return self.values[self._key(identity)]

    def resolve_optional(self, uri: str):
        return self.current.get(uri)

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        existing = self.current.get(uri)
        if existing is not None:
            if existing[1] != raw:
                raise RuntimeError("create-once collision differs")
            return existing[0]
        self.generation += 1
        identity = ObjectIdentity(
            uri=uri,
            generation=str(self.generation),
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        self.values[self._key(identity)] = bytes(raw)
        self.current[uri] = (identity, bytes(raw))
        return identity


def _fixture_member(source_ordinal: int) -> dict[str, object]:
    season = 2023 + source_ordinal // 18
    week = source_ordinal % 18 + 1
    lane_ordinal = 0 if source_ordinal < 28 else 1
    task_ordinal = source_ordinal if lane_ordinal == 0 else source_ordinal - 28
    return {
        "source_task_ordinal": source_ordinal,
        "task_ordinal": task_ordinal,
        "lane_ordinal": lane_ordinal,
        "lane_id": "v12a" if lane_ordinal == 0 else "v12b",
        "slate_id": f"{season}-w{week:02d}",
        "source_task_authority_sha256": f"{source_ordinal + 1:064x}",
        "task_acceptance_identity": _identity(
            f"acceptance-{source_ordinal}", 100 + source_ordinal
        ),
        "carrier_identity": _identity(
            f"carrier-{source_ordinal}", 200 + source_ordinal
        ),
        "arms": [
            {
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": parameter_set_id,
                "result_identity": _identity(
                    f"arm-{source_ordinal}-{arm_ordinal}",
                    1_000 + source_ordinal * 10 + arm_ordinal,
                ),
            }
            for arm_ordinal, parameter_set_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
    }


def _rehash(body: dict[str, Any], field: str) -> None:
    body.pop(field, None)
    body[field] = batch.canonical_sha256(body)


def _runtime_evidence(
    *,
    manifest: dict[str, Any],
    manifest_identity: dict[str, object],
    source_ordinal: int = 0,
    task_index: int = 0,
    task_count: int = 1,
    source_offset: int | None = None,
) -> dict[str, object]:
    job = (
        "atlas-minimal-c-s2023-w1-v1"
        if source_ordinal < 28
        else "atlas-cbc-32g-full-2023-w8-v1"
    )
    args = [
        "scripts/run_corpus_r6_full_union_panel_freeze_v1.py",
        "--project", "nfl-predictions-503414",
        "run-slate", "--execute",
        "--manifest-uri", str(manifest_identity["uri"]),
        "--manifest-generation", str(manifest_identity["generation"]),
        "--manifest-sha256", str(manifest_identity["sha256"]),
        "--manifest-bytes", str(manifest_identity["bytes"]),
    ]
    if source_offset is None:
        args.extend(["--source-ordinal", str(source_ordinal)])
    else:
        args.extend(["--source-offset", str(source_offset)])
    args.extend([
        "--expected-source-commit-sha", str(manifest["source_commit_sha"]),
        "--expected-immutable-image", str(manifest["immutable_image"]),
        "--expected-project-number", "817589974517",
        "--expected-region", "us-central1",
    ])
    evidence: dict[str, object] = {
        "schema_version": freeze.RUNTIME_EXECUTION_EVIDENCE_SCHEMA,
        "cloud_project_id": "nfl-predictions-503414",
        "cloud_project_number": "817589974517",
        "cloud_region": "us-central1",
        "cloud_job": job,
        "cloud_execution": f"{job}-fixture",
        "cloud_execution_uid": "execution-uid",
        "cloud_job_uid": (
            "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
            if source_ordinal < 28
            else "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
        ),
        "cloud_job_generation": "1",
        "execution_resource_version": "resource-version",
        "source_ordinal": source_ordinal,
        "task_index": task_index,
        "task_attempt": 0,
        "task_count": task_count,
        "parallelism": min(4, task_count),
        "max_retries": 0,
        "task_timeout_seconds": 7_200,
        "immutable_image": manifest["immutable_image"],
        "service_account": (
            "817589974517-compute@developer.gserviceaccount.com"
        ),
        "cpu": "4",
        "memory": "16Gi",
        "container_command": ["python"],
        "container_args": args,
        "execution_spec_keys": ["parallelism", "taskCount", "template"],
        "execution_template_keys": ["spec"],
        "task_spec_keys": [
            "containers", "maxRetries", "serviceAccountName", "timeoutSeconds",
        ],
        "container_keys": ["args", "command", "env", "image", "resources"],
        "configured_environment": {
            "R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED": "1",
            "R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE": manifest[
                "immutable_image"
            ],
        },
        "secret_env_count": 0,
        "volume_count": 0,
        "volume_mount_count": 0,
        "network_attachment_count": 0,
        "authenticated_execution_api_read": True,
    }
    _rehash(evidence, "runtime_execution_evidence_sha256")
    return evidence


def _runtime_api_response(
    *, manifest: dict[str, Any], manifest_identity: dict[str, object]
) -> tuple[dict[str, Any], Any, dict[str, object]]:
    evidence = _runtime_evidence(
        manifest=manifest,
        manifest_identity=manifest_identity,
        source_offset=0,
    )
    parsed_args = cli._parser().parse_args(evidence["container_args"][1:])
    task = {
        "cloud_job": evidence["cloud_job"],
        "cloud_execution": evidence["cloud_execution"],
        "task_index": evidence["task_index"],
        "task_attempt": evidence["task_attempt"],
        "task_count": evidence["task_count"],
    }
    response: dict[str, Any] = {
        "metadata": {
            "name": evidence["cloud_execution"],
            "namespace": evidence["cloud_project_number"],
            "uid": evidence["cloud_execution_uid"],
            "resourceVersion": evidence["execution_resource_version"],
            "annotations": {"run.googleapis.com/cloudsql-instances": ""},
            "labels": {
                "run.googleapis.com/job": evidence["cloud_job"],
                "run.googleapis.com/jobUid": evidence["cloud_job_uid"],
                "run.googleapis.com/jobGeneration": evidence[
                    "cloud_job_generation"
                ],
            },
        },
        "spec": {
            "parallelism": evidence["parallelism"],
            "taskCount": evidence["task_count"],
            "template": {
                "spec": {
                    "containers": [{
                        "args": evidence["container_args"],
                        "command": evidence["container_command"],
                        "env": [
                            {"name": name, "value": value}
                            for name, value in evidence[
                                "configured_environment"
                            ].items()
                        ],
                        "image": evidence["immutable_image"],
                        "resources": {"limits": {
                            "cpu": evidence["cpu"],
                            "memory": evidence["memory"],
                        }},
                    }],
                    "maxRetries": evidence["max_retries"],
                    "serviceAccountName": evidence["service_account"],
                    "timeoutSeconds": str(evidence["task_timeout_seconds"]),
                },
            },
        },
    }
    return response, parsed_args, task


def _prepared_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    _MemoryExact, dict[str, Any], dict[str, object],
    dict[str, Any], dict[str, object], dict[str, Any], dict[str, object]
]:
    receipt = batch.parse_canonical_json_bytes(
        TASK0_RECEIPT.read_bytes(), label="real task0 smoke receipt"
    )
    real_result = deepcopy(receipt["execution_result"])
    members = [_fixture_member(ordinal) for ordinal in range(54)]
    members[0] = deepcopy(real_result["accepted_slate_membership"])
    panel_id = "v12:" + "f" * 64
    panel: dict[str, Any] = {
        "schema_version": "foundry-v12-combined-panel-index/v1",
        "publication_mode": "create_once",
        "panel_id": panel_id,
        "artifact_source_authority_completion": _identity("source-completion", 9),
        "artifact_source_authority_completion_sha256": "1" * 64,
        "lane_count": 2,
        "lanes": [{"lane_ordinal": 0}, {"lane_ordinal": 1}],
        "accepted_slate_count": 54,
        "accepted_slates": members,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": 54,
            "accepted_task_count": 54,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
        "analytical_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    _rehash(panel, "panel_index_sha256")
    store = _MemoryExact()
    panel_identity = store.add("gs://fixture/fixed-panel.json", panel)
    monkeypatch.setattr(adapter, "FIXED_PANEL_ID", panel_id)
    monkeypatch.setattr(adapter, "FIXED_PANEL_INDEX_SHA256", panel["panel_index_sha256"])
    monkeypatch.setattr(adapter, "FIXED_PANEL_IDENTITY", panel_identity)

    real_result["panel_index_identity"] = panel_identity
    real_result["panel_index_sha256"] = panel["panel_index_sha256"]
    real_result["accepted_slate_membership"] = deepcopy(members[0])
    real_result["accepted_slate_membership_sha256"] = batch.canonical_sha256(members[0])
    _rehash(real_result, "task_result_sha256")

    manifest = freeze.build_execution_manifest_v1(
        panel_index_identity=panel_identity,
        exact_panel_index=panel,
        source_commit_sha="d" * 40,
        immutable_image="us-central1-docker.pkg.dev/p/r/i@sha256:" + "e" * 64,
        output_prefix="gs://fixture/r6-full-union-freeze/",
    )
    manifest_identity = store.add(
        "gs://fixture/r6-full-union-freeze/execution-manifest.json", manifest
    )
    result_uri = manifest["source_members"][0]["task_result_uri"]
    result_envelope = freeze.build_task_result_envelope_v1(
        manifest_identity=manifest_identity,
        source_ordinal=0,
        runtime_execution_evidence=_runtime_evidence(
            manifest=manifest, manifest_identity=manifest_identity
        ),
        task_result=real_result,
        read_exact=store.read_exact,
    )
    result_identity = store.add(str(result_uri), result_envelope)
    return (
        store, panel, panel_identity, manifest, manifest_identity,
        real_result, result_identity,
    )


def test_real_task0_builds_compact_leaf_with_48_books_and_144_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, manifest, manifest_identity, result, result_identity = (
        _prepared_fixture(monkeypatch)
    )
    leaf = freeze.build_slate_freeze_v1(
        manifest_identity=manifest_identity,
        source_ordinal=0,
        task_result_identity=result_identity,
        read_exact=store.read_exact,
    )
    assert leaf["book_count"] == 48
    assert leaf["prefix_count"] == 144
    assert leaf["scope_count"] == 6
    assert leaf["all_block_union"]["lineup_count"] == 3_815
    assert leaf["task_result_sha256"] == result["task_result_sha256"]
    assert leaf["task_result_envelope_sha256"] != result["task_result_sha256"]
    assert leaf["task_result_identity"]["sha256"] != result["task_result_sha256"]
    assert len(batch.canonical_json_bytes(leaf)) < 200_000
    assert leaf["manifest_identity"] == manifest_identity
    assert leaf["strategy_registry_sha256"] == manifest["strategy_registry_sha256"]


def test_prefix_descriptors_bind_exact_first_n_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, _, manifest_identity, result, result_identity = _prepared_fixture(
        monkeypatch
    )
    leaf = freeze.build_slate_freeze_v1(
        manifest_identity=manifest_identity,
        source_ordinal=0,
        task_result_identity=result_identity,
        read_exact=store.read_exact,
    )
    book = result["full_union_surface"]["scopes"][0]["books"][0]
    descriptor = leaf["book_descriptors"][0]
    for prefix, size in zip(descriptor["prefixes"], (4, 14, 80), strict=True):
        assert prefix["entry_count"] == size
        assert prefix["prefix_payload_sha256"] == batch.canonical_sha256({
            "selected_lineup_ids": book["selected_lineup_ids"][:size],
            "selected_rosters": book["selected_rosters"][:size],
        })


def test_task_result_rejects_coherently_rehashed_nested_result_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, panel, panel_identity, _, _, result, _ = _prepared_fixture(monkeypatch)
    mutated = deepcopy(result)
    scope = mutated["full_union_surface"]["scopes"][0]
    book = scope["books"][0]
    book["training_metrics"]["score_micro"] = 200_000_000
    _rehash(book, "book_sha256")
    _rehash(scope, "fit_scope_sha256")
    _rehash(mutated["full_union_surface"], "full_union_surface_sha256")
    mutated["full_union_surface_sha256"] = mutated["full_union_surface"][
        "full_union_surface_sha256"
    ]
    _rehash(mutated, "task_result_sha256")
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.validate_task_result_v1(
            mutated,
            panel_index_identity=panel_identity,
            panel_index_sha256=panel["panel_index_sha256"],
            panel_member=panel["accepted_slates"][0],
        )


def test_task_result_envelope_binds_manifest_commit_image_and_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, panel, _, manifest, manifest_identity, result, result_identity = (
        _prepared_fixture(monkeypatch)
    )
    envelope = batch.parse_canonical_json_bytes(
        store.read_exact(result_identity), label="task-result envelope"
    )
    assert envelope["manifest_identity"] == manifest_identity
    assert envelope["source_commit_sha"] == manifest["source_commit_sha"]
    assert envelope["immutable_image"] == manifest["immutable_image"]
    assert envelope["panel_member_sha256"] == batch.canonical_sha256(
        panel["accepted_slates"][0]
    )
    assert envelope["task_result_sha256"] == result["task_result_sha256"]
    assert envelope["task_result_payload_sha256"] == batch.canonical_sha256(result)
    assert envelope["runtime_execution_evidence"][
        "authenticated_execution_api_read"
    ] is True

    mutated = deepcopy(envelope)
    mutated["source_commit_sha"] = "0" * 40
    _rehash(mutated, "task_result_envelope_sha256")
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.validate_task_result_envelope_v1(
            mutated,
            manifest_identity=manifest_identity,
            manifest=manifest,
            panel=panel,
            panel_members=panel["accepted_slates"],
            source_ordinal=0,
        )


def test_runtime_execution_evidence_rejects_retry_or_wrong_actual_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, manifest, manifest_identity, _, _ = _prepared_fixture(monkeypatch)
    evidence = _runtime_evidence(
        manifest=manifest, manifest_identity=manifest_identity
    )
    for field, value in (
        ("task_attempt", 1),
        ("max_retries", 1),
        ("immutable_image", "us-central1/x@sha256:" + "0" * 64),
    ):
        mutated = deepcopy(evidence)
        mutated[field] = value
        _rehash(mutated, "runtime_execution_evidence_sha256")
        with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
            freeze.validate_runtime_execution_evidence_v1(
                mutated,
                manifest_identity=manifest_identity,
                manifest=manifest,
                source_ordinal=0,
            )


def test_authenticated_execution_projection_rejects_expanded_authority_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, manifest, manifest_identity, _, _ = _prepared_fixture(monkeypatch)
    response, parsed_args, task = _runtime_api_response(
        manifest=manifest, manifest_identity=manifest_identity
    )
    projected = cli._project_runtime_execution_response(
        execution=response,
        args=parsed_args,
        source_ordinal=0,
        task=task,
    )
    assert projected["secret_env_count"] == 0
    assert projected["network_attachment_count"] == 0

    mutations = []
    secret = deepcopy(response)
    secret["spec"]["template"]["spec"]["containers"][0]["env"].append({
        "name": "SECRET", "valueFrom": {"secretKeyRef": {"name": "x"}},
    })
    mutations.append(secret)
    volume = deepcopy(response)
    volume["spec"]["template"]["spec"]["volumes"] = [
        {"name": "secret-volume", "secret": {"secretName": "x"}},
    ]
    mutations.append(volume)
    network = deepcopy(response)
    network["metadata"]["annotations"][
        "run.googleapis.com/vpc-access-connector"
    ] = "projects/p/locations/r/connectors/c"
    mutations.append(network)
    template_network = deepcopy(response)
    template_network["spec"]["template"]["metadata"] = {
        "annotations": {
            "run.googleapis.com/cloudsql-instances": "project:region:instance",
        },
    }
    mutations.append(template_network)
    wrong_service_account = deepcopy(response)
    wrong_service_account["spec"]["template"]["spec"][
        "serviceAccountName"
    ] = "other@developer.gserviceaccount.com"
    mutations.append(wrong_service_account)
    extra_container_field = deepcopy(response)
    extra_container_field["spec"]["template"]["spec"]["containers"][0][
        "ports"
    ] = [{"containerPort": 8080}]
    mutations.append(extra_container_field)
    for mutated in mutations:
        with pytest.raises(cli.CorpusR6FullUnionPanelFreezeCLIError):
            cli._project_runtime_execution_response(
                execution=mutated,
                args=parsed_args,
                source_ordinal=0,
                task=task,
            )


def test_manifest_leaf_and_envelope_reject_copied_outer_uris(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, _, manifest_identity, _, result_identity = _prepared_fixture(
        monkeypatch
    )
    manifest = batch.parse_canonical_json_bytes(
        store.read_exact(manifest_identity), label="manifest"
    )
    copied_manifest_identity = store.add(
        "gs://fixture/copied-execution-manifest.json", manifest
    )
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.reopen_execution_manifest_v1(
            copied_manifest_identity, read_exact=store.read_exact
        )

    envelope = batch.parse_canonical_json_bytes(
        store.read_exact(result_identity), label="task-result envelope"
    )
    copied_result_identity = store.add(
        "gs://fixture/copied-task-result.json", envelope
    )
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.reopen_task_result_envelope_v1(
            copied_result_identity, read_exact=store.read_exact
        )

    leaf = freeze.build_slate_freeze_v1(
        manifest_identity=manifest_identity,
        source_ordinal=0,
        task_result_identity=result_identity,
        read_exact=store.read_exact,
    )
    copied_leaf_identity = store.add("gs://fixture/copied-slate-freeze.json", leaf)
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.reopen_slate_freeze_v1(
            copied_leaf_identity, read_exact=store.read_exact
        )


def _fake_leaf(
    *, source_ordinal: int, manifest: dict[str, Any], manifest_identity: dict[str, object]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, object]]:
    source_member = manifest["source_members"][source_ordinal]
    result_identity = _identity(f"root-result-{source_ordinal}", 5_000 + source_ordinal)
    result = {"task_result_sha256": f"{source_ordinal + 100:064x}"}
    leaf_identity = _identity(f"root-leaf-{source_ordinal}", 6_000 + source_ordinal)
    leaf = {
        "source_ordinal": source_ordinal,
        "slate_id": source_member["slate_id"],
        "manifest_identity": manifest_identity,
        "panel_member_sha256": source_member["panel_member_sha256"],
        "later_source_freeze_identity": manifest["later_source_freeze_identity"],
        "strategy_registry_sha256": manifest["strategy_registry_sha256"],
        "task_result_identity": result_identity,
        "task_result_envelope_sha256": f"{source_ordinal + 150:064x}",
        "runtime_execution_evidence_sha256": f"{source_ordinal + 175:064x}",
        "full_union_surface_sha256": f"{source_ordinal + 200:064x}",
        "slate_freeze_sha256": f"{source_ordinal + 300:064x}",
        "all_block_union": {
            "lineup_count": 80 + source_ordinal,
            "population_descriptor_sha256": f"{source_ordinal + 400:064x}",
        },
        "scope_count": 6,
        "book_count": 48,
        "prefix_count": 144,
        "complete": True,
    }
    return leaf, result, leaf_identity


def test_panel_root_requires_complete_ordered_54_leaf_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, panel, _, manifest, manifest_identity, _, _ = _prepared_fixture(monkeypatch)
    fake = [_fake_leaf(
        source_ordinal=ordinal, manifest=manifest, manifest_identity=manifest_identity
    ) for ordinal in range(54)]
    by_uri = {row[2]["uri"]: row for row in fake}

    def reopen(identity: object, *, read_exact: object):
        row = by_uri[dict(identity)["uri"]]
        return row[0], manifest, panel, panel["accepted_slates"], row[1], row[2]

    monkeypatch.setattr(freeze, "reopen_slate_freeze_v1", reopen)
    root = freeze.build_panel_freeze_v1(
        manifest_identity=manifest_identity,
        ordered_slate_freeze_identities=[row[2] for row in fake],
        read_exact=store.read_exact,
    )
    assert root["source_slate_count"] == 54
    assert root["rank_80_book_count"] == 2_592
    assert root["prefix_count"] == 7_776
    assert root["prefix_roster_occurrence_counts"] == {
        "4": 10_368, "14": 36_288, "80": 207_360,
    }
    assert root["outcome_key_projection_inputs_frozen"] is True
    root_identity = store.add(str(root["target_uri"]), root)
    reopened, reopened_identity = freeze.reopen_panel_freeze_v1(
        root_identity, read_exact=store.read_exact
    )
    assert reopened_identity == root_identity
    assert batch.canonical_json_bytes(reopened) == batch.canonical_json_bytes(root)
    copied_root_identity = store.add("gs://fixture/copied-panel-freeze.json", root)
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.reopen_panel_freeze_v1(
            copied_root_identity, read_exact=store.read_exact
        )
    reordered = [row[2] for row in fake]
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.build_panel_freeze_v1(
            manifest_identity=manifest_identity,
            ordered_slate_freeze_identities=reordered,
            read_exact=store.read_exact,
        )


def test_panel_root_rejects_wrong_extra_and_nested_outcome_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, panel, _, manifest, manifest_identity, _, _ = _prepared_fixture(monkeypatch)
    fake = [
        _fake_leaf(
            source_ordinal=ordinal,
            manifest=manifest,
            manifest_identity=manifest_identity,
        )
        for ordinal in range(54)
    ]
    by_uri = {row[2]["uri"]: row for row in fake}

    def reopen(identity: object, *, read_exact: object):
        row = by_uri[dict(identity)["uri"]]
        return row[0], manifest, panel, panel["accepted_slates"], row[1], row[2]

    monkeypatch.setattr(freeze, "reopen_slate_freeze_v1", reopen)
    root = freeze.build_panel_freeze_v1(
        manifest_identity=manifest_identity,
        ordered_slate_freeze_identities=[row[2] for row in fake],
        read_exact=store.read_exact,
    )

    wrong_value = deepcopy(root)
    wrong_value["outcome_key_projection_inputs_frozen"] = False
    near_name = deepcopy(root)
    near_name["outcome_key_projection_inputs_frozen_extra"] = True
    nested = deepcopy(root)
    nested["prefix_roster_occurrence_counts"][
        "outcome_key_projection_inputs_frozen"
    ] = True
    for mutated in (wrong_value, near_name, nested):
        _rehash(mutated, "panel_freeze_sha256")
        with pytest.raises(
            freeze.CorpusR6FullUnionPanelFreezeV1Error,
            match="outcome|top-level",
        ):
            freeze.validate_panel_freeze_structure_v1(
                mutated, read_exact=store.read_exact
            )


def test_manifest_rejects_mutable_image_and_incomplete_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, panel, panel_identity, _, _, _, _ = _prepared_fixture(monkeypatch)
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.build_execution_manifest_v1(
            panel_index_identity=panel_identity,
            exact_panel_index=panel,
            source_commit_sha="d" * 40,
            immutable_image="gcr.io/project/image:latest",
            output_prefix="gs://fixture/r6/",
        )
    incomplete = deepcopy(panel)
    incomplete["accepted_slates"] = incomplete["accepted_slates"][:-1]
    incomplete["accepted_slate_count"] = 53
    incomplete["coverage"]["accepted_task_count"] = 53
    _rehash(incomplete, "panel_index_sha256")
    monkeypatch.setattr(adapter, "FIXED_PANEL_INDEX_SHA256", incomplete["panel_index_sha256"])
    with pytest.raises(freeze.CorpusR6FullUnionPanelFreezeV1Error):
        freeze.validate_fixed_panel_v1(incomplete)


def test_release_recovers_result_then_leaf_without_reexecuting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, manifest, manifest_identity, _, _ = _prepared_fixture(monkeypatch)
    calls: list[bool] = []

    def forbidden_execute(**kwargs: object) -> dict[str, object]:
        calls.append(True)
        raise AssertionError("existing deterministic result must be recovered")

    first = release.run_slate_release_v1(
        storage=store,
        manifest_identity=manifest_identity,
        source_ordinal=0,
        runtime_source_commit_sha=str(manifest["source_commit_sha"]),
        runtime_immutable_image=str(manifest["immutable_image"]),
        runtime_execution_evidence=_runtime_evidence(
            manifest=manifest, manifest_identity=manifest_identity
        ),
        execute=forbidden_execute,
    )
    assert first["result_recovered_without_reexecution"] is True
    assert first["leaf_recovered_without_republication"] is False
    second = release.run_slate_release_v1(
        storage=store,
        manifest_identity=manifest_identity,
        source_ordinal=0,
        runtime_source_commit_sha=str(manifest["source_commit_sha"]),
        runtime_immutable_image=str(manifest["immutable_image"]),
        runtime_execution_evidence=_runtime_evidence(
            manifest=manifest, manifest_identity=manifest_identity
        ),
        execute=forbidden_execute,
    )
    assert second["leaf_recovered_without_republication"] is True
    assert calls == []
    status = release.panel_status_v1(
        storage=store, manifest_identity=manifest_identity
    )
    assert status["completed_source_ordinals"] == [0]
    assert status["completed_slate_count"] == 1
    assert status["rank_80_book_count"] == 48
    assert status["prefix_count"] == 144
    assert status["root_ready"] is False


def test_release_fresh_execution_wraps_publishes_and_reopens_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, manifest, manifest_identity, result, result_identity = (
        _prepared_fixture(monkeypatch)
    )
    result_uri = str(result_identity["uri"])
    store.current.pop(result_uri)
    calls: list[int] = []

    def execute(**kwargs: object) -> dict[str, object]:
        calls.append(1)
        return deepcopy(result)

    receipt = release.run_slate_release_v1(
        storage=store,
        manifest_identity=manifest_identity,
        source_ordinal=0,
        runtime_source_commit_sha=str(manifest["source_commit_sha"]),
        runtime_immutable_image=str(manifest["immutable_image"]),
        runtime_execution_evidence=_runtime_evidence(
            manifest=manifest, manifest_identity=manifest_identity
        ),
        execute=execute,
    )
    assert calls == [1]
    assert receipt["result_recovered_without_reexecution"] is False
    assert receipt["leaf_recovered_without_republication"] is False
    retained = store.resolve_optional(result_uri)
    assert retained is not None
    envelope = batch.parse_canonical_json_bytes(
        retained[1], label="fresh task-result envelope"
    )
    assert envelope["schema_version"] == freeze.TASK_RESULT_ENVELOPE_SCHEMA
    assert envelope["task_result_sha256"] == result["task_result_sha256"]


def test_prepare_release_recovers_byte_identical_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, panel_identity, manifest, manifest_identity, _, _ = _prepared_fixture(
        monkeypatch
    )
    receipt = release.prepare_release_v1(
        storage=store,
        panel_index_identity=panel_identity,
        source_commit_sha=str(manifest["source_commit_sha"]),
        immutable_image=str(manifest["immutable_image"]),
        output_prefix=str(manifest["output_prefix"]),
    )
    assert receipt["manifest_identity"] == manifest_identity
    assert receipt["source_slate_count"] == 54
    assert receipt["rank_80_book_count"] == 2_592
    assert receipt["prefix_count"] == 7_776


def test_release_rejects_runtime_image_or_commit_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, manifest, manifest_identity, _, _ = _prepared_fixture(monkeypatch)
    with pytest.raises(release.CorpusR6FullUnionPanelFreezeReleaseV1Error):
        release.run_slate_release_v1(
            storage=store,
            manifest_identity=manifest_identity,
            source_ordinal=0,
            runtime_source_commit_sha="0" * 40,
            runtime_immutable_image=str(manifest["immutable_image"]),
            runtime_execution_evidence=_runtime_evidence(
                manifest=manifest, manifest_identity=manifest_identity
            ),
        )
    with pytest.raises(release.CorpusR6FullUnionPanelFreezeReleaseV1Error):
        release.run_slate_release_v1(
            storage=store,
            manifest_identity=manifest_identity,
            source_ordinal=0,
            runtime_source_commit_sha=str(manifest["source_commit_sha"]),
            runtime_immutable_image="us-central1/x@sha256:" + "0" * 64,
            runtime_execution_evidence=_runtime_evidence(
                manifest=manifest, manifest_identity=manifest_identity
            ),
        )


def test_cli_maps_cloud_task_index_only_after_production_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, manifest, manifest_identity, _, _ = _prepared_fixture(monkeypatch)
    monkeypatch.setenv(cli.PRODUCTION_ENABLE_ENV, "1")
    monkeypatch.setenv(cli.RUNTIME_IMAGE_ENV, str(manifest["immutable_image"]))
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "1")
    monkeypatch.setenv("CLOUD_RUN_JOB", "atlas-minimal-c-s2023-w1-v1")
    monkeypatch.setenv(
        "CLOUD_RUN_EXECUTION", "atlas-minimal-c-s2023-w1-v1-fixture"
    )
    monkeypatch.setattr(cli, "_clean_head", lambda: manifest["source_commit_sha"])
    identity_args = [
        "--manifest-uri", str(manifest_identity["uri"]),
        "--manifest-generation", str(manifest_identity["generation"]),
        "--manifest-sha256", str(manifest_identity["sha256"]),
        "--manifest-bytes", str(manifest_identity["bytes"]),
    ]
    runtime_evidence = _runtime_evidence(
        manifest=manifest,
        manifest_identity=manifest_identity,
        source_offset=0,
    )
    receipt = cli.run([
        "--project", "nfl-predictions-503414", "run-slate", "--execute",
        *identity_args,
        "--source-offset", "0",
        "--expected-source-commit-sha", str(manifest["source_commit_sha"]),
        "--expected-immutable-image", str(manifest["immutable_image"]),
        "--expected-project-number", "817589974517",
        "--expected-region", "us-central1",
    ], storage=store, runtime_evidence_probe=lambda **_: runtime_evidence)
    assert receipt["source_ordinal"] == 0
    monkeypatch.delenv(cli.PRODUCTION_ENABLE_ENV)
    with pytest.raises(cli.CorpusR6FullUnionPanelFreezeCLIError):
        cli.run([
            "--project", "nfl-predictions-503414", "run-slate", "--execute",
            *identity_args,
            "--source-offset", "0",
            "--expected-source-commit-sha", str(manifest["source_commit_sha"]),
            "--expected-immutable-image", str(manifest["immutable_image"]),
            "--expected-project-number", "817589974517",
            "--expected-region", "us-central1",
        ], storage=store, runtime_evidence_probe=lambda **_: runtime_evidence)
