from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    _score_matrix_sha256,
    canonical_json_bytes,
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
    return sorted(f"player-{index:03d}-{slot}" for slot in range(9))


def _provenance(count: int = 90) -> dict[str, object]:
    rows = []
    for index in range(count):
        roster = _roster(index)
        lineup_id = canonical_lineup_id(SLATE, roster)
        block = "R4" if index == count - 1 else rw.WORLD_BLOCKS[index % 4]
        arm_ordinal = index % len(PARAMETER_SET_ORDER)
        occurrence = {
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": PARAMETER_SET_ORDER[arm_ordinal],
            "visit_ordinal": index,
            "block_id": block,
            "objective_world_index": index % 2,
        }
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
            "occurrences": [occurrence],
        })
    rows.sort(key=lambda row: row["lineup_id"])
    body: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": "a" * 64,
        "visits_per_block": 2,
        "arm_count": len(PARAMETER_SET_ORDER),
        "visit_occurrence_count": count,
        "candidate_count": count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": rows,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = canonical_sha256(body)
    return body


def _scores(provenance: dict[str, object]) -> np.ndarray:
    count = len(provenance["candidates"])
    row = np.arange(count, dtype=np.float64)[:, None]
    column = np.arange(10, dtype=np.float64)[None, :]
    scores = np.ascontiguousarray(188.0 + (row % 19) * 4.0 + column * 1.25)
    r4_only = next(
        index
        for index, candidate in enumerate(provenance["candidates"])
        if candidate["origin_blocks"] == ["R4"]
    )
    scores[r4_only] = 400.0 + column
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


def _run_scope(
    monkeypatch: pytest.MonkeyPatch,
    *,
    provenance: dict[str, object] | None = None,
    scores: np.ndarray | None = None,
    heldout_block: str | None = "R4",
) -> tuple[dict[str, object], dict[str, object], np.ndarray]:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance() if provenance is None else provenance
    scores = _scores(provenance) if scores is None else scores
    result = suite.run_extreme_tail_fit_scope_v1(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        heldout_block=heldout_block,
        worlds_per_block=2,
        require_authoritative=False,
    )
    return result, provenance, scores


def _book_projection(scope: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "strategy_id": book["strategy_id"],
            "entry_budget": book["entry_budget"],
            "selected_lineup_ids": book["selected_lineup_ids"],
            "marginal_trace": book["marginal_trace"],
            "training_metrics": book["training_metrics"],
        }
        for book in scope["books"]
    ]


def test_frozen_registry_is_exactly_four_laws_and_does_not_touch_r6() -> None:
    r6_before = canonical_json_bytes(
        retrieval.frozen_retrieval_strategies_v2(80)
    )
    strategies = suite.frozen_extreme_tail_strategies_v1()
    assert [row["strategy_id"] for row in strategies] == [
        "coverage-ge-230-v1",
        "bounded-tail-ladder-ge-210-250-v1",
        "block-robust-bounded-tail-ge-210-250-v1",
        "individual-ge-230-rank-v1",
    ]
    assert [row["ordinal"] for row in strategies] == list(range(4))
    assert all(row["entry_budgets"] == [4, 14, 80] for row in strategies)
    assert strategies[0]["parameters"] == {"threshold": 230.0, "operator": ">="}
    expected_rungs = [
        {"threshold": threshold, "operator": operator, "weight": weight}
        for threshold, operator, weight in suite.TAIL_RUNGS
    ]
    assert strategies[1]["parameters"]["rungs"] == expected_rungs
    assert strategies[2]["parameters"]["rungs"] == expected_rungs
    assert strategies[1]["parameters"]["maximum_new_world_utility"] == 31
    implementation = suite.frozen_selector_implementation_contract_v1()
    assert implementation["implementation_id"] == (
        suite.SELECTOR_IMPLEMENTATION_ID
    )
    assert implementation["dense_remaining_candidate_event_temporaries"] is False
    assert all(
        strategy["selector_implementation_sha256"]
        == implementation["selector_implementation_sha256"]
        for strategy in strategies
    )
    for ordinal, strategy in enumerate(strategies):
        assert suite.validate_extreme_tail_strategy_v1(
            strategy, expected_ordinal=ordinal
        ) == strategy
    tampered = deepcopy(strategies[1])
    tampered["parameters"]["rungs"][2]["weight"] = 5
    with pytest.raises(
        suite.CorpusExtremeTailRetrievalSuiteError, match="differs from registry"
    ):
        suite.validate_extreme_tail_strategy_v1(tampered, expected_ordinal=1)
    assert canonical_json_bytes(
        retrieval.frozen_retrieval_strategies_v2(80)
    ) == r6_before


