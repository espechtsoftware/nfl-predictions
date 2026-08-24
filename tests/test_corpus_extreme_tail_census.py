from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    _score_matrix_sha256,
    canonical_sha256,
)
from nfl_dfs.research.corpus_parametric_batch import PARAMETER_SET_ORDER
from nfl_dfs.research.corpus_v12_import import (
    MATRIX_BINDING_SCHEMA,
    PROVENANCE_SCHEMA,
    RECONSTRUCTION_SCHEMA,
    canonical_lineup_id,
)


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}


def _roster(index: int) -> list[str]:
    return sorted(f"tail-player-{index:03d}-{slot}" for slot in range(9))


def _provenance(count: int = 90) -> dict[str, object]:
    if count != 90:
        raise ValueError("the census fixture requires exactly 90 candidates")
    rosters = [_roster(index) for index in range(count)]
    lineup_ids = [canonical_lineup_id(SLATE, roster) for roster in rosters]
    occurrences_by_index: dict[int, list[dict[str, object]]] = {
        index: [] for index in range(count)
    }
    visits_per_block = 16
    visits_per_arm = len(rw.WORLD_BLOCKS) * visits_per_block
    schedule = [
        {
            "block": rw.WORLD_BLOCKS[visit // visits_per_block],
            "index": visit % visits_per_block,
        }
        for visit in range(visits_per_arm)
    ]
    for arm_ordinal, arm in enumerate(PARAMETER_SET_ORDER):
        for visit_ordinal, world in enumerate(schedule):
            candidate_index = (visit_ordinal + arm_ordinal * 13) % 89
            if arm_ordinal == 0 and visit_ordinal == visits_per_arm - 1:
                candidate_index = 89
            occurrences_by_index[candidate_index].append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": arm,
                "visit_ordinal": visit_ordinal,
                "block_id": world["block"],
                "objective_world_index": world["index"],
            })

    rows: list[dict[str, object]] = []
    for index in range(count):
        occurrences = occurrences_by_index[index]
        block_counts = {
            block: sum(
                occurrence["block_id"] == block for occurrence in occurrences
            )
            for block in rw.WORLD_BLOCKS
        }
        rows.append({
            "lineup_id": lineup_ids[index],
            "roster_player_ids": rosters[index],
            "origin_blocks": [
                block for block in rw.WORLD_BLOCKS if block_counts[block]
            ],
            "source_arms": sorted({
                occurrence["parameter_set_id"] for occurrence in occurrences
            }),
            "occurrence_counts_by_block": block_counts,
            "source_arms_by_block": {
                block: sorted({
                    occurrence["parameter_set_id"]
                    for occurrence in occurrences
                    if occurrence["block_id"] == block
                })
                for block in rw.WORLD_BLOCKS
            },
            "occurrence_count": len(occurrences),
            "occurrences": occurrences,
        })
    rows.sort(key=lambda row: str(row["lineup_id"]))
    body: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": canonical_sha256(schedule),
        "visits_per_block": visits_per_block,
        "arm_count": len(PARAMETER_SET_ORDER),
        "visit_occurrence_count": (
            len(PARAMETER_SET_ORDER) * visits_per_arm
        ),
        "candidate_count": count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": rows,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = canonical_sha256(body)
    return body


