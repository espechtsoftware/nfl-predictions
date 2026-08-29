from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_extreme_tail_retrieval_suite as retrieval_suite,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as current_contract,
)
from nfl_dfs.research import (
    corpus_r6_selector_diversity_challengers_v1 as challengers,
)


BLOCKS = ["R0", "R1", "R2", "R3"]


def _candidate_rows(
    lineup_ids: list[str],
    *,
    shared_players: int = 0,
    roster_by_index: dict[int, list[str]] | None = None,
) -> list[dict[str, object]]:
    shared = [f"shared-{slot:02d}" for slot in range(shared_players)]
    rows: list[dict[str, object]] = []
    for index, lineup_id in enumerate(lineup_ids):
        roster = (
            roster_by_index[index]
            if roster_by_index is not None and index in roster_by_index
            else [
                *shared,
                *[
                    f"p{index:03d}-{slot:02d}"
                    for slot in range(9 - shared_players)
                ],
            ]
        )
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": sorted(roster),
            "training_origin_blocks": list(BLOCKS),
            "training_source_arms": ["incumbent"],
            "training_occurrence_counts_by_block": {
                block: 1 for block in BLOCKS
            },
            "training_source_arms_by_block": {
                block: ["incumbent"] for block in BLOCKS
            },
            "training_occurrence_count": len(BLOCKS),
        })
    return rows


def _fixture(
    *, candidate_count: int = 160, worlds_per_block: int = 8,
    shared_players: int = 0,
) -> tuple[list[str], np.ndarray, list[dict[str, object]], int]:
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    rng = np.random.default_rng(20_260_829)
    scores = np.ascontiguousarray(
        rng.normal(
            208.0,
            21.0,
            size=(candidate_count, len(BLOCKS) * worlds_per_block),
        ),
        dtype=np.float64,
    )
    return (
        lineup_ids,
        scores,
        _candidate_rows(lineup_ids, shared_players=shared_players),
        worlds_per_block,
    )


def _run(
    fixture: tuple[list[str], np.ndarray, list[dict[str, object]], int]
    | None = None,
) -> dict[str, object]:
    lineup_ids, scores, candidates, worlds_per_block = (
        _fixture() if fixture is None else fixture
    )
    return challengers.run_diversity_challengers_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=BLOCKS,
        worlds_per_block=worlds_per_block,
    )


def test_contract_is_bounded_outcome_free_and_reuses_tail_ladder() -> None:
    contract = challengers.diversity_challenger_contract_v1()

    assert contract["base_strategy_id"] == "tail-ladder-200-210-220-v1"
    assert contract["base_strategy_sha256"] == challengers.BASE_STRATEGY_SHA256
    assert contract["overlap_cap_variants"] == [3, 4, 5]
    assert contract["entry_budgets"] == [80, 100, 150]
    assert contract["evil_twin_law"]["pair_event"] == {
        "threshold": 200.0,
        "operator": ">",
    }
    assert contract["overlap_cap_optimality_claimed"] is False
    assert all(value is False for value in contract["policy"].values())
    assert contract["contract_sha256"] == challengers._sha({
        key: value
        for key, value in contract.items()
        if key != "contract_sha256"
    })


def test_disjoint_fixture_emits_four_exact_nested_80_100_150_orders() -> None:
    fixture = _fixture()
    fixture[1].flags.writeable = False
    original_scores = fixture[1].copy()
    original_candidates = deepcopy(fixture[2])

    result = _run(fixture)
    replay = _run(fixture)

    assert result == replay
    assert result["selector_count"] == 4
    assert all(value is False for value in result["policy"].values())
    for selector in result["selectors"]:
        assert selector["status"] == "exact-rank-150"
        assert selector["greedy_prefix_count"] == 150
        assert selector["entry_budgets_available"] == [80, 100, 150]
        assert [book["entry_budget"] for book in selector["entry_books"]] == [
            80,
            100,
            150,
        ]
        ranked = selector["ranked_lineup_ids"]
        for book in selector["entry_books"]:
            assert book["selected_lineup_ids"] == ranked[: book["entry_budget"]]
            assert len(book["effective_tail_shots"]) == 4
            assert [
                row["threshold"] for row in book["effective_tail_shots"]
            ] == [200.0, 210.0, 220.0, 230.0]
            assert all(
                row["uses_realized_outcomes"] is False
                for row in book["effective_tail_shots"]
            )
    assert np.array_equal(fixture[1], original_scores)
    assert fixture[2] == original_candidates


