from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import _score_matrix_sha256


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}
FIXTURE_WORLDS_PER_BLOCK = 2


@pytest.fixture(autouse=True)
def _align_fixture_selector_world_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise block-aware laws at the explicit reduced fixture width."""
    monkeypatch.setattr(
        retrieval, "WORLDS_PER_BLOCK", FIXTURE_WORLDS_PER_BLOCK
    )


def _roster(index: int) -> list[str]:
    return sorted(f"player-{index:03d}-{slot}" for slot in range(9))


def _provenance(count: int = 100) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        roster = _roster(index)
        lineup_id = v12_import.canonical_lineup_id(SLATE, roster)
        block = rw.WORLD_BLOCKS[index % len(rw.WORLD_BLOCKS)]
        arm_ordinal = index % len(batch.PARAMETER_SET_ORDER)
        arm_id = batch.PARAMETER_SET_ORDER[arm_ordinal]
        occurrence = {
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": arm_id,
            "visit_ordinal": index,
            "block_id": block,
            "objective_world_index": index % 2,
        }
        occurrences = [occurrence]
        if index == 0:
            occurrences.append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": arm_id,
                "visit_ordinal": count,
                "block_id": rw.WORLD_BLOCKS[1],
                "objective_world_index": 1,
            })
        origin_blocks = [
            value
            for value in rw.WORLD_BLOCKS
            if any(item["block_id"] == value for item in occurrences)
        ]
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "origin_blocks": origin_blocks,
            "source_arms": [arm_id],
            "occurrence_counts_by_block": {
                value: sum(
                    int(item["block_id"] == value) for item in occurrences
                )
                for value in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": {
                value: (
                    [arm_id]
                    if any(item["block_id"] == value for item in occurrences)
                    else []
                )
                for value in rw.WORLD_BLOCKS
            },
            "occurrence_count": len(occurrences),
            "occurrences": occurrences,
        })
    rows.sort(key=lambda row: str(row["lineup_id"]))
    body: dict[str, object] = {
        "schema_version": v12_import.PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": "a" * 64,
        "visits_per_block": 2,
        "arm_count": len(batch.PARAMETER_SET_ORDER),
        "visit_occurrence_count": sum(
            int(row["occurrence_count"]) for row in rows
        ),
        "candidate_count": count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": rows,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = batch.canonical_sha256(body)
    return body


def _scores(provenance: dict[str, object]) -> np.ndarray:
    count = len(provenance["candidates"])
    scores = np.full(
        (count, len(rw.WORLD_BLOCKS) * FIXTURE_WORLDS_PER_BLOCK),
        180.0,
        dtype=np.float64,
    )
    # Strict-200 prefers row 2's ten exact-230 events; strict-230 must reject
    # that boundary and prefer row 0's single value immediately above 230.
    scores[0, 0] = np.nextafter(230.0, np.inf)
    scores[1, :] = 205.0
    scores[2, :] = 230.0
    for index in range(3, count):
        scores[index, :] += (index % 17) * 0.1
    return np.ascontiguousarray(scores)


def _reconstruction(
    provenance: dict[str, object], scores: np.ndarray,
) -> dict[str, object]:
    lineup_ids = [
        row["lineup_id"] for row in provenance["candidates"]
    ]
    matrix: dict[str, object] = {
        "schema_version": v12_import.MATRIX_BINDING_SCHEMA,
        "slate": dict(SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": batch.canonical_sha256(lineup_ids),
        "world_ids_sha256": "9" * 64,
        "shape": list(scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(scores),
        "uses_realized_outcomes": False,
    }
    matrix["matrix_binding_sha256"] = batch.canonical_sha256(matrix)
    receipt: dict[str, object] = {
        "schema_version": v12_import.RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": "8" * 64,
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": matrix,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": arm_id,
                "candidate_score_sha256": f"{ordinal + 1:x}" * 64,
                "selected_score_sha256": f"{ordinal + 8:x}" * 64,
                "unique_count": len(lineup_ids),
                "selected_count": lane.ENTRY_BUDGET,
                "verified": True,
            }
            for ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    receipt["reconstruction_sha256"] = batch.canonical_sha256(receipt)
    return receipt


def _surface() -> tuple[
    dict[str, object], np.ndarray, dict[str, object], dict[str, object]
]:
    provenance = _provenance()
    scores = _scores(provenance)
    receipt = _reconstruction(provenance, scores)
    surface = lane.run_full_union_surface_v1(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=receipt,
        worlds_per_block=FIXTURE_WORLDS_PER_BLOCK,
        require_authoritative=False,
    )
    return provenance, scores, receipt, surface


def test_registry_preserves_seven_v2_laws_and_adds_strict_230() -> None:
    strategies = lane.frozen_full_union_strategies_v1()
    assert strategies[:7] == retrieval.frozen_retrieval_strategies_v2(80)
    assert len(strategies) == lane.STRATEGY_COUNT == 8
    assert strategies[-1]["strategy_id"] == lane.STRICT_230_STRATEGY_ID
    assert strategies[-1]["parameters"] == {
        "threshold": 230.0,
        "operator": ">",
    }
    assert strategies[-1]["selection_inputs"] == (
        "discovery-block-simulated-scores-only"
    )


def test_surface_has_six_scopes_48_exact_books_and_no_matchup() -> None:
    _, _, _, surface = _surface()
    assert surface["scope_count"] == lane.SCOPE_COUNT == 6
    assert surface["book_count"] == lane.BOOKS_PER_SLATE == 48
    assert surface["matchup_source_read"] is False
    assert surface["uses_realized_outcomes"] is False
    assert [scope["heldout_block"] for scope in surface["scopes"]] == [
        *rw.WORLD_BLOCKS,
        None,
    ]
    for scope in surface["scopes"]:
        assert scope["book_count"] == lane.BOOKS_PER_SCOPE == 8
        assert scope["admission_mode"] == (
            "complete-fold-eligible-cross-arm-union"
        )
        assert scope["matchup_source_read"] is False
        assert [book["strategy_id"] for book in scope["books"]] == [
            strategy["strategy_id"]
            for strategy in lane.frozen_full_union_strategies_v1()
        ]
        for book in scope["books"]:
            assert book["entry_count"] == 80
            assert len(book["selected_lineup_ids"]) == 80
            assert len(set(book["selected_lineup_ids"])) == 80


def test_rotated_fold_strips_heldout_occurrences_and_restores_all() -> None:
    provenance, _, _, surface = _surface()
    multi_origin = next(
        row
        for row in provenance["candidates"]
        if len(row["origin_blocks"]) > 1
    )
    for ordinal, block in enumerate(rw.WORLD_BLOCKS):
        scope = surface["scopes"][ordinal]
        admitted = set(scope["admission"]["admitted_lineup_ids"])
        expected = {
            row["lineup_id"]
            for row in provenance["candidates"]
            if any(
                occurrence["block_id"] != block
                for occurrence in row["occurrences"]
            )
        }
        assert admitted == expected
        if block in multi_origin["origin_blocks"]:
            assert multi_origin["lineup_id"] in admitted
            projection = next(
                row
                for row in scope["candidate_view"]["eligible_candidates"]
                if row["lineup_id"] == multi_origin["lineup_id"]
            )
            assert block not in projection["training_origin_blocks"]
            assert block not in projection["training_occurrence_counts_by_block"]
            assert projection["training_occurrence_count"] == sum(
                int(occurrence["block_id"] != block)
                for occurrence in multi_origin["occurrences"]
            )
    assert set(surface["scopes"][-1]["admission"]["admitted_lineup_ids"]) == {
        row["lineup_id"] for row in provenance["candidates"]
    }


def test_strict_230_arm_is_behaviorally_distinct_in_final_fit() -> None:
    provenance, scores, _, surface = _surface()
    final_books = {
        book["strategy_id"]: book for book in surface["scopes"][-1]["books"]
    }
    first_200 = final_books["strict-200-coverage-v1"]["marginal_trace"][0]
    first_230 = final_books[lane.STRICT_230_STRATEGY_ID]["marginal_trace"][0]
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    assert np.all(scores[2] == 230.0)
    assert scores[0, 0] == np.nextafter(230.0, np.inf)
    assert first_200["lineup_id"] == lineup_ids[2]
    assert first_230["lineup_id"] == lineup_ids[0]
    assert first_200["lineup_id"] != first_230["lineup_id"]
    assert first_230["tie_break_values"][
        "individual_selector_event_count"
    ] == 1
    assert first_230["tie_break_values"]["selector_event_definition"] == {
        "threshold": 230.0,
        "operator": ">",
    }


def test_surface_canonical_replay_and_coherent_mutation_rejection() -> None:
    provenance, scores, receipt, surface = _surface()
    assert lane.validate_full_union_surface_v1(
        surface,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=receipt,
        worlds_per_block=FIXTURE_WORLDS_PER_BLOCK,
        require_authoritative=False,
    ) == surface
    mutated = deepcopy(surface)
    mutated["full_union_only"] = False
    mutated["full_union_surface_sha256"] = batch.canonical_sha256({
        key: value
        for key, value in mutated.items()
        if key != "full_union_surface_sha256"
    })
    with pytest.raises(lane.CorpusR6FullUnionFastLaneV1Error):
        lane.validate_full_union_surface_v1(
            mutated,
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
            worlds_per_block=FIXTURE_WORLDS_PER_BLOCK,
            require_authoritative=False,
        )


def test_execution_wrapper_retains_exact_predecessors_and_false_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    receipt = _reconstruction(provenance, scores)
    accepted = SimpleNamespace(
        slate_id=SLATE["slate_id"],
        panel_index_identity={
            "uri": "gs://fixture/panel.json",
            "generation": "1",
            "sha256": "1" * 64,
            "bytes": 1,
        },
        panel_index_sha256="2" * 64,
        accepted_slate_membership={"source_task_ordinal": 0},
        task_acceptance_identity={
            "uri": "gs://fixture/acceptance.json",
            "generation": "2",
            "sha256": "3" * 64,
            "bytes": 2,
        },
        carrier_identity={
            "uri": "gs://fixture/carrier.json",
            "generation": "3",
            "sha256": "4" * 64,
            "bytes": 3,
        },
        later_source_freeze_identity={
            "uri": "gs://fixture/source.json",
            "generation": "4",
            "sha256": "5" * 64,
            "bytes": 4,
        },
        world_artifact_identities={
            block: {
                "uri": f"gs://fixture/{block}.npz",
                "generation": str(10 + ordinal),
                "sha256": f"{ordinal + 6:x}" * 64,
                "bytes": 10 + ordinal,
            }
            for ordinal, block in enumerate(rw.WORLD_BLOCKS)
        },
        imported=SimpleNamespace(compatibility_receipt={
            "compatibility_import_sha256": "b" * 64
        }),
        reconstructed=SimpleNamespace(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
        ),
    )
    calls: list[dict[str, object]] = []
    validated_panel = {"fixture": "validated-panel"}
    panel_identity = {"fixture": "panel-identity"}
    accepted_membership = {"fixture": "accepted-membership"}
    task_acceptance_identity = {"fixture": "task-acceptance-identity"}
    carrier_identity = {"fixture": "carrier-identity"}

    def read_exact(identity: Mapping[str, object]) -> bytes:
        assert identity
        return b"fixture"

    def reconstruct(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return accepted

    monkeypatch.setattr(execution, "reconstruct_one_accepted_v12_slate", reconstruct)
    result = lane.execute_one_accepted_slate_full_union_v1(
        validated_panel_index=validated_panel,
        panel_index_identity=panel_identity,
        accepted_slate_membership=accepted_membership,
        task_acceptance_identity=task_acceptance_identity,
        carrier_identity=carrier_identity,
        read_exact=read_exact,
        worlds_per_block=FIXTURE_WORLDS_PER_BLOCK,
        require_authoritative=False,
    )
    assert calls == [{
        "validated_panel_index": validated_panel,
        "panel_index_identity": panel_identity,
        "accepted_slate_membership": accepted_membership,
        "task_acceptance_identity": task_acceptance_identity,
        "carrier_identity": carrier_identity,
        "read_exact": read_exact,
        "require_authoritative": False,
    }]
    assert result["schema_version"] == lane.EXECUTION_SCHEMA
    assert result["slate_id"] == accepted.slate_id
    assert result["panel_index_identity"] == accepted.panel_index_identity
    assert result["panel_index_sha256"] == accepted.panel_index_sha256
    assert result["accepted_slate_membership"] == (
        accepted.accepted_slate_membership
    )
    assert result["accepted_slate_membership_sha256"] == (
        batch.canonical_sha256(accepted.accepted_slate_membership)
    )
    assert result["task_acceptance_identity"] == (
        accepted.task_acceptance_identity
    )
    assert result["carrier_identity"] == accepted.carrier_identity
    assert result["later_source_freeze_identity"] == (
        accepted.later_source_freeze_identity
    )
    assert result["world_artifact_identities"] == (
        accepted.world_artifact_identities
    )
    assert result["world_artifact_identity_set_sha256"] == (
        batch.canonical_sha256(accepted.world_artifact_identities)
    )
    assert result["compatibility_import_sha256"] == "b" * 64
    assert result["candidate_provenance_sha256"] == (
        provenance["candidate_provenance_sha256"]
    )
    assert result["reconstruction_sha256"] == receipt[
        "reconstruction_sha256"
    ]
    assert result["full_union_surface"]["book_count"] == 48
    assert result["verification"]["all_48_books_materialized"] is True
    assert result["verification"]["matchup_source_not_read"] is True
    for field in lane._FALSE_EXECUTION_AUTHORITY_FIELDS:
        assert result[field] is False
    assert result["task_result_sha256"] == batch.canonical_sha256({
        key: value for key, value in result.items()
        if key != "task_result_sha256"
    })


def test_authoritative_dose_rejects_reduced_fixture_width_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    receipt = _reconstruction(provenance, scores)
    dispatched = 0

    def forbidden(**_: object) -> dict[str, object]:
        nonlocal dispatched
        dispatched += 1
        raise AssertionError("selector dispatched")

    monkeypatch.setattr(runner, "_run_book", forbidden)
    assert FIXTURE_WORLDS_PER_BLOCK != rw.WORLDS_PER_BLOCK == 10_000
    with pytest.raises(
        lane.CorpusR6FullUnionFastLaneV1Error,
        match="authoritative R6-v2 requires",
    ):
        lane.run_full_union_surface_v1(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
            worlds_per_block=FIXTURE_WORLDS_PER_BLOCK,
            require_authoritative=True,
        )
    assert dispatched == 0


def test_wrong_matrix_hash_fails_before_any_book_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    receipt = _reconstruction(provenance, scores)
    receipt["matrix_binding"]["score_matrix_sha256"] = "f" * 64
    receipt["matrix_binding"]["matrix_binding_sha256"] = batch.canonical_sha256({
        key: value
        for key, value in receipt["matrix_binding"].items()
        if key != "matrix_binding_sha256"
    })
    receipt["reconstruction_sha256"] = batch.canonical_sha256({
        key: value for key, value in receipt.items()
        if key != "reconstruction_sha256"
    })
    dispatched = 0

    def forbidden(**_: object) -> dict[str, object]:
        nonlocal dispatched
        dispatched += 1
        raise AssertionError("selector dispatched")

    monkeypatch.setattr(runner, "_run_book", forbidden)
    with pytest.raises(lane.CorpusR6FullUnionFastLaneV1Error):
        lane.run_full_union_surface_v1(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
            worlds_per_block=FIXTURE_WORLDS_PER_BLOCK,
            require_authoritative=False,
        )
    assert dispatched == 0
