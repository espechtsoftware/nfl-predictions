from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference import prospective_generation_retrieval_crossing as crossing
from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries


def _fixture() -> tuple[
    dict[str, CandidateBatch], dict[str, list[Lineup]], dict[object, str]
]:
    rng = np.random.default_rng(20260830)
    players = [
        {
            "id": f"p{index:03d}",
            "name": f"P{index}",
            "pos": "WR",
            "team": f"T{index % 12}",
            "opp": f"T{(index + 1) % 12}",
            "game_id": f"G{index % 6}",
            "salary": 5_000,
            "proj": 20.0,
        }
        for index in range(99)
    ]
    row_draws = rng.normal(
        20.0, 7.0, size=(len(players), crossing.WORLD_COUNT)
    ).astype(np.float32)

    def batch(offset: int) -> CandidateBatch:
        lineups = tuple(
            Lineup(
                [players[(offset + start + step) % len(players)] for step in range(9)],
                tag="boom" if offset else "lev",
            )
            for start in range(90)
        )
        totals = np.stack(
            [
                row_draws[
                    [int(str(player_id)[1:]) for player_id in lineup.ids]
                ].sum(axis=0)
                for lineup in lineups
            ]
        ).astype(np.float32)
        return CandidateBatch(
            candidates=lineups,
            candidate_totals=totals,
            player_ids=tuple(player["id"] for player in players),
            player_rows=tuple(players),
            row_draws=row_draws,
            all_tags={lineup.ids: (lineup.tag,) for lineup in lineups},
            metadata={
                "portfolio": "CBWU",
                "world_blocks": 5,
                "worlds_per_block": [10_000] * 5,
                "native_generation_exposure_ledgers": {
                    "sentinel": {"must_remain": "unchanged"}
                },
            },
        )

    populations = {
        "incumbent-160-40": batch(0),
        "boom-first-40-160": batch(7),
    }
    books = {
        population_id: [
            candidate_batch.candidates[index]
            for index in select_tail_entries(
                candidate_batch.candidate_totals, 80, 194.0, env={}
            )
        ]
        for population_id, candidate_batch in populations.items()
    }
    mapping = {
        player["id"]: f"dk-{index:03d}"
        for index, player in enumerate(players)
    }
    return populations, books, mapping


def _audit_draws(populations: dict[str, CandidateBatch]) -> np.ndarray:
    return np.random.default_rng(20260831).normal(
        20.0,
        7.0,
        size=(
            len(populations["incumbent-160-40"].player_ids),
            crossing.AUDIT_WORLD_COUNT,
        ),
    ).astype(np.float32)


@pytest.fixture(scope="module")
def frozen_crossing():
    populations, books, mapping = _fixture()
    ledgers_before = {
        arm: batch.metadata["native_generation_exposure_ledgers"].copy()
        for arm, batch in populations.items()
    }
    cap_books, receipt = crossing.build_generation_retrieval_crossing(
        populations,
        books,
        mapping,
        independent_audit_row_draws=_audit_draws(populations),
    )
    return populations, books, mapping, ledgers_before, cap_books, receipt


