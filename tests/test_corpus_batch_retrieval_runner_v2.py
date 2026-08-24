from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import corpus_retrieval_engine as retrieval
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
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}


def _roster(index: int) -> list[str]:
    return sorted(f"player-{index:03d}-{slot}" for slot in range(9))


def _provenance(count: int = 90) -> dict[str, object]:
    rows = []
    for index in range(count):
        roster = _roster(index)
        lineup_id = canonical_lineup_id(SLATE, roster)
        block = "R4" if index == count - 1 else rw.WORLD_BLOCKS[index % 4]
        arm_ordinal = index % len(PARAMETER_SET_ORDER)
        occurrences = [{
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": PARAMETER_SET_ORDER[arm_ordinal],
            "visit_ordinal": index,
            "block_id": block,
            "objective_world_index": index % 2,
        }]
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "origin_blocks": [block],
            "source_arms": [PARAMETER_SET_ORDER[arm_ordinal]],
            "occurrence_counts_by_block": {
                value: int(value == block) for value in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": {
                value: (
                    [PARAMETER_SET_ORDER[arm_ordinal]] if value == block else []
                )
                for value in rw.WORLD_BLOCKS
            },
            "occurrence_count": 1,
            "occurrences": occurrences,
        })
    rows.sort(key=lambda row: row["lineup_id"])
    body: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": "a" * 64,
        "visits_per_block": 2,
        "arm_count": 7,
        "visit_occurrence_count": count,
        "candidate_count": count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": rows,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = canonical_sha256(body)
    return body