def _exact_dose_provenance() -> dict[str, object]:
    visits_per_block = 200
    visits_per_arm = len(rw.WORLD_BLOCKS) * visits_per_block
    schedule = [
        {
            "block": rw.WORLD_BLOCKS[visit // visits_per_block],
            "index": visit % visits_per_block,
        }
        for visit in range(visits_per_arm)
    ]
    rows: list[dict[str, object]] = []
    for visit, world in enumerate(schedule):
        roster = _roster(visit)
        occurrences = [
            {
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": arm,
                "visit_ordinal": visit,
                "block_id": world["block"],
                "objective_world_index": world["index"],
            }
            for arm_ordinal, arm in enumerate(PARAMETER_SET_ORDER)
        ]
        rows.append({
            "lineup_id": canonical_lineup_id(SLATE, roster),
            "roster_player_ids": roster,
            "origin_blocks": [world["block"]],
            "source_arms": sorted(PARAMETER_SET_ORDER),
            "occurrence_counts_by_block": {
                block: (
                    len(PARAMETER_SET_ORDER)
                    if block == world["block"] else 0
                )
                for block in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": {
                block: (
                    sorted(PARAMETER_SET_ORDER)
                    if block == world["block"] else []
                )
                for block in rw.WORLD_BLOCKS
            },
            "occurrence_count": len(PARAMETER_SET_ORDER),
            "occurrences": occurrences,
        })
    rows.sort(key=lambda row: str(row["lineup_id"]))
    body: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": canonical_sha256(schedule),
        "visits_per_block": visits_per_block,
        "arm_count": len(PARAMETER_SET_ORDER),
        "visit_occurrence_count": (
            len(PARAMETER_SET_ORDER) * visits_per_arm
        ),
        "candidate_count": visits_per_arm,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": rows,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = canonical_sha256(body)
    return body


def _scores(provenance: dict[str, object]) -> np.ndarray:
    scores = np.full((len(provenance["candidates"]), 10), 100.0)
    eligible = [
        index for index, row in enumerate(provenance["candidates"])
        if row["origin_blocks"] != ["R4"]
    ]
    for index, column, value in zip(
        eligible[:4], (0, 2, 4, 6), (220.0, 230.0, 240.0, 250.0), strict=True
    ):
        scores[index, column] = value
    scores[eligible[4], 1] = np.nextafter(220.0, -np.inf)
    scores[eligible[0], 2] = 230.0
    heldout_only = next(
        index for index, row in enumerate(provenance["candidates"])
        if row["origin_blocks"] == ["R4"]
    )
    scores[heldout_only, 8:10] = 999.0
    return np.ascontiguousarray(scores, dtype=np.float64)


def _reconstruction(
    provenance: dict[str, object], scores: np.ndarray
) -> dict[str, object]:
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    worlds_per_block = scores.shape[1] // len(rw.WORLD_BLOCKS)
    binding: dict[str, object] = {
        "schema_version": MATRIX_BINDING_SCHEMA,
        "slate": dict(SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": canonical_sha256(lineup_ids),
        "world_ids_sha256": canonical_sha256(_world_ids(worlds_per_block)),
        "shape": list(scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(scores),
        "uses_realized_outcomes": False,
    }
    binding["matrix_binding_sha256"] = canonical_sha256(binding)
    body: dict[str, object] = {
        "schema_version": RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": "8" * 64,
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": binding,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": arm,
                "candidate_score_sha256": f"{ordinal + 1:x}" * 64,
                "selected_score_sha256": f"{ordinal + 8:x}" * 64,
                "unique_count": sum(
                    arm in row["source_arms"]
                    for row in provenance["candidates"]
                ),
                "selected_count": 80,
                "verified": True,
            }
            for ordinal, arm in enumerate(PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    body["reconstruction_sha256"] = canonical_sha256(body)
    return body


def _world_ids(worlds_per_block: int = 2) -> list[dict[str, object]]:
    return [
        {"block": block, "index": index}
        for block in rw.WORLD_BLOCKS for index in range(worlds_per_block)
    ]


def _build() -> tuple[dict[str, object], dict[str, object], np.ndarray]:
    provenance = _provenance()
    scores = _scores(provenance)
    result = census.build_extreme_tail_support_census(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        world_ids=_world_ids(),
        worlds_per_block=2,
        require_authoritative=False,
    )
    return result, provenance, scores


def _universe(result: dict[str, object], universe_id: str) -> dict[str, object]:
    return next(
        row for row in result["universes"]
        if row["universe_id"] == universe_id
    )


def _threshold(metrics: dict[str, object], label: str) -> dict[str, object]:
    return next(row for row in metrics["thresholds"] if row["label"] == label)


def test_census_uses_inclusive_tail_semantics_and_exact_opportunity_counts() -> None:
    result, _, _ = _build()
    final_union = _universe(result, "cross-arm-all-block-union")
    metrics = final_union["training_metrics"]

    assert result["threshold_registry"] == [
        {"threshold_id": "ge_220", "score": 220.0, "operator": ">="},
        {"threshold_id": "ge_230", "score": 230.0, "operator": ">="},
        {"threshold_id": "ge_240", "score": 240.0, "operator": ">="},
        {"threshold_id": "ge_250", "score": 250.0, "operator": ">="},
    ]
    assert _threshold(metrics, "ge_220")["opportunity_world_count"] == 6
    assert _threshold(metrics, "ge_230")["opportunity_world_count"] == 5
    assert _threshold(metrics, "ge_240")["opportunity_world_count"] == 4
    assert _threshold(metrics, "ge_250")["opportunity_world_count"] == 3
    assert _threshold(metrics, "ge_250")["lineup_world_event_count"] == 3
    assert _threshold(metrics, "ge_250")["event_union_efficiency_fraction"] == {
        "numerator": 3,
        "denominator": 3,
    }
    assert _threshold(metrics, "ge_220")["opportunity_rate_fraction"] == {
        "numerator": 6,
        "denominator": 10,
    }
    assert result["uses_realized_outcomes"] is False
    for field in (
        "historical_scoring_licensed",
        "corpus_fill_licensed",
        "graph_mutation_licensed",
        "production_change_licensed",
        "automatic_retry_licensed",
        "live_policy_access_licensed",
        "r6_freeze_authority",
        "analytical_authority",
        "promotion_authority",
        "decision_authority",
    ):
        assert result[field] is False


def test_holdout_only_candidate_is_excluded_before_tail_evaluation() -> None:
    result, _, _ = _build()
    fold = _universe(result, "cross-arm-fold-eligible:holdout-R4")

    assert fold["lineup_count"] == 89
    assert fold["heldout_only_excluded_lineup_count"] == 1
    assert _threshold(
        fold["heldout_metrics_descriptive"], "ge_250"
    )["opportunity_world_count"] == 0
    assert _threshold(
        fold["training_metrics"], "ge_230"
    )["opportunity_world_count"] == 3
    observation = next(
        row for row in result["coverage_ge_230_support_gate"]["fold_observations"]
        if row["heldout_block"] == "R4"
    )
    assert observation == {
        "heldout_block": "R4",
        "training_blocks": ["R0", "R1", "R2", "R3"],
        "every_training_block_nonzero": False,
        "training_opportunity_world_count": 3,
        "nomination_support_passed": False,
    }


def test_census_contains_exact_canonical_thirteen_universes() -> None:
    result, _, _ = _build()

    assert result["universe_count"] == 13
    assert [row["parameter_set_id"] for row in result["universes"][:7]] == list(
        PARAMETER_SET_ORDER
    )
    assert [row["heldout_block"] for row in result["universes"][7:12]] == list(
        rw.WORLD_BLOCKS
    )
    assert result["universes"][-1]["universe_id"] == (
        "cross-arm-all-block-union"
    )
    assert result["source_arm_order"] == list(census.SOURCE_ARM_ORDER)
    assert result["source_arm_order_sha256"] == (
        census.SOURCE_ARM_ORDER_SHA256
    )
    final_support = result["universes"][-1]["source_support"]
    assert final_support["training_visit_occurrence_count_total"] == 560
    assert final_support["distinct_training_arm_visit_count"] == 560
    assert (
        final_support[
            "candidate_counts_are_nonexclusive_across_arms_and_blocks"
        ]
        is True
    )
    assert (
        final_support[
            "occurrence_counts_partition_occurrences_by_arm_and_block"
        ]
        is True
    )
    assert sum(
        final_support["candidate_count_by_training_source_arm"].values()
    ) > final_support["candidate_count"]
    assert sum(
        final_support["training_occurrence_count_by_source_arm"].values()
    ) == final_support["training_visit_occurrence_count_total"]
    assert sum(
        final_support["training_occurrence_count_by_block"].values()
    ) == final_support["training_visit_occurrence_count_total"]

    ge_230 = _threshold(
        result["universes"][-1]["training_metrics"], "ge_230"
    )
    assert ge_230["event_score_block_breadth_histogram"] != (
        ge_230[
            "event_positive_lineup_generation_origin_block_breadth_histogram"
        ]
    )


def test_census_replay_is_exact_and_rejects_tampering_or_matrix_drift() -> None:
    result, provenance, scores = _build()
    reconstruction = _reconstruction(provenance, scores)
    replayed = census.validate_extreme_tail_support_census(
        result,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=reconstruction,
        world_ids=_world_ids(),
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert replayed == result

    tampered = deepcopy(result)
    tampered["universes"][0]["lineup_count"] += 1
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="canonical replay differs",
    ):
        census.validate_extreme_tail_support_census(
            tampered,
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction,
            world_ids=_world_ids(),
            worlds_per_block=2,
            require_authoritative=False,
        )

    drifted = scores.copy()
    drifted[0, 0] += 0.25
    with pytest.raises(census.CorpusExtremeTailCensusError):
        census.build_extreme_tail_support_census(
            provenance=provenance,
            union_scores=drifted,
            reconstruction_receipt=reconstruction,
            world_ids=_world_ids(),
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_heldout_score_changes_do_not_change_training_support_or_gate() -> None:
    result, provenance, scores = _build()
    changed = scores.copy()
    eligible = next(
        index for index, row in enumerate(provenance["candidates"])
        if row["origin_blocks"] != ["R4"]
    )
    changed[eligible, 8:10] = 999.0
    changed_result = census.build_extreme_tail_support_census(
        provenance=provenance,
        union_scores=changed,
        reconstruction_receipt=_reconstruction(provenance, changed),
        world_ids=_world_ids(),
        worlds_per_block=2,
        require_authoritative=False,
    )
    original_fold = _universe(
        result, "cross-arm-fold-eligible:holdout-R4"
    )
    changed_fold = _universe(
        changed_result, "cross-arm-fold-eligible:holdout-R4"
    )
    assert changed_fold["training_metrics"] == original_fold["training_metrics"]
    assert changed_fold["heldout_metrics_descriptive"] != (
        original_fold["heldout_metrics_descriptive"]
    )
    original_gate = next(
        row for row in result["coverage_ge_230_support_gate"]["fold_observations"]
        if row["heldout_block"] == "R4"
    )
    changed_gate = next(
        row for row in changed_result[
            "coverage_ge_230_support_gate"
        ]["fold_observations"]
        if row["heldout_block"] == "R4"
    )
    assert changed_gate == original_gate


def test_chunk_size_does_not_change_canonical_census_or_r6_registry(
    monkeypatch,
) -> None:
    baseline_registry = runner._validate_strategy_registry()
    baseline, provenance, scores = _build()
    monkeypatch.setattr(census, "_CANDIDATE_CHUNK_ROWS", 7)
    rechunked = census.build_extreme_tail_support_census(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        world_ids=_world_ids(),
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert rechunked == baseline
    assert runner._validate_strategy_registry() == baseline_registry

    reconstruction = _reconstruction(provenance, scores)
    wrong_world_ids = deepcopy(_world_ids())
    wrong_world_ids[0], wrong_world_ids[1] = wrong_world_ids[1], wrong_world_ids[0]
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="canonical block-major R order",
    ):
        census.build_extreme_tail_support_census(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction,
            world_ids=wrong_world_ids,
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_rehashed_reconstruction_with_wrong_world_hash_is_rejected() -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    reconstruction = _reconstruction(provenance, scores)
    binding = reconstruction["matrix_binding"]
    binding["world_ids_sha256"] = "0" * 64
    binding.pop("matrix_binding_sha256")
    binding["matrix_binding_sha256"] = canonical_sha256(binding)
    reconstruction.pop("reconstruction_sha256")
    reconstruction["reconstruction_sha256"] = canonical_sha256(reconstruction)

    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="differ from the reconstruction binding",
    ):
        census.build_extreme_tail_support_census(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction,
            world_ids=_world_ids(),
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_source_arm_universe_reconciles_verified_unique_count() -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    reconstruction = _reconstruction(provenance, scores)
    reconstruction["verified_arm_score_hashes"][0]["unique_count"] += 1
    reconstruction.pop("reconstruction_sha256")
    reconstruction["reconstruction_sha256"] = canonical_sha256(reconstruction)

    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="verified unique-candidate count",
    ):
        census.build_extreme_tail_support_census(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction,
            world_ids=_world_ids(),
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_mixed_origin_candidate_is_retained_but_holdout_lineage_is_stripped() -> None:
    result, provenance, scores = _build()
    mixed = next(
        row for row in provenance["candidates"]
        if "R4" in row["origin_blocks"] and len(row["origin_blocks"]) > 1
    )
    expected_view = runner.build_fit_candidate_view(
        provenance,
        heldout_block="R4",
        dose_authority=runner.FIXTURE_DOSE,
    )
    expected_ids = [
        row["lineup_id"] for row in expected_view["eligible_candidates"]
    ]
    expected_occurrences = [
        occurrence
        for row in provenance["candidates"]
        if row["lineup_id"] in expected_ids
        for occurrence in row["occurrences"]
        if occurrence["block_id"] != "R4"
    ]
    fold = _universe(result, "cross-arm-fold-eligible:holdout-R4")
    support = fold["source_support"]

    assert mixed["lineup_id"] in expected_ids
    assert fold["lineup_ids_sha256"] == canonical_sha256(expected_ids)
    assert fold["fit_candidate_view_sha256"] == (
        expected_view["fit_candidate_view_sha256"]
    )
    assert fold["selection_provenance_sha256"] == (
        expected_view["selection_provenance_sha256"]
    )
    assert support["candidate_count_by_training_origin_block"]["R4"] == 0
    assert support["training_occurrence_count_by_block"]["R4"] == 0
    assert support["training_visit_occurrence_count_total"] == len(
        expected_occurrences
    )
    assert support["training_occurrence_count_by_source_arm"] == {
        arm: sum(
            occurrence["parameter_set_id"] == arm
            for occurrence in expected_occurrences
        )
        for arm in PARAMETER_SET_ORDER
    }

    index_by_id = {
        row["lineup_id"]: index
        for index, row in enumerate(provenance["candidates"])
    }
    event_ids = {
        lineup_id for lineup_id in expected_ids
        if np.any(scores[index_by_id[lineup_id], :8] >= 230.0)
    }
    event_occurrences = [
        occurrence
        for row in provenance["candidates"]
        if row["lineup_id"] in event_ids
        for occurrence in row["occurrences"]
        if occurrence["block_id"] != "R4"
    ]
    event_lineage = _threshold(
        fold["training_metrics"], "ge_230"
    )["event_source_lineage"]
    assert event_lineage[
        "event_lineup_counts_are_nonexclusive_across_arms_and_blocks"
    ] is True
    assert event_lineage[
        "event_occurrence_counts_partition_occurrences_by_arm_and_block"
    ] is True
    assert event_lineage[
        "event_training_occurrence_count_by_origin_block"
    ] == {
        block: sum(
            occurrence["block_id"] == block
            for occurrence in event_occurrences
        )
        for block in rw.WORLD_BLOCKS
    }
    assert event_lineage[
        "event_training_occurrence_count_by_source_arm"
    ] == {
        arm: sum(
            occurrence["parameter_set_id"] == arm
            for occurrence in event_occurrences
        )
        for arm in PARAMETER_SET_ORDER
    }

    changed_provenance = deepcopy(provenance)
    changed_mixed = next(
        row for row in changed_provenance["candidates"]
        if row["lineup_id"] == mixed["lineup_id"]
    )
    changed_heldout_occurrence = next(
        occurrence for occurrence in changed_mixed["occurrences"]
        if occurrence["block_id"] == "R4"
    )
    changed_heldout_occurrence["objective_world_index"] = (
        int(changed_heldout_occurrence["objective_world_index"]) + 997
    ) % rw.WORLDS_PER_BLOCK
    changed_provenance.pop("candidate_provenance_sha256")
    changed_provenance["candidate_provenance_sha256"] = canonical_sha256(
        changed_provenance
    )
    changed_result = census.build_extreme_tail_support_census(
        provenance=changed_provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(changed_provenance, scores),
        world_ids=_world_ids(),
        worlds_per_block=2,
        require_authoritative=False,
    )
    changed_fold = _universe(
        changed_result, "cross-arm-fold-eligible:holdout-R4"
    )
    assert changed_fold["fit_candidate_view_sha256"] == (
        fold["fit_candidate_view_sha256"]
    )
    assert changed_fold["selection_provenance_sha256"] == (
        fold["selection_provenance_sha256"]
    )
    assert changed_fold["source_support"] == fold["source_support"]
    assert changed_fold["training_metrics"] == fold["training_metrics"]
    changed_gate = next(
        row for row in changed_result[
            "coverage_ge_230_support_gate"
        ]["fold_observations"]
        if row["heldout_block"] == "R4"
    )
    original_gate = next(
        row for row in result[
            "coverage_ge_230_support_gate"
        ]["fold_observations"]
        if row["heldout_block"] == "R4"
    )
    assert changed_gate == original_gate


def test_independent_tail_oracle_covers_hashes_blocks_zero_and_nesting() -> None:
    result, provenance, scores = _build()
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    metrics = _universe(
        result, "cross-arm-all-block-union"
    )["training_metrics"]
    prior_opportunity_count = scores.shape[1] + 1
    prior_event_count = scores.size + 1

    for label, threshold, _ in census.THRESHOLDS:
        event = scores >= threshold
        event_lineup_ids = [
            lineup_id for lineup_id, positive
            in zip(lineup_ids, event.any(axis=1), strict=True)
            if bool(positive)
        ]
        opportunity_world_ids = [
            world_id for world_id, positive
            in zip(_world_ids(), event.any(axis=0), strict=True)
            if bool(positive)
        ]
        observed = _threshold(metrics, label)
        assert observed["event_lineup_count"] == len(event_lineup_ids)
        assert observed["event_lineup_ids_sha256"] == canonical_sha256(
            event_lineup_ids
        )
        assert observed["lineup_world_event_count"] == int(event.sum())
        assert observed["opportunity_world_count"] == len(
            opportunity_world_ids
        )
        assert observed["opportunity_world_ids_sha256"] == canonical_sha256(
            opportunity_world_ids
        )
        assert observed["event_union_efficiency_fraction"] == {
            "numerator": len(opportunity_world_ids),
            "denominator": int(event.sum()),
        }
        assert observed["opportunity_world_count"] <= prior_opportunity_count
        assert observed["lineup_world_event_count"] <= prior_event_count
        prior_opportunity_count = observed["opportunity_world_count"]
        prior_event_count = observed["lineup_world_event_count"]

        for block_ordinal, block in enumerate(rw.WORLD_BLOCKS):
            start = block_ordinal * 2
            stop = start + 2
            block_event = event[:, start:stop]
            block_metric = next(
                row for row in observed["by_block"]
                if row["block_id"] == block
            )
            assert block_metric["lineup_world_event_count"] == int(
                block_event.sum()
            )
            block_lineup_ids = [
                lineup_id for lineup_id, positive
                in zip(lineup_ids, block_event.any(axis=1), strict=True)
                if bool(positive)
            ]
            block_world_ids = _world_ids()[start:stop]
            block_opportunity_ids = [
                world_id for world_id, positive
                in zip(
                    block_world_ids,
                    block_event.any(axis=0),
                    strict=True,
                )
                if bool(positive)
            ]
            assert block_metric["world_ids_sha256"] == canonical_sha256(
                block_world_ids
            )
            assert block_metric["event_lineup_ids_sha256"] == canonical_sha256(
                block_lineup_ids
            )
            assert block_metric[
                "opportunity_world_ids_sha256"
            ] == canonical_sha256(block_opportunity_ids)
            assert block_metric["opportunity_world_count"] == int(
                block_event.any(axis=0).sum()
            )
            expected_efficiency = (
                None if not int(block_event.sum()) else {
                    "numerator": len(block_opportunity_ids),
                    "denominator": int(block_event.sum()),
                }
            )
            assert block_metric[
                "event_union_efficiency_fraction"
            ] == expected_efficiency

    empty_scores = np.full(scores.shape, 100.0, dtype=np.float64)
    empty = census.build_extreme_tail_support_census(
        provenance=provenance,
        union_scores=empty_scores,
        reconstruction_receipt=_reconstruction(provenance, empty_scores),
        world_ids=_world_ids(),
        worlds_per_block=2,
        require_authoritative=False,
    )
    empty_ge_250 = _threshold(
        _universe(
            empty, "cross-arm-all-block-union"
        )["training_metrics"],
        "ge_250",
    )
    assert empty_ge_250["event_lineup_count"] == 0
    assert empty_ge_250["lineup_world_event_count"] == 0
    assert empty_ge_250["opportunity_world_count"] == 0
    assert empty_ge_250["event_lineup_ids_sha256"] == canonical_sha256([])
    assert empty_ge_250["opportunity_world_ids_sha256"] == canonical_sha256([])
    assert empty_ge_250["event_union_efficiency_fraction"] is None


def test_fixture_dose_cannot_claim_authoritative_generation() -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="exact 7x5x200 dose",
    ):
        census._validate_arm_membership_and_authoritative_dose(
            candidates=provenance["candidates"],
            provenance=provenance,
            reconstruction_receipt=_reconstruction(provenance, scores),
            require_authoritative=True,
        )


def test_exact_authoritative_dose_replays_and_rejects_schedule_drift() -> None:
    provenance = _exact_dose_provenance()
    candidates = runner._validate_provenance(provenance)
    scores = np.zeros((len(candidates), 5), dtype=np.float64)
    reconstruction = _reconstruction(provenance, scores)

    assert census._validate_arm_membership_and_authoritative_dose(
        candidates=candidates,
        provenance=provenance,
        reconstruction_receipt=reconstruction,
        require_authoritative=True,
    ) == {arm: 1000 for arm in PARAMETER_SET_ORDER}

    imbalanced_candidates = deepcopy(candidates)
    moved = next(
        occurrence
        for row in imbalanced_candidates
        for occurrence in row["occurrences"]
        if occurrence["arm_ordinal"] == 0
        and occurrence["visit_ordinal"] == 0
    )
    moved.update({
        "arm_ordinal": 1,
        "parameter_set_id": PARAMETER_SET_ORDER[1],
        "visit_ordinal": 1000,
    })
    imbalanced_receipt = deepcopy(reconstruction)
    imbalanced_receipt["verified_arm_score_hashes"][0]["unique_count"] = 999
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="visit dose/ordinal",
    ):
        census._validate_arm_membership_and_authoritative_dose(
            candidates=imbalanced_candidates,
            provenance=provenance,
            reconstruction_receipt=imbalanced_receipt,
            require_authoritative=True,
        )

    shifted_candidates = deepcopy(candidates)
    shifted = {
        occurrence["visit_ordinal"]: occurrence
        for row in shifted_candidates
        for occurrence in row["occurrences"]
        if occurrence["arm_ordinal"] == 1
        and occurrence["visit_ordinal"] in {0, 1}
    }
    shifted[0]["objective_world_index"], shifted[1][
        "objective_world_index"
    ] = (
        shifted[1]["objective_world_index"],
        shifted[0]["objective_world_index"],
    )
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="mapping differs across arms",
    ):
        census._validate_arm_membership_and_authoritative_dose(
            candidates=shifted_candidates,
            provenance=provenance,
            reconstruction_receipt=reconstruction,
            require_authoritative=True,
        )

    wrong_hash_provenance = dict(provenance)
    wrong_hash_provenance["visit_schedule_sha256"] = "0" * 64
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="schedule hash differs",
    ):
        census._validate_arm_membership_and_authoritative_dose(
            candidates=candidates,
            provenance=wrong_hash_provenance,
            reconstruction_receipt=reconstruction,
            require_authoritative=True,
        )


@pytest.mark.parametrize(
    "drifted_order",
    (
        tuple(reversed(census.SOURCE_ARM_ORDER)),
        census.SOURCE_ARM_ORDER[:-1] + (census.SOURCE_ARM_ORDER[-2],),
    ),
)
def test_frozen_source_arm_order_rejects_reorder_or_duplicate(
    monkeypatch, drifted_order: tuple[str, ...]
) -> None:
    monkeypatch.setattr(census, "PARAMETER_SET_ORDER", drifted_order)
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="frozen v12 source-arm order differs",
    ):
        census._validate_source_arm_order()


def test_matrix_preflight_rejects_noncontiguous_and_chunk_detects_nan() -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    noncontiguous = np.asfortranarray(scores)
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="C-contiguous",
    ):
        census.build_extreme_tail_support_census(
            provenance=provenance,
            union_scores=noncontiguous,
            reconstruction_receipt=_reconstruction(provenance, noncontiguous),
            world_ids=_world_ids(),
            worlds_per_block=2,
            require_authoritative=False,
        )

    nonfinite = scores.copy()
    nonfinite[-1, -1] = np.nan
    with pytest.raises(
        census.CorpusExtremeTailCensusError,
        match="non-finite",
    ):
        census.build_extreme_tail_support_census(
            provenance=provenance,
            union_scores=nonfinite,
            reconstruction_receipt=_reconstruction(provenance, nonfinite),
            world_ids=_world_ids(),
            worlds_per_block=2,
            require_authoritative=False,
        )


