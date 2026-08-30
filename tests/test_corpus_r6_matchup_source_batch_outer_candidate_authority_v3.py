from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import inspect
from types import SimpleNamespace

import pytest

from nfl_dfs.research import (
    corpus_r6_matchup_source_batch_outer_candidate_authority_v3 as batch,
)
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_outer_candidate_authority_v3 as release_v3,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import (
    test_corpus_r6_matchup_capture_plan_outer_candidate_authority_v3
    as capture_fixture,
)


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _closure() -> dict[str, object]:
    commit = "a" * 40
    identities = [{
        "source_commit_sha": commit,
        "module_path": path,
        "module_sha256": _digest(path),
    } for path in batch.EXECUTED_DEPENDENCY_MODULE_PATHS]
    body: dict[str, object] = {
        "schema_version": batch.DEPENDENCY_CLOSURE_SCHEMA,
        "source_commit_sha": commit,
        "module_paths": list(batch.EXECUTED_DEPENDENCY_MODULE_PATHS),
        "module_code_identities": identities,
        "module_code_identity_manifest_sha256": batch.canonical_sha256(
            identities
        ),
        "repository_status_clean": True,
        "all_head_blobs_match_current_nofollow_bytes": True,
    }
    body["dependency_closure_sha256"] = batch.canonical_sha256(body)
    return body


def _runtime(closure: dict[str, object]) -> dict[str, object]:
    origins = dict(sorted(batch._RUNTIME_MODULE_PATHS.items()))
    callables = []
    for owner, attribute, relative_path in batch._critical_loaded_callables_v3():
        loaded = getattr(owner, attribute)
        module_name = batch._callable_owner_module_name_v3(owner)
        code_sha = _digest(f"{module_name}:{attribute}:{relative_path}")
        callables.append({
            "module_name": module_name,
            "attribute": attribute,
            "module_path": relative_path,
            "qualname": loaded.__qualname__,
            "loaded_code_sha256": code_sha,
            "committed_source_code_sha256": code_sha,
            "loaded_code_matches_committed_source": True,
        })
    callables.sort(
        key=lambda row: (
            str(row["module_name"]),
            str(row["attribute"]),
            str(row["module_path"]),
        )
    )
    digest = f"sha256:{'b' * 64}"
    body: dict[str, object] = {
        "schema_version": batch.RUNTIME_BINDING_SCHEMA,
        "source_commit_sha": closure["source_commit_sha"],
        "dependency_closure_sha256": closure["dependency_closure_sha256"],
        "image_digest": digest,
        "image_reference": f"example.invalid/nfl-dfs@{digest}",
        "image_source_commit_sha": closure["source_commit_sha"],
        "image_identity_source": "environment-declared",
        "image_identity_environment_declared": True,
        "image_digest_runtime_provider_attested": False,
        "image_build_receipt_exact_reopened": False,
        "git_independent_runtime_receipt_required": True,
        "loaded_module_origins": origins,
        "loaded_module_origin_manifest_sha256": batch.canonical_sha256(origins),
        "critical_callables": callables,
        "critical_callable_manifest_sha256": batch.canonical_sha256(callables),
        "immutable_image_identity_required": True,
        "all_loaded_origins_match_clean_dependency_closure": True,
        "all_loaded_callable_code_matches_clean_dependency_closure": True,
        "same_clean_commit_and_image_required_for_resume": True,
    }
    body["runtime_binding_sha256"] = batch.canonical_sha256(body)
    return body


