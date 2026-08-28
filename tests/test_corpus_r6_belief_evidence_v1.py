from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.corpus_r6_belief_calibration_v1 import (
    L1_EVENT_COLUMNS,
    L1_METRICS,
    L1_MOMENT_COLUMNS,
    L2_RESIDUAL_COLUMNS,
)
from nfl_dfs.research.corpus_r6_belief_evidence_v1 import (
    BeliefEvidenceError,
    L1ConditionalBankShard,
    ROLE_HISTORY_SOURCE_SQL,
    build_l1_real_player_evidence_v1,
    build_l2_real_player_evidence_v1,
    snapshot_schema_smoke_v1,
)
from nfl_dfs.research.latent_role_state import INPUT_FEATURES


def _identity(name: str, digit: str = "a") -> dict[str, object]:
    return {
        "uri": f"gs://belief-evidence/{name}",
        "generation": "17",
        "sha256": digit * 64,
        "bytes": 1024,
    }


def _l1_snapshot_and_shards() -> tuple[
    pd.DataFrame, list[L1ConditionalBankShard]
]:
    snapshot_rows: list[dict[str, object]] = []
    shards: list[L1ConditionalBankShard] = []
    for season in (2019, 2021, 2022):
        slate_rows: list[dict[str, object]] = []
        for game_index in range(2):
            game = f"{season}-g{game_index}"
            teams = (f"A{game_index}", f"B{game_index}")
            for team_index, team in enumerate(teams):
                opponent = teams[1 - team_index]
                for position, mean, actual in (
                    ("QB", 20.0, 24.0 + game_index + team_index),
                    ("RB", 14.0, 12.0 + game_index),
                    ("WR", 16.0, 18.0 + 5.0 * game_index + 2.0 * team_index),
                    ("TE", 8.0, 7.0),
                ):
                    player_id = f"{season}-{game}-{team}-{position}"
                    slate_rows.append({
                        "gsis_id": player_id,
                        "season": season,
                        "week": 1,
                        "pos": position,
                        "team": team,
                        "opp": opponent,
                        "game_id": game,
                        "mean_projection": mean,
                        "actual": actual,
                    })
                # A lower-projected WR confirms WR1 uses pre-lock mean.
                slate_rows.append({
                    "gsis_id": f"{season}-{game}-{team}-WR-low",
                    "season": season,
                    "week": 1,
                    "pos": "WR",
                    "team": team,
                    "opp": opponent,
                    "game_id": game,
                    "mean_projection": 9.0,
                    "actual": 40.0,
                })
        snapshot_rows.extend(slate_rows)
        players = tuple(str(row["gsis_id"]) for row in reversed(slate_rows))
        ordinary = np.zeros((len(players), 4), dtype=float)
        shootout = np.zeros_like(ordinary)
        position_by_id = {
            str(row["gsis_id"]): str(row["pos"]) for row in slate_rows
        }
        low_by_id = {
            str(row["gsis_id"]): str(row["gsis_id"]).endswith("WR-low")
            for row in slate_rows
        }
        for index, player_id in enumerate(players):
            position = position_by_id[player_id]
            if position == "QB":
                ordinary[index] = [20.0, 20.0, 30.0, 30.0]
                shootout[index] = ordinary[index] + 10.0
            elif position == "WR" and not low_by_id[player_id]:
                # Team/game-specific offset yields nonzero WR1 variance.
                offset = float(sum(ord(char) for char in player_id) % 4)
                ordinary[index] = np.asarray([15.0, 25.0, 15.0, 25.0]) + offset
                shootout[index] = ordinary[index] + 10.0
            elif position == "RB":
                ordinary[index] = 10.0
                shootout[index] = 15.0
            else:
                ordinary[index] = 5.0
                shootout[index] = 6.0
        shards.append(L1ConditionalBankShard(
            season=season,
            week=1,
            player_ids=players,
            ordinary_draws=ordinary,
            shootout_draws=shootout,
            source_identity=_identity(f"bank-{season}", str(season)[-1]),
        ))
    return pd.DataFrame(snapshot_rows), shards


def test_l1_extracts_frozen_events_and_opposing_wr1_moments():
    snapshot, shards = _l1_snapshot_and_shards()
    result = build_l1_real_player_evidence_v1(
        player_snapshot=snapshot.sample(frac=1.0, random_state=7),
        bank_shards=list(reversed(shards)),
        snapshot_source_identity=_identity("snapshot"),
    )
    assert tuple(result.event_rows.columns) == L1_EVENT_COLUMNS
    assert tuple(result.opposing_wr1_moment_rows.columns) == L1_MOMENT_COLUMNS
    assert set(result.event_rows.metric) == set(L1_METRICS)
    assert len(result.event_rows) == 3 * 2 * 2 * len(L1_METRICS)
    assert result.event_rows.sample_id.nunique() == 12
    by_component = result.opposing_wr1_moment_rows.set_index(
        ["season", "component"]
    )
    assert by_component.loc[(2019, "observed"), "count"] == 2
    assert by_component.loc[(2019, "ordinary"), "count"] == 8
    assert by_component.loc[(2019, "shootout"), "count"] == 8
    assert result.receipt["uses_player_outcomes"] is True
    assert result.receipt["uses_lineup_outcomes"] is False
    assert result.receipt["opposing_game_count"] == 6


