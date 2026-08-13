"""Strictly-prior exploratory audit of paid SIS team-game context."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd


PANEL_ID = "20260812-pitclean-e80-selected-tabpfn-active-v2"
POSITIONS = ("QB", "RB", "WR", "TE")
SOURCE_FEATURES = {
    "pdef_epa_per_play": "sis_def_pdef_epa_l4",
    "pdef_points_saved_per_play": "sis_def_pdef_ps_l4",
    "pressure_rate": "sis_def_pressure_l4",
    "prush_points_saved_per_play": "sis_def_prush_ps_l4",
    "pass_bb_rate": "sis_off_pass_bb_l4",
    "run_bb_rate": "sis_off_run_bb_l4",
    "block_points_earned_per_play": "sis_off_block_pe_l4",
}
FEATURES = tuple(SOURCE_FEATURES.values())


def build_strict_prior_context(source: pd.DataFrame) -> pd.DataFrame:
    needed = {
        "season", "week", "team", "pdef_attempts", "prush_combined_sacks",
        "prush_pressures", "pdef_epa_per_play", "pdef_points_saved_per_play",
        "prush_points_saved_per_play", "pass_block_blown_blocks",
        "pass_block_snaps", "run_block_blown_blocks", "run_block_snaps",
        "block_points_earned_per_play",
    }
    if missing := needed - set(source):
        raise ValueError(f"SIS team context source missing {sorted(missing)}")
    keys = ["season", "week", "team"]
    if source.duplicated(keys).any():
        raise ValueError("SIS team context source repeats team-week keys")
    rows = source.copy().sort_values(keys).reset_index(drop=True)
    rows["pressure_rate"] = rows.prush_pressures / (
        rows.pdef_attempts + rows.prush_combined_sacks).replace(0, np.nan)
    rows["pass_bb_rate"] = (
        rows.pass_block_blown_blocks / rows.pass_block_snaps.replace(0, np.nan))
    rows["run_bb_rate"] = (
        rows.run_block_blown_blocks / rows.run_block_snaps.replace(0, np.nan))
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_source_week_end"] = grouped.week.shift(1)
    output["sis_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count())
    for source_name, output_name in SOURCE_FEATURES.items():
        output[output_name] = grouped[source_name].transform(
            lambda values: values.shift(1).rolling(4, min_periods=2).mean())
    supported = output.sis_prior_games.ge(2)
    if supported.any() and not (
        output.loc[supported, "sis_source_week_end"]
        < output.loc[supported, "week"]
    ).all():
        raise ValueError("SIS team context used target-week information")
    return output


def attach_context(panel: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    needed = {
        "season", "week", "gsis_id", "position", "team", "opp", "actual",
        "mean_projection",
    }
    if missing := needed - set(panel):
        raise ValueError(f"SIS audit panel missing {sorted(missing)}")
    if panel.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("SIS audit panel repeats player-week keys")
    off_names = {
        feature: feature for feature in FEATURES if feature.startswith("sis_off_")
    }
    off_names.update({
        "sis_source_week_end": "sis_off_source_week_end",
        "sis_prior_games": "sis_off_prior_games",
    })
    defense_names = {
        feature: feature for feature in FEATURES if feature.startswith("sis_def_")
    }
    defense_names.update({
        "sis_source_week_end": "sis_def_source_week_end",
        "sis_prior_games": "sis_def_prior_games",
    })
    out = panel.merge(
        context[["season", "week", "team", *off_names]].rename(
            columns=off_names),
        on=["season", "week", "team"], how="left", validate="many_to_one",
    )
    out = out.merge(
        context[["season", "week", "team", *defense_names]].rename(
            columns={"team": "opp", **defense_names}),
        on=["season", "week", "opp"], how="left", validate="many_to_one",
    )
    out["sis_supported"] = (
        out.sis_off_prior_games.ge(2) & out.sis_def_prior_games.ge(2)
    )
    supported = out.sis_supported
    if supported.any() and not (
        out.loc[supported, "sis_off_source_week_end"].lt(out.loc[supported, "week"])
        & out.loc[supported, "sis_def_source_week_end"].lt(
            out.loc[supported, "week"])
    ).all():
        raise ValueError("SIS attached context violates strict-prior scope")
    out["residual"] = out.actual - out.mean_projection
    out["beat_10"] = out.actual.ge(out.mean_projection + 10).astype(float)
    out["actual_20"] = out.actual.ge(20).astype(float)
    out["actual_30"] = out.actual.ge(30).astype(float)
    return out


def _correlation(left: pd.Series, right: pd.Series) -> float | None:
    valid = left.notna() & right.notna()
    if valid.sum() < 3 or left[valid].nunique() < 2 or right[valid].nunique() < 2:
        return None
    value = left[valid].corr(right[valid])
    return float(value) if np.isfinite(value) else None


def outcome_audit(rows: pd.DataFrame) -> dict:
    supported = rows[rows.sis_supported & rows.position.isin(POSITIONS)].copy()
    aggregate = []
    folds = []
    for position in POSITIONS:
        position_rows = supported[supported.position.eq(position)]
        for feature in FEATURES:
            aggregate.append({
                "position": position,
                "feature": feature,
                "rows": int(position_rows[feature].notna().sum()),
                "residual_correlation": _correlation(
                    position_rows[feature], position_rows.residual),
                "beat_10_correlation": _correlation(
                    position_rows[feature], position_rows.beat_10),
                "actual_20_correlation": _correlation(
                    position_rows[feature], position_rows.actual_20),
                "actual_30_correlation": _correlation(
                    position_rows[feature], position_rows.actual_30),
            })
            for season, season_rows in position_rows.groupby("season"):
                folds.append({
                    "position": position,
                    "feature": feature,
                    "season": int(season),
                    "rows": int(season_rows[feature].notna().sum()),
                    "residual_correlation": _correlation(
                        season_rows[feature], season_rows.residual),
                    "beat_10_correlation": _correlation(
                        season_rows[feature], season_rows.beat_10),
                })
    return {
        "rows": int(len(supported)),
        "slates": int(supported[["season", "week"]].drop_duplicates().shape[0]),
        "aggregate": aggregate,
        "by_season": folds,
        "exploratory_outcomes_read": True,
    }


def redundancy_audit(
    context: pd.DataFrame,
    existing: pd.DataFrame,
) -> dict:
    needed = {
        "season", "week", "team", "existing_pdef_epa", "existing_pressure",
    }
    if missing := needed - set(existing):
        raise ValueError(f"SIS redundancy source missing {sorted(missing)}")
    if existing.duplicated(["season", "week", "team"]).any():
        raise ValueError("SIS redundancy source repeats team-week keys")
    joined = existing.merge(
        context, on=["season", "week", "team"], how="inner",
        validate="one_to_one")
    return {
        "rows": int(len(joined)),
        "pdef_epa_vs_existing": _correlation(
            joined.sis_def_pdef_epa_l4, joined.existing_pdef_epa),
        "pressure_vs_existing": _correlation(
            joined.sis_def_pressure_l4, joined.existing_pressure),
        "outcomes_read": False,
    }


def run() -> dict:
    from ..bq import query_df
    from ..config import settings

    source = query_df(f"SELECT * FROM `{settings.raw}.sis_team_context_game`")
    context = build_strict_prior_context(source)
    panel = query_df(f"""
        SELECT season, week, gsis_id, pos AS position, team, opp, actual,
               mean_projection
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel AND research_eligible
          AND pos IN UNNEST(@positions)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel": PANEL_ID, "positions": list(POSITIONS)})
    existing = query_df(f"""
        SELECT season, week, opponent AS team,
               ANY_VALUE(epa_per_dropback_allowed_l6) AS existing_pdef_epa,
               ANY_VALUE(opp_pressure_rate_l6) AS existing_pressure
        FROM `{settings.features}.player_week_training`
        WHERE season IN UNNEST(@seasons)
        GROUP BY season, week, team
        """, params={"seasons": sorted(map(int, source.season.unique()))})
    attached = attach_context(panel, context)
    report = {
        "version": "v1",
        "panel": PANEL_ID,
        "source_table": f"{settings.raw}.sis_team_context_game",
        "strict_prior": True,
        "feature_window": "last four completed games; minimum two",
        "features": list(FEATURES),
        "coverage": {
            "panel_rows": int(len(attached)),
            "supported_rows": int(attached.sis_supported.sum()),
            "supported_fraction": float(attached.sis_supported.mean()),
        },
        "redundancy": redundancy_audit(context, existing),
        "outcomes": outcome_audit(attached),
        "disclosure": (
            "Exploratory/adaptive audit: outcomes were read. Any selected bundle "
            "requires a separately frozen model protocol before model output."),
    }
    print("SIS_TEAM_CONTEXT_AUDIT_JSON=" + json.dumps(report, sort_keys=True))
    return report


__all__ = [
    "FEATURES", "attach_context", "build_strict_prior_context",
    "outcome_audit", "redundancy_audit", "run",
]
