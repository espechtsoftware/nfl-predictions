"""Strictly-prior exploratory audit of paid SIS team run context."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd


PANEL_ID = "20260812-pitclean-e80-selected-tabpfn-active-v2"
POSITION = "RB"

# Every rolling rate is reconstructed from lagged numerators/denominators.
# That preserves volume weighting and prevents a two-carry game from receiving
# the same influence as a 30-carry game.  Vendor Value-view percentages use
# their independently exported attempt denominator.
RATIO_FEATURES = {
    "sis_rb_off_yac_per_att_l4": (
        "rush_yards_after_contact", "rush_attempts"),
    "sis_rb_off_broken_tackle_rate_l4": (
        "rush_broken_tackles", "rush_attempts"),
    "sis_rb_off_missed_tackle_rate_l4": (
        "rush_missed_tackles", "rush_attempts"),
    "sis_rb_off_hit_at_line_rate_l4": (
        "rush_hit_at_line", "rush_attempts"),
    "sis_rb_off_stuff_rate_l4": ("rush_stuffs", "rush_attempts"),
    "sis_rb_off_pe_per_play_l4": (
        "rush_points_earned", "rush_value_attempts"),
    "sis_rb_off_epa_per_att_l4": ("rush_epa", "rush_value_attempts"),
    "sis_rb_off_positive_rate_l4": (
        "_rush_positive_events", "rush_value_attempts"),
    "sis_rb_off_boom_rate_l4": (
        "_rush_boom_events", "rush_value_attempts"),
    "sis_rb_off_bust_rate_l4": (
        "_rush_bust_events", "rush_value_attempts"),
    "sis_rb_def_yards_per_att_l4": ("rdef_yards", "rdef_attempts"),
    "sis_rb_def_yac_per_att_l4": (
        "rdef_yards_after_contact", "rdef_attempts"),
    "sis_rb_def_stuff_rate_l4": ("rdef_stuffs", "rdef_attempts"),
    "sis_rb_def_tfl_rate_l4": (
        "rdef_tackles_for_loss", "rdef_attempts"),
    "sis_rb_def_ps_per_play_l4": (
        "rdef_points_saved", "rdef_attempts"),
    "sis_rb_def_epa_per_att_l4": (
        "_rdef_epa", "rdef_attempts"),
    "sis_rb_def_positive_rate_l4": (
        "_rdef_positive_events", "rdef_attempts"),
    "sis_rb_def_boom_rate_l4": (
        "_rdef_boom_events", "rdef_attempts"),
    "sis_rb_def_bust_rate_l4": (
        "_rdef_bust_events", "rdef_attempts"),
}
FEATURES = tuple(RATIO_FEATURES)
OFFENSE_FEATURES = tuple(name for name in FEATURES if "_off_" in name)
DEFENSE_FEATURES = tuple(name for name in FEATURES if "_def_" in name)


def _rolling_prior_sum(rows: pd.DataFrame, column: str) -> pd.Series:
    grouped = rows.groupby(["season", "team"], sort=False)[column]
    return grouped.transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum())


def build_strict_prior_run_context(source: pd.DataFrame) -> pd.DataFrame:
    direct = {
        "season", "week", "team", "rush_attempts", "rush_yards_after_contact",
        "rush_broken_tackles", "rush_missed_tackles", "rush_hit_at_line",
        "rush_stuffs", "rush_value_attempts", "rush_points_earned", "rush_epa",
        "rush_positive_rate", "rush_boom_rate", "rush_bust_rate",
        "rdef_attempts", "rdef_yards", "rdef_yards_after_contact",
        "rdef_stuffs", "rdef_tackles_for_loss", "rdef_points_saved",
        "rdef_epa_per_attempt", "rdef_positive_rate", "rdef_boom_rate",
        "rdef_bust_rate",
    }
    if missing := direct - set(source):
        raise ValueError(f"SIS run context source missing {sorted(missing)}")
    keys = ["season", "week", "team"]
    if source.duplicated(keys).any():
        raise ValueError("SIS run context source repeats team-week keys")
    rows = source.copy().sort_values(keys).reset_index(drop=True)
    numeric = direct - set(keys)
    rows[list(numeric)] = rows[list(numeric)].apply(pd.to_numeric, errors="coerce")
    for rate in (
        "rush_positive_rate", "rush_boom_rate", "rush_bust_rate",
        "rdef_positive_rate", "rdef_boom_rate", "rdef_bust_rate",
    ):
        valid = rows[rate].dropna()
        if not valid.between(0, 1).all():
            raise ValueError(f"SIS run context {rate} is outside [0,1]")
    rows["_rush_positive_events"] = (
        rows.rush_positive_rate * rows.rush_value_attempts)
    rows["_rush_boom_events"] = rows.rush_boom_rate * rows.rush_value_attempts
    rows["_rush_bust_events"] = rows.rush_bust_rate * rows.rush_value_attempts
    rows["_rdef_epa"] = rows.rdef_epa_per_attempt * rows.rdef_attempts
    rows["_rdef_positive_events"] = (
        rows.rdef_positive_rate * rows.rdef_attempts)
    rows["_rdef_boom_events"] = rows.rdef_boom_rate * rows.rdef_attempts
    rows["_rdef_bust_events"] = rows.rdef_bust_rate * rows.rdef_attempts

    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_run_source_week_end"] = grouped.week.shift(1)
    output["sis_run_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count())
    sums: dict[str, pd.Series] = {}
    for numerator, denominator in set(RATIO_FEATURES.values()):
        if numerator not in sums:
            sums[numerator] = _rolling_prior_sum(rows, numerator)
        if denominator not in sums:
            sums[denominator] = _rolling_prior_sum(rows, denominator)
    for name, (numerator, denominator) in RATIO_FEATURES.items():
        output[name] = sums[numerator] / sums[denominator].replace(0, np.nan)
    supported = output.sis_run_prior_games.ge(2)
    if supported.any() and not output.loc[
        supported, "sis_run_source_week_end"
    ].lt(output.loc[supported, "week"]).all():
        raise ValueError("SIS run context used target-week information")
    return output


def attach_run_context(panel: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    needed = {
        "season", "week", "gsis_id", "position", "team", "opp", "actual",
        "mean_projection", "was_active", "epa_per_rush_allowed_l6",
        "yards_per_carry_l8", "stacked_box_l4", "carry_share_l4",
    }
    if missing := needed - set(panel):
        raise ValueError(f"SIS run audit panel missing {sorted(missing)}")
    if panel.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("SIS run audit panel repeats player-week keys")
    offense = context[[
        "season", "week", "team", "sis_run_source_week_end",
        "sis_run_prior_games", *OFFENSE_FEATURES,
    ]].rename(columns={
        "sis_run_source_week_end": "sis_run_off_source_week_end",
        "sis_run_prior_games": "sis_run_off_prior_games",
    })
    defense = context[[
        "season", "week", "team", "sis_run_source_week_end",
        "sis_run_prior_games", *DEFENSE_FEATURES,
    ]].rename(columns={
        "team": "opp",
        "sis_run_source_week_end": "sis_run_def_source_week_end",
        "sis_run_prior_games": "sis_run_def_prior_games",
    })
    out = panel.merge(
        offense, on=["season", "week", "team"], how="left",
        validate="many_to_one")
    out = out.merge(
        defense, on=["season", "week", "opp"], how="left",
        validate="many_to_one")
    out["sis_run_supported"] = (
        out.sis_run_off_prior_games.ge(2)
        & out.sis_run_def_prior_games.ge(2)
        & out[list(FEATURES)].notna().all(axis=1)
    )
    supported = out.sis_run_supported
    if supported.any() and not (
        out.loc[supported, "sis_run_off_source_week_end"].lt(
            out.loc[supported, "week"])
        & out.loc[supported, "sis_run_def_source_week_end"].lt(
            out.loc[supported, "week"])
    ).all():
        raise ValueError("SIS attached run context violates strict-prior scope")
    out["residual"] = out.actual - out.mean_projection
    out["beat_10"] = out.actual.ge(out.mean_projection + 10).astype(float)
    out["actual_20"] = out.actual.ge(20).astype(float)
    out["actual_25"] = out.actual.ge(25).astype(float)
    out["actual_30"] = out.actual.ge(30).astype(float)
    return out


def _correlation(left: pd.Series, right: pd.Series) -> float | None:
    valid = left.notna() & right.notna()
    if valid.sum() < 3 or left[valid].nunique() < 2 or right[valid].nunique() < 2:
        return None
    value = left[valid].corr(right[valid])
    return float(value) if np.isfinite(value) else None


def audit_attached(rows: pd.DataFrame) -> dict:
    active = rows[
        rows.position.eq(POSITION) & rows.was_active.fillna(False).astype(bool)
    ].copy()
    supported = active[active.sis_run_supported].copy()
    aggregate = []
    folds = []
    for feature in FEATURES:
        aggregate.append({
            "feature": feature,
            "rows": int(supported[feature].notna().sum()),
            "residual_correlation": _correlation(
                supported[feature], supported.residual),
            "beat_10_correlation": _correlation(
                supported[feature], supported.beat_10),
            "actual_20_correlation": _correlation(
                supported[feature], supported.actual_20),
            "actual_25_correlation": _correlation(
                supported[feature], supported.actual_25),
            "actual_30_correlation": _correlation(
                supported[feature], supported.actual_30),
        })
        for season, season_rows in supported.groupby("season"):
            folds.append({
                "feature": feature,
                "season": int(season),
                "rows": int(season_rows[feature].notna().sum()),
                "residual_correlation": _correlation(
                    season_rows[feature], season_rows.residual),
                "beat_10_correlation": _correlation(
                    season_rows[feature], season_rows.beat_10),
                "actual_25_correlation": _correlation(
                    season_rows[feature], season_rows.actual_25),
                "actual_30_correlation": _correlation(
                    season_rows[feature], season_rows.actual_30),
            })
    redundancy = {
        "sis_def_epa_vs_existing_opp_epa": _correlation(
            supported.sis_rb_def_epa_per_att_l4,
            supported.epa_per_rush_allowed_l6),
        "sis_off_yac_vs_existing_player_ypc": _correlation(
            supported.sis_rb_off_yac_per_att_l4, supported.yards_per_carry_l8),
        "sis_off_hit_line_vs_existing_stacked_box": _correlation(
            supported.sis_rb_off_hit_at_line_rate_l4,
            supported.stacked_box_l4),
        "sis_off_boom_vs_existing_carry_share": _correlation(
            supported.sis_rb_off_boom_rate_l4, supported.carry_share_l4),
        "defense_features_vs_existing_opp_epa": {
            feature: _correlation(
                supported[feature], supported.epa_per_rush_allowed_l6)
            for feature in DEFENSE_FEATURES
        },
        "defense_feature_pairwise": {
            f"{left}__{right}": _correlation(
                supported[left], supported[right])
            for index, left in enumerate(DEFENSE_FEATURES)
            for right in DEFENSE_FEATURES[index + 1:]
        },
    }
    return {
        "active_rows": int(len(active)),
        "supported_active_rows": int(len(supported)),
        "supported_active_fraction": float(len(supported) / len(active)),
        "slates": int(supported[["season", "week"]].drop_duplicates().shape[0]),
        "aggregate": aggregate,
        "by_season": folds,
        "redundancy": redundancy,
        "exploratory_outcomes_read": True,
    }


def run() -> dict:
    from ..bq import query_df
    from ..config import settings

    table = f"{settings.raw}.sis_team_run_context_game"
    source = query_df(f"SELECT * FROM `{table}`")
    context = build_strict_prior_run_context(source)
    panel = query_df(f"""
        SELECT s.season, s.week, s.gsis_id, s.pos AS position, s.team, s.opp,
               s.actual, s.mean_projection, t.was_active,
               t.epa_per_rush_allowed_l6, t.yards_per_carry_l8,
               t.stacked_box_l4, t.carry_share_l4
        FROM `{settings.predictions}.slate_player_features` s
        JOIN `{settings.features}.player_week_training` t
          USING (season, week, gsis_id)
        WHERE s.panel_run_id = @panel AND s.research_eligible AND s.pos = @position
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY s.generated_at DESC
        ) = 1
        """, params={"panel": PANEL_ID, "position": POSITION})
    attached = attach_run_context(panel, context)
    audit = audit_attached(attached)
    report = {
        "version": "v1-active-rb-exploratory",
        "panel": PANEL_ID,
        "source_table": table,
        "strict_prior": True,
        "feature_window": (
            "volume-weighted last four completed games; minimum two; shift one"),
        "position": POSITION,
        "features": list(FEATURES),
        "audit": audit,
        "disclosure": (
            "Exploratory/adaptive audit: outcomes were read. Any selected bundle "
            "requires a separately frozen walk-forward model protocol before "
            "model output, and no lineup score is licensed by this report."),
    }
    print("SIS_TEAM_RUN_CONTEXT_AUDIT_JSON=" + json.dumps(report, sort_keys=True))
    return report


__all__ = [
    "FEATURES", "attach_run_context", "audit_attached",
    "build_strict_prior_run_context", "run",
]