def test_fixed_inventory_contains_only_v3_terminal_roots_and_is_preenumerated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = capture_fixture._fixture(monkeypatch)
    plan = capture_fixture._build(fixture)
    inventory = batch._output_uri_inventory_v3(
        run_id="fixture-source-v3", plan_value=plan
    )

    by_phase = {
        str(entry["phase"]): str(entry["uri"])
        for entry in inventory["entries"]
        if str(entry["phase"]).endswith("root")
    }
    assert by_phase["source-release-v3-root"].endswith(
        release_v3.ROOT_FILENAME
    )
    assert by_phase["terminal-batch-v3-root"].endswith(batch.ROOT_FILENAME)
    assert inventory["terminal_batch_root_uri"] == by_phase[
        "terminal-batch-v3-root"
    ]
    assert inventory["inventory_derived_before_write_client_construction"] is True
    assert inventory["broad_prefix_write_authority_allowed"] is False
    assert not any(
        "source-release-candidate-authority-v2" in str(uri)
        or "matchup-source-batch-release.json" in str(uri)
        for uri in inventory["uris"]
    )


def test_inventory_rejects_non_string_run_id_before_plan_or_uri_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_touched = False

    def validate_plan(_value: object) -> dict[str, object]:
        nonlocal plan_touched
        plan_touched = True
        raise AssertionError("run ID must fail before plan validation")

    monkeypatch.setattr(
        batch.capture_v3, "validate_capture_plan_lock_v3", validate_plan
    )
    with pytest.raises(
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
        match="run ID",
    ):
        batch._output_uri_inventory_v3(run_id=12345678, plan_value={})
    assert plan_touched is False


def test_dependency_and_runtime_binding_reject_coherently_rehashed_drift() -> None:
    closure = _closure()
    runtime = _runtime(closure)
    assert batch._normalize_dependency_closure(closure) == closure
    assert batch._normalize_runtime_binding(
        runtime, dependency_closure=closure
    ) == runtime

    changed = deepcopy(runtime)
    changed["image_source_commit_sha"] = "c" * 40
    changed["runtime_binding_sha256"] = batch.canonical_sha256({
        key: value
        for key, value in changed.items()
        if key != "runtime_binding_sha256"
    })
    with pytest.raises(
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
        match="fixed law",
    ):
        batch._normalize_runtime_binding(changed, dependency_closure=closure)


def test_runtime_builder_binds_loaded_callable_code_to_current_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closure = _closure()
    digest = f"sha256:{'f' * 64}"
    monkeypatch.setenv(batch.IMAGE_DIGEST_ENV, digest)
    monkeypatch.setenv(
        batch.IMAGE_REFERENCE_ENV, f"example.invalid/nfl-dfs@{digest}"
    )
    monkeypatch.setenv(
        batch.IMAGE_SOURCE_COMMIT_ENV, str(closure["source_commit_sha"])
    )

    runtime = batch._build_runtime_binding_v3(closure)

    assert runtime["all_loaded_callable_code_matches_clean_dependency_closure"] is True
    assert runtime["image_identity_source"] == "environment-declared"
    assert runtime["image_digest_runtime_provider_attested"] is False
    assert runtime["image_build_receipt_exact_reopened"] is False
    assert runtime["git_independent_runtime_receipt_required"] is True
    assert runtime["critical_callables"]
    assert all(
        row["loaded_code_sha256"] == row["committed_source_code_sha256"]
        for row in runtime["critical_callables"]
    )


def test_runtime_builder_rejects_substituted_internal_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closure = _closure()
    digest = f"sha256:{'f' * 64}"
    monkeypatch.setenv(batch.IMAGE_DIGEST_ENV, digest)
    monkeypatch.setenv(
        batch.IMAGE_REFERENCE_ENV, f"example.invalid/nfl-dfs@{digest}"
    )
    monkeypatch.setenv(
        batch.IMAGE_SOURCE_COMMIT_ENV, str(closure["source_commit_sha"])
    )
    monkeypatch.setattr(batch, "_build_batch_root_v3", lambda **_kwargs: {})

    with pytest.raises(
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
        match="critical callable origin differs",
    ):
        batch._build_runtime_binding_v3(closure)