def test_inclusive_ladder_has_exact_finite_incremental_utility() -> None:
    scores = np.full((2, 8), 100.0, dtype=np.float64)
    scores[0, :5] = [210.0, 220.0, 230.0, 240.0, 250.0]
    ids = ["lineup:a", "lineup:b"]
    strategy = suite.frozen_extreme_tail_strategies_v1()[1]
    selected, trace = suite._select_ladder_packed(
        scores,
        budget=1,
        rungs=strategy["parameters"]["rungs"],
        lineup_ids=ids,
    )
    assert selected == [0]
    assert trace[0]["marginal_utility"] == 1 + 3 + 7 + 15 + 31
    scores[0, 0] = np.nextafter(210.0, -np.inf)
    _, below_trace = suite._select_ladder_packed(
        scores,
        budget=1,
        rungs=strategy["parameters"]["rungs"],
        lineup_ids=ids,
    )
    assert below_trace[0]["marginal_utility"] == trace[0]["marginal_utility"] - 1


def test_block_robust_ladder_balances_training_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 8)
    scores = np.full((5, 32), 100.0, dtype=np.float64)
    scores[0, 0:4] = 250.0
    scores[1, 4:7] = 250.0
    scores[2, 8:10] = 250.0
    scores[3, 16] = 250.0
    scores[4, 24] = 250.0
    ids = [f"lineup:{index}" for index in range(5)]
    rungs = suite.frozen_extreme_tail_strategies_v1()[2]["parameters"][
        "rungs"
    ]
    plain, _ = suite._select_ladder_packed(
        scores, budget=4, rungs=rungs, lineup_ids=ids
    )
    robust, trace = suite._select_blockmin_ladder_packed(
        scores, budget=4, rungs=rungs, lineup_ids=ids
    )
    assert plain == [0, 1, 2, 3]
    assert robust == [0, 2, 3, 4]
    assert trace[-1]["leximin_profile_after"] == [31, 31, 62, 124]


def test_individual_rank_is_count_based_and_stably_tied() -> None:
    scores = np.asarray(
        [
            [230.0, 230.0, 230.0, 100.0],
            [230.0, 100.0, 100.0, 230.0],
            [230.0, 230.0, 100.0, 100.0],
            [230.0, 230.0, 100.0, 100.0],
        ],
        dtype=np.float64,
    )
    ids = ["lineup:d", "lineup:c", "lineup:b", "lineup:a"]
    selected, trace = suite._select_individual_ge_230(
        scores, budget=4, lineup_ids=ids
    )
    assert selected == [0, 3, 2, 1]
    assert trace[0]["individual_ge_230_probability"] == {
        "numerator": 3,
        "denominator": 4,
    }
    assert [trace[index]["lineup_id"] for index in (1, 2)] == [
        "lineup:a",
        "lineup:b",
    ]


def _dense_individual_reference(
    scores: np.ndarray, *, budget: int, lineup_ids: list[str]
) -> tuple[list[int], list[dict[str, object]]]:
    counts = retrieval._support(scores, 230.0, ">=").sum(
        axis=1, dtype=np.int64
    )
    means = scores.mean(axis=1, dtype=np.float64)
    selected = sorted(
        range(scores.shape[0]),
        key=lambda index: (
            -int(counts[index]),
            -float(means[index]),
            lineup_ids[index],
        ),
    )[:budget]
    trace = [
        {
            "selection_rank": rank,
            "lineup_index": index,
            "lineup_id": lineup_ids[index],
            "marginal_utility": int(counts[index]),
            "individual_ge_230_event_count": int(counts[index]),
            "individual_ge_230_probability": {
                "numerator": int(counts[index]),
                "denominator": int(scores.shape[1]),
            },
            "discovery_primary_event_count": int(counts[index]),
            "discovery_mean_score": float(means[index]),
        }
        for rank, index in enumerate(selected)
    ]
    return selected, trace


