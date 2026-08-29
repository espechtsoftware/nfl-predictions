from __future__ import annotations

from dataclasses import replace
from itertools import combinations
import os

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine, replay
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.research import boom_first_historical_paired_v1 as paired
from nfl_dfs.research import boom_first_historical_replay_adapter_v1 as adapter


def _identity(name: str) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "17",
        "sha256": "a" * 64,
        "bytes": 123,
    }


def _skill_players() -> tuple[dict[str, object], ...]:
    specs = (
        ("qb-a", "QB", "A", "B", "A@B", 6_200),
        ("qb-c", "QB", "C", "D", "C@D", 5_900),
        ("rb-a", "RB", "A", "B", "A@B", 6_800),
        ("rb-b", "RB", "B", "A", "A@B", 5_700),
        ("rb-c", "RB", "C", "D", "C@D", 6_100),
        ("wr-a1", "WR", "A", "B", "A@B", 5_500),
        ("wr-a2", "WR", "A", "B", "A@B", 4_500),
        ("wr-b1", "WR", "B", "A", "A@B", 5_300),
        ("wr-b2", "WR", "B", "A", "A@B", 4_200),
        ("wr-c1", "WR", "C", "D", "C@D", 5_800),
        ("wr-d1", "WR", "D", "C", "C@D", 4_800),
        ("te-a", "TE", "A", "B", "A@B", 3_900),
        ("te-b", "TE", "B", "A", "A@B", 3_600),
        ("te-d", "TE", "D", "C", "C@D", 3_500),
    )
    return tuple({
        "gsis_id": player_id,
        "name": player_id,
        "position": position,
        "team": team,
        "opponent": opponent,
        "game_id": game,
        "salary": salary,
    } for player_id, position, team, opponent, game, salary in specs)


def _inputs(*, poisoned_column: str | None = None) -> adapter.PITReplaySeasonInputs:
    panel_rows: list[dict[str, object]] = []
    for season in (2021, 2022):
        panel_rows.append({
            "season": season,
            "week": 1,
            "gsis_id": f"prior-{season}",
            "name": f"prior-{season}",
            "position": "QB",
            "team": "X",
            "opponent": "Y",
            "game_id": "X@Y",
            "salary": 6_000,
            "y_dk_points": 20.0,
            "y_targets": 0.0,
            "was_active": True,
            "actual": 20.0,
        })
    for player in _skill_players():
        panel_rows.append({
            **player,
            "season": 2023,
            "week": 1,
            "y_dk_points": np.nan,
            "y_targets": np.nan,
            "was_active": np.nan,
            "actual": np.nan,
        })
    panel = pd.DataFrame(panel_rows)
    if poisoned_column is not None:
        index = panel.index[panel.season == 2023][0]
        panel.loc[index, poisoned_column] = 1.0
    market = pd.DataFrame([{
        "season": 2023,
        "week": 1,
        "gsis_id": player["gsis_id"],
        "market_points": 14.0 + index / 10,
    } for index, player in enumerate(_skill_players())])
    tabpfn = pd.DataFrame([{
        "season": 2023,
        "week": 1,
        "gsis_id": player["gsis_id"],
        "q01": 1.0 + index / 100,
        "q99": 30.0 + index / 100,
    } for index, player in enumerate(_skill_players())])
    dst = pd.DataFrame([
        {
            "season": 2023,
            "week": 1,
            "team": "B",
            "opp": "A",
            "salary": 3_000,
            "dst_points_l4": np.nan,
            "opp_implied": 23.0,
            "opp_qb_starts": 20.0,
        },
        {
            "season": 2023,
            "week": 1,
            "team": "D",
            "opp": "C",
            "salary": 2_900,
            "dst_points_l4": 7.0,
            "opp_implied": 21.5,
            "opp_qb_starts": 2.0,
        },
    ])
    return adapter.PITReplaySeasonInputs(
        season=2023,
        panel=panel,
        dst_prelock=dst,
        market_points=market,
        tabpfn_marginals=tabpfn,
        source_identity_by_slate={"2023-w01": _identity("2023-w01-pit")},
    )