def test_gamma_caps_stop_instead_of_silently_relaxing() -> None:
    result = _run(_fixture(shared_players=6))

    for gamma, selector in zip(
        challengers.OVERLAP_CAPS, result["selectors"][:3], strict=True
    ):
        assert selector["strategy_id"].endswith(f"cap-{gamma}-v1")
        assert selector["status"] == "infeasible-before-exact-80"
        assert selector["greedy_prefix_count"] == 1
        assert selector["entry_budgets_available"] == []
        assert selector["entry_books"] == []
        assert selector["selector_summary"] == {
            "overlap_cap": gamma,
            "greedy_prefix_count": 1,
            "ranking_depth_reached": False,
            "unselected_feasible_candidate_count_at_stop": 0,
            "global_maximum_feasible_cardinality_claimed": False,
            "cap_relaxed": False,
        }
    assert result["selectors"][3]["status"] == "exact-rank-150"


def test_gamma_boundary_filters_higher_utility_four_player_overlap() -> None:
    lineup_ids = [f"lineup-{index:03d}" for index in range(4)]
    roster_by_index = {
        0: list("abcdefghi"),
        1: ["a", "b", "c", "j", "k", "l", "m", "n", "o"],
        2: ["a", "b", "c", "d", "p", "q", "r", "s", "t"],
        3: ["u", "v", "w", "x", "y", "z", "za", "zb", "zc"],
    }
    candidates = _candidate_rows(
        lineup_ids, roster_by_index=roster_by_index
    )
    scores = np.full((4, 8), 190.0, dtype=np.float64)
    for index, event_count in enumerate((8, 6, 7, 5)):
        scores[index, :event_count] = 221.0
    masks = challengers._pack_strict_masks(scores)
    counts = challengers._row_counts(masks[0])
    overlaps = challengers._roster_overlap_matrix(candidates)
    means = scores.mean(axis=1, dtype=np.float64)

    gamma3, _trace3, _summary3 = challengers._run_overlap_cap_order(
        gamma=3,
        lineup_ids=lineup_ids,
        masks=masks,
        primary_counts=counts,
        means=means,
        roster_overlaps=overlaps,
    )
    gamma4, _trace4, _summary4 = challengers._run_overlap_cap_order(
        gamma=4,
        lineup_ids=lineup_ids,
        masks=masks,
        primary_counts=counts,
        means=means,
        roster_overlaps=overlaps,
    )

    assert gamma3[:2] == [0, 1]
    assert gamma4[:2] == [0, 2]
    assert int(overlaps[gamma3[0], gamma3[1]]) == 3
    assert int(overlaps[gamma4[0], gamma4[1]]) == 4


def test_evil_twin_forces_negative_partner_before_better_positive_clone() -> None:
    candidate_count = 150
    worlds_per_block = 8
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    scores = np.full((candidate_count, 32), 190.0, dtype=np.float64)
    # Equal total ladder quality makes lineup-000 the stable first anchor.
    scores[0, :24] = 221.0
    # Positive-correlated near-clone adds four high-rung worlds after anchor.
    scores[1, :20] = 221.0
    scores[1, 28:32] = 221.0
    # Exact complement has lower marginal ladder utility but correlation -1.
    scores[2, 24:32] = 205.0
    fixture = (
        lineup_ids,
        scores,
        _candidate_rows(lineup_ids),
        worlds_per_block,
    )

    result = _run(fixture)
    evil = result["selectors"][3]

    assert evil["ranked_lineup_ids"][:3] == [
        "lineup-000",
        "lineup-002",
        "lineup-001",
    ]
    assert evil["selector_summary"]["negative_tail_partner_count"] >= 1
    # Replay output binds the full trace by hash; inspect the direct primitive
    # to prove why the second coordinate was selected.
    masks = challengers._pack_strict_masks(scores)
    counts = challengers._row_counts(masks[0])
    selected, trace, _summary = challengers._run_evil_twin_order(
        lineup_ids=lineup_ids,
        masks=masks,
        primary_counts=counts,
        means=scores.mean(axis=1, dtype=np.float64),
        world_count=scores.shape[1],
    )
    assert selected[:3] == [0, 2, 1]
    assert trace[1]["selection_role"] == "negative-tail-evil-twin"
    assert trace[1]["anchor_tail_correlation_micro"] == -1_000_000