def test_packed_global_selectors_match_dense_references_across_chunks() -> None:
    rng = np.random.default_rng(230)
    values = np.asarray(
        [
            190.0,
            200.0,
            np.nextafter(210.0, -np.inf),
            210.0,
            220.0,
            230.0,
            240.0,
            250.0,
            260.0,
        ],
        dtype=np.float64,
    )
    scores = np.ascontiguousarray(rng.choice(values, size=(73, 37)))
    scores[1] = scores[0]
    scores[65] = scores[64]
    ids = [f"lineup:{73 - index:03d}" for index in range(73)]
    rungs = suite.frozen_extreme_tail_strategies_v1()[1]["parameters"][
        "rungs"
    ]

    assert suite._select_coverage_packed(
        scores,
        budget=17,
        threshold=230.0,
        operator=">=",
        lineup_ids=ids,
    ) == retrieval._select_coverage(
        scores,
        budget=17,
        threshold=230.0,
        operator=">=",
        lineup_ids=ids,
    )
    assert suite._select_ladder_packed(
        scores, budget=17, rungs=rungs, lineup_ids=ids
    ) == retrieval._select_ladder(
        scores, budget=17, rungs=rungs, lineup_ids=ids
    )
    assert suite._select_individual_ge_230(
        scores, budget=17, lineup_ids=ids
    ) == _dense_individual_reference(scores, budget=17, lineup_ids=ids)


def test_packed_coverage_preserves_zero_gain_fill_and_ties() -> None:
    scores = np.asarray(
        [
            [210.0, 210.0, 210.0],
            [210.0, 210.0, 210.0],
            [220.0, 200.0, 200.0],
            [200.0, 220.0, 200.0],
        ],
        dtype=np.float64,
    )
    ids = ["lineup:d", "lineup:a", "lineup:c", "lineup:b"]
    packed = suite._select_coverage_packed(
        scores,
        budget=4,
        threshold=230.0,
        operator=">=",
        lineup_ids=ids,
    )
    dense = retrieval._select_coverage(
        scores,
        budget=4,
        threshold=230.0,
        operator=">=",
        lineup_ids=ids,
    )
    assert packed == dense
    assert [row["marginal_utility"] for row in packed[1]] == [0, 0, 0, 0]


@pytest.mark.parametrize("block_count", [4, 5])
def test_packed_blockmin_matches_dense_reference_for_dynamic_blocks(
    monkeypatch: pytest.MonkeyPatch, block_count: int
) -> None:
    worlds_per_block = 9
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", worlds_per_block)
    rng = np.random.default_rng(230 + block_count)
    values = np.asarray(
        [190.0, 200.0, 210.0, 220.0, 230.0, 240.0, 250.0, 260.0],
        dtype=np.float64,
    )
    scores = np.ascontiguousarray(
        rng.choice(values, size=(71, block_count * worlds_per_block))
    )
    scores[1] = scores[0]
    scores[70] = scores[69]
    ids = [f"lineup:{71 - index:03d}" for index in range(71)]
    rungs = suite.frozen_extreme_tail_strategies_v1()[2]["parameters"][
        "rungs"
    ]
    assert suite._select_blockmin_ladder_packed(
        scores, budget=13, rungs=rungs, lineup_ids=ids
    ) == retrieval._select_blockmin_ladder(
        scores, budget=13, rungs=rungs, lineup_ids=ids
    )


def test_fit_scope_dispatch_does_not_call_inherited_dense_selectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("inherited dense selector was called")

    for name in ("_select_coverage", "_select_ladder", "_select_blockmin_ladder"):
        monkeypatch.setattr(retrieval, name, forbidden)
    scope, _, _ = _run_scope(monkeypatch)
    assert scope["book_count"] == 12


def test_opportunity_conversion_retains_hits_misses_and_tail_regret() -> None:
    pool = np.asarray(
        [
            [230.0, 230.0, 100.0],
            [230.0, 100.0, 100.0],
            [100.0, 100.0, 250.0],
        ],
        dtype=np.float64,
    )
    book = pool[:2]
    result = suite._opportunity_conversion_summary(
        book_scores=book,
        admitted_pool_scores=pool,
    )
    ge_230 = next(
        row for row in result["thresholds"] if row["label"] == "ge_230"
    )
    assert ge_230["opportunity_world_count"] == 3
    assert ge_230["book_hit_world_count"] == 2
    assert ge_230["missed_opportunity_world_count"] == 1
    assert ge_230["summed_individual_event_count"] == 3
    assert ge_230["event_union_over_summed_individual_events"] == {
        "numerator": 2,
        "denominator": 3,
    }
    assert ge_230["opportunity_conversion"] == {
        "numerator": 2,
        "denominator": 3,
    }
    assert ge_230["conditional_regret_mean_over_all_worlds"] == 50.0
    assert ge_230["conditional_regret_mean_given_opportunity"] == 50.0
    ge_250 = next(
        row for row in result["thresholds"] if row["label"] == "ge_250"
    )
    assert ge_250["summed_individual_event_count"] == 0
    assert ge_250["event_union_over_summed_individual_events"] is None


