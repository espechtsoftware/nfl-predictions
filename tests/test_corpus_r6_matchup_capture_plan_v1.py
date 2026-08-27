from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from nfl_dfs.research import corpus_r6_matchup_capture_plan_v1 as capture
from nfl_dfs.research import (
    corpus_r6_matchup_component_producer_v1 as producer,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_adapter_v1 as fixed_g0,
)
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


CANDIDATE_NAMESPACE = "gs://fixture-candidate/r6-candidates-v1/"
UPSTREAM_NAMESPACE = "gs://fixture-upstream/r6-upstream-v1/"
PRODUCER_NAMESPACE = "gs://fixture-producer/r6-producer-v1/"


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity_for_raw(
    raw: bytes, *, uri: str, generation_label: str,
) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(int(_digest(generation_label)[:15], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_for_body(
    body: object, *, uri: str, generation_label: str,
) -> dict[str, object]:
    return _identity_for_raw(
        source.canonical_json_bytes(body),
        uri=uri,
        generation_label=generation_label,
    )


def _opaque_identity(label: str) -> dict[str, object]:
    return _identity_for_body(
        {"fixture": label},
        uri=f"gs://fixture-opaque/objects/{label}.json",
        generation_label=label,
    )


def _code(label: str, *, path: str) -> dict[str, str]:
    return {
        "source_commit_sha": _digest(f"commit:{label}")[:40],
        "module_path": path,
        "module_sha256": _digest(f"module:{label}"),
    }


def _policy(*, catalog: bool = False) -> dict[str, object]:
    fields = (
        catalog_v1.FALSE_AUTHORITY_FIELDS
        if catalog else source.FALSE_AUTHORITY_FIELDS
    )
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in fields},
    }


def _rehash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = deepcopy(dict(value))
    result.pop(field, None)
    result[field] = source.canonical_sha256(result)
    return result


def _tracked_root() -> dict[str, object]:
    fixed = capture.fixed_g0_authority_binding_v1()
    return {
        "g0_authority_lock_schema": catalog_v1.G0_AUTHORITY_LOCK_SCHEMA,
        "g0_authority_lock_relative_path": fixed["g0_lock_relative_path"],
        "g0_authority_lock_file_sha256": fixed["g0_lock_file_sha256"],
        "g0_authority_lock_sha256": fixed["g0_lock_internal_sha256"],
        "source_commit_sha": fixed["evidence_source_commit_sha"],
        "panel_object_identity": fixed["panel_identity"],
        "panel_index_sha256": fixed["panel_index_sha256"],
        "accepted_slate_count": source.TASK_COUNT,
    }


