"""Shared synthetic data for model/optimizer/backtest tests.

The generator produces a plausible player-week panel with real signal
(usage drives production) so models have something to learn, plus a noisy
market projection so market-comparison code paths run.
"""

import numpy as np
import pandas as pd
import pytest

POSITIONS = ["QB", "RB", "WR", "TE"]


def synthetic_panel(n_players=120, seasons=range(2018, 2025), seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = POSITIONS[p % 4]
        skill = rng.normal(0, 1)
        for season in seasons:
            team_total = rng.uniform(17, 30)
            usage = np.clip(rng.normal(0.15 + 0.05 * skill, 0.05), 0.01, 0.4)
            for week in range(1, 18):
                usage = np.clip(usage + rng.normal(0, 0.01), 0.01, 0.45)
                implied = team_total + rng.normal(0, 2)
                # True expectation: usage x game environment
                mu = 4 + 40 * usage + 0.35 * (implied - 22) + 2 * skill
                dk = max(0.0, rng.normal(mu, 6))
                rows.append({
                    "gsis_id": f"00-{p:07d}",
                    "season": season, "week": week,
                    "team": f"T{p % 32}", "opponent": f"T{(p + 7) % 32}",
                    "game_id": f"{season}_{week:02d}_T{p % 32}",
                    "position": pos,
                    "target_share_l4": usage if pos in ("WR", "TE") else usage / 3,
                    "carry_share_l4": usage if pos == "RB" else usage / 5,
                    "wopr_l4": 1.5 * usage,
                    "rz20_targets_smoothed": usage * 4,
                    "gl3_carries_smoothed": usage * (2 if pos == "RB" else 0.2),
                    "snap_share_l4": np.clip(usage * 2.2, 0, 1),
                    "dk_points_l4": mu + rng.normal(0, 2),
                    "dk_points_std": mu + rng.normal(0, 1.5),
                    "dk_points_vol": 6.0,
                    "implied_team_total": implied,
                    "spread": rng.normal(0, 5),
                    "game_total": implied * 2 + rng.normal(0, 2),
                    "expected_game_script": rng.normal(0, 4),
                    "games_played_prior": week - 1 + 17 * 2,
                    "is_home": float(rng.random() < 0.5),
                    "is_dome": float(rng.random() < 0.3),
                    "is_cold_start": 0.0,
                    "salary": int(np.clip(3000 + 320 * mu + rng.normal(0, 400), 2500, 9800)),
                    "salary_delta_wow": float(rng.normal(0, 200)),
                    # Market is a good but imperfect projection
                    "dk_ppg": mu + rng.normal(0, 2.0),
                    "injury_status": None,
                    # Component labels, roughly consistent with dk points
                    "y_targets": rng.poisson(9 * usage) if pos != "QB" else 0,
                    "y_receptions": rng.poisson(6 * usage) if pos != "QB" else 0,
                    "y_rec_yards": max(0, rng.normal(70 * usage, 20)) if pos != "QB" else 0,
                    "y_rec_tds": rng.binomial(1, min(0.6, usage)) if pos != "QB" else 0,
                    "y_carries": rng.poisson(18 * usage) if pos == "RB" else 0,
                    "y_rush_yards": max(0, rng.normal(80 * usage, 25)) if pos == "RB" else 0,
                    "y_rush_tds": rng.binomial(1, min(0.5, usage * 0.8)) if pos == "RB" else 0,
                    "y_pass_attempts": rng.poisson(33) if pos == "QB" else 0,
                    "y_pass_yards": max(0, rng.normal(240, 60)) if pos == "QB" else 0,
                    "y_pass_tds": rng.poisson(1.6) if pos == "QB" else 0,
                    "y_interceptions": rng.poisson(0.7) if pos == "QB" else 0,
                    "y_dk_points": dk,
                })
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    return synthetic_panel()


@pytest.fixture(scope="session")
def small_panel() -> pd.DataFrame:
    return synthetic_panel(n_players=60, seasons=range(2019, 2023), seed=5)