@pytest.fixture
def seven_world_policy(monkeypatch):
    policy = replace(ADOPTED_CLASSIC_POLICY, multiseed_worlds_per_block=7)
    monkeypatch.setattr(adapter, "ADOPTED_CLASSIC_POLICY", policy)
    monkeypatch.setattr(paired, "ADOPTED_CLASSIC_POLICY", policy)
    return policy


def _projection_frame(
    panel: pd.DataFrame, *, role: bool
) -> tuple[pd.DataFrame, np.ndarray]:
    target = panel[panel.season == 2023].reset_index(drop=True)
    frame = target[[
        "gsis_id", "name", "season", "week", "team", "opponent",
        "position", "game_id", "salary",
    ]].copy()
    offset = 1.0 if role else 0.0
    frame["proj_points"] = 11.0 + np.arange(len(frame)) / 3 + offset
    frame["proj_p10"] = frame.proj_points - 5.0
    frame["proj_p50"] = frame.proj_points
    frame["proj_p90"] = frame.proj_points + 8.0
    frame["proj_std"] = 6.0
    frame["proj_tail"] = frame.proj_points + 4.0
    frame["naive"] = 10.0
    draws = np.asarray([
        [float(index + world / 10 + offset) for world in range(7)]
        for index in range(len(frame))
    ], dtype=np.float32)
    return frame, draws