def _catalog_release() -> dict[str, Any]:
    namespace = fixed_g0.FIXED_CATALOG_NAMESPACE
    entries: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        slate = catalog_v1.expected_slate_for_source_task(ordinal)
        lane = catalog_v1.expected_lane_for_source_task(ordinal)
        catalog_identity = _identity_for_body(
            {"fixture_catalog": ordinal},
            uri=(
                f"{namespace}tasks/{ordinal:04d}-{slate['slate_id']}/"
                "player-catalog.json"
            ),
            generation_label=f"catalog:{ordinal}",
        )
        entries.append({
            "source_task_ordinal": ordinal,
            "task_id": catalog_v1.task_id_for_source_task(ordinal),
            "slate": slate,
            "lane_id": lane["lane_id"],
            "lane_ordinal": lane["lane_ordinal"],
            "task_ordinal": lane["task_ordinal"],
            "accepted_slate_membership_sha256": _digest(
                f"membership:{ordinal}"
            ),
            "source_task_authority_sha256": _digest(
                f"source-task:{ordinal}"
            ),
            "catalog_identity": catalog_identity,
            "derivation_receipt_identity": _identity_for_body(
                {"fixture": f"derivation:{ordinal}"},
                uri=(
                    f"{namespace}tasks/{ordinal:04d}-{slate['slate_id']}/"
                    "catalog-derivation-receipt.json"
                ),
                generation_label=f"derivation:{ordinal}",
            ),
            "source_catalog_sha256": _digest(f"catalog-body:{ordinal}"),
            "player_count": 500 + ordinal,
            "ordered_player_ids_sha256": _digest(
                f"catalog-ids:{ordinal}"
            ),
        })
    body: dict[str, object] = {
        "schema_version": catalog_v1.RELEASE_SCHEMA,
        "release_id": fixed_g0.FIXED_RELEASE_ID,
        "publication_mode": "create_once",
        "universe_scope": catalog_v1.UNIVERSE_SCOPE,
        "authority_boundary": catalog_v1.AUTHORITY_BOUNDARY,
        "catalog_namespace": namespace,
        "tracked_root_binding": _tracked_root(),
        "later_source_freeze_identity": dict(
            fixed_g0.FIXED_LATER_SOURCE_IDENTITY
        ),
        "later_source_freeze_manifest_sha256": _digest(
            "later-source-internal"
        ),
        "artifact_source_authority_completion_identity": dict(
            fixed_g0.FIXED_SOURCE_COMPLETION_IDENTITY
        ),
        "artifact_source_authority_completion_sha256": _digest(
            "source-completion-internal"
        ),
        "derivation_code_identity": _code(
            "catalog-derivation",
            path=fixed_g0.FIXED_CATALOG_MODULE_PATH,
        ),
        "task_count": source.TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": source.canonical_sha256(entries),
        **_policy(catalog=True),
    }
    release = _rehash(body, "release_sha256")
    identity = _identity_for_body(
        release,
        uri=f"{namespace}catalog-release.json",
        generation_label="catalog-release",
    )
    return {"body": release, "identity": identity}


def _fixed_g0_replay(catalog_release: Mapping[str, object]) -> dict[str, Any]:
    release = catalog_release["body"]
    fixed = capture.fixed_g0_authority_binding_v1()
    body: dict[str, object] = {
        "schema_version": producer.FIXED_G0_REPLAY_SCHEMA,
        "replay_id": "fixed-g0-r6-player-catalog-projection-v1",
        "replay_scope": (
            "accepted-panel-index-projection-rooted-in-frozen-g0-evidence"
        ),
        "pin_set_sha256": _digest("fixed-g0-pin-set"),
        "tracked_root_binding": release["tracked_root_binding"],
        "official_publication_receipt_file": {
            "relative_path": "reports/fixed-g0-publication.json",
            "sha256": _digest("fixed-g0-publication-file"),
            "bytes": 100,
        },
        "official_publication_receipt_sha256": _digest(
            "fixed-g0-publication"
        ),
        "adapter_review_binding": {
            "relative_path": "reports/fixed-g0-adapter-review.json",
            "sha256": _digest("fixed-g0-adapter-review"),
            "bytes": 100,
        },
        "lane_terminal_identities": fixed["lane_terminal_identities"],
        "lane_completion_identities": fixed["lane_completion_identities"],
        "later_source_freeze_identity": release[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_manifest_sha256": release[
            "later_source_freeze_manifest_sha256"
        ],
        "artifact_source_authority_completion_identity": release[
            "artifact_source_authority_completion_identity"
        ],
        "artifact_source_authority_completion_sha256": release[
            "artifact_source_authority_completion_sha256"
        ],
        "derivation_code_identity": release["derivation_code_identity"],
        "catalog_namespace": release["catalog_namespace"],
        "catalog_release_identity": catalog_release["identity"],
        "catalog_release_sha256": release["release_sha256"],
        "task_count": source.TASK_COUNT,
        "task_acceptance_body_count": source.TASK_COUNT,
        "task_acceptance_body_manifest_sha256": _digest("task-acceptances"),
        "carrier_body_count": source.TASK_COUNT,
        "carrier_body_manifest_sha256": _digest("carriers"),
        "member_binding_manifest_sha256": _digest("members"),
        "source_catalog_binding_manifest_sha256": _digest(
            "source-catalog-bindings"
        ),
        "completion_binding_manifest_sha256": _digest(
            "completion-bindings"
        ),
        "structural_catalog_manifest_sha256": _digest(
            "structural-catalogs"
        ),
        "catalog_identity_manifest_sha256": source.canonical_sha256([
            entry["catalog_identity"] for entry in release["entries"]
        ]),
        "accepted_panel_index_projection_only": True,
        "fresh_task_or_arm_body_revalidation_performed": True,
        "task_acceptance_bodies_reopened": True,
        "carrier_bodies_reopened": True,
        "source_completion_artifact_bodies_reopened": False,
        "world_matrix_bodies_reopened": False,
        "result_object_bodies_reopened": False,
        "execution_manifest_pin_required": True,
        "self_authorizing": False,
        **_policy(catalog=True),
        "analytical_authority": False,
        "automatic_retry_licensed": False,
    }
    receipt = _rehash(body, "replay_receipt_sha256")
    identity = _identity_for_body(
        receipt,
        uri=(
            f"{release['catalog_namespace']}"
            f"{fixed_g0.REPLAY_RECEIPT_FILENAME}"
        ),
        generation_label="replay-receipt",
    )
    return {"body": receipt, "identity": identity}


