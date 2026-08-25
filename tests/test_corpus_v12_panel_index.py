from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import build_corpus_v12_panel_index_v1 as cli
from nfl_dfs.research import corpus_artifact_source_authority as source_authority
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_v12_panel_index as panel
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw


def _hex(value: int) -> str:
    return f"{value:064x}"


class Store:
    def __init__(self) -> None:
        self.raw_by_uri: dict[str, bytes] = {}
        self.publish_calls: list[tuple[str, bytes]] = []
        self.read_calls: list[str] = []
        self.source_authority_fixture: (
            tuple[dict[str, object], dict[str, object]] | None
        ) = None

    def put_raw(self, uri: str, raw: bytes) -> dict[str, object]:
        assert uri not in self.raw_by_uri
        self.raw_by_uri[uri] = raw
        return {
            "uri": uri,
            "generation": "1",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def put_json(self, uri: str, value: object) -> dict[str, object]:
        return self.put_raw(uri, batch.canonical_json_bytes(value))

    def put_transport_json(self, uri: str, value: object) -> dict[str, object]:
        return self.put_raw(uri, batch.canonical_json_bytes(value) + b"\n")

    def read(self, identity: object) -> bytes:
        assert isinstance(identity, dict)
        uri = str(identity["uri"])
        self.read_calls.append(uri)
        return self.raw_by_uri[uri]

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> dict[str, object]:
        self.publish_calls.append((uri, raw))
        if uri in self.raw_by_uri:
            retained = self.raw_by_uri[uri]
            if retained != raw:
                raise cli.CorpusV12PanelIndexCLIError(
                    "create-once panel collision differs from requested bytes"
                )
        else:
            self.raw_by_uri[uri] = raw
        return {
            "uri": uri,
            "generation": "1",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


def _transport_sha256(value: object) -> str:
    return sha256(batch.canonical_json_bytes(value) + b"\n").hexdigest()


def _self_hash(
    value: dict[str, object], field: str, *, transport: bool = False
) -> dict[str, object]:
    value[field] = (
        _transport_sha256(value) if transport else batch.canonical_sha256(value)
    )
    return value


def _inventory(identities: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        [
            {
                "uri": identity["uri"],
                "generation": identity["generation"],
                "bytes": identity["bytes"],
            }
            for identity in identities
        ],
        key=lambda row: (row["uri"], row["generation"]),
    )


def _dummy_identity(
    store: Store, *, lane_id: str, label: str, ordinal: int
) -> dict[str, object]:
    return store.put_raw(
        f"gs://fixture/{lane_id}/evidence/{label}-{ordinal}.json",
        batch.canonical_json_bytes({"label": label, "ordinal": ordinal}),
    )


def _identity_stub(uri: str, *, generation: int, seed: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": _hex(seed),
        "bytes": 1,
    }


def _source_authority_fixture(
    store: Store,
) -> tuple[dict[str, object], dict[str, object]]:
    if store.source_authority_fixture is not None:
        return store.source_authority_fixture

    registration_identity = _identity_stub(
        "gs://fixture/source/registration.json", generation=10, seed=10
    )
    later_source_identity = _identity_stub(
        "gs://fixture/source/later-source.json", generation=11, seed=11
    )
    salary_identity = _identity_stub(
        "gs://fixture/source/salary-diagnostic.json", generation=12, seed=12
    )
    registration_sha = _hex(20)
    later_source_sha = _hex(21)
    salary_sha = _hex(22)
    tasks: list[dict[str, object]] = []
    receipt_manifest: list[dict[str, object]] = []
    validation_manifest: list[dict[str, object]] = []
    artifact_ordinal = 0
    empty_sha = source_authority.canonical_sha256([])
    for task_index, (season, week) in enumerate(later.EXPECTED_SLATE_KEYS):
        slate_id = f"{season}-w{week:02d}"
        catalog_player_ids_sha = _hex(30_000 + task_index)
        receipts: dict[str, object] = {}
        validations: dict[str, object] = {}
        for role_ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES):
            receipt = _identity_stub(
                f"gs://fixture/source/tasks/{task_index}/{role}.npz",
                generation=100_000 + artifact_ordinal,
                seed=40_000 + artifact_ordinal,
            )
            validation = {
                "artifact_ordinal": artifact_ordinal,
                "role": role,
                "object": receipt,
                "candidate_rows": 1,
                "player_count": 1,
                "ordered_player_ids_sha256": _hex(
                    50_000 + artifact_ordinal
                ),
                "player_set_sha256": catalog_player_ids_sha,
                "npz_fields": sorted(later.NPZ_FIELDS),
                "player_draws_dtype": "float32",
                "player_draws_shape": [1, rw.WORLDS_PER_BLOCK],
                "world_count": rw.WORLDS_PER_BLOCK,
                "player_set_matches_catalog": True,
                "uses_realized_outcomes": False,
            }
            receipts[role] = receipt
            validations[role] = validation
            receipt_manifest.append(
                {
                    "artifact_ordinal": artifact_ordinal,
                    "task_index": task_index,
                    "role": role,
                    "object": receipt,
                }
            )
            validation_manifest.append(validation)
            artifact_ordinal += 1
        coverage = {
            "salary_player_count": 1,
            "salary_player_ids_sha256": catalog_player_ids_sha,
            "artifact_supported_player_count": 1,
            "artifact_supported_player_ids_sha256": catalog_player_ids_sha,
            "artifact_supported_in_salary_count": 1,
            "salary_only_player_count": 0,
            "salary_only_player_ids_sha256": empty_sha,
            "artifact_only_player_count": 0,
            "artifact_only_player_ids_sha256": empty_sha,
            "artifact_equals_salary_diagnostic": True,
            "salary_only_players_have_world_draws": False,
            "coverage_is_predeclared_query_relative": True,
            "query_result_independently_verified": False,
            "complete_dk_salary_coverage_claimed": False,
        }
        task = {
            "task_index": task_index,
            "season": season,
            "week": week,
            "slate_id": slate_id,
            "universe_scope": source_authority.UNIVERSE_SCOPE,
            "registration_sha256": registration_sha,
            "later_source_freeze_manifest_sha256": later_source_sha,
            "salary_diagnostic_sha256": salary_sha,
            "catalog_sha256": _hex(60_000 + task_index),
            "catalog_player_count": 1,
            "catalog_player_ids_sha256": catalog_player_ids_sha,
            "incumbent_candidates_sha256": _hex(61_000 + task_index),
            "world_artifact_receipts": receipts,
            "world_artifact_receipt_set_sha256": (
                source_authority.canonical_sha256(receipts)
            ),
            "world_artifact_validations": validations,
            "world_artifact_validation_set_sha256": (
                source_authority.canonical_sha256(validations)
            ),
            "salary_coverage": coverage,
            "complete_dk_salary_universe_claimed": False,
        }
        task["task_source_authority_sha256"] = (
            source_authority.canonical_sha256(task)
        )
        tasks.append(task)

    completion = {
        "schema": source_authority.COMPLETION_SCHEMA,
        "authority_scope": source_authority.UNIVERSE_SCOPE,
        "registration_object": registration_identity,
        "registration_sha256": registration_sha,
        "later_source_freeze_object": later_source_identity,
        "later_source_freeze_manifest_sha256": later_source_sha,
        "salary_diagnostic_object": salary_identity,
        "salary_diagnostic_sha256": salary_sha,
        "task_count": source_authority.EXPECTED_TASK_COUNT,
        "world_blocks": list(rw.WORLD_BLOCKS),
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "artifact_count": source_authority.EXPECTED_ARTIFACT_COUNT,
        "artifact_stream_order": "task-index-major_then-r0-r1-r2-r3-r4",
        "artifact_receipt_manifest_sha256": (
            source_authority.canonical_sha256(receipt_manifest)
        ),
        "artifact_validation_manifest_sha256": (
            source_authority.canonical_sha256(validation_manifest)
        ),
        "tasks": tasks,
        "task_manifest_sha256": source_authority.canonical_sha256(tasks),
        "salary_coverage_summary": {
            "task_count": source_authority.EXPECTED_TASK_COUNT,
            "exact_match_task_count": source_authority.EXPECTED_TASK_COUNT,
            "artifact_player_slate_count": source_authority.EXPECTED_TASK_COUNT,
            "salary_player_slate_count": source_authority.EXPECTED_TASK_COUNT,
            "salary_only_player_slate_count": 0,
            "coverage_numerator_artifact_player_slates": (
                source_authority.EXPECTED_TASK_COUNT
            ),
            "coverage_denominator_salary_player_slates": (
                source_authority.EXPECTED_TASK_COUNT
            ),
            "diagnostic_required": True,
            "diagnostic_grants_world_draws": False,
            "coverage_is_predeclared_query_relative": True,
            "query_result_independently_verified": False,
            "complete_dk_salary_coverage_claimed": False,
        },
        "artifact_supported_universe_complete": True,
        "complete_dk_salary_universe_claimed": False,
        "salary_coverage_is_predeclared_query_relative": True,
        "salary_query_result_independently_verified": False,
        "complete_dk_salary_coverage_claimed": False,
        "salary_only_players_have_world_draws": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "live_strategy_authority": False,
    }
    completion["completion_sha256"] = source_authority.canonical_sha256(
        completion
    )
    source_authority.validate_completion_bytes(
        source_authority.canonical_json_bytes(completion)
    )
    identity = store.put_raw(
        "gs://fixture/source/completion.json",
        source_authority.canonical_json_bytes(completion),
    )
    store.source_authority_fixture = (identity, completion)
    return store.source_authority_fixture


def _build_lane(
    store: Store,
    *,
    lane_ordinal: int,
    lane_id: str,
    slate_ids: list[str],
    arm_count_by_task: dict[int, int] | None = None,
    terminal_complete: bool = True,
    terminal_batch_mode: str | None = None,
) -> dict[str, object]:
    arm_count_by_task = arm_count_by_task or {}
    source_authority_identity, source_completion = _source_authority_fixture(store)
    seed = 1_000 + lane_ordinal * 10_000
    manifest_identity = _dummy_identity(
        store, lane_id=lane_id, label="manifest", ordinal=seed
    )
    transport_contract = _dummy_identity(
        store, lane_id=lane_id, label="transport", ordinal=seed
    )
    retrieval_prerequisite = _dummy_identity(
        store, lane_id=lane_id, label="retrieval", ordinal=seed
    )
    inventory_authority = _dummy_identity(
        store, lane_id=lane_id, label="policy-inventory", ordinal=seed
    )
    batch_id = f"batch-{lane_id}"
    batch_manifest_sha = _hex(seed + 1)
    parameter_schema_sha = _hex(seed + 2)
    common_law_sha = _hex(seed + 3)
    later_source_sha = str(
        source_completion["later_source_freeze_manifest_sha256"]
    )
    source_authority_sha = str(source_completion["completion_sha256"])
    classified_projection_sha = _hex(seed + 6)
    carriers: list[dict[str, object]] = []
    acceptances: list[dict[str, object]] = []
    task_inputs: list[dict[str, object]] = []
    completion_rows: list[dict[str, object]] = []

    for task_ordinal, slate_id in enumerate(slate_ids):
        source_task_ordinal = (
            int(panel.V12_LANE_LATTICE[lane_ordinal]["source_task_offset"])
            + task_ordinal
        )
        source_task = source_completion["tasks"][source_task_ordinal]
        task_seed = seed + 100 + task_ordinal * 100
        task_sha = _hex(task_seed + 1)
        world_set_sha = str(source_task["world_artifact_receipt_set_sha256"])
        source_task_sha = str(source_task["task_source_authority_sha256"])
        variant_rows: list[dict[str, object]] = []
        arm_count = arm_count_by_task.get(
            task_ordinal, len(batch.PARAMETER_SET_ORDER)
        )
        for arm_ordinal in range(arm_count):
            arm_result = store.put_json(
                (
                    f"gs://fixture/{lane_id}/tasks/{task_ordinal}/arms/"
                    f"{arm_ordinal}/result.json"
                ),
                {
                    "lane": lane_id,
                    "task": task_ordinal,
                    "arm": arm_ordinal,
                    "uses_realized_outcomes": False,
                },
            )
            policy = _dummy_identity(
                store,
                lane_id=lane_id,
                label=f"policy-{task_ordinal}",
                ordinal=arm_ordinal,
            )
            variant_rows.append(
                {
                    "ordinal": arm_ordinal,
                    "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
                    "parameter_set_sha256": _hex(task_seed + 10 + arm_ordinal),
                    "effective_policy_receipt": policy,
                    "result_object": arm_result,
                }
            )
        carrier = _self_hash(
            {
                "schema_version": batch.TASK_RESULT_SCHEMA,
                "publication_mode": "create_once",
                "batch_manifest_identity": manifest_identity,
                "batch_id": batch_id,
                "batch_manifest_sha256": batch_manifest_sha,
                "parameter_schema_sha256": parameter_schema_sha,
                "common_law_sha256": common_law_sha,
                "task_index": task_ordinal,
                "task_sha256": task_sha,
                "slate_id": slate_id,
                "world_artifact_receipts": {},
                "world_artifact_receipt_set_sha256": world_set_sha,
                "artifact_source_authority_task_sha256": source_task_sha,
                "code_source": {"fixture": True},
                "immutable_image": {"fixture": True},
                "source_receipts": {},
                "source_receipt_set_sha256": _hex(task_seed + 4),
                "later_source_freeze_manifest_sha256": later_source_sha,
                "artifact_source_authority_completion": (
                    source_authority_identity
                ),
                "artifact_source_authority_completion_sha256": (
                    source_authority_sha
                ),
                "effective_policy_inventory_identity": inventory_authority,
                "effective_policy_inventory_sha256": _hex(task_seed + 5),
                "effective_policy_rule_universe_sha256": _hex(task_seed + 6),
                "effective_policy_inventory_source_set_sha256": _hex(
                    task_seed + 7
                ),
                "effective_policy_classified_input_projection_sha256": (
                    classified_projection_sha
                ),
                "world_schedule": [],
                "world_seed": task_seed,
                "solver": {"fixture": True},
                "execution": {"fixture": True},
                "variant_results": variant_rows,
            },
            "task_result_sha256",
        )
        carrier_identity = store.put_json(
            f"gs://fixture/{lane_id}/tasks/{task_ordinal}/task-result.json",
            carrier,
        )
        carriers.append(carrier_identity)

        acceptance = _self_hash(
            {
                "schema_version": panel.TASK_ACCEPTANCE_SCHEMA,
                "accepted_at_utc": "2026-08-25T01:00:00Z",
                "transport_contract": transport_contract,
                "retrieval_task0_prerequisite_identity": retrieval_prerequisite,
                "task_index": task_ordinal,
                "task_sha256": task_sha,
                "producer_close": _dummy_identity(
                    store,
                    lane_id=lane_id,
                    label=f"producer-close-{task_ordinal}",
                    ordinal=task_seed,
                ),
                "science_terminal": _dummy_identity(
                    store,
                    lane_id=lane_id,
                    label=f"science-terminal-{task_ordinal}",
                    ordinal=task_seed,
                ),
                "task_result": carrier_identity,
                "verifier_worker_completion": _dummy_identity(
                    store,
                    lane_id=lane_id,
                    label=f"verifier-completion-{task_ordinal}",
                    ordinal=task_seed,
                ),
                "independent_verification": _dummy_identity(
                    store,
                    lane_id=lane_id,
                    label=f"verification-{task_ordinal}",
                    ordinal=task_seed,
                ),
                "independent_verification_sha256": _hex(task_seed + 8),
                "verifier_terminal_execution": {"fixture": True},
                "terminal_governance_census": {"fixture": True},
                "evidence_object_count": 140,
                "complete_evidence_receipt": True,
                "independent_verification_complete": True,
                "strict_verifier_terminal_success": True,
                "accepted": True,
                "partial_result": False,
                "automatic_retry_licensed": False,
                "uses_realized_outcomes": False,
                "historical_scoring_licensed": False,
                "corpus_fill_licensed": False,
                "graph_mutation_licensed": False,
                "production_change_licensed": False,
                "decision_authority": False,
            },
            "task_acceptance_sha256",
            transport=True,
        )
        acceptance_identity = store.put_transport_json(
            f"gs://fixture/{lane_id}/tasks/{task_ordinal}/acceptance.json",
            acceptance,
        )
        acceptances.append(acceptance_identity)
        task_inputs.append(
            {
                "task_ordinal": task_ordinal,
                "acceptance_identity": acceptance_identity,
                "carrier_identity": carrier_identity,
            }
        )
        completion_rows.append(
            {
                "task_index": task_ordinal,
                "task_sha256": task_sha,
                "artifact_source_authority_task_sha256": source_task_sha,
                "world_artifact_receipt_set_sha256": world_set_sha,
                "task_result_sha256": carrier["task_result_sha256"],
                "task_result_object": carrier_identity,
            }
        )

    task_count = len(slate_ids)
    completion = _self_hash(
        {
            "schema_version": batch.BATCH_COMPLETION_SCHEMA,
            "publication_mode": "create_once",
            "batch_manifest_identity": manifest_identity,
            "batch_id": batch_id,
            "batch_manifest_sha256": batch_manifest_sha,
            "parameter_schema_sha256": parameter_schema_sha,
            "common_law_sha256": common_law_sha,
            "later_source_freeze_manifest_sha256": later_source_sha,
            "artifact_source_authority_completion": source_authority_identity,
            "artifact_source_authority_completion_sha256": source_authority_sha,
            "effective_policy_classified_input_projection_sha256": (
                classified_projection_sha
            ),
            "coverage": {
                "task_count": task_count,
                "parameter_set_count": len(batch.PARAMETER_SET_ORDER),
                "matrix_cell_count": task_count * len(batch.PARAMETER_SET_ORDER),
                "complete": True,
            },
            "task_results": completion_rows,
        },
        "batch_completion_sha256",
    )
    completion_identity = store.put_json(
        f"gs://fixture/{lane_id}/batch-completion.json", completion
    )
    inventory = _inventory([completion_identity, *acceptances, *carriers])
    terminal = _self_hash(
        {
            "schema_version": panel.LANE_TERMINAL_SCHEMA,
            "accepted_at_utc": "2026-08-25T02:00:00Z",
            "transport_contract": transport_contract,
            "retrieval_task0_prerequisite_identity": retrieval_prerequisite,
            "batch_mode": (
                panel.V12_LANE_LATTICE[lane_ordinal]["batch_mode"]
                if terminal_batch_mode is None
                else terminal_batch_mode
            ),
            "batch_completion": completion_identity,
            "task_acceptances": acceptances,
            "task_count": task_count,
            "parameter_set_count": len(batch.PARAMETER_SET_ORDER),
            "matrix_cell_count": task_count * len(batch.PARAMETER_SET_ORDER),
            "output_inventory_before_batch_acceptance": inventory,
            "output_inventory_before_batch_acceptance_sha256": (
                _transport_sha256(inventory)
            ),
            "output_object_count_before_batch_acceptance": len(inventory),
            "complete": terminal_complete,
            "accepted": terminal_complete,
            "partial_result": not terminal_complete,
            "independent_verification_complete_for_every_task": terminal_complete,
            "automatic_retry_licensed": False,
            "uses_realized_outcomes": False,
            "historical_scoring_licensed": False,
            "corpus_fill_licensed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        },
        "batch_acceptance_sha256",
        transport=True,
    )
    terminal_identity = store.put_transport_json(
        f"gs://fixture/{lane_id}/batch-acceptance.json", terminal
    )
    return {
        "lane_ordinal": lane_ordinal,
        "lane_id": lane_id,
        "terminal_receipt_identity": terminal_identity,
        "tasks": task_inputs,
    }


def _fixture() -> tuple[Store, list[dict[str, object]]]:
    store = Store()
    lanes = [
        _build_lane(
            store,
            lane_ordinal=0,
            lane_id="v12a",
            slate_ids=_slates(0, 28),
        ),
        _build_lane(
            store,
            lane_ordinal=1,
            lane_id="v12b",
            slate_ids=_slates(28, 26),
        ),
    ]
    return store, lanes


def _slates(start: int, count: int) -> list[str]:
    return [
        f"{season}-w{week:02d}"
        for season, week in later.EXPECTED_SLATE_KEYS[start : start + count]
    ]


def test_build_and_exact_read_replay_complete_two_lane_index() -> None:
    store, lanes = _fixture()
    result = panel.build_v12_panel_index(lane_inputs=lanes, read_exact=store.read)
    assert result["schema_version"] == panel.PANEL_INDEX_SCHEMA
    assert result["publication_mode"] == "create_once"
    assert result["lane_count"] == 2
    assert result["accepted_slate_count"] == 54
    assert [row["slate_id"] for row in result["accepted_slates"]] == _slates(
        0, 54
    )
    assert [
        (row["lane_ordinal"], row["task_ordinal"])
        for row in result["accepted_slates"]
    ] == [
        *( (0, ordinal) for ordinal in range(28) ),
        *( (1, ordinal) for ordinal in range(26) ),
    ]
    assert [
        row["source_task_ordinal"] for row in result["accepted_slates"]
    ] == list(range(54))
    source_identity, source_completion = _source_authority_fixture(store)
    assert store.read_calls.count(str(source_identity["uri"])) == 1
    assert result["artifact_source_authority_completion"] == source_identity
    assert result["artifact_source_authority_completion_sha256"] == (
        source_completion["completion_sha256"]
    )
    assert all(
        row["artifact_source_authority_completion"] == source_identity
        and row["artifact_source_authority_completion_sha256"]
        == source_completion["completion_sha256"]
        for row in result["lanes"]
    )
    assert [
        row["source_task_authority_sha256"]
        for row in result["accepted_slates"]
    ] == [
        task["task_source_authority_sha256"]
        for task in source_completion["tasks"]
    ]
    assert all(len(row["arms"]) == 7 for row in result["accepted_slates"])
    assert result["exclusions"] == []
    assert result["failures"] == []
    assert result["missing_tasks"] == []
    assert result["uses_realized_outcomes"] is False
    assert result["coverage"] == {
        "expected_task_count": 54,
        "accepted_task_count": 54,
        "excluded_task_count": 0,
        "failed_task_count": 0,
        "missing_task_count": 0,
        "complete": True,
    }
    false_fields = {
        key
        for key, value in result.items()
        if key.endswith("authority") or key.endswith("licensed")
        if value is False
    }
    assert false_fields == {
        "automatic_retry_licensed",
        "historical_scoring_licensed",
        "corpus_fill_licensed",
        "graph_mutation_licensed",
        "live_policy_access_licensed",
        "production_change_licensed",
        "analytical_authority",
        "promotion_authority",
        "decision_authority",
    }
    remainder = dict(result)
    retained = remainder.pop("panel_index_sha256")
    assert batch.canonical_sha256(remainder) == retained

    index_identity = store.put_json(
        "gs://fixture/combined-v12-panel-index.json", result
    )
    assert panel.reopen_v12_panel_index(
        panel_index_identity=index_identity,
        lane_inputs=lanes,
        read_exact=store.read,
    ) == result


def test_index_self_hash_and_exact_input_replay_both_fail_closed() -> None:
    store, lanes = _fixture()
    result = panel.build_v12_panel_index(lane_inputs=lanes, read_exact=store.read)
    tampered = deepcopy(result)
    tampered["accepted_slates"][0]["slate_id"] = "2025-w01"
    with pytest.raises(panel.CorpusV12PanelIndexError, match="self-hash"):
        panel.validate_v12_panel_index(
            tampered, lane_inputs=lanes, read_exact=store.read
        )

    tampered["panel_index_sha256"] = batch.canonical_sha256(
        {
            key: value
            for key, value in tampered.items()
            if key != "panel_index_sha256"
        }
    )
    with pytest.raises(panel.CorpusV12PanelIndexError, match="exact-input replay"):
        panel.validate_v12_panel_index(
            tampered, lane_inputs=lanes, read_exact=store.read
        )


def test_swapped_source_subset_is_rejected_before_panel_indexing() -> None:
    store = Store()
    lanes = [
        _build_lane(
            store,
            lane_ordinal=0,
            lane_id="v12a",
            slate_ids=_slates(0, 28),
        ),
        _build_lane(
            store,
            lane_ordinal=1,
            lane_id="v12b",
            slate_ids=_slates(0, 26),
        ),
    ]
    with pytest.raises(
        panel.CorpusV12PanelIndexError, match="frozen source-authority task"
    ):
        panel.build_v12_panel_index(lane_inputs=lanes, read_exact=store.read)


def test_nonterminal_or_incomplete_lane_is_rejected() -> None:
    store = Store()
    lanes = [
        _build_lane(
            store,
            lane_ordinal=0,
            lane_id="v12a",
            slate_ids=_slates(0, 28),
            terminal_complete=False,
        ),
        _build_lane(
            store,
            lane_ordinal=1,
            lane_id="v12b",
            slate_ids=_slates(28, 26),
        ),
    ]
    with pytest.raises(
        panel.CorpusV12PanelIndexError, match="nonterminal, incomplete"
    ):
        panel.build_v12_panel_index(lane_inputs=lanes, read_exact=store.read)


def test_lane_batch_mode_must_match_the_frozen_v12_lattice() -> None:
    store = Store()
    lanes = [
        _build_lane(
            store,
            lane_ordinal=0,
            lane_id="v12a",
            slate_ids=_slates(0, 28),
            terminal_batch_mode="production-54-task",
        ),
        _build_lane(
            store,
            lane_ordinal=1,
            lane_id="v12b",
            slate_ids=_slates(28, 26),
        ),
    ]
    with pytest.raises(
        panel.CorpusV12PanelIndexError, match="nonterminal, incomplete"
    ):
        panel.build_v12_panel_index(lane_inputs=lanes, read_exact=store.read)


@pytest.mark.parametrize("mutation", ["missing", "order", "identity"])
def test_task_count_order_and_identity_mismatches_are_rejected(
    mutation: str,
) -> None:
    store, lanes = _fixture()
    changed = deepcopy(lanes)
    if mutation == "missing":
        changed[0]["tasks"] = changed[0]["tasks"][:-1]
        message = "frozen v12 lattice"
    elif mutation == "order":
        changed[0]["tasks"] = list(reversed(changed[0]["tasks"]))
        message = "fixed ordinal order"
    else:
        changed[0]["tasks"][0]["carrier_identity"] = changed[1]["tasks"][0][
            "carrier_identity"
        ]
        message = "differs from batch completion"
    with pytest.raises(panel.CorpusV12PanelIndexError, match=message):
        panel.build_v12_panel_index(lane_inputs=changed, read_exact=store.read)


def test_missing_seventh_arm_is_rejected() -> None:
    store = Store()
    lanes = [
        _build_lane(
            store,
            lane_ordinal=0,
            lane_id="v12a",
            slate_ids=_slates(0, 28),
            arm_count_by_task={0: 6},
        ),
        _build_lane(
            store,
            lane_ordinal=1,
            lane_id="v12b",
            slate_ids=_slates(28, 26),
        ),
    ]
    with pytest.raises(panel.CorpusV12PanelIndexError, match="exactly seven arms"):
        panel.build_v12_panel_index(lane_inputs=lanes, read_exact=store.read)


def test_exact_read_content_drift_is_rejected() -> None:
    store, lanes = _fixture()
    drift_uri = lanes[0]["terminal_receipt_identity"]["uri"]

    def drifted_read(identity: object) -> bytes:
        raw = store.read(identity)
        assert isinstance(identity, dict)
        return raw + b" " if identity["uri"] == drift_uri else raw

    with pytest.raises(panel.CorpusV12PanelIndexError, match="bytes differ"):
        panel.build_v12_panel_index(lane_inputs=lanes, read_exact=drifted_read)


def test_source_authority_completion_tamper_is_rejected() -> None:
    store, lanes = _fixture()
    source_identity, _ = _source_authority_fixture(store)
    source_uri = str(source_identity["uri"])
    store.raw_by_uri[source_uri] += b"tamper"
    with pytest.raises(panel.CorpusV12PanelIndexError, match="bytes differ"):
        panel.build_v12_panel_index(lane_inputs=lanes, read_exact=store.read)


def test_terminal_derivation_reproduces_every_authoritative_task_binding() -> None:
    store, lanes = _fixture()
    derived = [
        panel.derive_v12_lane_input(
            lane_ordinal=lane_ordinal,
            lane_id=str(lane["lane_id"]),
            terminal_receipt_identity=lane["terminal_receipt_identity"],
            read_exact=store.read,
        )
        for lane_ordinal, lane in enumerate(lanes)
    ]
    assert derived == lanes


def test_transport_and_batch_json_dialects_are_role_specific() -> None:
    store, lanes = _fixture()
    changed = deepcopy(lanes)
    terminal_identity = changed[0]["terminal_receipt_identity"]
    terminal_uri = str(terminal_identity["uri"])
    terminal_raw = store.raw_by_uri[terminal_uri][:-1]
    store.raw_by_uri[terminal_uri] = terminal_raw
    changed[0]["terminal_receipt_identity"] = {
        **terminal_identity,
        "sha256": sha256(terminal_raw).hexdigest(),
        "bytes": len(terminal_raw),
    }
    with pytest.raises(
        panel.CorpusV12PanelIndexError, match="not canonical JSON"
    ):
        panel.build_v12_panel_index(lane_inputs=changed, read_exact=store.read)

    store, lanes = _fixture()
    carrier_identity = lanes[0]["tasks"][0]["carrier_identity"]
    carrier_uri = str(carrier_identity["uri"])
    carrier_raw = store.raw_by_uri[carrier_uri] + b"\n"
    store.raw_by_uri[carrier_uri] = carrier_raw
    newline_carrier_identity = {
        **carrier_identity,
        "sha256": sha256(carrier_raw).hexdigest(),
        "bytes": len(carrier_raw),
    }
    with pytest.raises(
        panel.CorpusV12PanelIndexError, match="not canonical JSON"
    ):
        panel._exact_read_json(
            newline_carrier_identity,
            read_exact=store.read,
            label="task result carrier",
        )


def _identity_files(
    tmp_path: Path, lanes: list[dict[str, object]]
) -> list[Path]:
    paths: list[Path] = []
    for ordinal, lane in enumerate(lanes):
        path = tmp_path / f"lane-{ordinal}-terminal-identity.json"
        path.write_text(
            json.dumps(lane["terminal_receipt_identity"], indent=2) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def _batch_envelope_files(
    tmp_path: Path, lanes: list[dict[str, object]]
) -> list[Path]:
    paths: list[Path] = []
    for ordinal, lane in enumerate(lanes):
        path = tmp_path / f"lane-{ordinal}-batch-accepted.json"
        body = {
            "schema_version": "corpus-parametric-batch-accepted/v1",
            "batch_mode": panel.V12_LANE_LATTICE[ordinal]["batch_mode"],
            "task_count": panel.V12_LANE_LATTICE[ordinal]["task_count"],
            "matrix_cell_count": (
                panel.V12_LANE_LATTICE[ordinal]["task_count"] * 7
            ),
            "batch_completion": _identity_stub(
                f"gs://fixture/{ordinal}/completion.json",
                generation=900 + ordinal,
                seed=900 + ordinal,
            ),
            "batch_acceptance": lane["terminal_receipt_identity"],
            "final_output_inventory_sha256": _hex(950 + ordinal),
            "final_output_object_count": 100,
            "complete": True,
            "accepted": True,
        }
        path.write_bytes(batch.canonical_json_bytes(body) + b"\n")
        paths.append(path)
    return paths


def _cli_args(paths: list[Path], *, execute: bool) -> list[str]:
    return [
        "--lane-id",
        "v12a",
        "--lane-id",
        "v12b",
        "--lane-terminal-identity",
        str(paths[0]),
        "--lane-terminal-identity",
        str(paths[1]),
        "--panel-uri",
        "gs://fixture/panels/foundry-v12.json",
        "--execute" if execute else "--validate-only",
    ]


def test_cli_validate_only_derives_and_replays_without_publication(
    tmp_path: Path,
) -> None:
    store, lanes = _fixture()
    receipt = cli.run(
        _cli_args(_identity_files(tmp_path, lanes), execute=False),
        store=store,
    )
    assert receipt["schema_version"] == cli.PUBLICATION_RECEIPT_SCHEMA
    assert receipt["mode"] == "validate_only"
    assert receipt["published"] is False
    assert receipt["panel_object_identity"] is None
    assert receipt["accepted_slate_count"] == 54
    assert receipt["exact_input_replay_verified"] is True
    assert store.publish_calls == []
    assert all(
        receipt[field] is False
        for field in (
            "automatic_retry_licensed",
            "uses_realized_outcomes",
            "historical_scoring_licensed",
            "corpus_fill_licensed",
            "graph_mutation_licensed",
            "live_policy_access_licensed",
            "production_change_licensed",
            "analytical_authority",
            "promotion_authority",
            "decision_authority",
        )
    )
    body = dict(receipt)
    retained = body.pop("publication_receipt_sha256")
    assert batch.canonical_sha256(body) == retained


def test_cli_execute_is_create_once_and_exactly_replayable(tmp_path: Path) -> None:
    store, lanes = _fixture()
    paths = _identity_files(tmp_path, lanes)
    first = cli.run(_cli_args(paths, execute=True), store=store)
    second = cli.run(_cli_args(paths, execute=True), store=store)
    assert first == second
    assert first["mode"] == "create_once"
    assert first["published"] is True
    assert first["panel_object_identity"] == {
        "uri": "gs://fixture/panels/foundry-v12.json",
        "generation": "1",
        "sha256": first["panel_content_sha256"],
        "bytes": first["panel_content_bytes"],
    }
    assert len(store.publish_calls) == 2
    published = store.raw_by_uri["gs://fixture/panels/foundry-v12.json"]
    assert sha256(published).hexdigest() == first["panel_content_sha256"]


def test_cli_accepts_exact_finish_batch_local_envelopes(tmp_path: Path) -> None:
    store, lanes = _fixture()
    receipt = cli.run(
        _cli_args(
            _batch_envelope_files(tmp_path, lanes),
            execute=False,
        ),
        store=store,
    )
    assert receipt["accepted_slate_count"] == 54
    assert receipt["exact_input_replay_verified"] is True
    assert receipt["published"] is False


def test_cli_rejects_noncanonical_finish_batch_local_envelope(
    tmp_path: Path,
) -> None:
    store, lanes = _fixture()
    paths = _batch_envelope_files(tmp_path, lanes)
    value = json.loads(paths[0].read_text(encoding="utf-8"))
    paths[0].write_text(
        json.dumps(value, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        cli.CorpusV12PanelIndexCLIError,
        match="local batch-accepted envelope is not canonical",
    ):
        cli.run(_cli_args(paths, execute=False), store=store)


def test_cli_writes_and_reopens_exact_local_receipt_create_once(
    tmp_path: Path,
) -> None:
    store, lanes = _fixture()
    paths = _identity_files(tmp_path, lanes)
    receipt_path = tmp_path / "receipts" / "panel-publication.json"
    args = [
        *_cli_args(paths, execute=False),
        "--receipt-output",
        str(receipt_path),
    ]
    first = cli.run(args, store=store)
    second = cli.run(args, store=store)
    assert second == first
    assert receipt_path.read_bytes() == (
        batch.canonical_json_bytes(first) + b"\n"
    )

    receipt_path.write_bytes(b"{}\n")
    with pytest.raises(
        cli.CorpusV12PanelIndexCLIError,
        match="existing local receipt preflight differs",
    ):
        cli.run(args, store=store)


def test_cli_execute_receipt_binds_exact_published_panel_identity(
    tmp_path: Path,
) -> None:
    store, lanes = _fixture()
    receipt_path = tmp_path / "receipts" / "panel-publication.json"
    receipt = cli.run(
        [
            *_cli_args(_identity_files(tmp_path, lanes), execute=True),
            "--receipt-output",
            str(receipt_path),
        ],
        store=store,
    )
    assert receipt_path.read_bytes() == (
        batch.canonical_json_bytes(receipt) + b"\n"
    )
    assert receipt["mode"] == "create_once"
    assert receipt["published"] is True
    assert receipt["panel_object_identity"] == {
        "uri": receipt["panel_uri"],
        "generation": "1",
        "sha256": receipt["panel_content_sha256"],
        "bytes": receipt["panel_content_bytes"],
    }
    assert len(store.publish_calls) == 1


def test_cli_bad_local_receipt_paths_fail_before_publication(
    tmp_path: Path,
) -> None:
    def execute_with(receipt_path: Path) -> Store:
        store, lanes = _fixture()
        input_root = tmp_path / f"inputs-{len(stores)}"
        input_root.mkdir()
        with pytest.raises(cli.CorpusV12PanelIndexCLIError):
            cli.run(
                [
                    *_cli_args(
                        _identity_files(input_root, lanes),
                        execute=True,
                    ),
                    "--receipt-output",
                    str(receipt_path),
                ],
                store=store,
            )
        assert store.publish_calls == []
        stores.append(store)
        return store

    stores: list[Store] = []
    relative_path = Path("relative-panel-publication.json")
    execute_with(relative_path)

    final_target = tmp_path / "final-target.json"
    final_target.write_bytes(b"target\n")
    final_symlink = tmp_path / "final-symlink.json"
    final_symlink.symlink_to(final_target)
    execute_with(final_symlink)

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    parent_symlink = tmp_path / "parent-symlink"
    parent_symlink.symlink_to(real_parent, target_is_directory=True)
    execute_with(parent_symlink / "receipt.json")

    parent_file = tmp_path / "parent-file"
    parent_file.write_bytes(b"not a directory\n")
    execute_with(parent_file / "receipt.json")

    directory_target = tmp_path / "directory-target"
    directory_target.mkdir()
    execute_with(directory_target)


def test_cli_differing_valid_local_receipt_fails_before_publication(
    tmp_path: Path,
) -> None:
    store, lanes = _fixture()
    paths = _identity_files(tmp_path, lanes)
    validate_receipt = cli.run(
        _cli_args(paths, execute=False),
        store=store,
    )
    changed = {
        **validate_receipt,
        "mode": "create_once",
        "published": True,
        "panel_id": _hex(999_999),
        "panel_object_identity": {
            "uri": validate_receipt["panel_uri"],
            "generation": "1",
            "sha256": validate_receipt["panel_content_sha256"],
            "bytes": validate_receipt["panel_content_bytes"],
        },
    }
    changed.pop("publication_receipt_sha256")
    changed["publication_receipt_sha256"] = batch.canonical_sha256(changed)
    receipt_path = tmp_path / "differing-valid-receipt.json"
    receipt_path.write_bytes(batch.canonical_json_bytes(changed) + b"\n")

    with pytest.raises(
        cli.CorpusV12PanelIndexCLIError,
        match="content differs before publication",
    ):
        cli.run(
            [
                *_cli_args(paths, execute=True),
                "--receipt-output",
                str(receipt_path),
            ],
            store=store,
        )
    assert store.publish_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("uri", "gs://fixture/panels/wrong.json"),
        ("sha256", "f" * 64),
        ("bytes", 999_999),
    ],
)
def test_cli_wrong_existing_panel_identity_fails_before_publication(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    store, lanes = _fixture()
    paths = _identity_files(tmp_path, lanes)
    validate_receipt = cli.run(
        _cli_args(paths, execute=False),
        store=store,
    )
    panel_identity = {
        "uri": validate_receipt["panel_uri"],
        "generation": "1",
        "sha256": validate_receipt["panel_content_sha256"],
        "bytes": validate_receipt["panel_content_bytes"],
    }
    panel_identity[field] = value
    changed = {
        **validate_receipt,
        "mode": "create_once",
        "published": True,
        "panel_object_identity": panel_identity,
    }
    changed.pop("publication_receipt_sha256")
    changed["publication_receipt_sha256"] = batch.canonical_sha256(changed)
    receipt_path = tmp_path / f"wrong-panel-{field}.json"
    receipt_path.write_bytes(batch.canonical_json_bytes(changed) + b"\n")

    with pytest.raises(
        cli.CorpusV12PanelIndexCLIError,
        match="panel identity differs from requested content",
    ):
        cli.run(
            [
                *_cli_args(paths, execute=True),
                "--receipt-output",
                str(receipt_path),
            ],
            store=store,
        )
    assert store.publish_calls == []


def test_cli_rejects_nonterminal_finish_batch_local_envelope(
    tmp_path: Path,
) -> None:
    store, lanes = _fixture()
    paths = _batch_envelope_files(tmp_path, lanes)
    changed = json.loads(paths[0].read_text(encoding="utf-8"))
    changed["complete"] = False
    paths[0].write_bytes(batch.canonical_json_bytes(changed) + b"\n")
    with pytest.raises(
        cli.CorpusV12PanelIndexCLIError,
        match="local batch-accepted envelope differs",
    ):
        cli.run(_cli_args(paths, execute=False), store=store)


@pytest.mark.parametrize("lane_count", [1, 3])
def test_cli_requires_exactly_two_lane_identity_pairs(
    tmp_path: Path, lane_count: int
) -> None:
    identity = {
        "uri": "gs://fixture/lane-terminal.json",
        "generation": "1",
        "sha256": _hex(1),
        "bytes": 1,
    }
    path = tmp_path / "identity.json"
    path.write_bytes(batch.canonical_json_bytes(identity))
    args: list[str] = []
    for ordinal in range(lane_count):
        args.extend(["--lane-id", f"v12{chr(ord('a') + ordinal)}"])
        args.extend(["--lane-terminal-identity", str(path)])
    args.extend(
        [
            "--panel-uri",
            "gs://fixture/panels/foundry-v12.json",
            "--validate-only",
        ]
    )
    with pytest.raises(
        cli.CorpusV12PanelIndexCLIError, match="exactly two lane ids"
    ):
        cli.run(args, store=Store())


class _FakeCollision(Exception):
    pass


class _FakeBlob:
    def __init__(
        self,
        backend: dict[tuple[str, str], tuple[int, bytes]],
        calls: list[tuple[object, ...]],
        bucket: str,
        name: str,
        generation: int | None,
    ) -> None:
        self._backend = backend
        self._calls = calls
        self._bucket = bucket
        self._name = name
        self._requested_generation = generation
        self.generation: int | None = generation

    @property
    def _key(self) -> tuple[str, str]:
        return (self._bucket, self._name)

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        generation, raw = self._backend[self._key]
        self._calls.append(
            (
                "download",
                self._key,
                self._requested_generation,
                if_generation_match,
            )
        )
        assert self._requested_generation == generation
        assert if_generation_match == generation
        return raw

    def upload_from_string(
        self,
        raw: bytes,
        *,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        self._calls.append(
            (
                "upload",
                self._key,
                content_type,
                if_generation_match,
            )
        )
        assert if_generation_match == 0
        if self._key in self._backend:
            raise _FakeCollision
        self._backend[self._key] = (1, raw)

    def reload(self) -> None:
        self._calls.append(("reload", self._key))
        self.generation = self._backend[self._key][0]


class _FakeBucket:
    def __init__(
        self,
        backend: dict[tuple[str, str], tuple[int, bytes]],
        calls: list[tuple[object, ...]],
        name: str,
    ) -> None:
        self._backend = backend
        self._calls = calls
        self._name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(
            self._backend, self._calls, self._name, name, generation
        )


class _FakeGCSClient:
    def __init__(self) -> None:
        self.backend: dict[tuple[str, str], tuple[int, bytes]] = {}
        self.calls: list[tuple[object, ...]] = []

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self.backend, self.calls, name)


def test_gcs_store_pins_reads_and_create_once_reopens_equal_bytes() -> None:
    client = _FakeGCSClient()
    store = cli.GCSPanelStore(
        client, collision_exceptions=(_FakeCollision,)
    )
    raw = b'{"panel":true}'
    uri = "gs://fixture/panels/foundry-v12.json"
    identity = store.publish_create_once(uri, raw)
    assert store.publish_create_once(uri, raw) == identity
    assert store.read(identity) == raw
    with pytest.raises(
        cli.CorpusV12PanelIndexCLIError, match="collision differs"
    ):
        store.publish_create_once(uri, b'{"panel":false}')
    upload_calls = [call for call in client.calls if call[0] == "upload"]
    download_calls = [call for call in client.calls if call[0] == "download"]
    assert upload_calls
    assert all(call[3] == 0 for call in upload_calls)
    assert download_calls
    assert all(call[2] == call[3] == 1 for call in download_calls)
