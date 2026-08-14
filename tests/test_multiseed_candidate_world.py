import numpy as np
import pandas as pd
import pytest

from nfl_dfs.optimizer.lineup import select_from_support
from nfl_dfs.research.multiseed_candidate_world import (
    ARMS,
    evaluate_factorial_slate,
    summarize_factorial,
    summarize_standalone_seed_books,
    validate_and_cross_score_slate,
)


ROSTERS = (
    tuple(f"p{i}" for i in range(9)),
    tuple(f"p{i}" for i in range(1, 10)),
    tuple(f"p{i}" for i in range(2, 11)),
)


def _fixture(seeds=(0, 1, 2), worlds=200):
    rows, artifacts = {}, {}
    all_ids = [f"p{i}" for i in range(11)]
    for seed in seeds:
        rng = np.random.default_rng(100 + seed)
        player_draws = rng.normal(
            np.linspace(12, 24, len(all_ids))[:, None], 8,
            size=(len(all_ids), worlds),
        ).astype(np.float32)
        # Each seed has one shared and two seed-specific roster identities by
        # rotating the non-shared player ids inside the same full universe.
        seed_rosters = [ROSTERS[0]]
        seed_rosters.extend(
            tuple(all_ids[(i + seed) % len(all_ids)] for i in range(9))
            for seed_offset in (1, 2)
            for i in [seed_offset]
        )
        # Avoid accidental duplicate player ids after modular construction.
        seed_rosters = [seed_rosters[0], ROSTERS[(seed % 2) + 1],
                        tuple(reversed(ROSTERS[((seed + 1) % 2) + 1]))]
        id_to_row = {player_id: index for index, player_id in enumerate(all_ids)}
        totals = np.stack([
            player_draws[[id_to_row[player] for player in roster]].sum(axis=0)
            for roster in seed_rosters
        ]).astype(np.float32)
        picked = select_from_support(
            totals >= 194, (totals >= 194).mean(axis=1), totals.mean(axis=1), 2
        )
        selected_rank = {index: rank for rank, index in enumerate(picked)}
        rows[seed] = pd.DataFrame([
            {
                "cand_ix": index,
                "players": ",".join(roster),
                "selected": index in selected_rank,
                "selected_rank": selected_rank.get(index, -1),
                "actual_score": float(100 + sum(int(player[1:]) for player in roster)),
            }
            for index, roster in enumerate(seed_rosters)
        ])
        artifacts[seed] = {
            "cand_ix": np.arange(len(totals), dtype=np.int32),
            "totals": totals,
            "tail_line": np.float32(194),
            "player_ids": np.asarray(all_ids),
            "player_draws": player_draws,
        }
    return rows, artifacts


def test_cross_scores_every_candidate_in_every_seed_world():
    rows, artifacts = _fixture()
    canonical, cross = validate_and_cross_score_slate(
        rows, artifacts, entry_count=2
    )
    assert set(canonical) == {0, 1, 2}
    assert set(cross) == {
        (candidate_seed, world_seed)
        for candidate_seed in range(3) for world_seed in range(3)
    }
    assert cross[(1, 2)].shape == (3, 200)
    assert not np.array_equal(cross[(1, 1)], cross[(1, 2)])


def test_factorial_returns_exact_books_and_equal_weight_world_union():
    rows, artifacts = _fixture()
    result = evaluate_factorial_slate(rows, artifacts, entry_count=2)
    assert set(result["arms"]) == set(ARMS)
    assert set(result["standalone_seed_books"]) == {"R0", "R1", "R2"}
    assert set(result["fixed_budget_confirmation"]) == {"CBW0", "CBWU"}
    assert all(
        len(book["selected_rosters"]) == 2
        for book in result["standalone_seed_books"].values()
    )
    for arm, report in result["arms"].items():
        assert len(report["selected_rosters"]) == 2
        assert report["world_count"] == (600 if "WU" in arm else 200)
        assert set(report["simulated_weekly_best_quantile"]) == {"0.95", "0.99"}
    assert all(
        book["candidate_count"] == result["arms"]["C0W0"]["candidate_count"]
        for book in result["fixed_budget_confirmation"].values()
    )
    assert result["arms"]["C0W0"]["candidate_count"] == 3
    assert result["arms"]["CUWU"]["candidate_count"] >= 3


def test_rejects_native_totals_that_do_not_reconstruct():
    rows, artifacts = _fixture()
    artifacts[1]["totals"] = artifacts[1]["totals"].copy()
    artifacts[1]["totals"][0, 0] += 0.1
    with pytest.raises(ValueError, match="do not reconstruct"):
        validate_and_cross_score_slate(rows, artifacts, entry_count=2)


def test_rejects_mismatched_player_universe():
    rows, artifacts = _fixture()
    artifacts[2]["player_ids"] = artifacts[2]["player_ids"].copy()
    artifacts[2]["player_ids"][0] = "missing"
    with pytest.raises(ValueError, match="universes differ"):
        validate_and_cross_score_slate(rows, artifacts, entry_count=2)


def test_tail_first_summary_and_least_change_tie_break():
    slate = {
        "arms": {
            arm: {
                "selected_best": 200.0,
                "oracle_best": 210.0,
                "candidate_count": 3,
                "selected_overlap_c0w0": 2,
                "simulated_weekly_best_quantile": {
                    "0.95": 205.0,
                    "0.99": 215.0,
                },
            }
            for arm in ARMS
        },
        "fixed_budget_confirmation": {
            arm: {
                "selected_best": 200.0,
                "oracle_best": 210.0,
                "candidate_count": 3,
                "simulated_weekly_best_quantile": {
                    "0.95": 205.0,
                    "0.99": 215.0,
                },
            }
            for arm in ("CBW0", "CBWU")
        },
    }
    tied = summarize_factorial([slate])
    assert tied["selected_arm"] == "C0W0"
    assert tied["production_selected_arm"] == "C0W0"

    slate["arms"]["CUWU"]["selected_best"] = 241.0
    won = summarize_factorial([slate])
    assert won["selected_arm"] == "CUWU"
    assert won["metrics"]["CUWU"]["selected_tail"]["240"] == 1
    assert won["production_selected_arm"] == "C0W0"
    assert won["candidate_union_confirmation_required"] is True
    assert won["final_production_arm"] == "C0W0"

    slate["fixed_budget_confirmation"]["CBW0"]["selected_best"] = 242.0
    confirmed = summarize_factorial([slate])
    assert confirmed["final_production_arm"] == "CBW0"


def test_standalone_seed_noise_floor_and_proper_scores():
    rows, artifacts = _fixture()
    result = evaluate_factorial_slate(rows, artifacts, entry_count=2)
    summary = summarize_standalone_seed_books([result])
    assert set(summary["metrics"]) == {"R0", "R1", "R2"}
    assert summary["pairwise_selected_overlap_mean"] >= 0
    assert set(summary["tail_count_envelope"]) == {
        "240", "230", "220", "210", "200", "194", "187",
    }
    for seed in summary["metrics"].values():
        scores = seed["selected_weekly_best_pinball"]
        assert set(scores) == {"0.95", "0.99"}
        assert all(value >= 0 for value in scores.values())
