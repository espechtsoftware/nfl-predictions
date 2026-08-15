"""Frozen prospective 2026 SIS pass-tail shadow contract.

This module is deliberately independent of the historical write-once cache
builder.  It prepares a target-week spine from completed SIS games and pins
the exact live control/treatment environments selected before 2026 outcomes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd


PROTOCOL_VERSION = "prospective-sis-pass-tail-finite-k-v1"
CONTROL_TABLE = "tabpfn_sis_pass_tail_live_control_v1"
TREATMENT_TABLE = "tabpfn_sis_pass_tail_live_treatment_v1"
FITTED_K = "28.154043586960896"
FROZEN_BETA = "0.07771181538347656"
ENTRIES = 80
TAIL_LINE = 194.0
WORLDS = 10_000
SEEDS = {
    "R0": (0, 7331),
    "R1": (1137260708, 2690847602),
    "R2": (2875959182, 1630284992),
    "R3": (253722715, 3374646876),
    "R4": (1643280042, 3977633467),
}
FEATURES = (
    "sis_pass_def_boom_rate_l4",
    "sis_pass_def_bust_rate_l4",
    "sis_pass_rush_pressure_rate_l4",
)
SCHEDULES = {
    "control": "QB:0.85,RB:0.895,TE:0.96,WR:1.04",
    "treatment": "QB:0.92,RB:0.965,TE:0.945,WR:1.04",
}
TABLES = {"control": CONTROL_TABLE, "treatment": TREATMENT_TABLE}
PASS_POSITIONS = ("QB", "WR", "TE")
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

_SOURCE_COLUMNS = (
    "pdef_attempts",
    "pdef_value_attempts",
    "pdef_boom_rate",
    "pdef_bust_rate",
    "prush_combined_sacks",
    "prush_pressures",
)


def _prior_sum(rows: pd.DataFrame, column: str) -> pd.Series:
    return rows.groupby(["season", "team"], sort=False)[column].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum()
    )


def build_target_context(
    source: pd.DataFrame,
    *,
    season: int,
    week: int,
    teams: Iterable[str],
) -> pd.DataFrame:
    """Build last-four context for an explicit pregame target-week spine.

    Rows at or after the target week are excluded before aggregation.  This
    makes a later rerun point-in-time safe and ensures the target game never
    needs to exist in the source table.
    """
    required = {
        "season", "week", "team", "source_run_id", *_SOURCE_COLUMNS,
    }
    if missing := required - set(source.columns):
        raise ValueError(f"live SIS pass-tail source lacks {sorted(missing)}")
    season = int(season)
    week = int(week)
    if week < 1:
        raise ValueError("live SIS pass-tail target week must be positive")
    target_teams = sorted({TEAM_ALIASES.get(str(team), str(team)) for team in teams})
    if not target_teams:
        raise ValueError("live SIS pass-tail target spine has no teams")

    rows = source.copy()
    rows["team"] = rows.team.astype(str).replace(TEAM_ALIASES)
    rows["season"] = pd.to_numeric(rows.season, errors="coerce")
    rows["week"] = pd.to_numeric(rows.week, errors="coerce")
    rows = rows[
        rows.season.eq(season)
        & rows.week.lt(week)
        & rows.team.isin(target_teams)
    ].copy()
    if rows.source_run_id.isna().any() or rows.source_run_id.astype(str).str.strip().eq("").any():
        raise ValueError("live SIS pass-tail source identity is blank")
    keys = ["season", "week", "team"]
    if rows.duplicated(keys).any():
        raise ValueError("live SIS pass-tail source repeats team-week keys")
    for column in _SOURCE_COLUMNS:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    for column in ("pdef_boom_rate", "pdef_bust_rate"):
        valid = rows[column].dropna()
        if not valid.between(0, 1).all():
            raise ValueError(f"live SIS pass-tail {column} is outside [0,1]")

    spine = pd.DataFrame({
        "season": season,
        "week": week,
        "team": target_teams,
        "source_run_id": PROTOCOL_VERSION,
    })
    for column in _SOURCE_COLUMNS:
        spine[column] = np.nan
    rows = pd.concat([rows, spine], ignore_index=True, sort=False)
    rows = rows.sort_values(keys).reset_index(drop=True)
    rows["_boom_events"] = rows.pdef_boom_rate * rows.pdef_value_attempts
    rows["_bust_events"] = rows.pdef_bust_rate * rows.pdef_value_attempts
    rows["_pressure_opportunities"] = (
        rows.pdef_attempts + rows.prush_combined_sacks
    )
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_pass_tail_source_week_end"] = grouped.week.shift(1)
    output["sis_pass_tail_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count()
    )
    value_attempts = _prior_sum(rows, "pdef_value_attempts")
    pressure_opportunities = _prior_sum(rows, "_pressure_opportunities")
    output[FEATURES[0]] = (
        _prior_sum(rows, "_boom_events") / value_attempts.replace(0, np.nan)
    )
    output[FEATURES[1]] = (
        _prior_sum(rows, "_bust_events") / value_attempts.replace(0, np.nan)
    )
    output[FEATURES[2]] = (
        _prior_sum(rows, "prush_pressures")
        / pressure_opportunities.replace(0, np.nan)
    )
    output = output[output.week.eq(week)].reset_index(drop=True)
    if set(output.team) != set(target_teams) or len(output) != len(target_teams):
        raise ValueError("live SIS pass-tail target spine is incomplete")
    output["sis_pass_tail_supported"] = (
        output.sis_pass_tail_prior_games.ge(2)
        & output[list(FEATURES)].notna().all(axis=1)
    )
    supported = output.sis_pass_tail_supported
    if supported.any() and not output.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(week).all():
        raise ValueError("live SIS pass-tail context used target-week data")
    return output


def attach_target_context(
    inference: pd.DataFrame, context: pd.DataFrame,
) -> pd.DataFrame:
    """Attach opponent-team context to the target inference player rows."""
    required = {"season", "week", "opponent", "position"}
    if missing := required - set(inference.columns):
        raise ValueError(f"live SIS pass-tail inference lacks {sorted(missing)}")
    context_required = {
        "season", "week", "team", "sis_pass_tail_source_week_end",
        "sis_pass_tail_prior_games", "sis_pass_tail_supported", *FEATURES,
    }
    if missing := context_required - set(context.columns):
        raise ValueError(f"live SIS pass-tail context lacks {sorted(missing)}")
    players = inference.copy()
    players["opponent"] = players.opponent.astype(str).replace(TEAM_ALIASES)
    defense = context.rename(columns={"team": "opponent"}).copy()
    keys = ["season", "week", "opponent"]
    if defense.duplicated(keys).any():
        raise ValueError("live SIS pass-tail context repeats target keys")
    out = players.merge(
        defense[[*keys, "sis_pass_tail_source_week_end",
                 "sis_pass_tail_prior_games", "sis_pass_tail_supported",
                 *FEATURES]],
        on=keys,
        how="left",
        sort=False,
        validate="many_to_one",
    )
    if len(out) != len(inference):
        raise ValueError("live SIS pass-tail join changed inference row count")
    non_pass = ~out.position.astype(str).isin(PASS_POSITIONS)
    out.loc[non_pass, [
        "sis_pass_tail_source_week_end", "sis_pass_tail_prior_games", *FEATURES,
    ]] = np.nan
    out.loc[non_pass, "sis_pass_tail_supported"] = False
    supported = out[list(FEATURES)].notna().all(axis=1)
    if supported.any() and not out.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(out.loc[supported, "week"]).all():
        raise ValueError("live SIS pass-tail attachment violates PIT scope")
    return out


def arm_environment(arm: str, *, projection_seed: int, role_seed: int) -> dict[str, str]:
    """Return the exact historical-mechanism environment for one live book."""
    if arm not in TABLES:
        raise ValueError(f"unknown prospective SIS pass-tail arm {arm!r}")
    return {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "MODEL_REGISTRY_VARIANT": "tail_k1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": TABLES[arm],
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": (
            "target_share_last,carry_share_last,snap_share_last,"
            "target_share_jump,carry_share_jump,snap_share_jump"
        ),
        "ROLE_BELIEF_SEED": str(int(role_seed)),
        "REPLAY_PROJECTION_SEED": str(int(projection_seed)),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": FITTED_K,
        "SIS_ASOE_TARGET_ALLOCATION": "1",
        "SIS_ASOE_BETA": FROZEN_BETA,
        "SERVED_POSITION_SCALES": SCHEDULES[arm],
        "MIN_LINEUP_SALARY": "49000",
        "LIVE_SIMS": str(WORLDS),
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "PROSPECTIVE_SIS_PASS_TAIL_VERSION": PROTOCOL_VERSION,
    }


def environment_failures(arm: str, source: Mapping[str, object]) -> list[str]:
    """Fail closed if a deployed runner drifts from the frozen contract."""
    expected = arm_environment(arm, projection_seed=0, role_seed=0)
    expected.pop("REPLAY_PROJECTION_SEED")
    expected.pop("ROLE_BELIEF_SEED")
    failures = [
        f"{name} differs"
        for name, value in expected.items()
        if str(source.get(name, "")) != value
    ]
    seed_pair = (
        int(str(source.get("REPLAY_PROJECTION_SEED", "-1"))),
        int(str(source.get("ROLE_BELIEF_SEED", "-1"))),
    )
    if seed_pair not in set(SEEDS.values()):
        failures.append("seed pair is not registered")
    if any(str(source.get(name, "")).strip() for name in (
        "MULTISEED_PORTFOLIO", "ARCHETYPE_ALLOCATION_VERSION",
        "EXTRA_FEATURES", "DROP_FEATURES",
    )):
        failures.append("unregistered composition lever is active")
    return failures


__all__ = [
    "CONTROL_TABLE", "ENTRIES", "FEATURES", "FITTED_K", "FROZEN_BETA",
    "PROTOCOL_VERSION", "SCHEDULES", "SEEDS", "TABLES", "TAIL_LINE",
    "TREATMENT_TABLE", "WORLDS", "arm_environment", "attach_target_context",
    "build_target_context", "environment_failures",
]
