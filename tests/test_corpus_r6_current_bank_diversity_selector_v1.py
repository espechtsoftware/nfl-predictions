from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)


EXPECTED_CONTRACT_SHA256 = (
    "747416eb96d7a51eb1846ab08deac3e6d99f65b083b09b2dfd4860245d2c3869"
)
EXPECTED_FIXTURE_RESULT_SHA256 = (
    "f4adc9408b27c4ea1188f4ac750d31d0344378af5081fb33b6a6995ad68d2920"
)


def _candidate_rows(
    lineup_ids: list[str],
    blocks: list[str],
    *,
    roster_by_index: dict[int, list[str]] | None = None,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for index, lineup_id in enumerate(lineup_ids):
        roster = (
            roster_by_index[index]
            if roster_by_index is not None and index in roster_by_index
            else [f"p{index:03d}-{slot:02d}" for slot in range(9)]
        )
        counts = {block: 1 for block in blocks}
        candidates.append({
            "lineup_id": lineup_id,
            "roster_player_ids": sorted(roster),
            "training_origin_blocks": list(blocks),
            "training_source_arms": ["incumbent"],
            "training_occurrence_counts_by_block": counts,
            "training_source_arms_by_block": {
                block: ["incumbent"] for block in blocks
            },
            "training_occurrence_count": len(blocks),
        })
    return candidates


def _fixture(
    *, candidate_count: int = 160, worlds_per_block: int = 32
) -> tuple[list[str], np.ndarray, list[dict[str, object]], list[str], int]:
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    blocks = ["R0", "R1", "R2", "R3"]
    rng = np.random.default_rng(20_260_828)
    common = rng.normal(0.0, 10.0, size=(1, 4 * worlds_per_block))
    scores = np.ascontiguousarray(
        211.0
        + common
        + rng.normal(
            0.0, 24.0, size=(candidate_count, 4 * worlds_per_block)
        ),
        dtype=np.float64,
    )
    return (
        lineup_ids,
        scores,
        _candidate_rows(lineup_ids, blocks),
        blocks,
        worlds_per_block,
    )


def _run(
    fixture: tuple[
        list[str], np.ndarray, list[dict[str, object]], list[str], int
    ] | None = None,
) -> dict[str, object]:
    lineup_ids, scores, candidates, blocks, worlds_per_block = (
        _fixture() if fixture is None else fixture
    )
    return diversity.run_effective_independent_shots_selector_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
    )


def test_frozen_contract_discloses_one_mechanism_and_approximation() -> None:
    contract = diversity.frozen_diversity_selector_contract_v1()

    assert contract["contract_sha256"] == EXPECTED_CONTRACT_SHA256
    assert contract["strategy_id"] == (
        "effective-independent-tail-shots-dpp-ge-230-v1"
    )
    assert contract["entry_budget"] == 150
    assert contract["prefix_sizes"] == [80, 100, 150]
    assert contract["approximation_disclosure"] == {
        "global_size-k_maximum_determinant_solved_exactly": False,
        "reason": "global-cardinality-constrained-dpp-map-is-np-hard",
        "greedy_conditional_gain_computed_exactly_for_current_prefix": True,
        "floating_decision_quantization_is_part_of_law": True,
        "promotion_requires_heldout-realized-comparison": True,
    }
    assert all(value is False for value in contract["policy"].values())


def test_result_is_exact_deterministic_ranked_150_with_nested_prefixes() -> None:
    fixture = _fixture()
    original_scores = fixture[1].copy()
    original_candidates = deepcopy(fixture[2])

    result = _run(fixture)
    replay = _run(fixture)

    assert result == replay
    assert result["result_sha256"] == EXPECTED_FIXTURE_RESULT_SHA256
    assert result["entry_budget"] == 150
    assert result["prefix_sizes"] == [80, 100, 150]
    assert len(result["selected_lineup_ids"]) == 150
    assert len(set(result["selected_lineup_ids"])) == 150
    assert [row["prefix_size"] for row in result["prefixes"]] == [80, 100, 150]
    for prefix in result["prefixes"]:
        assert prefix["selected_lineup_ids"] == result["selected_lineup_ids"][
            : prefix["prefix_size"]
        ]
    assert all(value is False for value in result["policy"].values())
    assert result["input_binding"]["production_authority_validated"] is False
    assert np.array_equal(fixture[1], original_scores)
    assert fixture[2] == original_candidates