def test_fit_scope_builds_exact_nested_4_14_80_books_and_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, provenance, scores = _run_scope(monkeypatch)
    assert scope["schema_version"] == suite.SCOPE_SCHEMA
    assert scope["book_count"] == 12
    assert scope["entry_budgets"] == [4, 14, 80]
    assert scope["uses_matchup_admission"] is False
    assert scope["uses_realized_outcomes"] is False
    assert all(scope[field] is False for field in suite._FALSE_AUTHORITY_FIELDS)
    heldout_only = next(
        row["lineup_id"]
        for row in provenance["candidates"]
        if row["origin_blocks"] == ["R4"]
    )
    for strategy in suite.frozen_extreme_tail_strategies_v1():
        books = [
            book
            for book in scope["books"]
            if book["strategy_id"] == strategy["strategy_id"]
        ]
        assert [book["entry_budget"] for book in books] == [4, 14, 80]
        assert books[1]["selected_lineup_ids"][:4] == books[0][
            "selected_lineup_ids"
        ]
        assert books[2]["selected_lineup_ids"][:14] == books[1][
            "selected_lineup_ids"
        ]
        for book in books:
            budget = book["entry_budget"]
            assert book["entry_count"] == budget
            assert len(set(book["selected_lineup_ids"])) == budget
            assert len(book["marginal_trace"]) == budget
            assert [row["selection_rank"] for row in book["marginal_trace"]] == list(
                range(budget)
            )
            assert heldout_only not in book["selected_lineup_ids"]
            assert all(
                row["operator"] == ">=" for row in book["threshold_semantics"]
            )
            assert all(
                book[field] is False
                for field in suite._FALSE_AUTHORITY_FIELDS
            )
            for key in (
                "training_opportunity_conversion",
                "heldout_opportunity_conversion_descriptive",
            ):
                comparison = book[key]
                assert comparison is not None
                for threshold in comparison["aggregate"]["thresholds"]:
                    assert threshold["missed_opportunity_world_count"] == (
                        threshold["opportunity_world_count"]
                        - threshold["book_hit_world_count"]
                    )
                    conversion = threshold["opportunity_conversion"]
                    if threshold["opportunity_world_count"] == 0:
                        assert conversion is None
                    else:
                        assert conversion == {
                            "numerator": threshold["book_hit_world_count"],
                            "denominator": threshold[
                                "opportunity_world_count"
                            ],
                        }
                    summed = threshold["summed_individual_event_count"]
                    ratio = threshold[
                        "event_union_over_summed_individual_events"
                    ]
                    assert summed >= threshold["book_hit_world_count"]
                    if summed == 0:
                        assert ratio is None
                    else:
                        assert ratio == {
                            "numerator": threshold["book_hit_world_count"],
                            "denominator": summed,
                        }
    assert suite.validate_extreme_tail_fit_scope_v1(
        scope,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        heldout_block="R4",
        worlds_per_block=2,
        require_authoritative=False,
    ) == scope


def test_heldout_scores_and_occurrences_cannot_change_fold_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline, provenance, scores = _run_scope(monkeypatch)
    poisoned_scores = scores.copy()
    poisoned_scores[:, 8:10] = (
        np.arange(len(scores), dtype=np.float64)[:, None] * 10_000.0
    )
    poisoned, _, _ = _run_scope(
        monkeypatch, provenance=provenance, scores=poisoned_scores
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
        block
        for block in rw.WORLD_BLOCKS
        if block in {*candidate["origin_blocks"], "R4"}
    ]
    candidate["source_arms"] = sorted({
        *candidate["source_arms"],
        PARAMETER_SET_ORDER[6],
    })
    candidate["occurrence_counts_by_block"]["R4"] += 1
    candidate["source_arms_by_block"]["R4"] = sorted({
        *candidate["source_arms_by_block"]["R4"],
        PARAMETER_SET_ORDER[6],
    })
    candidate["occurrence_count"] += 1
    changed["visit_occurrence_count"] += 1
    changed.pop("candidate_provenance_sha256")
    changed["candidate_provenance_sha256"] = canonical_sha256(changed)
    changed_scope, _, _ = _run_scope(
        monkeypatch, provenance=changed, scores=scores
    )
    assert _book_projection(changed_scope) == _book_projection(baseline)
    assert changed_scope["candidate_view"]["selection_provenance_sha256"] == (
        baseline["candidate_view"]["selection_provenance_sha256"]
    )