def _candidate_release(
    catalog_release: Mapping[str, object], *, duplicate_rosters: bool = False,
) -> dict[str, Any]:
    release = catalog_release["body"]
    entries: list[dict[str, object]] = []
    for ordinal, catalog_entry in enumerate(release["entries"]):
        rows = []
        for candidate in range(source.ENTRY_BUDGET):
            roster_ordinal = 0 if duplicate_rosters else candidate
            rows.append({
                "candidate_id": f"candidate-{ordinal:02d}-{candidate:03d}",
                "player_ids": [
                    f"p-{ordinal:02d}-{roster_ordinal:03d}-{slot}"
                    for slot in range(9)
                ],
            })
        artifact = source.build_accepted_candidate_artifact_v1(
            source_task_ordinal=ordinal, rows=rows
        )
        slate = artifact["slate"]
        artifact_identity = _identity_for_body(
            artifact,
            uri=(
                f"{CANDIDATE_NAMESPACE}source-task-{ordinal:02d}-"
                f"{slate['slate_id']}/accepted-candidates.json"
            ),
            generation_label=f"candidate-artifact:{ordinal}",
        )
        entry_body = {
            "source_task_ordinal": ordinal,
            "task_id": artifact["task_id"],
            "slate": slate,
            "catalog_identity": catalog_entry["catalog_identity"],
            "candidate_artifact": artifact,
            "candidate_artifact_identity": artifact_identity,
            "candidate_count": artifact["candidate_count"],
            "ordered_candidate_ids_sha256": artifact[
                "ordered_candidate_ids_sha256"
            ],
        }
        entries.append({
            **entry_body,
            "accepted_candidate_release_entry_sha256": (
                source.canonical_sha256(entry_body)
            ),
        })
    candidate_release = source.build_accepted_candidate_release_v1(
        release_id="accepted-v12-candidates-fixed-g0-v1",
        namespace=CANDIDATE_NAMESPACE,
        source_candidate_panel_identity=fixed_g0.FIXED_PANEL_IDENTITY,
        entries=entries,
    )
    identity = _identity_for_body(
        candidate_release,
        uri=f"{CANDIDATE_NAMESPACE}accepted-candidate-release.json",
        generation_label="candidate-release",
    )
    return {"body": candidate_release, "identity": identity}


def _positive_row(
    *, pack_id: str, slice_kind: str, fields: list[str],
) -> dict[str, object]:
    row: dict[str, object] = {}
    for field in fields:
        if field == "season":
            row[field] = 2022
        elif field == "week":
            row[field] = 1
        else:
            row[field] = f"{pack_id}:{slice_kind}:{field}"
    return row


