from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_support_switch as switch
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
WIDTH = 25


def _roster(index: int) -> list[str]:
    return sorted(f"switch-player-{index:03d}-{slot}" for slot in range(9))


def _provenance() -> dict[str, object]:
    count = 90
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
        "visit_occurrence_count": len(PARAMETER_SET_ORDER) * visits_per_arm,
        "candidate_count": count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": rows,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = canonical_sha256(body)
    return body


def _world_ids() -> list[dict[str, object]]:
    return [
        {"block": block, "index": index}
        for block in rw.WORLD_BLOCKS for index in range(WIDTH)
    ]


def _reconstruction(
    provenance: dict[str, object], scores: np.ndarray
) -> dict[str, object]:
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    binding: dict[str, object] = {
        "schema_version": MATRIX_BINDING_SCHEMA,
        "slate": dict(SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": canonical_sha256(lineup_ids),
        "world_ids_sha256": canonical_sha256(_world_ids()),
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


def _score_case(case: str, count: int) -> np.ndarray:
    scores = np.full((count, len(rw.WORLD_BLOCKS) * WIDTH), 230.0)
    if case == "one-missing":
        scores[:, 4 * WIDTH - 1] = 100.0
    elif case == "block-zero":
        scores[:, :WIDTH] = 100.0
    elif case != "supported":
        raise ValueError(case)
    return np.ascontiguousarray(scores, dtype=np.float64)


def _build_sources(case: str) -> dict[str, object]:
    provenance = _provenance()
    scores = _score_case(case, len(provenance["candidates"]))
    reconstruction = _reconstruction(provenance, scores)
    support = census.build_extreme_tail_support_census(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=reconstruction,
        world_ids=_world_ids(),
        worlds_per_block=WIDTH,
        require_authoritative=False,
    )
    raw_suite = suite.run_extreme_tail_retrieval_suite_v1(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=reconstruction,
        worlds_per_block=WIDTH,
        require_authoritative=False,
    )
    policy = switch.build_extreme_tail_support_switched_policy_v1(
        support_census=support,
        extreme_tail_suite=raw_suite,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=reconstruction,
        world_ids=_world_ids(),
        worlds_per_block=WIDTH,
        require_authoritative=False,
    )
    return {
        "provenance": provenance,
        "scores": scores,
        "reconstruction": reconstruction,
        "census": support,
        "suite": raw_suite,
        "policy": policy,
    }


@pytest.fixture(scope="module")
def source_cases() -> dict[str, dict[str, object]]:
    prior = retrieval.WORLDS_PER_BLOCK
    retrieval.WORLDS_PER_BLOCK = WIDTH
    try:
        yield {
            case: _build_sources(case)
            for case in ("supported", "one-missing", "block-zero")
        }
    finally:
        retrieval.WORLDS_PER_BLOCK = prior


def _source_book(
    raw_scope: dict[str, object], strategy_id: str, budget: int
) -> dict[str, object]:
    return next(
        book for book in raw_scope["books"]
        if book["strategy_id"] == strategy_id
        and book["entry_budget"] == budget
    )


def test_exact_100_and_125_select_literal_exact_books_and_fully_replay(
    source_cases: dict[str, dict[str, object]],
) -> None:
    case = source_cases["supported"]
    policy = case["policy"]

    assert [
        fold["support_gate"]["training_opportunity_world_count"]
        for fold in policy["folds"]
    ] == [100] * 5
    assert all(
        fold["selected_strategy_id"] == switch.LITERAL_COVERAGE_STRATEGY_ID
        for fold in policy["folds"]
    )
    assert policy["final_fit"]["support_gate"][
        "training_opportunity_world_count"
    ] == 125
    assert policy["final_fit"]["selected_strategy_id"] == (
        switch.LITERAL_COVERAGE_STRATEGY_ID
    )
    assert policy["entry_budgets"] == [4, 14, 80]
    assert policy["selected_book_count"] == 18

    for projected, budget in zip(
        policy["folds"][0]["selected_books"], (4, 14, 80), strict=True
    ):
        raw = _source_book(
            case["suite"]["folds"][0],
            switch.LITERAL_COVERAGE_STRATEGY_ID,
            budget,
        )
        assert projected["source_book_id"] == raw["book_id"]
        assert projected["source_book_sha256"] == raw["book_sha256"]
        assert projected["selected_lineup_ids"] == raw["selected_lineup_ids"]
        assert projected["marginal_trace"] == raw["marginal_trace"]
        assert projected["entry_count"] == budget

    replayed = switch.validate_extreme_tail_support_switched_policy_v1(
        policy,
        support_census=case["census"],
        extreme_tail_suite=case["suite"],
        provenance=case["provenance"],
        union_scores=case["scores"],
        reconstruction_receipt=case["reconstruction"],
        world_ids=_world_ids(),
        worlds_per_block=WIDTH,
        require_authoritative=False,
    )
    assert canonical_json_bytes(replayed) == canonical_json_bytes(policy)
    assert replayed["source_receipts"]["support_census_sha256"] == (
        case["census"]["support_census_sha256"]
    )
    assert replayed["source_receipts"]["extreme_tail_suite_sha256"] == (
        case["suite"]["suite_sha256"]
    )


def test_99_and_124_fail_while_exact_100_and_125_pass(
    source_cases: dict[str, dict[str, object]],
) -> None:
    policy = source_cases["one-missing"]["policy"]
    folds = {fold["heldout_block"]: fold for fold in policy["folds"]}

    assert folds["R3"]["support_gate"]["training_opportunity_world_count"] == 100
    assert folds["R3"]["selected_strategy_id"] == (
        switch.LITERAL_COVERAGE_STRATEGY_ID
    )
    assert folds["R4"]["support_gate"]["training_opportunity_world_count"] == 99
    assert folds["R4"]["support_gate"]["every_training_block_nonzero"] is True
    assert folds["R4"]["selected_strategy_id"] == switch.FALLBACK_STRATEGY_ID
    assert folds["R4"]["support_gate"]["failure_reasons"] == [
        "aggregate-training-ge-230-opportunity-below-frozen-minimum"
    ]
    final = policy["final_fit"]
    assert final["support_gate"]["training_opportunity_world_count"] == 124
    assert final["support_gate"]["every_training_block_nonzero"] is True
    assert final["selected_strategy_id"] == switch.FALLBACK_STRATEGY_ID

    raw_scope = source_cases["one-missing"]["suite"]["folds"][4]
    for projected, budget in zip(final["selected_books"], (4, 14, 80), strict=True):
        assert projected["entry_count"] == budget
    for projected, budget in zip(
        folds["R4"]["selected_books"], (4, 14, 80), strict=True
    ):
        raw = _source_book(raw_scope, switch.FALLBACK_STRATEGY_ID, budget)
        assert projected["source_book_id"] == raw["book_id"]
        assert projected["selected_lineup_ids"] == raw["selected_lineup_ids"]
        assert projected["marginal_trace"] == raw["marginal_trace"]


def test_block_zero_is_retained_as_a_reason_and_forces_robust_fallback(
    source_cases: dict[str, dict[str, object]],
) -> None:
    policy = source_cases["block-zero"]["policy"]
    folds = {fold["heldout_block"]: fold for fold in policy["folds"]}

    assert folds["R0"]["support_gate"]["passed"] is True
    assert folds["R0"]["selected_strategy_id"] == (
        switch.LITERAL_COVERAGE_STRATEGY_ID
    )
    failed = folds["R4"]
    assert failed["support_gate"]["per_block_opportunity_world_counts"][0] == {
        "block_id": "R0", "opportunity_world_count": 0,
    }
    assert failed["support_gate"]["zero_opportunity_training_blocks"] == ["R0"]
    assert failed["support_gate"]["every_training_block_nonzero"] is False
    assert failed["selected_strategy_id"] == switch.FALLBACK_STRATEGY_ID
    assert failed["support_gate"]["failure_reasons"] == [
        "one-or-more-training-blocks-have-zero-ge-230-opportunity",
        "aggregate-training-ge-230-opportunity-below-frozen-minimum",
    ]


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = canonical_sha256(value)


def _retop(
    policy: dict[str, object], slate_index: int
) -> dict[str, object]:
    result = deepcopy(policy)
    result["slate"] = {
        "season": 2023,
        "week": slate_index + 1,
        "slate_id": f"panel-slate-{slate_index:02d}",
    }
    _rehash(result, "support_switched_policy_sha256")
    return result


def test_panel_80_percent_boundary_uses_integer_cross_products(
    source_cases: dict[str, dict[str, object]],
) -> None:
    supported = source_cases["supported"]["policy"]
    zero_fold = source_cases["block-zero"]["policy"]
    # R0 is the one passing fold in the block-zero case. Replace it with the
    # corresponding failing R0 scope from the one-missing case, yielding a
    # structurally complete policy with zero passing folds and a failing final.
    zero_fold = deepcopy(zero_fold)
    zero_fold["folds"][0] = deepcopy(
        source_cases["one-missing"]["policy"]["folds"][0]
    )
    _rehash(zero_fold, "support_switched_policy_sha256")

    at_boundary = [
        _retop(supported, index) for index in range(4)
    ] + [_retop(zero_fold, 4)]
    result = switch.build_extreme_tail_panel_nomination_summary_v1(
        at_boundary, require_authoritative=False
    )
    assert result["fold_gates"] == {
        "passed": 20,
        "total": 25,
        "passed_times_denominator": 100,
        "total_times_numerator": 100,
        "meets_support_fraction": True,
    }
    assert result["final_fit_gates"] == {
        "passed": 4,
        "total": 5,
        "passed_times_denominator": 20,
        "total_times_numerator": 20,
        "meets_support_fraction": True,
    }
    assert result["joint_support_fraction_arithmetic_passed"] is True
    assert result["literal_coverage_ge_230_generally_supported"] is False
    assert result["authoritative_panel_certification"] is False
    assert result["evidence_role"] == (
        "non-authoritative-structural-diagnostic-only"
    )
    assert result["nomination_role"] == (
        "literal-coverage-ge-230-diagnostic-only"
    )
    assert result["authoritative_expected_counts"] == {
        "slates": 54,
        "fold_gates": 270,
        "final_fit_gates": 54,
    }
    assert switch.validate_extreme_tail_panel_nomination_summary_v1(
        result, at_boundary, require_authoritative=False
    ) == result

    below = [
        _retop(supported, index) for index in range(3)
    ] + [_retop(zero_fold, 3), _retop(zero_fold, 4)]
    below_result = switch.build_extreme_tail_panel_nomination_summary_v1(
        below, require_authoritative=False
    )
    assert below_result["fold_gates"]["passed_times_denominator"] == 75
    assert below_result["fold_gates"]["total_times_numerator"] == 100
    assert below_result["final_fit_gates"]["passed_times_denominator"] == 15
    assert below_result["literal_coverage_ge_230_generally_supported"] is False
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError,
        match="generation/content-bound panel replay receipts",
    ):
        switch.build_extreme_tail_panel_nomination_summary_v1(
            at_boundary, require_authoritative=True
        )


def test_structural_panel_rejects_dose_width_shape_and_gate_count_drift(
    source_cases: dict[str, dict[str, object]],
) -> None:
    base = source_cases["supported"]["policy"]

    dose_drift = deepcopy(base)
    dose_drift["dose_authority"] = runner.AUTHORITATIVE_DOSE
    _rehash(dose_drift, "support_switched_policy_sha256")

    width_drift = deepcopy(base)
    width_drift["worlds_per_block"] = WIDTH + 1
    _rehash(width_drift, "support_switched_policy_sha256")

    shape_drift = deepcopy(base)
    shape_drift["input_binding"]["score_shape"][1] += 1
    _rehash(shape_drift, "support_switched_policy_sha256")

    retagged_fixture = deepcopy(base)
    retagged_fixture["require_authoritative"] = True
    retagged_fixture["dose_authority"] = runner.AUTHORITATIVE_DOSE
    _rehash(retagged_fixture, "support_switched_policy_sha256")

    count_drift = deepcopy(base)
    gate = count_drift["folds"][0]["support_gate"]
    gate["per_block_opportunity_world_counts"][0][
        "opportunity_world_count"
    ] = WIDTH + 1
    gate["training_opportunity_world_count"] += 1
    _rehash(count_drift["folds"][0], "support_switch_scope_sha256")
    _rehash(count_drift, "support_switched_policy_sha256")

    for altered in (dose_drift, width_drift, shape_drift, retagged_fixture):
        with pytest.raises(
            switch.CorpusExtremeTailSupportSwitchError,
            match="dose authority/world width/score shape differs",
        ):
            switch.build_extreme_tail_panel_nomination_summary_v1(
                [altered], require_authoritative=False
            )
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError,
        match="per-block count differs",
    ):
        switch.build_extreme_tail_panel_nomination_summary_v1(
            [count_drift], require_authoritative=False
        )