def test_complete_suite_rotates_five_folds_then_refits_all_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance(count=120)
    scores = _scores(provenance)
    result = suite.run_extreme_tail_retrieval_suite_v1(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert result["schema_version"] == suite.SUITE_SCHEMA
    assert [fold["heldout_block"] for fold in result["folds"]] == list(
        rw.WORLD_BLOCKS
    )
    assert result["fold_count"] == 5
    assert result["books_per_scope"] == 12
    assert result["cross_fit_book_count"] == 60
    assert result["final_fit_book_count"] == 12
    assert result["final_fit"]["training_blocks"] == list(rw.WORLD_BLOCKS)
    assert result["final_fit"]["heldout_block"] is None
    assert result["final_fit"]["candidate_view"]["excluded_count"] == 0
    assert all(result[field] is False for field in suite._FALSE_AUTHORITY_FIELDS)
    implementation = suite.frozen_selector_implementation_contract_v1()
    assert result["selector_implementation_binding"] == {
        "implementation_id": implementation["implementation_id"],
        "selector_implementation_sha256": implementation[
            "selector_implementation_sha256"
        ],
    }
    assert result["selector_implementation_contract"] == implementation
    assert result["nominated_book_pair_event_diagnostic_prerequisite"] == {
        "required_before_promotion": True,
        "must_be_separately_bound": True,
        "required_metrics": [
            "pair-event-intersection-jaccard",
            "duplicate-event-vector-groups",
        ],
    }
    r4_only = next(
        row["lineup_id"]
        for row in provenance["candidates"]
        if row["origin_blocks"] == ["R4"]
    )
    assert r4_only in {
        row["lineup_id"]
        for row in result["final_fit"]["candidate_view"]["eligible_candidates"]
    }
    assert suite.validate_extreme_tail_retrieval_suite_v1(
        result,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        worlds_per_block=2,
        require_authoritative=False,
    ) == result


def test_fail_closed_on_budget_tamper_matrix_drift_and_output_tamper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, provenance, scores = _run_scope(monkeypatch)
    with pytest.raises(
        suite.CorpusExtremeTailRetrievalSuiteError,
        match="exact entry budgets 4/14/80",
    ):
        suite.run_extreme_tail_fit_scope_v1(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            heldout_block="R4",
            entry_budgets=(4, 80),
            worlds_per_block=2,
            require_authoritative=False,
        )

    drifted = scores.copy()
    drifted[0, 0] += 1.0
    with pytest.raises(
        suite.CorpusExtremeTailRetrievalSuiteError,
        match="matrix binding differs",
    ):
        suite.run_extreme_tail_fit_scope_v1(
            provenance=provenance,
            union_scores=drifted,
            reconstruction_receipt=_reconstruction(provenance, scores),
            heldout_block="R4",
            worlds_per_block=2,
            require_authoritative=False,
        )

    nonfinite = scores.copy()
    nonfinite[0, 0] = np.nan
    with pytest.raises(
        suite.CorpusExtremeTailRetrievalSuiteError,
        match="contains a non-finite value",
    ):
        suite.run_extreme_tail_fit_scope_v1(
            provenance=provenance,
            union_scores=nonfinite,
            reconstruction_receipt=_reconstruction(provenance, scores),
            heldout_block="R4",
            worlds_per_block=2,
            require_authoritative=False,
        )

    tampered = deepcopy(scope)
    tampered["books"][0]["selected_lineup_ids"][0] = "lineup:tampered"
    with pytest.raises(
        suite.CorpusExtremeTailRetrievalSuiteError,
        match="canonical replay differs",
    ):
        suite.validate_extreme_tail_fit_scope_v1(
            tampered,
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            heldout_block="R4",
            worlds_per_block=2,
            require_authoritative=False,
        )