def test_runtime_builder_rejects_substituted_callable_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closure = _closure()
    digest = f"sha256:{'f' * 64}"
    monkeypatch.setenv(batch.IMAGE_DIGEST_ENV, digest)
    monkeypatch.setenv(
        batch.IMAGE_REFERENCE_ENV, f"example.invalid/nfl-dfs@{digest}"
    )
    monkeypatch.setenv(
        batch.IMAGE_SOURCE_COMMIT_ENV, str(closure["source_commit_sha"])
    )
    monkeypatch.setattr(batch, "_critical_loaded_callables_v3", lambda: ())

    with pytest.raises(
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
        match="callable registry origin differs",
    ):
        batch._build_runtime_binding_v3(closure)


def test_runtime_builder_rejects_substituted_nested_release_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closure = _closure()
    digest = f"sha256:{'f' * 64}"
    monkeypatch.setenv(batch.IMAGE_DIGEST_ENV, digest)
    monkeypatch.setenv(
        batch.IMAGE_REFERENCE_ENV, f"example.invalid/nfl-dfs@{digest}"
    )
    monkeypatch.setenv(
        batch.IMAGE_SOURCE_COMMIT_ENV, str(closure["source_commit_sha"])
    )
    monkeypatch.setattr(
        batch.release_v1,
        "build_matchup_source_release_v1",
        lambda **_kwargs: {},
    )

    with pytest.raises(
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
        match="critical callable origin differs",
    ):
        batch._build_runtime_binding_v3(closure)


def test_public_publication_boundary_accepts_only_run_id() -> None:
    parameters = inspect.signature(
        batch.publish_matchup_source_batch_outer_candidate_authority_v3
    ).parameters
    assert tuple(parameters) == ("run_id",)
    forbidden = {
        "candidate_authority_root_identity",
        "capture_plan",
        "component_result",
        "source_release",
        "read_exact",
        "publish_create_once",
        "score",
        "outcome",
        "selector",
    }
    assert forbidden.isdisjoint(parameters)


def test_publication_rejects_non_string_run_id_before_local_or_cloud_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_touched = False

    def local_context() -> tuple[object, ...]:
        nonlocal context_touched
        context_touched = True
        raise AssertionError("run ID must fail before local context")

    monkeypatch.setenv(batch.PUBLISH_ENABLE_ENV, "1")
    monkeypatch.setattr(batch, "_validate_local_context_v3", local_context)
    with pytest.raises(
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
        match="run ID",
    ):
        batch.publish_matchup_source_batch_outer_candidate_authority_v3(
            run_id=12345678  # type: ignore[arg-type]
        )
    assert context_touched is False


def test_public_reopen_boundary_accepts_only_terminal_identity() -> None:
    parameters = inspect.signature(
        batch.reopen_matchup_source_batch_outer_candidate_authority_v3
    ).parameters
    assert tuple(parameters) == ("batch_release_identity",)
    assert "read_exact" not in parameters
    assert "publish_create_once" not in parameters


def test_preterminal_write_receipt_cannot_claim_unattempted_outputs_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = capture_fixture._fixture(monkeypatch)
    plan = capture_fixture._build(fixture)
    inventory = batch._output_uri_inventory_v3(
        run_id="fixture-source-v3", plan_value=plan
    )
    root_uri = str(inventory["terminal_batch_root_uri"])
    completed = sorted(set(inventory["uris"]) - {root_uri})
    receipt: dict[str, object] = {
        "schema_version": batch.batch_mechanics.CREATE_ONCE_BUDGET_SCHEMA,
        "expected_write_uris": inventory["uris"],
        "expected_write_uri_manifest_sha256": inventory["uri_manifest_sha256"],
        "expected_write_uri_count": inventory["uri_count"],
        "max_write_operations": (
            int(inventory["uri_count"])
            * batch.batch_mechanics.CREATE_ONCE_ATTEMPTS
        ),
        "max_invocation_write_bytes": (
            batch.batch_mechanics.MAX_CREATE_ONCE_INVOCATION_BYTES
        ),
        "write_operations_reserved": 0,
        "write_bytes_reserved": 0,
        "write_charges": [],
        "write_charge_manifest_sha256": batch.canonical_sha256([]),
        "completed_write_uris": completed,
        "completed_write_uri_manifest_sha256": batch.canonical_sha256(completed),
        "pending_write_uris": [root_uri],
        "pending_write_uri_manifest_sha256": batch.canonical_sha256([root_uri]),
        "all_backend_writes_charged_before_call": True,
        "failed_attempts_remain_charged": True,
        "unexpected_uri_backend_call_possible": False,
        "per_invocation_only": True,
        "cross_process_durable_ledger": False,
    }
    receipt["publication_work_receipt_sha256"] = batch.canonical_sha256(receipt)
    with pytest.raises(
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
        match="fixed law",
    ):
        batch._normalize_write_budget_receipt_v3(
            receipt, output_uri_inventory=inventory
        )