def _gate_observation(
    scores: np.ndarray,
    provenance: dict[str, object],
    *,
    worlds_per_block: int,
) -> dict[str, object]:
    result = census.build_extreme_tail_support_census(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        world_ids=_world_ids(worlds_per_block),
        worlds_per_block=worlds_per_block,
        require_authoritative=False,
    )
    return next(
        row for row in result["coverage_ge_230_support_gate"]["fold_observations"]
        if row["heldout_block"] == "R4"
    )


def test_literal_230_support_gate_exact_boundaries_and_every_block_law() -> None:
    provenance = _provenance()
    eligible = next(
        index for index, row in enumerate(provenance["candidates"])
        if row["origin_blocks"] != ["R4"]
    )
    worlds_per_block = 25
    scores_100 = np.full((90, 125), 100.0, dtype=np.float64)
    scores_100[eligible, :100] = 230.0
    at_100 = _gate_observation(
        scores_100, provenance, worlds_per_block=worlds_per_block
    )
    assert at_100["training_opportunity_world_count"] == 100
    assert at_100["every_training_block_nonzero"] is True
    assert at_100["nomination_support_passed"] is True

    scores_99 = scores_100.copy()
    scores_99[eligible, 99] = 100.0
    at_99 = _gate_observation(
        scores_99, provenance, worlds_per_block=worlds_per_block
    )
    assert at_99["training_opportunity_world_count"] == 99
    assert at_99["every_training_block_nonzero"] is True
    assert at_99["nomination_support_passed"] is False

    worlds_per_block = 34
    one_zero_block = np.full((90, 170), 100.0, dtype=np.float64)
    one_zero_block[eligible, :102] = 230.0
    zero_block = _gate_observation(
        one_zero_block, provenance, worlds_per_block=worlds_per_block
    )
    assert zero_block["training_opportunity_world_count"] == 102
    assert zero_block["every_training_block_nonzero"] is False
    assert zero_block["nomination_support_passed"] is False