def test_l1_fails_closed_on_missing_bank_support_or_lineup_outcome():
    snapshot, shards = _l1_snapshot_and_shards()
    with pytest.raises(BeliefEvidenceError, match="slate coverage"):
        build_l1_real_player_evidence_v1(
            player_snapshot=snapshot,
            bank_shards=shards[:-1],
            snapshot_source_identity=_identity("snapshot"),
        )
    snapshot["lineup_score"] = 200.0
    with pytest.raises(BeliefEvidenceError, match="lineup outcomes"):
        build_l1_real_player_evidence_v1(
            player_snapshot=snapshot,
            bank_shards=shards,
            snapshot_source_identity=_identity("snapshot"),
        )


def _feature_values(position: str) -> dict[str, object]:
    values: dict[str, object] = {
        "target_share_last": 0.18,
        "target_share_l4": 0.17,
        "carry_share_last": 0.10,
        "carry_share_l4": 0.09,
        "snap_share_last": 0.65,
        "snap_share_l4": 0.61,
        "target_share_jump": 0.01,
        "carry_share_jump": 0.01,
        "snap_share_jump": 0.04,
        "games_played_prior": 8.0,
        "practice_level": 1.0,
        "team_vacated_target_share": 0.0,
        "team_vacated_carry_share": 0.0,
        "position": position,
        "previous_state": "secondary",
        "injury_status": "Healthy",
    }
    assert set(values) == set(INPUT_FEATURES)
    return values


def _l2_sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    role_rows: list[dict[str, object]] = []
    snapshot_rows: list[dict[str, object]] = []
    for season in range(2018, 2023):
        for ordinal, position in enumerate(("RB", "WR", "TE")):
            player_id = f"{season}-{position}"
            role_rows.append({
                "gsis_id": player_id,
                "season": season,
                "week": 1,
                "team": "A",
                "is_sunday_main": True,
                "target_share": 0.20,
                "carry_share": 0.15,
                "snap_share": 0.70,
                "realized_state": "secondary",
                **_feature_values(position),
            })
            if season in (2019, 2021, 2022):
                snapshot_rows.append({
                    "gsis_id": player_id,
                    "season": season,
                    "week": 1,
                    "pos": position,
                    "team": "A",
                    "opp": "B",
                    "game_id": f"{season}-g0",
                    "mean_projection": 10.0 + ordinal,
                    "actual": 15.0 + ordinal,
                })
    return pd.DataFrame(role_rows), pd.DataFrame(snapshot_rows)


def test_l2_joins_exact_role_labels_to_player_residual_source():
    roles, snapshot = _l2_sources()
    result = build_l2_real_player_evidence_v1(
        role_history=roles,
        player_snapshot=snapshot,
        snapshot_source_identity=_identity("snapshot"),
        role_source_identity=_identity("roles", "b"),
    )
    assert tuple(result.residual_history.columns) == L2_RESIDUAL_COLUMNS
    assert len(result.role_history) == 15
    assert len(result.residual_history) == 9
    residual = (
        result.residual_history.player_actual_points
        - result.residual_history.ordinary_mean
    )
    assert np.allclose(residual, 5.0)
    assert result.receipt["previous_state_formed_before_target_universe_filter"]
    assert result.receipt["uses_lineup_outcomes"] is False


def test_l2_reports_the_concrete_missing_player_join():
    roles, snapshot = _l2_sources()
    snapshot = snapshot.iloc[:-1]
    result = build_l2_real_player_evidence_v1(
        role_history=roles,
        player_snapshot=snapshot,
        snapshot_source_identity=_identity("snapshot"),
        role_source_identity=_identity("roles", "b"),
    )
    assert len(result.residual_history) == 8
    assert result.receipt[
        "calibration_role_rows_excluded_without_frozen_ordinary_mean"
    ] == 1
    assert result.receipt["role_row_count_before_snapshot_intersection"] == 15
    assert result.receipt["role_row_count"] == 14


def test_source_sql_and_schema_smoke_preserve_outcome_boundaries():
    normalized_sql = ROLE_HISTORY_SOURCE_SQL.lower()
    assert "is_sunday_main" in normalized_sql
    assert "between 2018 and 2022" in normalized_sql
    assert "y_dk_points" not in normalized_sql
    assert "lineup_score" not in normalized_sql
    columns = [
        "gsis_id", "season", "week", "pos", "team", "opp", "game_id",
        "mean_projection", "actual", "unrelated_point_in_time_feature",
    ]
    smoke = snapshot_schema_smoke_v1(columns)
    assert smoke["values_read"] is False
    assert smoke["uses_player_outcomes"] is False
    with pytest.raises(BeliefEvidenceError, match="lineup outcomes"):
        snapshot_schema_smoke_v1([*columns, "actual_score"])