def test_terminal_budget_evidence_is_retry_history_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = capture_fixture._fixture(monkeypatch)
    plan = capture_fixture._build(fixture)
    inventory = batch._output_uri_inventory_v3(
        run_id="fixture-source-v3", plan_value=plan
    )
    terminal = str(inventory["terminal_batch_root_uri"])
    completed = sorted(set(inventory["uris"]) - {terminal})

    def read_receipt(*, with_charge: bool) -> dict[str, object]:
        charges: list[dict[str, object]] = []
        if with_charge:
            charge: dict[str, object] = {
                "ordinal": 0,
                "uri": "gs://fixture-input/exact/object.json",
                "generation": "9",
                "bytes": 17,
                "purpose": "generation-pinned-exact-read",
                "charged_before_payload_access": True,
                "failed_reads_remain_charged": True,
            }
            charge["read_charge_sha256"] = batch.canonical_sha256(charge)
            charges.append(charge)
        body: dict[str, object] = {
            "schema_version": batch.batch_mechanics.EXACT_READ_BUDGET_SCHEMA,
            "ledger_kind": "genuine-production-gcs-transport",
            "max_object_bytes": batch.batch_mechanics.MAX_EXACT_OBJECT_BYTES,
            "max_invocation_read_bytes": (
                batch.batch_mechanics.MAX_EXACT_READ_INVOCATION_BYTES
            ),
            "max_read_operations": (
                batch.batch_mechanics.MAX_EXACT_READ_OPERATIONS
            ),
            "read_bytes_reserved": sum(int(row["bytes"]) for row in charges),
            "read_operations_reserved": len(charges),
            "read_charges": charges,
            "read_charge_manifest_sha256": batch.canonical_sha256(charges),
            "all_payload_reads_charged_before_access": True,
            "failed_reads_remain_charged": True,
            "per_invocation_only": True,
            "cross_process_durable_ledger": False,
        }
        body["exact_read_budget_sha256"] = batch.canonical_sha256(body)
        return body

    def write_receipt(*, one_retry: bool) -> dict[str, object]:
        charges: list[dict[str, object]] = []
        for uri in completed:
            attempts = (1, 2) if one_retry and uri == completed[0] else (1,)
            for attempt in attempts:
                charge: dict[str, object] = {
                    "ordinal": len(charges),
                    "uri": uri,
                    "attempt": attempt,
                    "bytes": 1,
                    "charged_before_backend_call": True,
                    "failed_attempts_remain_charged": True,
                }
                charge["write_charge_sha256"] = batch.canonical_sha256(charge)
                charges.append(charge)
        body: dict[str, object] = {
            "schema_version": batch.batch_mechanics.CREATE_ONCE_BUDGET_SCHEMA,
            "expected_write_uris": inventory["uris"],
            "expected_write_uri_manifest_sha256": inventory[
                "uri_manifest_sha256"
            ],
            "expected_write_uri_count": inventory["uri_count"],
            "max_write_operations": (
                int(inventory["uri_count"])
                * batch.batch_mechanics.CREATE_ONCE_ATTEMPTS
            ),
            "max_invocation_write_bytes": (
                batch.batch_mechanics.MAX_CREATE_ONCE_INVOCATION_BYTES
            ),
            "write_operations_reserved": len(charges),
            "write_bytes_reserved": len(charges),
            "write_charges": charges,
            "write_charge_manifest_sha256": batch.canonical_sha256(charges),
            "completed_write_uris": completed,
            "completed_write_uri_manifest_sha256": batch.canonical_sha256(
                completed
            ),
            "pending_write_uris": [terminal],
            "pending_write_uri_manifest_sha256": batch.canonical_sha256(
                [terminal]
            ),
            "all_backend_writes_charged_before_call": True,
            "failed_attempts_remain_charged": True,
            "unexpected_uri_backend_call_possible": False,
            "per_invocation_only": True,
            "cross_process_durable_ledger": False,
        }
        body["publication_work_receipt_sha256"] = batch.canonical_sha256(body)
        return body

    first = batch._preterminal_root_evidence_v3(
        output_uri_inventory=inventory,
        read_budget_receipt=read_receipt(with_charge=False),
        write_budget_receipt=write_receipt(one_retry=False),
    )
    resumed = batch._preterminal_root_evidence_v3(
        output_uri_inventory=inventory,
        read_budget_receipt=read_receipt(with_charge=True),
        write_budget_receipt=write_receipt(one_retry=True),
    )

    assert resumed == first
    assert "preterminal_read_budget_receipt" not in first
    assert "preterminal_write_budget_receipt" not in first
    assert first["preterminal_completion"]["pending_write_uri"] == terminal


