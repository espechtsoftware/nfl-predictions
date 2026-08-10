from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis.pass_participation import (
    attach_strict_prior,
    build_weekly_participation,
    evaluate_proxy,
)


def _personnel(ids: list[str], positions: list[str]) -> dict[str, str]:
    return {
        "offense_players": ";".join(ids),
        "offense_positions": ";".join(positions),
    }


def test_weekly_pass_participation_uses_only_valid_dropbacks():
    positions = ["QB", "RB", "WR", "WR", "TE", "C", "G", "G", "T", "T", "FB"]
    first = ["qb", "rb", "a", "b", "te", "c", "g1", "g2", "t1", "t2", "fb"]
    second = ["qb", "rb", "a", "c2", "te", "c", "g1", "g2", "t1", "t2", "fb"]
    malformed = first[:-1]
    participation = pd.DataFrame([
        {
            "nflverse_game_id": "2025_01_A_B", "play_id": 1,
            "possession_team": "A", **_personnel(first, positions),
        },
        {
            "nflverse_game_id": "2025_01_A_B", "play_id": 2,
            "possession_team": "A", **_personnel(second, positions),
        },
        {
            "nflverse_game_id": "2025_01_A_B", "play_id": 3,
            "possession_team": "A", **_personnel(malformed, positions[:-1]),
        },
    ])
    pbp = pd.DataFrame([
        {
            "game_id": "2025_01_A_B", "play_id": play, "season": 2025,
            "week": 1, "posteam": "A", "qb_dropback": 1,
            "yardline_100": yardline, "season_type": "REG",
            "play_type": "pass",
        }
        for play, yardline in ((1, 40), (2, 10), (3, 5))
    ])

    result, audit = build_weekly_participation(participation, pbp)
    a = result[result.gsis_id.eq("a")].iloc[0]
    b = result[result.gsis_id.eq("b")].iloc[0]

    assert audit["malformed_personnel_rows"] == 1
    assert audit["joined_valid_dropbacks"] == 2
    assert a.pass_play_share == pytest.approx(1.0)
    assert a.redzone_pass_play_share == pytest.approx(1.0)
    assert b.pass_play_share == pytest.approx(0.5)
    assert b.redzone_pass_play_share == pytest.approx(0.0)


def test_strict_prior_never_uses_target_week():
    weekly = pd.DataFrame({
        "season": [2025, 2025],
        "week": [1, 3],
        "gsis_id": ["p", "p"],
        "pass_play_share": [0.4, 0.7],
        "redzone_pass_play_share": [0.2, 0.8],
    })
    targets = pd.DataFrame({
        "season": [2025, 2025, 2025],
        "week": [1, 3, 4],
        "gsis_id": ["p", "p", "p"],
    })

    result = attach_strict_prior(targets, weekly)

    assert result.participation_source_week.tolist() == [-1, 1, 3]
    assert np.isnan(result.pass_play_share_last.iloc[0])
    assert result.pass_play_share_last.iloc[1] == pytest.approx(0.4)
    assert np.isnan(result.pass_play_share_jump.iloc[1])
    assert result.pass_play_share_last.iloc[2] == pytest.approx(0.7)
    assert result.pass_play_share_jump.iloc[2] == pytest.approx(0.3)
    assert result.redzone_pass_play_share_jump.iloc[2] == pytest.approx(0.6)


def test_proxy_evaluation_is_walk_forward_and_detects_strong_signal():
    rng = np.random.default_rng(919)
    rows = []
    for season in (2023, 2024, 2025):
        for ix in range(120):
            share = float(rng.uniform())
            proj = 10.0
            actual = proj + (15.0 if share >= 0.5 else -3.0)
            rows.append({
                "season": season,
                "week": ix % 18 + 1,
                "gsis_id": f"{season}-{ix}",
                "pos": ("WR", "TE", "RB")[ix % 3],
                "actual": actual,
                "proj": proj,
                "salary": 5000.0,
                "target_share_last": 0.15,
                "target_share_jump": 0.0,
                "snap_share_last": 0.6,
                "snap_share_jump": 0.0,
                "team_vacated_target_share": 0.0,
                "pass_play_share_last": share,
                "pass_play_share_jump": share - 0.5,
                "redzone_pass_play_share_last": share,
                "redzone_pass_play_share_jump": share - 0.5,
            })

    report = evaluate_proxy(pd.DataFrame(rows))

    assert [fold["fold"] for fold in report["folds"]] == ["2024", "2025"]
    assert report["aggregate"]["rows"] == 240
    assert report["aggregate"]["treatment_mae"] < report["aggregate"]["control_mae"]
    assert report["aggregate"]["treatment_brier"] < report["aggregate"]["control_brier"]
    assert report["disposition"] == "supports-paid-route-trial"