def test_crossing_freezes_exact_2x2_and_never_regenerates(
    frozen_crossing,
) -> None:
    populations, _books, _mapping, ledgers_before, cap_books, receipt = (
        frozen_crossing
    )

    assert receipt["schema_version"] == crossing.SCHEMA_VERSION
    assert receipt["population_order"] == list(crossing.POPULATION_ORDER)
    assert receipt["retrieval_order"] == list(crossing.RETRIEVAL_ORDER)
    assert len(receipt["cell_order"]) == 4
    assert receipt["candidate_solves_requested_by_crossing"] == 0
    assert receipt["shared_generation_exposure_ledger_modified"] is False
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["post_lock_data_read"] is False
    assert receipt["report_thresholds"] == [194, 200, 210, 220, 230, 240]
    assert receipt["shared_selection_bank"]["world_count"] == 50_000
    assert receipt["shared_selection_bank"][
        "identical_across_both_populations"
    ] is True

    for population_id in crossing.POPULATION_ORDER:
        population = receipt["populations"][population_id]
        assert population["same_candidate_pool_for_both_official_retrievals"]
        assert population["candidate_solves_requested_by_crossing"] == 0
        assert len(population["candidate_lineup_ids"]) == 90
        assert len(cap_books[population_id]) == 80
        retrievals = population["retrievals"]
        assert list(retrievals) == list(crossing.RETRIEVAL_ORDER)
        for retrieval_id in crossing.RETRIEVAL_ORDER:
            book = retrievals[retrieval_id]
            assert len(book["selected_lineup_ids"]) == 80
            assert len(book["selected_rosters"]) == 80
            assert list(book["prefixes"]) == ["20", "40", "80"]
            assert list(
                book["simulated_diagnostics"][
                    "simulated_p_book_max_at_least"
                ]
            ) == ["194", "200", "210", "220", "230", "240"]
            assert book["selector_runtime_seconds"] >= 0.0
            assert book["uses_realized_outcomes"] is False
        cap = retrievals[crossing.CAP4_RETRIEVAL_ID]
        engagement = cap["cap_engagement"]
        assert engagement["overlap_cap"] == 4
        assert engagement["cap_relaxed_within_hard_cap_prefix"] is False
        assert engagement["prefix_exhaustion_is_not_cap_engagement"] is True
        assert engagement["unique_candidates_excluded_by_cap_count"] > 0
        assert engagement["cap_engaged_rank_count"] > 0
        assert cap["selection_trace_sha256"] == canonical_sha256(
            cap["selection_trace"]
        )
        assert population["incumbent_vs_cap4"][
            "membership_choices_changed_per_side"
        ] >= 0
        assert population["cap4_vs_uncapped_ladder"][
            "ordered_position_change_count"
        ] >= 0
        assert populations[population_id].metadata[
            "native_generation_exposure_ledgers"
        ] == ledgers_before[population_id]

    root_science = dict(receipt)
    root_science.pop("science_sha256_excluding_runtime")
    root_science.pop("receipt_sha256")
    assert receipt["science_sha256_excluding_runtime"] == canonical_sha256(
        crossing._without_runtime(root_science)
    )
    receipt_without_hash = dict(receipt)
    receipt_hash = receipt_without_hash.pop("receipt_sha256")
    assert receipt_hash == canonical_sha256(receipt_without_hash)


def test_cap_trace_measures_feasible_set_and_same_path_choice_changes(
    frozen_crossing,
) -> None:
    receipt = frozen_crossing[-1]
    for population_id in crossing.POPULATION_ORDER:
        cap = receipt["populations"][population_id]["retrievals"][
            crossing.CAP4_RETRIEVAL_ID
        ]
        prefix_count = cap["cap_engagement"]["hard_cap_prefix_count"]
        prefix = cap["selection_trace"][:prefix_count]
        assert any(row["cap_engaged_before_pick"] for row in prefix)
        assert cap["cap_engagement"][
            "cap_changed_same_path_choice_rank_count"
        ] == sum(row["choice_changed_by_cap_on_same_path"] for row in prefix)
        assert cap["cap_engagement"][
            "cap_excluded_candidate_instances_across_prefix"
        ] == sum(
            row["cap_excluded_candidate_count_before_pick"] for row in prefix
        )
        assert all(
            row["maximum_overlap_with_prior_roster"] <= 4 for row in prefix
        )