def test_diverse_tail_shot_beats_near_clone_after_quality_leader() -> None:
    candidate_count = 151
    worlds_per_block = 8
    blocks = ["R0", "R1", "R2", "R3"]
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    scores = np.full((candidate_count, 32), 200.0, dtype=np.float64)
    scores[0, :16] = 230.0
    scores[1, :16] = 230.0
    scores[2, 16:31] = 230.0
    shared = [f"shared-{slot:02d}" for slot in range(8)]
    roster_by_index = {
        0: [*shared, "unique-0"],
        1: [*shared, "unique-1"],
        2: [f"diverse-{slot:02d}" for slot in range(9)],
    }
    candidates = _candidate_rows(
        lineup_ids, blocks, roster_by_index=roster_by_index
    )

    result = _run((lineup_ids, scores, candidates, blocks, worlds_per_block))

    assert result["selected_lineup_ids"][:3] == [
        "lineup-000",
        "lineup-002",
        "lineup-001",
    ]
    assert result["selection_trace"][1]["conditional_determinant_gain"] > (
        result["selection_trace"][2]["conditional_determinant_gain"]
    )


def test_all_ties_use_ascending_lineup_id_order() -> None:
    candidate_count = 160
    worlds_per_block = 8
    blocks = ["R0", "R1", "R2", "R3"]
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    scores = np.full((candidate_count, 32), 200.0, dtype=np.float64)
    candidates = _candidate_rows(lineup_ids, blocks)

    result = _run((lineup_ids, scores, candidates, blocks, worlds_per_block))

    assert result["selected_lineup_ids"] == lineup_ids[:150]


def test_tail_threshold_is_inclusive_230() -> None:
    candidate_count = 150
    worlds_per_block = 8
    blocks = ["R0", "R1", "R2", "R3"]
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    scores = np.full((candidate_count, 32), 200.0, dtype=np.float64)
    scores[0, 0] = 230.0
    scores[1, 0] = np.nextafter(230.0, -np.inf)
    candidates = _candidate_rows(lineup_ids, blocks)

    result = _run((lineup_ids, scores, candidates, blocks, worlds_per_block))

    assert result["preprocessing"]["quality_mass_max"] == 2
    assert result["preprocessing"]["quality_mass_min"] == 1
    assert result["selected_lineup_ids"][0] == "lineup-000"


def test_kernel_is_psd_with_exact_integer_similarity_inputs() -> None:
    lineup_ids, scores, candidates, _blocks, _worlds_per_block = _fixture()
    packed, tail_counts = diversity._packed_tail_signatures_v1(scores)
    roster_overlaps = diversity._roster_overlap_counts_v1(candidates)
    kernel, _tail_similarity, intersections = (
        diversity._build_quality_weighted_kernel_v1(
            packed=packed,
            tail_counts=tail_counts,
            roster_overlaps=roster_overlaps,
        )
    )

    eigenvalues = np.linalg.eigvalsh(kernel)
    assert np.array_equal(intersections, intersections.T)
    assert np.array_equal(roster_overlaps, roster_overlaps.T)
    assert float(eigenvalues.min()) > 0.0
    assert kernel.shape == (len(lineup_ids), len(lineup_ids))


def test_replay_validator_rejects_tamper() -> None:
    fixture = _fixture()
    result = _run(fixture)

    assert diversity.validate_effective_independent_shots_result_v1(
        result,
        sampled_lineup_ids=fixture[0],
        training_score_matrix=fixture[1],
        candidate_rows=fixture[2],
        training_blocks=fixture[3],
        worlds_per_block=fixture[4],
    ) == result

    tampered = deepcopy(result)
    tampered["selected_lineup_ids"][0] = "lineup-tampered"
    with pytest.raises(
        diversity.CorpusR6CurrentBankDiversitySelectorV1Error,
        match="differs from exact pure replay",
    ):
        diversity.validate_effective_independent_shots_result_v1(
            tampered,
            sampled_lineup_ids=fixture[0],
            training_score_matrix=fixture[1],
            candidate_rows=fixture[2],
            training_blocks=fixture[3],
            worlds_per_block=fixture[4],
        )


def test_fails_closed_below_exact_150_candidate_budget() -> None:
    fixture = _fixture(candidate_count=149)

    with pytest.raises(
        diversity.CorpusR6CurrentBankDiversitySelectorV1Error,
        match="requires 150..250",
    ):
        _run(fixture)
