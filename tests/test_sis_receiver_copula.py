from __future__ import annotations

import numpy as np
import pandas as pd

from nfl_dfs.ingest.sis_receiver_copula import build_defense_prior


def _player_games() -> pd.DataFrame:
    rows = []
    player_id = 1
    for season, weeks in ((2022, range(1, 19)), (2023, range(1, 6))):
        for week in weeks:
            for alignment in ("wide", "slot"):
                coverage = 10.0
                targets = 2.0 if alignment == "wide" else 1.0
                completions = 1.0
                yards = 10.0 if alignment == "wide" else 5.0
                touchdowns = 0.0
                if season == 2023 and week == 5:
                    coverage = targets = completions = yards = touchdowns = 999.0
                rows.append({
                    "season": season, "week": week,
                    "alignment": alignment, "defense": "ARI",
                    "defender_player_id": player_id,
                    "coverage_snaps": coverage, "targets": targets,
                    "completions": completions, "yards": yards,
                    "touchdowns": touchdowns,
                })
                player_id += 1
    return pd.DataFrame(rows)


def test_defense_prior_is_cross_season_strict_and_empirically_shrunk():
    schedule = pd.DataFrame([
        {"season": 2022, "week": 5, "team": "ARI", "opponent": "BUF"},
        {"season": 2023, "week": 5, "team": "ARI", "opponent": "BUF"},
    ])
    result, audit = build_defense_prior(_player_games(), schedule)

    assert len(result) == 4
    assert result.context_supported.all()
    assert audit["strictly_prior"] is True
    first = result[
        result.season.eq(2022) & result.alignment.eq("wide")
    ].iloc[0]
    assert first.prior_games == 4
    assert first.source_last_week == 4
    assert first.vulnerability == 0.2
    crossed = result[
        result.season.eq(2023) & result.alignment.eq("wide")
    ].iloc[0]
    assert crossed.prior_games == 8
    assert crossed.source_first_season == 2022
    assert crossed.source_last_season == 2023
    assert crossed.source_last_week == 4
    assert crossed.coverage_snaps == 80.0
    assert crossed.targets == 16.0
    assert np.isclose(crossed.vulnerability, 0.2)


def test_defense_prior_marks_less_than_four_games_unsupported():
    games = _player_games()
    games = games[
        ~(
            games.season.eq(2022)
            & games.week.between(1, 2)
        )
    ]
    schedule = pd.DataFrame([
        {"season": 2022, "week": 5, "team": "ARI", "opponent": "BUF"},
    ])
    result, audit = build_defense_prior(games, schedule)
    assert not result.context_supported.any()
    assert audit["supported_rows"] == 0
