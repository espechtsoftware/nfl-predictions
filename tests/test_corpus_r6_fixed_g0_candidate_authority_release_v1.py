from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_release_v1 as release
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as core
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


RUN_ID = "20260827-fixed-g0-candidate-authority-v1"


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _rehash(body: dict[str, Any], field: str) -> None:
    body.pop(field, None)
    body[field] = release.canonical_sha256(body)


class MemoryExactStore:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}
        self._heads: dict[str, str] = {}
        self.create_calls: list[str] = []
        self.read_calls: list[str] = []
        self.fail_create_uri: str | None = None

    @staticmethod
    def _identity(uri: str, generation: str, raw: bytes) -> dict[str, object]:
        return {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def force(self, uri: str, raw: bytes) -> dict[str, object]:
        generation = str(int(self._heads.get(uri, "0")) + 1)
        self._objects[(uri, generation)] = raw
        self._heads[uri] = generation
        return self._identity(uri, generation, raw)

    def create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        self.create_calls.append(uri)
        if uri == self.fail_create_uri:
            raise RuntimeError("fixture create failure")
        if uri in self._heads:
            generation = self._heads[uri]
            retained = self._objects[(uri, generation)]
            if retained != raw:
                raise RuntimeError("create-once collision")
            return self._identity(uri, generation, retained)
        return self.force(uri, raw)

    def read_exact(self, identity: dict[str, object]) -> bytes:
        uri = str(identity["uri"])
        generation = str(identity["generation"])
        self.read_calls.append(uri)
        return self._objects[(uri, generation)]

    def latest_raw(self, uri: str) -> bytes:
        return self._objects[(uri, self._heads[uri])]


def _identity(uri: str, label: str) -> dict[str, object]:
    raw = f"fixture {label}\n".encode("utf-8")
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _candidate_artifact(ordinal: int) -> dict[str, object]:
    rows = [{
        "candidate_id": f"candidate-{ordinal:02d}-{index:03d}",
        "player_ids": [
            f"player-{ordinal:02d}-{index:03d}-{slot}"
            for slot in range(9)
        ],
    } for index in range(source.ENTRY_BUDGET)]
    return source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=ordinal,
        rows=rows,
    )