def _matchup_rows(provenance: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for ordinal, candidate in enumerate(provenance["candidates"]):
        for player_offset, player_id in enumerate(
            candidate["roster_player_ids"][:8]
        ):
            rows.append({
                "gsis_id": player_id,
                "family": (
                    "qb" if player_offset == 0
                    else "rb" if player_offset in {1, 2}
                    else "receiver"
                ),
                "matchup_edge_score": float(ordinal + player_offset / 10),
            })
    return rows


def _eligible_players(provenance: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for candidate in provenance["candidates"]:
        for player_offset, player_id in enumerate(
            candidate["roster_player_ids"][:8]
        ):
            if player_offset == 0:
                family, position, depth = "qb", "QB", True
            elif player_offset in {1, 2}:
                family, position, depth = "rb", "RB", None
            else:
                family, position, depth = "receiver", "WR", None
            rows.append({
                "gsis_id": player_id,
                "family": family,
                "position": position,
                "qb_depth1": depth,
            })
    return rows


def _object_identity(name: str) -> dict[str, object]:
    raw = name.encode()
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _matchup_source(
    provenance: dict[str, object],
    *,
    rows: list[dict[str, object]] | None = None,
    eligible_players: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return runner.build_matchup_source_snapshot(
        slate=SLATE,
        lock_time_utc="2023-09-10T17:00:00Z",
        maximum_source_time_utc="2023-09-10T16:59:59Z",
        eligible_players=(
            _eligible_players(provenance)
            if eligible_players is None else eligible_players
        ),
        annotation_rows=_matchup_rows(provenance) if rows is None else rows,
        player_catalog_identity=_object_identity("player-catalog"),
        annotation_query_receipt_identity=_object_identity("query-receipt"),
    )


def _scores(provenance: dict[str, object]) -> np.ndarray:
    count = len(provenance["candidates"])
    row = np.arange(count, dtype=np.float64)[:, None]
    column = np.arange(10, dtype=np.float64)[None, :]
    scores = np.ascontiguousarray(180.0 + (row % 31) + column * 0.75)
    # The heldout-only candidate would dominate if origin filtering failed.
    r4_only_index = next(
        index for index, candidate in enumerate(provenance["candidates"])
        if candidate["origin_blocks"] == ["R4"]
    )
    scores[r4_only_index] = 400.0 + column
    return scores


def _reconstruction(
    provenance: dict[str, object], scores: np.ndarray
) -> dict[str, object]:
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    matrix: dict[str, object] = {
        "schema_version": MATRIX_BINDING_SCHEMA,
        "slate": dict(SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": canonical_sha256(lineup_ids),
        "world_ids_sha256": "9" * 64,
        "shape": list(scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(scores),
        "uses_realized_outcomes": False,
    }
    matrix["matrix_binding_sha256"] = canonical_sha256(matrix)
    receipt: dict[str, object] = {
        "schema_version": RECONSTRUCTION_SCHEMA,
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
                "selected_count": 80,
                "verified": True,
            }
            for ordinal, arm_id in enumerate(PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    receipt["reconstruction_sha256"] = canonical_sha256(receipt)
    return receipt


def _summary(provenance: dict[str, object]) -> dict[str, object]:
    return runner.build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=_matchup_source(provenance),
        minimum_supported_players=2,
        minimum_completeness=1.0,
    )


def _book_projection(scope: dict[str, object]) -> list[dict[str, object]]:
    return [{
        "book_id": book["book_id"],
        "selected_lineup_ids": book["selected_lineup_ids"],
        "marginal_trace": book["marginal_trace"],
        "training_metrics": book["training_metrics"],
    } for book in scope["books"]]


def test_all_seven_laws_run_for_union_and_matchup_with_exact_traces(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    scope = runner.run_fit_scope(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=2,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert scope["book_count"] == 16
    assert scope["dose_authority"] == runner.FIXTURE_DOSE
    assert scope["require_authoritative"] is False
    assert scope["worlds_per_block"] == 2
    ids_by_admission = {}
    for book in scope["books"]:
        ids_by_admission.setdefault(book["admission_id"], set()).add(
            book["strategy_id"]
        )
        assert book["entry_count"] == 80
        assert len(set(book["selected_lineup_ids"])) == 80
        assert len(book["marginal_trace"]) == 80
        diagnostics = book["redundancy_diagnostics"]
        assert diagnostics["lineup_pair_count"] == 3160
        assert sum(
            row["lineup_pair_count"]
            for row in diagnostics["shared_player_count_histogram"]
        ) == 3160
        assert len(diagnostics["simulated_outcome_event_redundancy"]) == 4
        assert diagnostics["uses_realized_outcomes"] is False
        correlation = diagnostics["pairwise_score_correlation"]
        assert correlation["pair_population_count"] == 3160
        assert correlation["sampled_pair_count"] == 32
        assert len(correlation["rows"]) == 32
        assert correlation["full_pairwise_materialized"] is False
        assert correlation["uses_realized_outcomes"] is False
        assert all(
            "objective_before" in row
            and "objective_gain" in row
            and "objective_after" in row
            and "global_lineup_index" in row
            and "block_contributions" in row
            for row in book["marginal_trace"]
        )
    expected = {
        strategy["strategy_id"]
        for strategy in retrieval.frozen_retrieval_strategies_v2(80)
    }
    fixture_full = f"{runner.FIXTURE_ID_PREFIX}{runner.FULL_UNION_ADMISSION_ID}"
    fixture_matchup = f"{runner.FIXTURE_ID_PREFIX}matchup-top-80-supported-v2"
    assert ids_by_admission[fixture_full] == expected
    assert ids_by_admission[fixture_matchup] == expected
    neutral_ids = [
        admission["admission_id"]
        for admission in scope["admissions"]
        if admission["admission_id"].startswith(
            f"{runner.FIXTURE_ID_PREFIX}neutral-"
        )
    ]
    assert len(neutral_ids) == 2
    assert all(ids_by_admission[value] == {runner.PRIMARY_STRATEGY_ID} for value in neutral_ids)
    heldout_only = next(
        row["lineup_id"] for row in provenance["candidates"]
        if row["origin_blocks"] == ["R4"]
    )
    assert all(
        heldout_only not in book["selected_lineup_ids"] for book in scope["books"]
    )
    assert runner.validate_fit_scope(
        scope,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=2,
        worlds_per_block=2,
        require_authoritative=False,
    ) == scope


def test_heldout_scores_and_occurrences_cannot_change_fold_selection(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    summary = _summary(provenance)
    baseline = runner.run_fit_scope(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=summary,
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )

    poisoned_scores = scores.copy()
    poisoned_scores[:, 8:10] = np.arange(len(scores))[:, None] * 10_000.0
    poisoned = runner.run_fit_scope(
        provenance=provenance,
        union_scores=poisoned_scores,
        reconstruction_receipt=_reconstruction(provenance, poisoned_scores),
        matchup_summary=summary,
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert _book_projection(poisoned) == _book_projection(baseline)
    assert any(
        left["heldout_metrics_descriptive"]
        != right["heldout_metrics_descriptive"]
        for left, right in zip(poisoned["books"], baseline["books"], strict=True)
    )

    changed = deepcopy(provenance)
    candidate = next(
        row for row in changed["candidates"] if row["origin_blocks"] != ["R4"]
    )
    candidate["occurrences"].append({
        "arm_ordinal": 6,
        "parameter_set_id": PARAMETER_SET_ORDER[6],
        "visit_ordinal": 999,
        "block_id": "R4",
        "objective_world_index": 1,
    })
    candidate["origin_blocks"] = [
        block for block in rw.WORLD_BLOCKS
        if block in {*candidate["origin_blocks"], "R4"}
    ]
    candidate["source_arms"] = sorted({
        *candidate["source_arms"], PARAMETER_SET_ORDER[6]
    })
    candidate["occurrence_counts_by_block"]["R4"] += 1
    candidate["source_arms_by_block"]["R4"] = sorted({
        *candidate["source_arms_by_block"]["R4"], PARAMETER_SET_ORDER[6]
    })
    candidate["occurrence_count"] += 1
    changed["visit_occurrence_count"] += 1
    changed.pop("candidate_provenance_sha256")
    changed["candidate_provenance_sha256"] = canonical_sha256(changed)
    changed_scope = runner.run_fit_scope(
        provenance=changed,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(changed, scores),
        matchup_summary=summary,
        matchup_source=_matchup_source(changed),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert changed_scope["candidate_view"]["selection_provenance_sha256"] == (
        baseline["candidate_view"]["selection_provenance_sha256"]
    )
    assert _book_projection(changed_scope) == _book_projection(baseline)


def test_neutral_is_order_independent_and_exactly_composition_matched() -> None:
    candidate_ids = [f"lineup:{index:064x}" for index in range(12)]
    strata = {
        lineup_id: {"cell": index % 3}
        for index, lineup_id in enumerate(candidate_ids)
    }
    targets = candidate_ids[:6]
    first = runner.build_score_blind_neutral_admission(
        candidate_ids=candidate_ids,
        target_ids=targets,
        strata_by_id=strata,
        slate=SLATE,
        fit_scope_id="holdout-R4",
        seed_root="fixture-seed",
        replicate_index=0,
        selection_provenance_sha256="c" * 64,
        target_admission_sha256="e" * 64,
        dose_authority=runner.FIXTURE_DOSE,
    )
    replay = runner.build_score_blind_neutral_admission(
        candidate_ids=list(reversed(candidate_ids)),
        target_ids=list(reversed(targets)),
        strata_by_id=strata,
        slate=SLATE,
        fit_scope_id="holdout-R4",
        seed_root="fixture-seed",
        replicate_index=0,
        selection_provenance_sha256="c" * 64,
        target_admission_sha256="e" * 64,
        dose_authority=runner.FIXTURE_DOSE,
    )
    assert first == replay
    target_counts = Counter(strata[value]["cell"] for value in targets)
    admitted_counts = Counter(
        strata[value]["cell"] for value in first["admitted_lineup_ids"]
    )
    assert admitted_counts == target_counts
    assert first["admitted_count"] == len(targets)
    assert first["uses_simulated_scores"] is False
    assert first["uses_matchup_values"] is False
    excluded_ids = [
        row["lineup_id"] for row in first["excluded_eligible_candidates"]
    ]
    assert excluded_ids == sorted(set(candidate_ids) - set(first["admitted_lineup_ids"]))
    assert all(
        row["reason_code"] == "neutral-not-sampled"
        for row in first["excluded_eligible_candidates"]
    )
    assert first["excluded_eligible_candidate_count"] == 6
    assert first["excluded_eligible_lineup_ids_sha256"] == canonical_sha256(
        excluded_ids
    )
    runner._validate_admission_partition(first, eligible_ids=candidate_ids)

    tampered = deepcopy(first)
    tampered["excluded_eligible_candidates"].pop()
    tampered["admission_sha256"] = canonical_sha256({
        key: value for key, value in tampered.items() if key != "admission_sha256"
    })
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="partition does not replay",
    ):
        runner._validate_admission_partition(tampered, eligible_ids=candidate_ids)


def test_matchup_preserves_zero_missing_and_qb_starter_semantics() -> None:
    provenance = _provenance(count=3)
    first = provenance["candidates"][0]
    second = provenance["candidates"][1]
    rows = [
        {
            "gsis_id": first["roster_player_ids"][3],
            "family": "receiver",
            "matchup_edge_score": 0.0,
        },
        {
            "gsis_id": first["roster_player_ids"][4],
            "family": "receiver",
            "matchup_edge_score": None,
        },
        {
            "gsis_id": second["roster_player_ids"][0],
            "family": "qb",
            "matchup_edge_score": 100.0,
        },
    ]
    eligible = _eligible_players(provenance)
    second_qb = second["roster_player_ids"][0]
    for player in eligible:
        if player["gsis_id"] == second_qb:
            player["qb_depth1"] = False
    summary = runner.build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=_matchup_source(
            provenance, rows=rows, eligible_players=eligible
        ),
        minimum_supported_players=1,
        minimum_completeness=0.1,
    )
    by_id = {row["lineup_id"]: row for row in summary["lineups"]}
    first_row = by_id[first["lineup_id"]]
    assert first_row["matchup_edge_mean"] == 0.0
    assert first_row["eligible_player_count"] == 8
    assert first_row["supported_player_count"] == 1
    assert first_row["qualifies_for_matchup_admission"] is True
    second_row = by_id[second["lineup_id"]]
    assert second_row["eligible_player_count"] == 7
    assert second_row["matchup_edge_mean"] is None
    assert second_row["qualifies_for_matchup_admission"] is False


def test_final_fit_uses_all_blocks_and_includes_heldout_only_origin(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    final_fit = runner.run_fit_scope(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        heldout_block=None,
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert final_fit["training_blocks"] == list(rw.WORLD_BLOCKS)
    assert final_fit["heldout_block"] is None
    assert final_fit["candidate_view"]["excluded_count"] == 0
    r4_only = next(
        row["lineup_id"] for row in provenance["candidates"]
        if row["origin_blocks"] == ["R4"]
    )
    assert r4_only in {
        row["lineup_id"]
        for row in final_fit["candidate_view"]["eligible_candidates"]
    }
    assert all(book["heldout_metrics_descriptive"] is None for book in final_fit["books"])


def test_complete_surface_rotates_all_five_blocks_then_refits_all_blocks(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance(count=120)
    scores = _scores(provenance)
    surface = runner.run_retrieval_surface_v2(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert [fold["heldout_block"] for fold in surface["folds"]] == list(
        rw.WORLD_BLOCKS
    )
    assert all(fold["book_count"] == 15 for fold in surface["folds"])
    assert surface["cross_fit_book_count"] == 75
    assert surface["final_fit_book_count"] == 15
    assert surface["final_fit"]["training_blocks"] == list(rw.WORLD_BLOCKS)
    assert surface["final_fit"]["fit_scope_id"] == "all-block-final-fit"
    assert surface["uses_realized_outcomes"] is False
    assert surface["dose_authority"] == runner.FIXTURE_DOSE
    assert all(
        admission["admission_id"].startswith(runner.FIXTURE_ID_PREFIX)
        for scope in [*surface["folds"], surface["final_fit"]]
        for admission in scope["admissions"]
    )


def test_authoritative_surface_rejects_fixture_doses_before_dispatch(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="authoritative R6-v2 requires top-200 admission",
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            matchup_summary=_summary(provenance),
            matchup_source=_matchup_source(provenance),
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
        )


def test_threshold_boundaries_are_ge_194_then_strict_above_tail_lines() -> None:
    summary = runner._score_summary(np.asarray(
        [[194.0, 200.0, 210.0, 220.0]], dtype=np.float64
    ))
    assert summary["worlds_ge_194"] == 4
    assert summary["worlds_gt_200"] == 2
    assert summary["worlds_gt_210"] == 1
    assert summary["worlds_gt_220"] == 0


def test_bounded_pairwise_correlation_is_identity_order_independent() -> None:
    lineup_ids = [f"lineup:{index:064x}" for index in range(5)]
    scores = np.asarray([
        [1.0, 2.0, 3.0, 4.0],
        [4.0, 3.0, 2.0, 1.0],
        [2.0, 4.0, 6.0, 8.0],
        [7.0, 7.0, 7.0, 7.0],
        [1.0, 4.0, 2.0, 9.0],
    ], dtype=np.float64)
    first = runner._bounded_pairwise_score_correlation(
        scores, lineup_ids=lineup_ids
    )
    replay = runner._bounded_pairwise_score_correlation(
        scores[::-1], lineup_ids=list(reversed(lineup_ids))
    )
    assert replay == first
    assert first["pair_population_count"] == 10
    assert first["sampled_pair_count"] == 10
    assert first["full_pairwise_materialized"] is True
    assert first["constant-series-pair-count"] == 4


def test_sparse_matchup_support_fails_closed_before_selector_dispatch(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    eligible_r4_fold = [
        row for row in provenance["candidates"]
        if row["origin_blocks"] != ["R4"]
    ]
    supported_ids = {
        player
        for candidate in eligible_r4_fold[:79]
        for player in candidate["roster_player_ids"][:8]
    }
    rows = [
        row for row in _matchup_rows(provenance)
        if row["gsis_id"] in supported_ids
    ]
    sparse_source = _matchup_source(provenance, rows=rows)
    sparse = runner.build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=sparse_source,
        minimum_supported_players=2,
        minimum_completeness=1.0,
    )
    scores = _scores(provenance)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="fewer qualifying candidates",
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            matchup_summary=sparse,
            matchup_source=sparse_source,
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_registry_deletion_fails_the_seven_law_compatibility_gate(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    frozen = retrieval.frozen_retrieval_strategies_v2(80)
    monkeypatch.setattr(
        retrieval,
        "frozen_retrieval_strategies_v2",
        lambda entry_budget: frozen[:-1],
    )
    scores = _scores(provenance)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error, match="seven-law retrieval registry"
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            matchup_summary=_summary(provenance),
            matchup_source=_matchup_source(provenance),
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_registry_reordering_fails_the_canonical_ordinal_gate(monkeypatch) -> None:
    frozen = retrieval.frozen_retrieval_strategies_v2(80)
    monkeypatch.setattr(
        retrieval,
        "frozen_retrieval_strategies_v2",
        lambda entry_budget: list(reversed(frozen)),
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="registry order/ordinal differs",
    ):
        runner._validate_strategy_registry()


def test_registry_duplicate_identity_fails_even_with_a_valid_self_hash(
    monkeypatch,
) -> None:
    frozen = deepcopy(retrieval.frozen_retrieval_strategies_v2(80))
    duplicate = deepcopy(frozen[5])
    duplicate["ordinal"] = 6
    duplicate["strategy_sha256"] = canonical_sha256({
        key: value for key, value in duplicate.items()
        if key != "strategy_sha256"
    })
    frozen[6] = duplicate
    monkeypatch.setattr(
        retrieval,
        "frozen_retrieval_strategies_v2",
        lambda entry_budget: frozen,
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="identities are not unique/canonical",
    ):
        runner._validate_strategy_registry()


def test_expected_max_dispatch_is_byte_semantic_with_the_frozen_v1_law() -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    strategy = retrieval.frozen_retrieval_strategies_v2(80)[4]
    legacy_selected, legacy_trace = retrieval._run_strategy(
        strategy,
        discovery_scores=scores,
        lineup_ids=lineup_ids,
    )
    selected, trace = runner._run_strategy_v2(
        strategy,
        training_scores=scores,
        lineup_ids=lineup_ids,
    )
    assert selected == legacy_selected
    assert trace == legacy_trace


def test_blockmin_trace_publishes_and_replays_the_leximin_vector(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    strategy = retrieval.frozen_retrieval_strategies_v2(80)[6]
    selected, base_trace = runner._run_strategy_v2(
        strategy,
        training_scores=scores,
        lineup_ids=lineup_ids,
    )
    trace = runner._trace_evidence(
        strategy=strategy,
        scores=scores,
        lineup_ids=lineup_ids,
        selected=selected,
        base_trace=base_trace,
        blocks=rw.WORLD_BLOCKS,
        worlds_per_block=2,
    )
    for row in trace:
        assert row["objective_law"] == (
            "leximin-ascending-per-block-weighted-coverage"
        )
        assert row["objective_before"]["block_utilities"] == row[
            "base_trace"
        ]["block_utilities_before"]
        assert row["objective_gain"]["block_utility_delta"] == row[
            "base_trace"
        ]["block_utilities_added"]
        assert row["objective_after"]["block_utilities"] == row[
            "base_trace"
        ]["block_utilities_after"]
        assert row["objective_after"]["leximin_profile"] == sorted(
            row["objective_after"]["block_utilities"]
        )


def test_matchup_source_rejects_post_lock_and_tampered_evidence() -> None:
    provenance = _provenance(count=3)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="not point-in-time",
    ):
        runner.build_matchup_source_snapshot(
            slate=SLATE,
            lock_time_utc="2023-09-10T17:00:00Z",
            maximum_source_time_utc="2023-09-10T17:00:00.001Z",
            eligible_players=_eligible_players(provenance),
            annotation_rows=_matchup_rows(provenance),
            player_catalog_identity=_object_identity("player-catalog"),
            annotation_query_receipt_identity=_object_identity("query-receipt"),
        )
    source = _matchup_source(provenance)
    tampered = deepcopy(source)
    tampered["rows"][0]["matchup_edge_score"] = 999.0
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="self-hash differs",
    ):
        runner.validate_matchup_source_snapshot(tampered)


def test_non_boolean_qb_depth_is_rejected() -> None:
    provenance = _provenance(count=3)
    eligible = _eligible_players(provenance)
    eligible[0]["qb_depth1"] = 1
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match=r"eligible player\[0\] values differ",
    ):
        _matchup_source(provenance, eligible_players=eligible)


def test_matchup_summary_must_replay_from_its_bound_source() -> None:
    provenance = _provenance(count=3)
    summary = _summary(provenance)
    different_rows = deepcopy(_matchup_rows(provenance))
    different_rows[0]["matchup_edge_score"] += 1.0
    different_source = _matchup_source(provenance, rows=different_rows)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="source binding differs",
    ):
        runner.validate_matchup_lineup_summaries(
            summary,
            provenance=provenance,
            matchup_source=different_source,
        )


def test_matchup_catalog_missing_a_skill_player_fails_closed() -> None:
    provenance = _provenance(count=3)
    eligible = _eligible_players(provenance)[1:]
    rows = [
        row for row in _matchup_rows(provenance)
        if row["gsis_id"] != _eligible_players(provenance)[0]["gsis_id"]
    ]
    source = _matchup_source(
        provenance,
        rows=rows,
        eligible_players=eligible,
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="does not cover exactly eight skill players",
    ):
        runner.build_matchup_lineup_summaries(
            provenance=provenance,
            matchup_source=source,
            minimum_supported_players=1,
            minimum_completeness=0.1,
        )


def test_reconstruction_mismatch_fails_before_selector_dispatch(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    receipt = _reconstruction(provenance, scores)
    receipt["matrix_binding"]["score_matrix_sha256"] = "0" * 64
    receipt["matrix_binding"]["matrix_binding_sha256"] = canonical_sha256({
        key: value
        for key, value in receipt["matrix_binding"].items()
        if key != "matrix_binding_sha256"
    })
    receipt["reconstruction_sha256"] = canonical_sha256({
        key: value
        for key, value in receipt.items()
        if key != "reconstruction_sha256"
    })

    def selector_must_not_run(*args, **kwargs):
        raise AssertionError("selector dispatched before reconstruction validation")

    monkeypatch.setattr(runner, "_run_strategy_v2", selector_must_not_run)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="matrix binding differs",
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
            matchup_summary=_summary(provenance),
            matchup_source=_matchup_source(provenance),
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_candidate_provenance_rejects_hidden_outcome_fields() -> None:
    provenance = _provenance()
    provenance["candidates"][0]["actual_points"] = 250.0
    provenance["candidate_provenance_sha256"] = canonical_sha256({
        key: value
        for key, value in provenance.items()
        if key != "candidate_provenance_sha256"
    })
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match=r"candidate\[0\] fields differ",
    ):
        runner.build_fit_candidate_view(provenance, heldout_block="R4")