def test_unconstrained_primitive_has_exact_frozen_ladder_parity() -> None:
    lineup_ids, scores, candidates, _worlds_per_block = _fixture()
    masks = challengers._pack_strict_masks(scores)
    counts = challengers._row_counts(masks[0])
    overlaps = challengers._roster_overlap_matrix(candidates)

    selected, _trace, summary = challengers._run_overlap_cap_order(
        gamma=9,
        lineup_ids=lineup_ids,
        masks=masks,
        primary_counts=counts,
        means=scores.mean(axis=1, dtype=np.float64),
        roster_overlaps=overlaps,
    )
    expected, _expected_trace = retrieval_suite._select_ladder_packed(
        scores,
        budget=150,
        rungs=[
            {"threshold": threshold, "operator": operator, "weight": weight}
            for threshold, operator, weight in challengers.TAIL_RUNGS
        ],
        lineup_ids=lineup_ids,
    )

    assert summary["ranking_depth_reached"] is True
    assert selected == expected


def test_effective_tail_shots_distinguish_independent_and_duplicate_rows() -> None:
    independent_events = np.asarray([
        [0, 0, 0, 0, 1, 1, 1, 1],
        [0, 0, 1, 1, 0, 0, 1, 1],
        [0, 1, 0, 1, 0, 1, 0, 1],
    ], dtype=bool)
    independent_scores = np.where(independent_events, 201.0, 199.0).astype(
        np.float64
    )
    duplicate_scores = np.vstack([
        independent_scores[0], independent_scores[0], independent_scores[0]
    ])

    independent = challengers._effective_tail_shots(
        independent_scores, threshold=200.0
    )
    duplicate = challengers._effective_tail_shots(
        duplicate_scores, threshold=200.0
    )

    assert independent["participation_ratio_micro"] == 3_000_000
    assert independent["entropy_effective_rank_micro"] == 3_000_000
    assert duplicate["participation_ratio_micro"] == 1_000_000
    assert duplicate["entropy_effective_rank_micro"] == 1_000_000
    assert independent["pairwise_active_correlation_mean_micro"] == 0
    assert duplicate["pairwise_active_correlation_mean_micro"] == 1_000_000


def test_effective_tail_diagnostics_match_frozen_rank80_law() -> None:
    _lineup_ids, scores, _candidates, _worlds_per_block = _fixture()
    selected = np.ascontiguousarray(scores[:80], dtype=np.float64)

    for threshold in challengers.EFFECTIVE_SHOT_THRESHOLDS:
        observed = challengers._effective_tail_shots(
            selected, threshold=threshold
        )
        expected = current_contract._effective_independent_tail_shots_fixture_v1(
            selected, threshold=threshold
        )
        for field in (
            "active_tail_lineup_count",
            "zero_event_lineup_count",
            "all_event_lineup_count",
            "active_pair_count",
            "pairwise_active_correlation_mean_micro",
            "pairwise_active_correlation_minimum_micro",
            "pairwise_active_correlation_maximum_micro",
            "participation_ratio_micro",
            "entropy_effective_rank_micro",
        ):
            assert observed[field] == expected[field]


