"""Frozen PIT helpers for the SIS opponent pass-tail TabPFN arm."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


SIS_SOURCE_RUN = "sis-team-context-tranche-1-v1"
SIS_PASS_TAIL_FEATURES = (
    "sis_pass_def_boom_rate_l4",
    "sis_pass_def_bust_rate_l4",
    "sis_pass_rush_pressure_rate_l4",
)
PASS_POSITIONS = ("QB", "WR", "TE")
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def feature_contract(baseline: Sequence[str], arm: str) -> list[str]:
    """Return the inherited shared-33 control or fixed three-column arm."""
    if arm not in {"control", "treatment"}:
        raise ValueError(f"unknown SIS pass-tail arm {arm!r}")
    listed = sorted(baseline)
    if len(listed) != len(set(listed)):
        raise ValueError("baseline feature contract contains duplicates")
    forbidden = set(SIS_PASS_TAIL_FEATURES).intersection(listed)
    if forbidden:
        raise ValueError(
            f"baseline feature contract already contains {sorted(forbidden)}")
    return listed if arm == "control" else [*listed, *SIS_PASS_TAIL_FEATURES]


def _prior_sum(rows: pd.DataFrame, column: str) -> pd.Series:
    return rows.groupby(["season", "team"], sort=False)[column].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum()
    )


def build_strict_prior_sis_pass_tail(source: pd.DataFrame) -> pd.DataFrame:
    """Build volume-weighted opponent context from completed same-season games."""
    required = {
        "season", "week", "team", "source_run_id", "pdef_attempts",
        "pdef_value_attempts", "pdef_boom_rate", "pdef_bust_rate",
        "prush_combined_sacks", "prush_pressures",
    }
    if missing := required - set(source.columns):
        raise ValueError(f"SIS pass-tail source lacks {sorted(missing)}")
    if set(source.source_run_id.dropna().astype(str)) != {SIS_SOURCE_RUN}:
        raise ValueError("SIS pass-tail source-run identity differs")
    keys = ["season", "week", "team"]
    if source.duplicated(keys).any():
        raise ValueError("SIS pass-tail source repeats team-week keys")
    rows = source.copy()
    rows["team"] = rows.team.replace(TEAM_ALIASES)
    if rows.duplicated(keys).any():
        raise ValueError("SIS pass-tail aliases create duplicate team-week keys")
    rows = rows.sort_values(keys).reset_index(drop=True)
    numeric = required - {"season", "week", "team", "source_run_id"}
    rows[list(numeric)] = rows[list(numeric)].apply(
        pd.to_numeric, errors="coerce")
    for rate in ("pdef_boom_rate", "pdef_bust_rate"):
        valid = rows[rate].dropna()
        if not valid.between(0, 1).all():
            raise ValueError(f"SIS pass-tail {rate} is outside [0,1]")
    rows["_boom_events"] = rows.pdef_boom_rate * rows.pdef_value_attempts
    rows["_bust_events"] = rows.pdef_bust_rate * rows.pdef_value_attempts
    rows["_pressure_opportunities"] = (
        rows.pdef_attempts + rows.prush_combined_sacks)
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_pass_tail_source_week_end"] = grouped.week.shift(1)
    output["sis_pass_tail_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count())
    value_attempts = _prior_sum(rows, "pdef_value_attempts")
    pressure_opportunities = _prior_sum(rows, "_pressure_opportunities")
    output[SIS_PASS_TAIL_FEATURES[0]] = (
        _prior_sum(rows, "_boom_events") / value_attempts.replace(0, np.nan))
    output[SIS_PASS_TAIL_FEATURES[1]] = (
        _prior_sum(rows, "_bust_events") / value_attempts.replace(0, np.nan))
    output[SIS_PASS_TAIL_FEATURES[2]] = (
        _prior_sum(rows, "prush_pressures")
        / pressure_opportunities.replace(0, np.nan))
    supported = output[list(SIS_PASS_TAIL_FEATURES)].notna().all(axis=1)
    if supported.any() and not output.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(output.loc[supported, "week"]).all():
        raise ValueError("SIS pass-tail feature used target-week information")
    return output


def attach_sis_pass_tail(
    panel: pd.DataFrame, strict_prior: pd.DataFrame,
) -> pd.DataFrame:
    """Join opponent context and expose it only to QB/WR/TE rows."""
    required = {"season", "week", "opponent", "position"}
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    feature_required = {
        "season", "week", "team", "sis_pass_tail_source_week_end",
        "sis_pass_tail_prior_games", *SIS_PASS_TAIL_FEATURES,
    }
    if missing := feature_required - set(strict_prior.columns):
        raise ValueError(f"strict-prior SIS pass-tail features lack {sorted(missing)}")
    players = panel.copy()
    players["opponent"] = players.opponent.replace(TEAM_ALIASES)
    features = strict_prior.rename(columns={"team": "opponent"}).copy()
    features["opponent"] = features.opponent.replace(TEAM_ALIASES)
    keys = ["season", "week", "opponent"]
    if features.duplicated(keys).any():
        raise ValueError("strict-prior SIS pass-tail keys are not unique")
    feature_columns = [
        *keys, "sis_pass_tail_source_week_end", "sis_pass_tail_prior_games",
        *SIS_PASS_TAIL_FEATURES,
    ]
    joined = players.merge(
        features[feature_columns], on=keys, how="left", sort=False,
        validate="many_to_one")
    if len(joined) != len(panel):
        raise ValueError("SIS pass-tail join changed player row count")
    non_pass = ~joined.position.astype(str).isin(PASS_POSITIONS)
    joined.loc[non_pass, [
        *SIS_PASS_TAIL_FEATURES, "sis_pass_tail_source_week_end",
        "sis_pass_tail_prior_games",
    ]] = np.nan
    supported = joined[list(SIS_PASS_TAIL_FEATURES)].notna().all(axis=1)
    if supported.any() and not joined.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(joined.loc[supported, "week"]).all():
        raise ValueError("attached SIS pass-tail feature violates PIT scope")
    return joined


def active_pass_tail_coverage(panel: pd.DataFrame) -> list[dict[str, object]]:
    """Return active QB/WR/TE support by season for the mechanical gate."""
    required = {"season", "position", "was_active", *SIS_PASS_TAIL_FEATURES}
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    active = panel[
        panel.position.isin(PASS_POSITIONS)
        & panel.was_active.fillna(False).astype(bool)
    ]
    output = []
    for season, rows in active.groupby("season", sort=True):
        supported = rows[list(SIS_PASS_TAIL_FEATURES)].notna().all(axis=1)
        output.append({
            "season": int(season),
            "rows": int(len(rows)),
            "supported_rows": int(supported.sum()),
            "support_rate": float(supported.mean()),
            "by_position": {
                str(position): {
                    "rows": int(len(group)),
                    "supported_rows": int(
                        group[list(SIS_PASS_TAIL_FEATURES)].notna().all(axis=1).sum()),
                    "support_rate": float(
                        group[list(SIS_PASS_TAIL_FEATURES)].notna().all(axis=1).mean()),
                }
                for position, group in rows.groupby("position", sort=True)
            },
        })
    return output


__all__ = [
    "PASS_POSITIONS", "SIS_PASS_TAIL_FEATURES", "SIS_SOURCE_RUN",
    "active_pass_tail_coverage", "attach_sis_pass_tail",
    "build_strict_prior_sis_pass_tail", "feature_contract",
]