def _upstream_release(
    replay_receipt_identity: Mapping[str, object],
) -> dict[str, Any]:
    registry = source.frozen_upstream_pack_registry_v1()
    packs: list[dict[str, object]] = []
    row_objects: list[dict[str, object]] = []
    for ordinal, registry_value in enumerate(registry["packs"]):
        registry_entry = dict(registry_value)
        slices = []
        for schema_value in registry_entry["positive_row_schemas"]:
            schema = dict(schema_value)
            slices.append({
                "slice_kind": schema["slice_kind"],
                "rows": [_positive_row(
                    pack_id=str(registry_entry["pack_id"]),
                    slice_kind=str(schema["slice_kind"]),
                    fields=list(schema["row_fields"]),
                )],
            })
        rows = source.build_upstream_pack_rows_v1(
            pack_id=str(registry_entry["pack_id"]), slices=slices
        )
        row_objects.append(rows)
        rows_identity = _identity_for_body(
            rows,
            uri=(
                f"{UPSTREAM_NAMESPACE}packs/{registry_entry['pack_id']}/"
                "rows.json"
            ),
            generation_label=f"pack-rows:{ordinal}",
        )
        warehouse = (
            _opaque_identity(f"query-receipt:{ordinal}")
            if registry_entry["provenance_kind"]
            == "warehouse-query-receipt"
            else None
        )
        artifacts = (
            [] if warehouse is not None
            else [_opaque_identity(f"artifact-manifest:{ordinal}")]
        )
        packs.append({
            "pack_id": registry_entry["pack_id"],
            "source_kind": registry_entry["source_kind"],
            "provenance_kind": registry_entry["provenance_kind"],
            "positive_row_schemas": registry_entry[
                "positive_row_schemas"
            ],
            "positive_row_schema_manifest_sha256": registry_entry[
                "positive_row_schema_manifest_sha256"
            ],
            "exact_rows_identity": rows_identity,
            "row_count": rows["row_count"],
            "rows_sha256": rows["rows_sha256"],
            "source_period_min": registry_entry["source_period_min"],
            "source_period_max": registry_entry["source_period_max"],
            "warehouse_query_receipt_identity": warehouse,
            "frozen_artifact_manifest_identities": artifacts,
            "projection_code_identity": _code(
                f"pack:{ordinal}",
                path=f"src/nfl_dfs/research/pack_{ordinal}.py",
            ),
        })
    upstream = source.build_upstream_release_v1(
        release_id="r6-seven-pack-source-v1",
        namespace=UPSTREAM_NAMESPACE,
        fixed_source_root_identity=replay_receipt_identity,
        packs=packs,
        pack_row_objects=row_objects,
    )
    identity = _identity_for_body(
        upstream,
        uri=f"{UPSTREAM_NAMESPACE}upstream-release.json",
        generation_label="upstream-release",
    )
    return {"body": upstream, "identity": identity, "rows": row_objects}