def test_exact_r0_r4_native_books_feed_paired_core_without_queries(
    monkeypatch,
    seven_world_policy,
):
    projection_calls: list[dict[str, object]] = []
    role_calls: list[dict[str, object]] = []
    candidate_calls: list[dict[str, object]] = []

    def project(panel, season, **kwargs):
        assert season == 2023
        assert os.environ["MODEL_ENSEMBLE"] == "1"
        assert kwargs["include_actual"] is False
        assert kwargs["num_boost_round"] == 400
        assert kwargs["n_sims"] == 7
        assert kwargs["tabpfn_cache_rows"]["q99"].notna().all()
        projection_calls.append(dict(kwargs))
        return _projection_frame(panel, role=False)

    def role(panel, season, **kwargs):
        assert season == 2023
        assert kwargs["include_actual"] is False
        assert kwargs["num_boost_round"] == 400
        assert kwargs["n_sims"] == 7
        assert os.environ["ROLE_BELIEF_SEED"] == str(
            seven_world_policy.multiseed_seed_pairs[len(role_calls)][1])
        role_calls.append(dict(kwargs))
        return _projection_frame(panel, role=True)

    def generate(slate, pool, draws, **kwargs):
        assert kwargs["cand_log_table"] == ""
        assert kwargs["cand_log_required"] is False
        assert kwargs["candidate_generation_entries"] == 80
        assert kwargs["n_entries"] == 80
        assert kwargs["tail_line"] == 194.0
        assert kwargs["stack"].qb_stack_min == 2
        assert kwargs["stack"].bring_back_min == 1
        assert kwargs["stack"].forbid_rb_vs_dst is True
        assert kwargs["stack"].forbid_two_rb_same_team is True
        assert "actual" not in slate and "was_active" not in slate
        assert all(
            not adapter._is_outcome_field(key)
            for player in pool for key in player
        )
        env = kwargs["policy_env"]
        rd = engine._row_draws(slate, draws, env=env)
        count = 100 if env["N_LEV"] == "160" else 105
        roster_indices = list(combinations(range(len(slate)), 9))[:count]
        rows = slate.to_dict("records")
        lineups = tuple(Lineup(
            [rows[index] for index in roster],
            tag="lev" if env["N_LEV"] == "160" else "boom",
        ) for roster in roster_indices)
        totals = np.stack([
            rd[list(roster)].sum(axis=0) for roster in roster_indices
        ]).astype(np.float32)
        leverage, boom = int(env["N_LEV"]), int(env["N_BOOM"])
        batch = engine.CandidateBatch(
            candidates=lineups,
            candidate_totals=totals,
            player_ids=tuple(slate.id.tolist()),
            player_rows=tuple(rows),
            row_draws=rd,
            all_tags={lineup.ids: (lineup.tag,) for lineup in lineups},
            metadata={
                "generation_allocation": {
                    "leverage_requested": leverage,
                    "leverage_unique": leverage,
                    "leverage_solve_attempts": leverage,
                    "leverage_solver_errors": 0,
                    "leverage_infeasible": 0,
                    "leverage_successful": leverage,
                    "boom_requested": boom,
                    "boom_attempted": boom,
                    "boom_successful": boom,
                    "boom_solver_errors": 0,
                    "boom_infeasible": 0,
                    "boom_duplicates": 0,
                    "boom_failures": 0,
                    "boom_unique_added": boom,
                    "boom_unique_fill": False,
                    "ce_requested": 0,
                    "role_or_epistemic_requested": 12,
                    "gumbel_requested": 0,
                    "core_requested": leverage + boom,
                    "total_requested_with_replacement_families": (
                        leverage + boom + 12
                    ),
                    "unique_candidates_after_all_families": count,
                },
                "generation_timing_seconds": {
                    "leverage": 1.0,
                    "primary_boom": 2.0,
                    "all_generation_through_candidate_matrix": 3.0,
                },
            },
        )
        candidate_calls.append({
            "source": env["MULTISEED_SOURCE_LABEL"],
            "projection_seed": env["REPLAY_PROJECTION_SEED"],
            "role_seed": env["ROLE_BELIEF_SEED"],
            "n_lev": env["N_LEV"],
            "n_boom": env["N_BOOM"],
        })
        kwargs["candidate_capture"](batch)
        return list(lineups[:80])

    def forbidden(*args, **kwargs):
        raise AssertionError("score-blind adapter attempted an external read")

    monkeypatch.setattr(replay, "replay_projections", project)
    monkeypatch.setattr(replay, "role_belief_projections", role)
    monkeypatch.setattr(engine, "tail_select_lineups", generate)
    monkeypatch.setattr(replay, "dst_slate_rows", forbidden)
    import nfl_dfs.bq as bq
    monkeypatch.setattr(bq, "query_df", forbidden)
    monkeypatch.setenv("N_BOOM", "999")
    monkeypatch.setenv("EXTRA_FEATURES", "poison")

    result = adapter.build_score_blind_panel_from_pit_inputs(
        [_inputs()],
        panel_id="boom-first-pit-replay-test",
        code_sha="abcdef123456",
        image_digest="sha256:" + "b" * 64,
    )

    assert len(projection_calls) == 5
    assert len(role_calls) == 5
    assert [call["seed"] for call in projection_calls] == [
        pair[0] for pair in seven_world_policy.multiseed_seed_pairs
    ]
    assert len(candidate_calls) == 10
    assert candidate_calls == [
        {
            "source": f"R{index}",
            "projection_seed": str(projection_seed),
            "role_seed": str(role_seed),
            "n_lev": "160" if arm == "control" else "40",
            "n_boom": "40" if arm == "control" else "160",
        }
        for index, (projection_seed, role_seed) in enumerate(
            seven_world_policy.multiseed_seed_pairs
        )
        for arm in ("control", "treatment")
    ]
    assert result["uses_target_slate_outcomes"] is False
    assert result["selection_completed_before_target_slate_outcomes"] is True
    assert result[
        "prior_only_historical_labels_may_train_later_targets"
    ] is True
    assert result["sealed_2025_outcomes_read"] is False
    assert result["development_seasons"] == [2023]
    assert result["h1_readiness"][
        "score_blind_selection_ready_for_h1_grading"
    ] is False
    assert result["h1_readiness"]["h1_complete"] is False
    assert result["requested_allocation"][
        "nominal_all_requested_per_five_book_arm"
    ] == 1330
    assert len(result["slates"][0]["arms"]["control"]["selected_rosters"]) == 80
    assert len(result["slates"][0]["arms"]["treatment"]["selected_rosters"]) == 80
    assert result["slates"][0]["same_role_player_worlds"] is True
    assert os.environ["N_BOOM"] == "999"
    assert os.environ["EXTRA_FEATURES"] == "poison"