def test_policy_is_strictly_outcome_and_score_free() -> None:
    policy = batch._policy()
    assert policy["outcome_columns_read"] == []
    assert policy["score_columns_read"] == []
    assert policy["uses_realized_outcomes"] is False
    assert policy["scores_read"] is False
    assert policy["world_matrix_bodies_read"] is False
    assert policy["world_schedule_bodies_read"] is True
    assert policy["accepted_arm_result_object_bodies_read"] is True
    assert policy["accepted_task_result_and_carrier_bodies_reopened"] is True
    assert policy["promotion_eligible"] is False
    assert all(policy[field] is False for field in source.FALSE_AUTHORITY_FIELDS)


def test_task0_readiness_constructs_zero_write_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closure = _closure()
    runtime = _runtime(closure)
    candidate_identity = {
        "uri": "gs://candidate-bucket/fixed/candidate-v2-root.json",
        "generation": "1",
        "sha256": "c" * 64,
        "bytes": 1,
    }
    plan = {"fixed_g0_candidate_authority_root_identity": candidate_identity}
    binding = {
        "commit_sha": closure["source_commit_sha"],
        "relative_path": "reports/fixture-capture-plan-v3.json",
        "sha256": "d" * 64,
        "bytes": 1,
        "capture_plan_sha256": "e" * 64,
    }
    constructed: list[tuple[str, ...]] = []

    class FakeTransport:
        def read_exact(self, _identity: Mapping[str, object]) -> bytes:
            raise AssertionError("fixture should not perform a backing read")

        def read_budget_receipt(self) -> dict[str, object]:
            return {"fixture": "read-budget", "write_uri_count": 0}

    class FakeCache:
        def __init__(self, reader: object) -> None:
            self.read = reader

        def budget_receipt(self) -> dict[str, object]:
            return {"fixture": "cache-budget"}

    def transport_factory(
        *, expected_write_uris: Sequence[str]
    ) -> FakeTransport:
        constructed.append(tuple(expected_write_uris))
        return FakeTransport()

    monkeypatch.setattr(
        batch,
        "_validate_local_context_v3",
        lambda: (closure, runtime, plan, binding, b"{}\n"),
    )
    monkeypatch.setattr(
        batch.batch_mechanics,
        "_trusted_gcs_transport_v1",
        transport_factory,
    )
    monkeypatch.setattr(batch.batch_mechanics, "ExactReadCacheV1", FakeCache)
    monkeypatch.setattr(
        batch,
        "_trusted_remote_prerequisites_v3",
        lambda **_kwargs: {"fixture": "prerequisites"},
    )
    monkeypatch.setattr(
        batch, "_deep_validate_capture_plan_v3", lambda **_kwargs: plan
    )
    monkeypatch.setattr(
        batch.candidate_v2,
        "reopen_fixed_g0_candidate_authority_release_v2",
        lambda *_args, **_kwargs: SimpleNamespace(
            root_identity=candidate_identity,
            candidate_release={
                "entries": [{
                    "task_id": "task-00",
                    "slate": {"slate_id": "2023-w01"},
                    "candidate_count": 214,
                }]
            },
        ),
    )

    receipt = batch.validate_matchup_source_batch_task0_readiness_v3()

    assert constructed == [()]
    assert receipt["prerequisite_target_source_task_ordinals"] == [0]
    assert receipt["smoke_scope"] == (
        "candidate-v2-capture-v3-prerequisites-only"
    )
    assert receipt["component_source_worker_executed"] is False
    assert receipt["source_triple_worker_executed"] is False
    assert receipt["source_release_v3_published"] is False
    assert receipt["terminal_batch_v3_published"] is False
    assert receipt["distinct_process_verifier_executed"] is False
    assert receipt["real_source_worker_and_distinct_verifier_required"] is True
    assert receipt["write_capability_enabled"] is False
    assert receipt["cloud_mutation_performed"] is False