def test_cap_selector_records_a_same_path_choice_change() -> None:
    scores = np.full((81, 32), 190.0, dtype=np.float32)
    scores[0] = 250.0
    scores[1] = 240.0
    scores[1, -1] = 190.0
    scores[2] = 230.0
    scores[2, -2:] = 190.0
    rosters = [
        frozenset(f"p{index}" for index in range(9)),
        frozenset([*(f"p{index}" for index in range(8)), "p9"]),
        frozenset(f"p{index}" for index in range(10, 19)),
    ]
    rosters.extend(
        frozenset(f"p{100 + ordinal * 9 + index}" for index in range(9))
        for ordinal in range(78)
    )
    lineup_ids = [f"lineup-{index:03d}" for index in range(81)]

    selected, summary, trace = crossing._cap4_prefix_then_fill(
        scores=scores,
        lineup_ids=lineup_ids,
        rosters=rosters,
        entry_budget=80,
    )

    assert len(selected) == 80
    assert selected[:2] == [0, 2]
    assert trace[1]["unconstrained_best_on_same_path_lineup_id"] == "lineup-001"
    assert trace[1]["choice_changed_by_cap_on_same_path"] is True
    assert summary["cap_changed_same_path_choice_ranks"][0] == 1
    assert summary["cap_changed_same_path_choice_rank_count"] == 79
    assert summary["unique_candidates_excluded_by_cap_count"] == 1


def test_crossing_rejects_candidate_scores_not_from_shared_bank() -> None:
    populations, books, mapping = _fixture()
    drifted = dict(populations)
    totals = populations["incumbent-160-40"].candidate_totals.copy()
    totals[0, 0] += np.float32(0.25)
    drifted["incumbent-160-40"] = replace(
        populations["incumbent-160-40"], candidate_totals=totals
    )

    with pytest.raises(
        crossing.ProspectiveGenerationRetrievalCrossingError,
        match="score row differs",
    ):
        crossing.build_generation_retrieval_crossing(
            drifted,
            books,
            mapping,
            independent_audit_row_draws=_audit_draws(populations),
        )


def test_crossing_rejects_non_common_player_world_bank() -> None:
    populations, books, mapping = _fixture()
    drifted = dict(populations)
    worlds = populations["boom-first-40-160"].row_draws.copy()
    worlds[0, 0] += np.float32(0.25)
    drifted["boom-first-40-160"] = replace(
        populations["boom-first-40-160"], row_draws=worlds
    )

    with pytest.raises(
        crossing.ProspectiveGenerationRetrievalCrossingError,
        match="common selection bank",
    ):
        crossing.build_generation_retrieval_crossing(
            drifted,
            books,
            mapping,
            independent_audit_row_draws=_audit_draws(populations),
        )


def test_frozen_selector_law_is_exact_production_not_lab_analog() -> None:
    assert crossing.SELECTION_RUNGS == (
        (200.0, 1),
        (210.0, 4),
        (220.0, 12),
    )
    assert 194.0 not in {threshold for threshold, _ in crossing.SELECTION_RUNGS}
    assert crossing.REPORT_THRESHOLDS == (194, 200, 210, 220, 230, 240)


def test_cap_prefix_order_matches_existing_production_kernel() -> None:
    from nfl_dfs.research import (
        corpus_r6_selector_diversity_challengers_v1 as production,
    )

    rng = np.random.default_rng(83)
    scores = rng.normal(195.0, 28.0, size=(160, 257)).astype(np.float32)
    lineup_ids = [f"lineup-v1-{index:03d}" for index in range(160)]
    rosters = [
        frozenset(
            f"player-{ordinal * 9 + player}" for player in range(9)
        )
        for ordinal in range(160)
    ]
    candidates = [
        {"roster_player_ids": sorted(roster)} for roster in rosters
    ]
    masks = production._pack_strict_masks(scores)
    reference, _trace, _summary = production._run_overlap_cap_order(
        gamma=4,
        lineup_ids=lineup_ids,
        masks=masks,
        primary_counts=production._row_counts(masks[0]),
        means=scores.mean(axis=1, dtype=np.float64),
        roster_overlaps=production._roster_overlap_matrix(candidates),
    )

    selected, summary, _trace = crossing._cap4_prefix_then_fill(
        scores=scores,
        lineup_ids=lineup_ids,
        rosters=rosters,
        entry_budget=80,
    )

    assert len(reference) == 150
    assert selected == reference[:80]
    assert summary["hard_cap_prefix_reached_k80"] is True
    assert summary["completion_count"] == 0
