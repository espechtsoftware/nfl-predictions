"""The shared model feature matrix.

One canonical feature list for the baseline and component models so a
model loaded from the registry always sees the columns it trained on.
Columns absent from an input frame become NaN (LightGBM handles missing
natively); extra columns are ignored.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

POSITIONS = ["QB", "RB", "WR", "TE"]

# LightGBM thread cap shared by every model in this package. Our panels are
# small (tens of thousands of rows at most); letting OpenMP grab all cores
# adds per-split sync overhead and has livelocked outright on WSL. Eight is
# plenty and matches Cloud Run job sizing.
import os as _os  # noqa: E402

LGB_THREADS = max(1, min(8, _os.cpu_count() or 1))

NUMERIC_FEATURES = [
    # Usage (point-in-time rollups, §5.2)
    "target_share_l4",
    "carry_share_l4",
    "wopr_l4",
    "rz20_targets_smoothed",
    "ez_targets_l4",
    "deep_targets_l4",
    "separation_l4",
    "stacked_box_l4",
    "gl3_carries_smoothed",
    "snap_share_l4",
    # Production trail
    "dk_points_l4",
    "dk_points_std",
    "dk_points_vol",
    # Game environment
    "implied_team_total",
    "spread",
    "game_total",
    "expected_game_script",
    "is_home",
    "is_dome",
    # Experience / role
    "games_played_prior",
    "is_cold_start",
    "depth_rank",
    # depth_rank_delta (Addendum 24) was REMOVED from the model inputs
    # 2026-08-01: the replay pipeline turned out to be fully
    # deterministic (3 identical confirmation runs), which retroactively
    # converts its "neutral within noise" replay result into a real
    # -4.6 mean-best cost (188.4 -> 183.8). The SQL column remains in
    # the feature tables for analysis; it just doesn't feed the model.
    # Game environment extras (2026-08-01): referee-crew flag tendency
    # (strictly-prior; NULL live until midweek crew assignments are
    # sourced) and script-stripped neutral pass rate.
    "ref_flags_prior",
    "neutral_pass_rate_l6",
    # OL injuries (2026-08-01): count of T/G/C ruled Out on the week's
    # report -- pass-protection losses reprice every skill player.
    "team_ol_out",
    # Next-man-up: opportunity vacated by teammates ruled Out this week
    "team_vacated_target_share",
    "team_vacated_carry_share",
    # Opponent secondary (CB coverage from PFR advstats; NULL before 2018)
    "cb_ypt_allowed_l6",
    "cb_comp_rate_allowed_l6",
    "db_ypt_allowed_l6",
    "top_cb_out",
    # Market signal
    "salary",
    "salary_delta_wow",
]

FEATURES = NUMERIC_FEATURES + ["position"]


def build_X(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in NUMERIC_FEATURES:
        if c in df.columns:
            X[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            X[c] = np.nan
    X["position"] = pd.Categorical(df["position"], categories=POSITIONS)
    return X