@pytest.mark.parametrize("column", ["actual", "was_active", "y_dk_points"])
def test_rejects_target_outcomes_before_replay(column):
    with pytest.raises(adapter.BoomFirstReplayAdapterError, match="absent or null"):
        adapter.ProductionReplayNativeBookBuilder([
            _inputs(poisoned_column=column)
        ])


def test_rejects_even_null_outcome_column_on_preprojected_dst():
    value = _inputs()
    dst = value.dst_prelock.copy()
    dst["actual"] = np.nan
    with pytest.raises(
        adapter.BoomFirstReplayAdapterError, match="DST frame contains outcome"
    ):
        adapter.ProductionReplayNativeBookBuilder([
            replace(value, dst_prelock=dst)
        ])


def test_build_slates_score_blind_preprojected_dst_skips_legacy_loaders(
    monkeypatch,
):
    projected, _ = _projection_frame(_inputs().panel, role=False)
    dst = pd.DataFrame([{
        "season": 2023,
        "week": 1,
        "team": "B",
        "opp": "A",
        "salary": 3_000,
        "proj": 6.75,
        "id": "DST_B",
        "name": "B DST",
        "pos": "DST",
    }])

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy DST loader ran")

    monkeypatch.setattr(replay, "dst_slate_rows", forbidden)
    monkeypatch.setenv("OWN_MODEL", "")
    slates = replay.build_slates(
        projected,
        dst,
        include_actual=False,
        dst_preprojected=True,
    )
    assert len(slates) == 1
    slate = slates[0]
    assert "actual" not in slate
    assert "was_active" not in slate
    dst_row = slate[slate.id == "DST_B"].iloc[0]
    assert dst_row.draw_idx == -1
    assert dst_row.proj == pytest.approx(6.75)


def test_role_belief_passes_score_blind_cache_and_restores_extra_features(
    monkeypatch,
):
    panel = _inputs().panel
    cache = _inputs().tabpfn_marginals
    observed: dict[str, object] = {}

    def project(arg_panel, season, **kwargs):
        assert arg_panel is panel
        assert season == 2023
        assert os.environ["EXTRA_FEATURES"] == ",".join(
            replay.ROLE_BELIEF_FEATURES)
        observed.update(kwargs)
        return _projection_frame(arg_panel, role=True)

    monkeypatch.setattr(replay, "replay_projections", project)
    monkeypatch.setenv("ROLE_BELIEF_FEATURES", ",".join(replay.ROLE_BELIEF_FEATURES))
    monkeypatch.setenv("ROLE_BELIEF_SEED", "73")
    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    frame, draws = replay.role_belief_projections(
        panel,
        2023,
        n_sims=7,
        num_boost_round=4,
        include_actual=False,
        tabpfn_cache_rows=cache,
    )
    assert observed["include_actual"] is False
    assert observed["tabpfn_cache_rows"] is cache
    assert "actual" not in frame
    assert draws.shape == (len(_skill_players()), 7)
    assert "EXTRA_FEATURES" not in os.environ


def test_replay_outcome_blind_omits_was_active_and_uses_injected_cache(
    small_panel,
    monkeypatch,
):
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    monkeypatch.setenv("TABPFN_MARGINALS", "0")
    frame, draws = replay.replay_projections(
        small_panel,
        season=2022,
        n_sims=8,
        num_boost_round=2,
        seed=91,
        return_draws=True,
        include_actual=False,
        tabpfn_cache_rows=pd.DataFrame(),
    )
    assert "actual" not in frame
    assert "was_active" not in frame
    assert draws.shape == (len(frame), 8)