def _file_binding(path: str, label: str) -> dict[str, object]:
    raw = f"fixture:{label}".encode("utf-8")
    return {
        "relative_path": path,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _final_lock_raw() -> bytes:
    measurements = [
        _file_binding(path, f"adapter-implementation:{ordinal}")
        for ordinal, path in enumerate(fixed_g0.FIXED_ADAPTER_IMPLEMENTATION_PATHS)
    ]
    body: dict[str, object] = {
        "schema_version": fixed_g0.FINAL_RELEASE_LOCK_SCHEMA,
        "evidence_source_commit_sha": fixed_g0.FIXED_SOURCE_COMMIT_SHA,
        "implementation_commit_sha": _digest("adapter-implementation")[:40],
        "implementation_measurements": measurements,
        "preliminary_review_lock_commit_sha": _digest(
            "preliminary-review"
        )[:40],
        "preliminary_review_lock_file": _file_binding(
            fixed_g0.FIXED_ADAPTER_REVIEW_LOCK_PATH, "preliminary-review"
        ),
        "preliminary_review_lock_internal_sha256": _digest(
            "preliminary-review-internal"
        ),
        "task0_smoke_receipt_file": _file_binding(
            fixed_g0.FIXED_TASK0_SMOKE_RECEIPT_PATH, "smoke-receipt"
        ),
        "task0_smoke_receipt_internal_sha256": _digest(
            "smoke-receipt-internal"
        ),
        "task0_smoke_attempt_file": _file_binding(
            fixed_g0.FIXED_TASK0_SMOKE_ATTEMPT_PATH, "smoke-attempt"
        ),
        "task0_smoke_attempt_internal_sha256": _digest(
            "smoke-attempt-internal"
        ),
        "task0_smoke_command": list(fixed_g0.FIXED_TASK0_SMOKE_COMMAND),
        "task0_smoke_invocation_count": 1,
        "task0_smoke_passed": True,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "current_clean_git_required": True,
        "required_source_task_count": source.TASK_COUNT,
        "required_task_acceptance_body_reopen_count": source.TASK_COUNT,
        "required_carrier_body_reopen_count": source.TASK_COUNT,
        "projection_only_publication_reviewed": True,
        "projection_only_publication_licensed": True,
        "projection_release_command": list(
            fixed_g0.FIXED_PROJECTION_RELEASE_COMMAND
        ),
        "production_enable_environment_variable": fixed_g0.PRODUCTION_ENABLE_ENV,
        "production_enable_environment_value": "1",
        "gcs_create_once_required": True,
        "gcs_overwrite_licensed": False,
        "world_matrix_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in catalog_v1.FALSE_AUTHORITY_FIELDS},
    }
    body["final_release_lock_sha256"] = source.canonical_sha256(body)
    return source.canonical_json_bytes(body) + b"\n"


def _implementation_fixture() -> dict[str, Any]:
    commit = _digest("source-v2-implementation")[:40]
    raw_by_path = {
        capture.SOURCE_V2_MODULE_PATH: b"source-v2-fixture-bytes\n",
        capture.COMPONENT_PRODUCER_MODULE_PATH: b"producer-fixture-bytes\n",
    }
    measurements = [
        {
            "relative_path": path,
            "sha256": sha256(raw_by_path[path]).hexdigest(),
            "bytes": len(raw_by_path[path]),
        }
        for path in capture.IMPLEMENTATION_PATHS
    ]
    return {"commit": commit, "raw_by_path": raw_by_path, "rows": measurements}


def _fixture(*, duplicate_rosters: bool = False) -> dict[str, Any]:
    catalogs = _catalog_release()
    replay = _fixed_g0_replay(catalogs)
    candidates = _candidate_release(
        catalogs, duplicate_rosters=duplicate_rosters
    )
    upstream = _upstream_release(replay["identity"])
    implementation = _implementation_fixture()
    return {
        "catalogs": catalogs,
        "replay": replay,
        "candidates": candidates,
        "upstream": upstream,
        "implementation": implementation,
        "final_lock_commit": _digest("adapter-final-lock-commit")[:40],
        "final_lock_raw": _final_lock_raw(),
    }


def _build(fixture: Mapping[str, Any]) -> dict[str, object]:
    return capture.build_capture_plan_lock_v1(
        adapter_final_release_lock_commit_sha=fixture["final_lock_commit"],
        adapter_final_release_lock_raw=fixture["final_lock_raw"],
        fixed_g0_replay_receipt=fixture["replay"]["body"],
        fixed_g0_replay_receipt_identity=fixture["replay"]["identity"],
        catalog_release=fixture["catalogs"]["body"],
        catalog_release_identity=fixture["catalogs"]["identity"],
        accepted_candidate_release=fixture["candidates"]["body"],
        accepted_candidate_release_identity=fixture["candidates"]["identity"],
        upstream_source_release=fixture["upstream"]["body"],
        upstream_source_release_identity=fixture["upstream"]["identity"],
        upstream_pack_row_objects=fixture["upstream"]["rows"],
        implementation_commit_sha=fixture["implementation"]["commit"],
        implementation_measurements=fixture["implementation"]["rows"],
        producer_id="r6-matchup-component-producer-v1",
        producer_release_id="r6-matchup-component-panel-v1",
        producer_namespace=PRODUCER_NAMESPACE,
    )


def _rehash_plan(plan: Mapping[str, object]) -> dict[str, object]:
    return _rehash(plan, "capture_plan_sha256")


def _secure_observation(path: str, raw: bytes) -> dict[str, object]:
    return {
        "relative_path": path,
        "raw": raw,
        "is_regular_file": True,
        "is_symlink": False,
        "opened_nofollow": True,
    }


def test_capture_plan_binds_fixed_g0_seven_packs_and_all_54() -> None:
    fixture = _fixture()
    plan = _build(fixture)

    assert plan["fixed_g0_authority_binding"] == (
        capture.fixed_g0_authority_binding_v1()
    )
    assert plan["upstream_pack_count"] == 7
    assert [row["pack_id"] for row in plan["upstream_pack_bindings"]] == list(
        source.PACK_IDS
    )
    assert plan["source_task_count"] == 54
    assert [
        row["source_task_ordinal"] for row in plan["source_task_bindings"]
    ] == list(range(54))
    assert all(
        row["candidate_count"] >= source.ENTRY_BUDGET
        for row in plan["source_task_bindings"]
    )
    assert plan["source_v2_code_identity"]["module_path"] == (
        capture.SOURCE_V2_MODULE_PATH
    )
    assert plan["component_producer_code_identity"]["module_path"] == (
        capture.COMPONENT_PRODUCER_MODULE_PATH
    )
    assert all(plan[field] is False for field in capture.FALSE_AUTHORITY_FIELDS)


def test_capture_plan_rebuilds_from_exact_prerequisite_bodies() -> None:
    fixture = _fixture()
    plan = _build(fixture)

    reopened = capture.validate_capture_plan_against_prerequisites_v1(
        plan,
        adapter_final_release_lock_commit_sha=fixture["final_lock_commit"],
        adapter_final_release_lock_raw=fixture["final_lock_raw"],
        fixed_g0_replay_receipt=fixture["replay"]["body"],
        fixed_g0_replay_receipt_identity=fixture["replay"]["identity"],
        catalog_release=fixture["catalogs"]["body"],
        catalog_release_identity=fixture["catalogs"]["identity"],
        accepted_candidate_release=fixture["candidates"]["body"],
        accepted_candidate_release_identity=fixture["candidates"]["identity"],
        upstream_source_release=fixture["upstream"]["body"],
        upstream_source_release_identity=fixture["upstream"]["identity"],
        upstream_pack_row_objects=fixture["upstream"]["rows"],
    )

    assert reopened == plan


def test_coherently_rehashed_alternate_g0_is_rejected() -> None:
    plan = _build(_fixture())
    poisoned = deepcopy(plan)
    poisoned["fixed_g0_authority_binding"]["panel_id"] = "alternate-panel"
    poisoned["fixed_g0_authority_binding_sha256"] = source.canonical_sha256(
        poisoned["fixed_g0_authority_binding"]
    )
    poisoned = _rehash_plan(poisoned)

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="accepted August-23 G0",
    ):
        capture.validate_capture_plan_lock_v1(poisoned)


