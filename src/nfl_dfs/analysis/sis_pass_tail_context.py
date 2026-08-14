"""Outcome-free, strictly-prior SIS pass-tail support/redundancy audit."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd


PANEL_ID = "20260812-pitclean-e80-selected-tabpfn-active-v2"
POSITIONS = ("QB", "WR", "TE")
FEATURES = (
    "sis_pass_def_boom_rate_l4",
    "sis_pass_def_bust_rate_l4",
    "sis_pass_rush_pressure_rate_l4",
)


def _rolling_prior_sum(rows: pd.DataFrame, column: str) -> pd.Series:
    return rows.groupby(["season", "team"], sort=False)[column].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum()
    )


def build_strict_prior_context(source: pd.DataFrame) -> pd.DataFrame:
    needed = {
        "season", "week", "team", "pdef_attempts", "pdef_value_attempts",
        "pdef_boom_rate", "pdef_bust_rate", "prush_combined_sacks",
        "prush_pressures",
    }
    if missing := needed - set(source):
        raise ValueError(f"SIS pass-tail source missing {sorted(missing)}")
    keys = ["season", "week", "team"]
    if source.duplicated(keys).any():
        raise ValueError("SIS pass-tail source repeats team-week keys")
    rows = source.copy().sort_values(keys).reset_index(drop=True)
    numeric = needed - set(keys)
    rows[list(numeric)] = rows[list(numeric)].apply(
        pd.to_numeric, errors="coerce"
    )
    for rate in ("pdef_boom_rate", "pdef_bust_rate"):
        valid = rows[rate].dropna()
        if not valid.between(0, 1).all():
            raise ValueError(f"SIS pass-tail {rate} is outside [0,1]")
    rows["_pdef_boom_events"] = (
        rows.pdef_boom_rate * rows.pdef_value_attempts
    )
    rows["_pdef_bust_events"] = (
        rows.pdef_bust_rate * rows.pdef_value_attempts
    )
    rows["_pass_rush_opportunities"] = (
        rows.pdef_attempts + rows.prush_combined_sacks
    )
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_pass_tail_source_week_end"] = grouped.week.shift(1)
    output["sis_pass_tail_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count()
    )
    value_attempts = _rolling_prior_sum(rows, "pdef_value_attempts")
    pass_rush_opportunities = _rolling_prior_sum(
        rows, "_pass_rush_opportunities"
    )
    output["sis_pass_def_boom_rate_l4"] = (
        _rolling_prior_sum(rows, "_pdef_boom_events")
        / value_attempts.replace(0, np.nan)
    )
    output["sis_pass_def_bust_rate_l4"] = (
        _rolling_prior_sum(rows, "_pdef_bust_events")
        / value_attempts.replace(0, np.nan)
    )
    output["sis_pass_rush_pressure_rate_l4"] = (
        _rolling_prior_sum(rows, "prush_pressures")
        / pass_rush_opportunities.replace(0, np.nan)
    )
    supported = (
        output.sis_pass_tail_prior_games.ge(2)
        & output[list(FEATURES)].notna().all(axis=1)
    )
    if supported.any() and not output.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(output.loc[supported, "week"]).all():
        raise ValueError("SIS pass-tail context used target-week information")
    output["sis_pass_tail_supported"] = supported
    return output


def attach_context(panel: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    needed = {
        "season", "week", "gsis_id", "position", "opp", "was_active",
        "epa_per_dropback_allowed_l6", "opp_pressure_rate_l6",
    }
    if missing := needed - set(panel):
        raise ValueError(f"SIS pass-tail panel missing {sorted(missing)}")
    if panel.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("SIS pass-tail panel repeats player-week keys")
    defense = context.rename(columns={"team": "opp"})
    out = panel.merge(
        defense,
        on=["season", "week", "opp"],
        how="left",
        validate="many_to_one",
    )
    supported = out.sis_pass_tail_supported.fillna(False).astype(bool)
    if supported.any() and not out.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(out.loc[supported, "week"]).all():
        raise ValueError("SIS pass-tail attachment violates strict-prior scope")
    return out


def _correlation(left: pd.Series, right: pd.Series) -> float | None:
    valid = left.notna() & right.notna()
    if valid.sum() < 3 or left[valid].nunique() < 2 or right[valid].nunique() < 2:
        return None
    value = left[valid].corr(right[valid])
    return float(value) if np.isfinite(value) else None


def audit_attached(rows: pd.DataFrame) -> dict:
    eligible = rows[
        rows.position.isin(POSITIONS)
        & rows.was_active.fillna(False).astype(bool)
    ].copy()
    supported = eligible[
        eligible.sis_pass_tail_supported.fillna(False).astype(bool)
    ].copy()
    team_weeks = supported.drop_duplicates(["season", "week", "opp"])
    return {
        "panel_rows": int(len(eligible)),
        "supported_rows": int(len(supported)),
        "supported_fraction": float(len(supported) / len(eligible)),
        "supported_by_position": {
            str(key): int(value)
            for key, value in supported.groupby("position").size().items()
        },
        "supported_by_season": {
            str(int(key)): int(value)
            for key, value in supported.groupby("season").size().items()
        },
        "team_weeks": int(len(team_weeks)),
        "redundancy": {
            "boom_vs_existing_pdef_epa": _correlation(
                team_weeks.sis_pass_def_boom_rate_l4,
                team_weeks.epa_per_dropback_allowed_l6,
            ),
            "bust_vs_existing_pdef_epa": _correlation(
                team_weeks.sis_pass_def_bust_rate_l4,
                team_weeks.epa_per_dropback_allowed_l6,
            ),
            "pressure_vs_existing_pressure": _correlation(
                team_weeks.sis_pass_rush_pressure_rate_l4,
                team_weeks.opp_pressure_rate_l6,
            ),
            "boom_vs_bust": _correlation(
                team_weeks.sis_pass_def_boom_rate_l4,
                team_weeks.sis_pass_def_bust_rate_l4,
            ),
        },
        "outcomes_read": False,
    }


def run() -> dict:
    from ..bq import query_df
    from ..config import settings

    source = query_df(f"SELECT * FROM `{settings.raw}.sis_team_context_game`")
    context = build_strict_prior_context(source)
    panel = query_df(f"""
        SELECT s.season, s.week, s.gsis_id, s.pos AS position, s.opp,
               t.was_active, t.epa_per_dropback_allowed_l6,
               t.opp_pressure_rate_l6
        FROM `{settings.predictions}.slate_player_features` s
        JOIN `{settings.features}.player_week_training` t
          USING (season, week, gsis_id)
        WHERE s.panel_run_id=@panel AND s.research_eligible
          AND s.pos IN UNNEST(@positions)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY s.generated_at DESC
        ) = 1
        """, params={"panel": PANEL_ID, "positions": list(POSITIONS)})
    attached = attach_context(panel, context)
    report = {
        "version": "v1-outcome-free",
        "panel": PANEL_ID,
        "source_table": f"{settings.raw}.sis_team_context_game",
        "strict_prior": True,
        "feature_window": "last four completed games; minimum two",
        "features": list(FEATURES),
        **audit_attached(attached),
    }
    print("SIS_PASS_TAIL_SUPPORT_JSON=" + json.dumps(report, sort_keys=True))
    return report


__all__ = [
    "FEATURES", "attach_context", "audit_attached",
    "build_strict_prior_context", "run",
]