def test_one_deep_boundary_can_exact_validate_all_54_source_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_identity = {
        "uri": "gs://fixture/candidate-release.json",
        "generation": "1",
        "sha256": "a" * 64,
        "bytes": 1,
    }
    producer_identity = {
        "uri": "gs://fixture/producer-release.json",
        "generation": "2",
        "sha256": "b" * 64,
        "bytes": 1,
    }
    candidate_entries: list[dict[str, object]] = []
    members: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        slate = {"slate_id": f"fixture-{ordinal:02d}"}
        artifact = {
            "source_task_ordinal": ordinal,
            "candidate_artifact_sha256": _digest(f"artifact-{ordinal}"),
        }
        artifact_identity = {
            "uri": f"gs://fixture/artifact-{ordinal:02d}.json",
            "generation": str(ordinal + 10),
            "sha256": _digest(f"artifact-raw-{ordinal}"),
            "bytes": 1,
        }
        common = {
            "source_task_ordinal": ordinal,
            "task_id": f"task-{ordinal:02d}",
            "slate": slate,
            "catalog_identity": {
                "uri": f"gs://fixture/catalog-{ordinal:02d}.json",
                "generation": str(ordinal + 100),
                "sha256": _digest(f"catalog-{ordinal}"),
                "bytes": 1,
            },
            "candidate_artifact_identity": artifact_identity,
            "candidate_artifact_sha256": artifact[
                "candidate_artifact_sha256"
            ],
            "candidate_count": 200 + ordinal,
            "ordered_candidate_ids_sha256": _digest(f"order-{ordinal}"),
        }
        candidate_entries.append({
            **common,
            "candidate_artifact": artifact,
        })
        members.append({
            **common,
            "source_export_identity": artifact_identity,
            "capture_receipt_identity": artifact_identity,
            "operator_result_identity": artifact_identity,
            "matchup_source_member_candidate_authority_sha256": _digest(
                f"member-{ordinal}"
            ),
        })
        artifacts.append(artifact)
    candidate_release = {
        "accepted_candidate_release_sha256": "c" * 64,
        "entries": candidate_entries,
    }
    terminal = {
        "accepted_candidate_release_identity": candidate_identity,
        "accepted_candidate_release_sha256": "c" * 64,
        "producer_release_identity": producer_identity,
        "entries": members,
    }
    monkeypatch.setattr(
        batch.release_v3,
        "validate_matchup_source_release_outer_candidate_authority_v3",
        lambda value: value,
    )
    monkeypatch.setattr(
        batch,
        "_parse_exact_json",
        lambda identity, **_kwargs: (
            (candidate_release, candidate_identity)
            if identity == candidate_identity
            else ({"producer": True}, producer_identity)
        ),
    )
    monkeypatch.setattr(
        batch.source,
        "validate_accepted_candidate_release_v1",
        lambda value: value,
    )
    monkeypatch.setattr(
        batch.release_v1,
        "_producer_release_shape",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        batch.release_v3, "_project_release_v1", lambda _value: {}
    )
    reopened_ordinals: list[int] = []

    def reopen_member(*, ordinal: int, **_kwargs: object) -> dict[str, object]:
        reopened_ordinals.append(ordinal)
        return {"candidate_artifact": artifacts[ordinal]}

    monkeypatch.setattr(
        batch.release_v1,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        reopen_member,
    )

    receipt = batch._exact_validate_all_source_members_v3(
        source_release=terminal,
        read_exact=lambda _identity: b"",
    )

    assert reopened_ordinals == list(range(source.TASK_COUNT))
    assert receipt["source_task_count"] == source.TASK_COUNT
    assert receipt["all_54_base_source_members_generation_exact_reopened"] is True