def test_coherently_rehashed_pack_uri_substitution_is_rejected() -> None:
    plan = _build(_fixture())
    poisoned = deepcopy(plan)
    poisoned["upstream_pack_bindings"][0]["exact_rows_identity"]["uri"] = (
        "gs://alternate-bucket/rows.json"
    )
    poisoned["upstream_pack_binding_manifest_sha256"] = source.canonical_sha256(
        poisoned["upstream_pack_bindings"]
    )
    poisoned = _rehash_plan(poisoned)

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="rows URI differs",
    ):
        capture.validate_capture_plan_lock_v1(poisoned)


def test_pack_body_drift_is_rejected_against_prerequisites() -> None:
    fixture = _fixture()
    plan = _build(fixture)
    drifted_rows = deepcopy(fixture["upstream"]["rows"])
    drifted_rows[0]["slices"][0]["rows"][0]["game_id"] = "changed"

    with pytest.raises(capture.CorpusR6MatchupCapturePlanV1Error):
        capture.validate_capture_plan_against_prerequisites_v1(
            plan,
            adapter_final_release_lock_commit_sha=fixture["final_lock_commit"],
            adapter_final_release_lock_raw=fixture["final_lock_raw"],
            fixed_g0_replay_receipt=fixture["replay"]["body"],
            fixed_g0_replay_receipt_identity=fixture["replay"]["identity"],
            catalog_release=fixture["catalogs"]["body"],
            catalog_release_identity=fixture["catalogs"]["identity"],
            accepted_candidate_release=fixture["candidates"]["body"],
            accepted_candidate_release_identity=fixture["candidates"][
                "identity"
            ],
            upstream_source_release=fixture["upstream"]["body"],
            upstream_source_release_identity=fixture["upstream"]["identity"],
            upstream_pack_row_objects=drifted_rows,
        )