def _sidecar(
    ordinal: int, artifact: dict[str, object],
) -> dict[str, object]:
    world_schedule_identity = _identity(
        f"gs://fixture-schedules/{ordinal:02d}/world-schedule.json",
        f"world-schedule-{ordinal}",
    )
    candidates = [{
        "candidate_id": row["candidate_id"],
        "player_ids": row["player_ids"],
        "roster_sha256": row["roster_sha256"],
        "source_arm_ordinals": [0],
        "source_arms": ["baseline"],
        "origin_blocks": ["R0"],
        "occurrence_counts_by_block": {
            block: 1 if block == "R0" else 0 for block in core.rw.WORLD_BLOCKS
        },
        "source_arms_by_block": {
            block: ["baseline"] if block == "R0" else []
            for block in core.rw.WORLD_BLOCKS
        },
        "occurrence_count": 1,
        "occurrences": [{
            "arm_ordinal": 0,
            "parameter_set_id": "baseline",
            "visit_ordinal": index,
            "block_id": "R0",
            "objective_world_index": index,
        }],
    } for index, row in enumerate(artifact["rows"])]
    body: dict[str, object] = {
        "schema_version": core.LINEAGE_SIDECAR_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": artifact["task_id"],
        "slate": artifact["slate"],
        "full_union_law": core.FULL_UNION_LAW,
        "lineup_order_law": core.LINEUP_ORDER_LAW,
        "lineage_order_law": core.LINEAGE_ORDER_LAW,
        "world_schedule_identity": world_schedule_identity,
        "world_schedule_object_sha256": world_schedule_identity["sha256"],
        "world_schedule_task_row_sha256": _digest(
            f"world-schedule-row-{ordinal}"
        ),
        "visit_schedule_sha256": _digest(f"schedule-{ordinal}"),
        "visits_per_block": core.VISITS_PER_BLOCK,
        "task_source_binding_sha256": _digest(f"task-source-{ordinal}"),
        "arm_count": core.EXPECTED_ARM_COUNT,
        "visit_occurrence_count": len(candidates),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "candidate_lineage_manifest_sha256": release.canonical_sha256(candidates),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    _rehash(body, "candidate_lineage_sidecar_sha256")
    return body


def _slate_receipt(
    ordinal: int,
    artifact: dict[str, object],
    artifact_identity: dict[str, object],
    sidecar: dict[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": core.SLATE_DERIVATION_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": artifact["task_id"],
        "slate": artifact["slate"],
        "candidate_artifact_identity": artifact_identity,
        "candidate_artifact_sha256": artifact["candidate_artifact_sha256"],
        "candidate_count": artifact["candidate_count"],
        "ordered_candidate_ids_sha256": artifact[
            "ordered_candidate_ids_sha256"
        ],
        "candidate_row_manifest_sha256": artifact[
            "candidate_row_manifest_sha256"
        ],
        "lineage_sidecar_sha256": sidecar[
            "candidate_lineage_sidecar_sha256"
        ],
        "candidate_lineage_manifest_sha256": sidecar[
            "candidate_lineage_manifest_sha256"
        ],
        "world_schedule_identity": sidecar["world_schedule_identity"],
        "world_schedule_object_sha256": sidecar[
            "world_schedule_object_sha256"
        ],
        "world_schedule_task_row_sha256": sidecar[
            "world_schedule_task_row_sha256"
        ],
        "visit_schedule_sha256": sidecar["visit_schedule_sha256"],
        "visits_per_block": sidecar["visits_per_block"],
        "visit_occurrence_count": sidecar["visit_occurrence_count"],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    _rehash(body, "slate_derivation_sha256")
    return body


def _fake_bundle(
    *,
    run_id: str,
    namespace: str,
    artifacts: list[dict[str, object]],
    artifact_identities: list[dict[str, object]],
    catalog_receipt_identity: dict[str, object],
    panel_identity: dict[str, object],
) -> dict[str, object]:
    catalog_identity = _identity(
        "gs://fixture-catalog/catalog.json", "catalog"
    )
    entries = []
    sidecars = []
    receipts = []
    for ordinal, (artifact, artifact_identity) in enumerate(
        zip(artifacts, artifact_identities, strict=True)
    ):
        entry_body = {
            "source_task_ordinal": ordinal,
            "task_id": artifact["task_id"],
            "slate": artifact["slate"],
            "catalog_identity": catalog_identity,
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
                release.canonical_sha256(entry_body)
            ),
        })
        sidecar = _sidecar(ordinal, artifact)
        sidecars.append(sidecar)
        receipts.append(
            _slate_receipt(ordinal, artifact, artifact_identity, sidecar)
        )
    candidate_release = source.build_accepted_candidate_release_v1(
        release_id=run_id,
        namespace=namespace,
        source_candidate_panel_identity=panel_identity,
        entries=entries,
    )
    total_candidates = sum(int(row["candidate_count"]) for row in artifacts)
    total_visits = sum(int(row["visit_occurrence_count"]) for row in sidecars)
    panel_rows = [{
        "source_task_ordinal": ordinal,
        "task_id": artifact["task_id"],
        "slate": artifact["slate"],
        "accepted_slate_membership_sha256": _digest(f"member-{ordinal}"),
        "slate_derivation_sha256": receipts[ordinal][
            "slate_derivation_sha256"
        ],
        "candidate_artifact_identity": artifact_identities[ordinal],
        "candidate_count": artifact["candidate_count"],
        "ordered_candidate_ids_sha256": artifact[
            "ordered_candidate_ids_sha256"
        ],
        "lineage_sidecar_sha256": sidecars[ordinal][
            "candidate_lineage_sidecar_sha256"
        ],
        "world_schedule_identity": sidecars[ordinal][
            "world_schedule_identity"
        ],
        "world_schedule_task_row_sha256": sidecars[ordinal][
            "world_schedule_task_row_sha256"
        ],
        "visit_schedule_sha256": sidecars[ordinal][
            "visit_schedule_sha256"
        ],
    } for ordinal, artifact in enumerate(artifacts)]
    panel: dict[str, object] = {
        "schema_version": core.PANEL_DERIVATION_SCHEMA,
        "fixed_g0_panel_identity": panel_identity,
        "fixed_g0_panel_id": "fixture-fixed-g0-panel",
        "fixed_g0_panel_index_sha256": _digest("fixed-g0-panel-index"),
        "catalog_replay_receipt_identity": catalog_receipt_identity,
        "catalog_replay_receipt_sha256": _digest("catalog-replay-receipt"),
        "candidate_release_id": run_id,
        "candidate_namespace": namespace,
        "candidate_release_sha256": candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "candidate_release_body_sha256": release.canonical_sha256(
            candidate_release
        ),
        "task_count": source.TASK_COUNT,
        "arm_result_count": release.EXPECTED_ARM_RESULT_COUNT,
        "total_candidate_count": total_candidates,
        "total_visit_occurrence_count": total_visits,
        "slates": panel_rows,
        "slate_derivation_manifest_sha256": release.canonical_sha256(receipts),
        "candidate_artifact_identity_manifest_sha256": (
            release.canonical_sha256(artifact_identities)
        ),
        "lineage_sidecar_manifest_sha256": release.canonical_sha256(sidecars),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    _rehash(panel, "panel_derivation_sha256")
    return release._assemble_bundle(  # noqa: SLF001 - fixture predecessor shape
        candidate_release=candidate_release,
        artifacts=artifacts,
        sidecars=sidecars,
        receipts=receipts,
        panel=panel,
    )


def _install_core_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: MemoryExactStore,
) -> dict[str, Any]:
    artifacts = [_candidate_artifact(ordinal) for ordinal in range(source.TASK_COUNT)]
    catalog_uri = (
        f"{core.catalog_adapter.FIXED_CATALOG_NAMESPACE}"
        f"{core.CATALOG_REPLAY_RECEIPT_FILENAME}"
    )
    catalog_receipt_identity = store.force(
        catalog_uri, b'{"fixture":"catalog-replay"}'
    )
    panel_identity = store.force(
        "gs://fixture-fixed-g0/panel-index.json",
        b'{"fixture":"fixed-g0-panel"}',
    )
    state: dict[str, Any] = {
        "artifacts": artifacts,
        "catalog_receipt_identity": catalog_receipt_identity,
        "panel_identity": panel_identity,
        "expected_bundle": None,
        "derive_calls": 0,
        "build_calls": 0,
        "validate_calls": 0,
    }

    def derive(**_kwargs: Any) -> dict[str, object]:
        state["derive_calls"] += 1
        return {
            "schema_version": core.MATERIAL_SCHEMA,
            "task_count": source.TASK_COUNT,
            "candidate_artifacts": deepcopy(artifacts),
            "candidate_artifact_manifest_sha256": release.canonical_sha256(
                artifacts
            ),
        }

    def build(
        *,
        release_id: str,
        namespace: str,
        candidate_artifact_identities: list[dict[str, object]],
        **_kwargs: Any,
    ) -> dict[str, object]:
        state["build_calls"] += 1
        bundle = _fake_bundle(
            run_id=release_id,
            namespace=namespace,
            artifacts=deepcopy(artifacts),
            artifact_identities=deepcopy(candidate_artifact_identities),
            catalog_receipt_identity=deepcopy(catalog_receipt_identity),
            panel_identity=deepcopy(panel_identity),
        )
        state["expected_bundle"] = deepcopy(bundle)
        return bundle

    def validate(value: object, **_kwargs: Any) -> dict[str, object]:
        state["validate_calls"] += 1
        expected = state["expected_bundle"]
        if expected is None or release.canonical_json_bytes(value) != (
            release.canonical_json_bytes(expected)
        ):
            raise core.CorpusR6FixedG0CandidateAuthorityV1Error(
                "fixture predecessor replay differs"
            )
        return deepcopy(expected)

    monkeypatch.setattr(core, "derive_fixed_g0_candidate_material_v1", derive)
    monkeypatch.setattr(core, "build_fixed_g0_candidate_authority_v1", build)
    monkeypatch.setattr(core, "validate_fixed_g0_candidate_authority_v1", validate)
    return state


def _publish(
    *,
    store: MemoryExactStore,
    state: dict[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    return release.publish_fixed_g0_candidate_authority_release_v1(
        run_id=RUN_ID,
        repository_root=Path("/fixture/repository"),
        catalog_replay_receipt_identity=state["catalog_receipt_identity"],
        read_exact=store.read_exact,
        publish_create_once=store.create_once,
        git_head=lambda _root: "1" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture\n",
        git_status=lambda _root, _paths: b"",
    )


def _reopen(
    *,
    store: MemoryExactStore,
    root_identity: dict[str, object],
) -> release.ReopenedFixedG0CandidateAuthorityV1:
    return release.reopen_fixed_g0_candidate_authority_release_v1(
        root_identity,
        repository_root=Path("/fixture/repository"),
        read_exact=store.read_exact,
        git_head=lambda _root: "1" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture\n",
        git_status=lambda _root, _paths: b"",
    )


@pytest.fixture
def published(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    store = MemoryExactStore()
    state = _install_core_fixture(monkeypatch, store=store)
    root, root_identity = _publish(store=store, state=state)
    return {
        "store": store,
        "state": state,
        "root": root,
        "root_identity": root_identity,
    }


def test_root_last_publication_and_authoritative_reopen(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    root = published["root"]
    prefix = release.output_prefix_for_run_v1(RUN_ID)
    assert len(store.create_calls) == source.TASK_COUNT * 3 + 3
    assert store.create_calls[-1] == f"{prefix}{release.ROOT_FILENAME}"
    assert root["candidate_population_authority"] is True
    assert root["exact_occurrence_provenance_authority"] is True
    assert root["total_candidate_count"] == source.TASK_COUNT * source.ENTRY_BUDGET
    assert len(root["objects"]) == source.TASK_COUNT

    reopened = _reopen(
        store=store, root_identity=published["root_identity"]
    )
    assert reopened.root == root
    assert reopened.candidate_release["task_count"] == source.TASK_COUNT
    assert published["state"]["validate_calls"] == 1
    first_lineage = reopened.authority_bundle["lineage_sidecars"][0]
    assert first_lineage["candidates"][0]["occurrences"] == [{
        "arm_ordinal": 0,
        "parameter_set_id": "baseline",
        "visit_ordinal": 0,
        "block_id": "R0",
        "objective_world_index": 0,
    }]


def test_public_api_has_no_candidate_or_namespace_bypass() -> None:
    parameters = inspect.signature(
        release.publish_fixed_g0_candidate_authority_release_v1
    ).parameters
    assert "candidate_artifacts" not in parameters
    assert "candidate_artifact_identities" not in parameters
    assert "lineage_sidecars" not in parameters
    assert "namespace" not in parameters
    assert "output_prefix" not in parameters


def test_identical_create_once_resume_reuses_every_generation(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    first_identity = published["root_identity"]
    first_object_count = len(store._objects)
    root, second_identity = _publish(
        store=store, state=published["state"]
    )
    assert root == published["root"]
    assert second_identity == first_identity
    assert len(store._objects) == first_object_count


def test_different_candidate_collision_never_publishes_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryExactStore()
    state = _install_core_fixture(monkeypatch, store=store)
    prefix = release.output_prefix_for_run_v1(RUN_ID)
    first_slate = catalog_v1.expected_slate_for_source_task(0)["slate_id"]
    store.force(
        f"{prefix}source-task-00-{first_slate}/accepted-candidates.json",
        b'{"different":true}',
    )
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV1Error,
        match="create-once publication failed",
    ):
        _publish(store=store, state=state)
    assert f"{prefix}{release.ROOT_FILENAME}" not in store._heads


def test_late_lineage_failure_leaves_root_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryExactStore()
    state = _install_core_fixture(monkeypatch, store=store)
    prefix = release.output_prefix_for_run_v1(RUN_ID)
    last_slate = catalog_v1.expected_slate_for_source_task(53)["slate_id"]
    store.fail_create_uri = (
        f"{prefix}source-task-53-{last_slate}/{release.LINEAGE_FILENAME}"
    )
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV1Error,
        match="create-once publication failed",
    ):
        _publish(store=store, state=state)
    assert f"{prefix}{release.ROOT_FILENAME}" not in store._heads


def test_escaped_lineage_identity_rejected_before_backing_read(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    changed = deepcopy(published["root"])
    escaped_uri = "gs://attacker-bucket/lineage.json"
    changed["objects"][0]["lineage_sidecar_identity"]["uri"] = escaped_uri
    _rehash(changed["objects"][0], "object_descriptor_sha256")
    changed["object_manifest_sha256"] = release.canonical_sha256(
        changed["objects"]
    )
    _rehash(changed, "candidate_authority_release_sha256")
    changed_identity = store.force(
        changed["target_uri"], release.canonical_json_bytes(changed)
    )
    store.read_calls.clear()
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV1Error,
        match=r"descriptor\[0\] differs",
    ):
        _reopen(store=store, root_identity=changed_identity)
    assert escaped_uri not in store.read_calls


def test_root_generation_pin_ignores_newer_uri_head(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    old_identity = published["root_identity"]
    store.force(old_identity["uri"], b'{"newer":"invalid"}')
    reopened = _reopen(store=store, root_identity=old_identity)
    assert reopened.root == published["root"]


def test_alternate_catalog_receipt_uri_rejected_before_dependency_read(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    changed = deepcopy(published["root"])
    alternate_uri = "gs://attacker-bucket/catalog-replay.json"
    changed["catalog_replay_receipt_identity"]["uri"] = alternate_uri
    _rehash(changed, "candidate_authority_release_sha256")
    changed_identity = store.force(
        changed["target_uri"], release.canonical_json_bytes(changed)
    )
    store.read_calls.clear()
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV1Error,
        match="policy or namespace differs",
    ):
        _reopen(store=store, root_identity=changed_identity)
    assert alternate_uri not in store.read_calls


def test_coherently_rehashed_lineage_substitution_fails_predecessor_replay(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    changed_root = deepcopy(published["root"])
    descriptor = changed_root["objects"][0]

    sidecar_identity = descriptor["lineage_sidecar_identity"]
    sidecar = json.loads(store.read_exact(sidecar_identity).decode("utf-8"))
    sidecar["candidates"][0]["occurrences"][0]["visit_ordinal"] += 999
    sidecar["candidate_lineage_manifest_sha256"] = release.canonical_sha256(
        sidecar["candidates"]
    )
    _rehash(sidecar, "candidate_lineage_sidecar_sha256")
    new_sidecar_identity = store.force(
        sidecar_identity["uri"], release.canonical_json_bytes(sidecar)
    )

    receipt_identity = descriptor["slate_derivation_identity"]
    receipt = json.loads(store.read_exact(receipt_identity).decode("utf-8"))
    receipt["lineage_sidecar_sha256"] = sidecar[
        "candidate_lineage_sidecar_sha256"
    ]
    receipt["candidate_lineage_manifest_sha256"] = sidecar[
        "candidate_lineage_manifest_sha256"
    ]
    _rehash(receipt, "slate_derivation_sha256")
    new_receipt_identity = store.force(
        receipt_identity["uri"], release.canonical_json_bytes(receipt)
    )

    descriptor["lineage_sidecar_identity"] = new_sidecar_identity
    descriptor["lineage_sidecar_sha256"] = sidecar[
        "candidate_lineage_sidecar_sha256"
    ]
    descriptor["candidate_lineage_manifest_sha256"] = sidecar[
        "candidate_lineage_manifest_sha256"
    ]
    descriptor["slate_derivation_identity"] = new_receipt_identity
    descriptor["slate_derivation_sha256"] = receipt[
        "slate_derivation_sha256"
    ]
    _rehash(descriptor, "object_descriptor_sha256")
    changed_root["object_manifest_sha256"] = release.canonical_sha256(
        changed_root["objects"]
    )
    _rehash(changed_root, "candidate_authority_release_sha256")
    changed_root_identity = store.force(
        changed_root["target_uri"], release.canonical_json_bytes(changed_root)
    )
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV1Error,
        match="predecessor replay failed",
    ):
        _reopen(store=store, root_identity=changed_root_identity)


def test_structure_validator_explicitly_grants_no_reopen_authority(
    published: dict[str, Any],
) -> None:
    retained = release.validate_fixed_g0_candidate_authority_release_structure_v1(
        published["root"]
    )
    assert retained["candidate_population_authority"] is True
    assert retained["authoritative_reopen_required"] is True
    assert retained["structure_only_validation_authority"] is False
    assert published["state"]["validate_calls"] == 0