def test_publish_control_path_requests_terminal_batch_root_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "fixture-source-v3"
    prefix = batch.output_prefix_for_run_v3(run_id)
    component_uri = f"{prefix}00-component.json"
    triple_uri = f"{prefix}01-triple.json"
    source_uri = f"{prefix}{release_v3.ROOT_FILENAME}"
    root_uri = f"{prefix}{batch.ROOT_FILENAME}"
    uris = sorted((component_uri, triple_uri, source_uri, root_uri))
    inventory = {
        "run_id": run_id,
        "namespace": prefix,
        "uris": uris,
        "source_release_root_uri": source_uri,
        "terminal_batch_root_uri": root_uri,
    }
    closure = _closure()
    runtime = _runtime(closure)
    candidate_identity = {
        "uri": "gs://candidate-bucket/fixed/candidate-v2-root.json",
        "generation": "1",
        "sha256": "c" * 64,
        "bytes": 1,
    }
    plan = {"fixed_g0_candidate_authority_root_identity": candidate_identity}
    binding = {
        "commit_sha": closure["source_commit_sha"],
        "relative_path": "reports/fixture-capture-plan-v3.json",
        "sha256": "d" * 64,
        "bytes": 1,
        "capture_plan_sha256": "e" * 64,
    }
    writes: list[str] = []
    stored: dict[str, bytes] = {}

    class FakeTransport:
        def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
            assert uri in uris
            assert uri not in stored
            stored[uri] = raw
            writes.append(uri)
            return {
                "uri": uri,
                "generation": str(len(writes)),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }

        def read_exact(self, identity: Mapping[str, object]) -> bytes:
            return stored[str(identity["uri"])]

        def require_completed_exactly_v1(
            self, *, completed_uris: Sequence[str], pending_uris: Sequence[str]
        ) -> None:
            assert sorted(writes) == sorted(completed_uris)
            assert sorted(set(uris) - set(writes)) == sorted(pending_uris)

        def read_budget_receipt(self) -> dict[str, object]:
            return {"fixture": "read-budget"}

        def write_budget_receipt(self) -> dict[str, object]:
            return {"fixture": "write-budget"}

    class FakeCache:
        def __init__(self, reader: object) -> None:
            self.read = reader

        def budget_receipt(self) -> dict[str, object]:
            return {"fixture": "cache-budget"}

    transport = FakeTransport()
    monkeypatch.setenv(batch.PUBLISH_ENABLE_ENV, "1")
    monkeypatch.setattr(
        batch,
        "_validate_local_context_v3",
        lambda: (closure, runtime, plan, binding, b"{}\n"),
    )
    monkeypatch.setattr(batch, "_output_uri_inventory_v3", lambda **_kwargs: inventory)
    monkeypatch.setattr(
        batch.batch_mechanics,
        "_trusted_gcs_transport_v1",
        lambda **_kwargs: transport,
    )
    monkeypatch.setattr(batch.batch_mechanics, "ExactReadCacheV1", FakeCache)
    prerequisites = {
        "upstream_source_release": {},
        "upstream_source_release_identity": {},
        "upstream_pack_row_objects": [],
    }
    monkeypatch.setattr(
        batch,
        "_trusted_remote_prerequisites_v3",
        lambda **_kwargs: prerequisites,
    )
    monkeypatch.setattr(batch, "_deep_validate_capture_plan_v3", lambda **_kwargs: plan)

    component_result = {
        "publication_receipt": {"fixture": "component-v3"},
        "component_publication_result": {"offline_panel": {}},
    }

    def publish_component(**kwargs: object) -> dict[str, object]:
        kwargs["publish_create_once"](
            component_uri, batch.canonical_json_bytes({"component": 3})
        )
        return component_result

    monkeypatch.setattr(
        batch.component_v3,
        "publish_all_54_component_release_outer_candidate_authority_v3",
        publish_component,
    )
    monkeypatch.setattr(
        batch.component_v3,
        "validate_component_publication_against_outer_candidate_authority_v3",
        lambda value, **_kwargs: value,
    )

    def publish_triples(**kwargs: object) -> list[dict[str, object]]:
        kwargs["publish_create_once"](
            triple_uri, batch.canonical_json_bytes({"triple": 3})
        )
        triple = {
            "source_export": {},
            "source_export_identity": {},
            "capture_receipt": {},
            "capture_receipt_identity": {},
            "operator_result": {},
            "operator_result_identity": {},
        }
        return [deepcopy(triple) for _ in range(source.TASK_COUNT)]

    monkeypatch.setattr(batch, "_publish_source_triples_v3", publish_triples)
    monkeypatch.setattr(batch, "_operator_code_identity", lambda _value: {})
    monkeypatch.setattr(batch, "_trusted_dependency_closure_v3", lambda: closure)
    monkeypatch.setattr(batch, "_build_runtime_binding_v3", lambda _value: runtime)
    source_body = {
        "fixture": "source-v3",
        "entries": [{"fixture": "source-v3-member-0"}],
    }

    def publish_source(**kwargs: object) -> dict[str, object]:
        identity = kwargs["publish_create_once"](
            source_uri, batch.canonical_json_bytes(source_body)
        )
        return {"release": source_body, "release_identity": identity}

    monkeypatch.setattr(
        batch.release_v3,
        "publish_matchup_source_release_outer_candidate_authority_root_last_v3",
        publish_source,
    )
    monkeypatch.setattr(
        batch.release_v3,
        "validate_matchup_source_release_outer_candidate_authority_v3",
        lambda value: value,
    )
    deep_ordinals: list[int] = []

    def deep_reopen(**kwargs: object) -> dict[str, object]:
        deep_ordinals.append(int(kwargs["source_task_ordinal"]))
        return {"release": source_body, "member": source_body["entries"][0]}

    monkeypatch.setattr(
        batch.release_v3,
        "reopen_matchup_source_release_outer_candidate_authority_ordinal_v3",
        deep_reopen,
    )
    monkeypatch.setattr(
        batch,
        "_exact_validate_all_source_members_v3",
        lambda **_kwargs: {"source_task_count": source.TASK_COUNT},
    )
    monkeypatch.setattr(
        batch,
        "_build_batch_root_v3",
        lambda **_kwargs: {"schema_version": "fixture-batch-root", "complete": True},
    )
    monkeypatch.setattr(
        batch,
        "_deep_reopen_batch_v3",
        lambda **_kwargs: {
            "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete": True
        },
    )

    receipt = batch.publish_matchup_source_batch_outer_candidate_authority_v3(
        run_id=run_id
    )
    assert receipt["complete"] is True
    assert receipt["same_process_deep_reopen_complete"] is True
    assert receipt["independent_process_deep_reopen_complete"] is False
    assert receipt["independent_process_deep_reopen_required"] is True
    assert receipt["publisher_process_reused_exact_read_cache"] is True
    assert writes == [component_uri, triple_uri, source_uri, root_uri]
    assert writes[-1] == root_uri
    assert deep_ordinals == [0]