def test_duplicate_candidate_rosters_fail_before_plan_freeze() -> None:
    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="distinct entry-budget support",
    ):
        _build(_fixture(duplicate_rosters=True))


def test_adapter_final_lock_authority_poison_is_rejected() -> None:
    fixture = _fixture()
    raw = fixture["final_lock_raw"]
    body = deepcopy(json.loads(raw[:-1].decode("utf-8")))
    body["scoring_authority"] = True
    body = _rehash(body, "final_release_lock_sha256")
    poisoned = source.canonical_json_bytes(body) + b"\n"

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="must be false",
    ):
        capture.build_capture_plan_lock_v1(
            adapter_final_release_lock_commit_sha=fixture["final_lock_commit"],
            adapter_final_release_lock_raw=poisoned,
            fixed_g0_replay_receipt=fixture["replay"]["body"],
            fixed_g0_replay_receipt_identity=fixture["replay"]["identity"],
            catalog_release=fixture["catalogs"]["body"],
            catalog_release_identity=fixture["catalogs"]["identity"],
            accepted_candidate_release=fixture["candidates"]["body"],
            accepted_candidate_release_identity=fixture["candidates"][
                "identity"
            ],
            upstream_source_release=fixture["upstream"]["body"],
            upstream_source_release_identity=fixture["upstream"]["identity"],
            upstream_pack_row_objects=fixture["upstream"]["rows"],
            implementation_commit_sha=fixture["implementation"]["commit"],
            implementation_measurements=fixture["implementation"]["rows"],
            producer_id="r6-matchup-component-producer-v1",
            producer_release_id="r6-matchup-component-panel-v1",
            producer_namespace=PRODUCER_NAMESPACE,
        )


def test_measure_implementation_requires_git_current_byte_equality() -> None:
    fixture = _implementation_fixture()

    measured = capture.measure_implementation_files_v1(
        implementation_commit_sha=fixture["commit"],
        read_git_blob=lambda commit, path: fixture["raw_by_path"][path],
        secure_read_current=lambda path: _secure_observation(
            path, fixture["raw_by_path"][path]
        ),
        repository_clean=True,
    )
    assert measured == fixture["rows"]

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="Git/current bytes differ",
    ):
        capture.measure_implementation_files_v1(
            implementation_commit_sha=fixture["commit"],
            read_git_blob=lambda commit, path: fixture["raw_by_path"][path],
            secure_read_current=lambda path: _secure_observation(
                path, b"drifted\n"
            ),
            repository_clean=True,
        )