def test_source_binding_membership_missing_book_and_law_drift_fail_closed(
    source_cases: dict[str, dict[str, object]],
) -> None:
    case = source_cases["supported"]
    kwargs = {
        "provenance": case["provenance"],
        "union_scores": case["scores"],
        "reconstruction_receipt": case["reconstruction"],
        "world_ids": _world_ids(),
        "worlds_per_block": WIDTH,
        "require_authoritative": False,
    }

    binding_drift = deepcopy(case["suite"])
    binding_drift["input_binding"]["score_matrix_sha256"] = "0" * 64
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError, match="suite replay failed"
    ):
        switch.build_extreme_tail_support_switched_policy_v1(
            support_census=case["census"],
            extreme_tail_suite=binding_drift,
            **kwargs,
        )

    membership_drift = deepcopy(case["census"])
    membership_drift["universes"][7]["heldout_block"] = "R1"
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError, match="census replay failed"
    ):
        switch.build_extreme_tail_support_switched_policy_v1(
            support_census=membership_drift,
            extreme_tail_suite=case["suite"],
            **kwargs,
        )

    missing_book = deepcopy(case["suite"])
    missing_book["folds"][0]["books"] = missing_book["folds"][0]["books"][:-1]
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError, match="suite replay failed"
    ):
        switch.build_extreme_tail_support_switched_policy_v1(
            support_census=case["census"],
            extreme_tail_suite=missing_book,
            **kwargs,
        )

    altered = deepcopy(case["policy"])
    altered["folds"][0]["support_gate"]["operator"] = ">"
    _rehash(altered["folds"][0], "support_switch_scope_sha256")
    _rehash(altered, "support_switched_policy_sha256")
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError,
        match="threshold/operator/facts differ",
    ):
        switch.build_extreme_tail_panel_nomination_summary_v1(
            [altered], require_authoritative=False
        )


def test_retained_policy_binding_drift_and_nonfinite_values_fail_replay(
    source_cases: dict[str, dict[str, object]],
) -> None:
    case = source_cases["supported"]
    retained = deepcopy(case["policy"])
    retained["source_receipts"]["support_census_sha256"] = "f" * 64
    _rehash(retained["source_receipts"], "source_pair_sha256")
    _rehash(retained, "support_switched_policy_sha256")
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError, match="canonical replay differs"
    ):
        switch.validate_extreme_tail_support_switched_policy_v1(
            retained,
            support_census=case["census"],
            extreme_tail_suite=case["suite"],
            provenance=case["provenance"],
            union_scores=case["scores"],
            reconstruction_receipt=case["reconstruction"],
            world_ids=_world_ids(),
            worlds_per_block=WIDTH,
            require_authoritative=False,
        )

    nonfinite = deepcopy(case["policy"])
    nonfinite["folds"][0]["selected_books"][0]["marginal_trace"][0][
        "marginal_utility"
    ] = float("nan")
    with pytest.raises(
        switch.CorpusExtremeTailSupportSwitchError, match="canonical JSON"
    ):
        switch.build_extreme_tail_panel_nomination_summary_v1(
            [nonfinite], require_authoritative=False
        )