def test_result_replay_rejects_book_tamper() -> None:
    fixture = _fixture()
    result = _run(fixture)

    assert challengers.validate_diversity_challengers_v1(
        result,
        sampled_lineup_ids=fixture[0],
        training_score_matrix=fixture[1],
        candidate_rows=fixture[2],
        training_blocks=BLOCKS,
        worlds_per_block=fixture[3],
    ) == result

    tampered = deepcopy(result)
    tampered["selectors"][0]["entry_books"][0]["selected_lineup_ids"][0] = (
        "lineup-tampered"
    )
    with pytest.raises(
        challengers.CorpusR6SelectorDiversityChallengersV1Error,
        match="differs from exact pure replay",
    ):
        challengers.validate_diversity_challengers_v1(
            tampered,
            sampled_lineup_ids=fixture[0],
            training_score_matrix=fixture[1],
            candidate_rows=fixture[2],
            training_blocks=BLOCKS,
            worlds_per_block=fixture[3],
        )


def test_all_emitted_overlap_cap_books_obey_their_exact_gamma() -> None:
    fixture = _fixture(candidate_count=250)
    result = _run(fixture)
    roster_by_id = {
        row["lineup_id"]: set(row["roster_player_ids"])
        for row in fixture[2]
    }

    for gamma, selector in zip(
        challengers.OVERLAP_CAPS, result["selectors"][:3], strict=True
    ):
        assert selector["status"] == "exact-rank-150"
        for book in selector["entry_books"]:
            selected = book["selected_lineup_ids"]
            assert max(
                len(roster_by_id[left] & roster_by_id[right])
                for left_index, left in enumerate(selected)
                for right in selected[left_index + 1:]
            ) <= gamma


def test_evil_twin_fully_rehashed_tamper_still_fails_exact_replay() -> None:
    fixture = _fixture()
    result = _run(fixture)
    tampered = deepcopy(result)
    evil = tampered["selectors"][-1]
    evil["ranked_lineup_ids"][:2] = evil["ranked_lineup_ids"][1::-1]
    evil["ranked_lineup_ids_sha256"] = challengers._sha(
        evil["ranked_lineup_ids"]
    )
    for book in evil["entry_books"]:
        budget = book["entry_budget"]
        book["selected_lineup_ids"] = evil["ranked_lineup_ids"][:budget]
        book["selected_lineup_ids_sha256"] = challengers._sha(
            book["selected_lineup_ids"]
        )
        roster_by_id = {
            row["lineup_id"]: row["roster_player_ids"] for row in fixture[2]
        }
        book["selected_rosters_sha256"] = challengers._sha([
            roster_by_id[lineup_id] for lineup_id in book["selected_lineup_ids"]
        ])
        book.pop("book_sha256")
        book["book_sha256"] = challengers._sha(book)
    evil["entry_book_sha256s"] = [
        book["book_sha256"] for book in evil["entry_books"]
    ]
    evil.pop("selector_result_sha256")
    evil["selector_result_sha256"] = challengers._sha(evil)
    tampered["selector_result_sha256s"][-1] = evil[
        "selector_result_sha256"
    ]
    tampered.pop("result_sha256")
    tampered["result_sha256"] = challengers._sha(tampered)

    with pytest.raises(
        challengers.CorpusR6SelectorDiversityChallengersV1Error,
        match="differs from exact pure replay",
    ):
        challengers.validate_diversity_challengers_v1(
            tampered,
            sampled_lineup_ids=fixture[0],
            training_score_matrix=fixture[1],
            candidate_rows=fixture[2],
            training_blocks=BLOCKS,
            worlds_per_block=fixture[3],
        )


def test_duplicate_candidate_roster_fails_closed_before_selection() -> None:
    fixture = _fixture()
    fixture[2][1]["roster_player_ids"] = list(
        fixture[2][0]["roster_player_ids"]
    )
    with pytest.raises(
        challengers.CorpusR6SelectorDiversityChallengersV1Error,
        match="unique candidate rosters",
    ):
        _run(fixture)


def test_fails_closed_below_rank150_input() -> None:
    with pytest.raises(
        challengers.CorpusR6SelectorDiversityChallengersV1Error,
        match="at least 150",
    ):
        _run(_fixture(candidate_count=149))