def test_measure_implementation_rejects_symlink_evidence() -> None:
    fixture = _implementation_fixture()

    def symlink(path: str) -> dict[str, object]:
        observed = _secure_observation(path, fixture["raw_by_path"][path])
        observed["is_regular_file"] = False
        observed["is_symlink"] = True
        observed["opened_nofollow"] = False
        return observed

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="secure current read evidence differs",
    ):
        capture.measure_implementation_files_v1(
            implementation_commit_sha=fixture["commit"],
            read_git_blob=lambda commit, path: fixture["raw_by_path"][path],
            secure_read_current=symlink,
            repository_clean=True,
        )


def test_secure_git_reopen_binds_plan_code_final_lock_and_g0() -> None:
    fixture = _fixture()
    plan = _build(fixture)
    plan_commit = _digest("capture-plan-commit")[:40]
    plan_raw = source.canonical_json_bytes(plan) + b"\n"
    repository_root = Path(__file__).resolve().parents[1]
    g0_raw = (repository_root / fixed_g0.FIXED_G0_LOCK_PATH).read_bytes()
    blobs = {
        (plan_commit, capture.CAPTURE_PLAN_LOCK_PATH): plan_raw,
        (fixture["final_lock_commit"], fixed_g0.FIXED_FINAL_RELEASE_LOCK_PATH): (
            fixture["final_lock_raw"]
        ),
        (fixed_g0.FIXED_SOURCE_COMMIT_SHA, fixed_g0.FIXED_G0_LOCK_PATH): g0_raw,
        **{
            (fixture["implementation"]["commit"], path): raw
            for path, raw in fixture["implementation"]["raw_by_path"].items()
        },
    }
    current = {
        capture.CAPTURE_PLAN_LOCK_PATH: plan_raw,
        fixed_g0.FIXED_FINAL_RELEASE_LOCK_PATH: fixture["final_lock_raw"],
        fixed_g0.FIXED_G0_LOCK_PATH: g0_raw,
        **fixture["implementation"]["raw_by_path"],
    }

    reopened = capture.reopen_capture_plan_lock_from_git_v1(
        plan_commit_sha=plan_commit,
        plan_file_sha256=sha256(plan_raw).hexdigest(),
        plan_file_bytes=len(plan_raw),
        read_git_blob=lambda commit, path: blobs[(commit, path)],
        secure_read_current=lambda path: _secure_observation(
            path, current[path]
        ),
        repository_clean=True,
    )
    assert reopened == plan


def test_secure_git_reopen_rejects_dirty_repository_before_reads() -> None:
    calls = 0

    def forbidden_blob(commit: str, path: str) -> bytes:
        nonlocal calls
        calls += 1
        raise AssertionError("read must not occur")

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="clean repository",
    ):
        capture.reopen_capture_plan_lock_from_git_v1(
            plan_commit_sha=_digest("plan")[:40],
            plan_file_sha256=_digest("plan-file"),
            plan_file_bytes=100,
            read_git_blob=forbidden_blob,
            secure_read_current=lambda path: _secure_observation(path, b"x"),
            repository_clean=False,
        )
    assert calls == 0


def test_plan_rejects_nested_realized_outcome_carrier() -> None:
    plan = _build(_fixture())
    poisoned = deepcopy(plan)
    poisoned["fixed_g0_authority_binding"]["realized_score"] = 200.0
    poisoned["fixed_g0_authority_binding_sha256"] = source.canonical_sha256(
        poisoned["fixed_g0_authority_binding"]
    )
    poisoned = _rehash_plan(poisoned)

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanV1Error,
        match="forbidden outcome field",
    ):
        capture.validate_capture_plan_lock_v1(poisoned)
