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
    # qb_cpoe_l6 ADOPTED 2026-08-01 (Addendum 32): the first feature to
    # pass a six-season panel -- tail weeks 18 -> 23 of 101 at flat
    # mean/median. Found via the audit (ngs_passing was fully unused).
    "qb_cpoe_l6",
    # team_ol_out was REMOVED 2026-08-01 same day it was added: exact
    # replay cost -8.7 mean-best / -4 tail weeks (180.8/4-17 vs
    # 189.5/8-17). Plausible mechanism, bad feature -- likely confounded
    # (teams missing linemen are bad teams). Column remains in the
    # tables for analysis.
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

# Candidate features (2026-08-01): materialized in the feature tables but
# EXCLUDED from the model unless named in the EXTRA_FEATURES env var
# (comma-separated) -- so one table rebuild supports N parallel exact
# feature A/Bs, each arm enabling exactly one. The deterministic-replay
# lesson (depth_rank_delta -4.6, team_ol_out -8.7): every feature pays
# its own way through a replay before joining NUMERIC_FEATURES.
CANDIDATE_FEATURES = (
    "pace_env_l6",                # own off plays + opp def plays faced (l6)
    "opp_blitz_rate_l6",          # opponent defense blitz rate (FTN, 2022+)
    "team_top2_target_share_l6",  # target concentration -> stack strength
    "qb_time_to_throw_l6",        # NGS avg time to throw (2016+)
    "pa_rate_l6",                 # team play-action rate (FTN, 2022+) — deep-shot / WR-ceiling context
    "opp_pressure_rate_l6",       # opp pressure GENERATED per dropback (FTN, 2022+) — outcome, not rushers sent
    "xfp_l4",                     # expected FP from opportunity alone (bucketed pbp rates; FantasyPoints lineage)
    "net_rest_diff",              # own minus opponent days rest (pure schedule join)
    "body_clock_hour",            # kickoff hour on the team's home-tz body clock (west-coast night effect)
    "vacated_capture_tgt",        # vacated targets x empirical (pos,depth) capture rate (Addendum 44 event study)
    "vacated_capture_car",        # vacated carries x empirical capture rate (backfield-concentrated)
)


def _active_numeric_features() -> list[str]:
    """EXTRA_FEATURES adds registered candidates; DROP_FEATURES removes
    any baseline feature -- the ablation mirror (2026-08-01: built to test
    whether the pre-A/B-era salary features earn their slots, after the
    salary backfill's -4.4 on 2025 suggested consensus features eat tails).
    Both call-time envs; unset = the validated baseline."""
    import os

    extra = [f.strip() for f in os.environ.get("EXTRA_FEATURES", "").split(",")
             if f.strip()]
    drop = {f.strip() for f in os.environ.get("DROP_FEATURES", "").split(",")
            if f.strip()}
    base = [f for f in NUMERIC_FEATURES if f not in drop]
    return base + [f for f in extra if f in CANDIDATE_FEATURES]


def build_X(df: pd.DataFrame) -> pd.DataFrame:
    # SORTED columns (2026-08-01, Addendum 34): LightGBM's split
    # tie-breaking depends on column ORDER, so the same feature set in a
    # different order trains a different (equally valid) model -- worth
    # ~+/-5 mean-best of "order luck". Discovered when adopting
    # qb_cpoe_l6 (EXTRA_FEATURES appends last; adoption inserted
    # mid-list) shifted deterministic replays. Canonical alphabetical
    # order makes candidate arms and post-adoption baselines train
    # IDENTICAL models, restoring exact A/B equivalence forever.
    X = pd.DataFrame(index=df.index)
    for c in sorted(_active_numeric_features()):
        if c in df.columns:
            X[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            X[c] = np.nan
    X["position"] = pd.Categorical(df["position"], categories=POSITIONS)
    return X
