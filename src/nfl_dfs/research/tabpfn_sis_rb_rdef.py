"""Frozen PIT helpers for the SIS RB opponent run-defense TabPFN arm."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


SIS_SOURCE_RUN = "sis-team-run-context-tranche-2-v1"
SIS_RB_FEATURE = "sis_rb_def_ps_per_play_l4"
SOURCE_HASH_COLUMNS = (
    "source_original_plan_sha256", "source_recovery_plan_sha256",
    "source_original_state_sha256", "source_recovery_state_sha256",
)
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def feature_contract(baseline: Sequence[str], arm: str) -> list[str]:
    if arm not in {"control", "treatment"}:
        raise ValueError(f"unknown SIS RB run-defense arm {arm!r}")
    listed = sorted(baseline)
    if len(listed) != len(set(listed)):
        raise ValueError("baseline feature contract contains duplicates")
    if SIS_RB_FEATURE in listed:
        raise ValueError("baseline already contains SIS RB run-defense feature")
    return listed if arm == "control" else [*listed, SIS_RB_FEATURE]


def build_strict_prior_sis_rb_rdef(source: pd.DataFrame) -> pd.DataFrame:
    required = {
        "season", "week", "team", "source_run_id", "rdef_points_saved",
        "rdef_attempts", *SOURCE_HASH_COLUMNS,
    }
    if missing := required - set(source):
        raise ValueError(f"SIS RB run-defense source lacks {sorted(missing)}")
    if set(source.source_run_id.dropna().astype(str)) != {SIS_SOURCE_RUN}:
        raise ValueError("SIS RB run-defense source-run identity differs")
    for column in SOURCE_HASH_COLUMNS:
        if source[column].isna().any() or source[column].nunique() != 1:
            raise ValueError(f"SIS RB run-defense {column} identity differs")
    keys = ["season", "week", "team"]
    rows = source.copy()
    rows["team"] = rows.team.replace(TEAM_ALIASES)
    if rows.duplicated(keys).any():
        raise ValueError("SIS RB run-defense source repeats team-week keys")
    rows = rows.sort_values(keys).reset_index(drop=True)
    rows["_points_saved"] = pd.to_numeric(
        rows.rdef_points_saved, errors="coerce")
    rows["_attempts"] = pd.to_numeric(rows.rdef_attempts, errors="coerce")
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_rb_rdef_source_week_end"] = grouped.week.shift(1)
    output["sis_rb_rdef_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count())
    numerator = grouped["_points_saved"].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum())
    denominator = grouped["_attempts"].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum())
    output[SIS_RB_FEATURE] = numerator / denominator.replace(0, np.nan)
    supported = output[SIS_RB_FEATURE].notna()
    if supported.any() and not output.loc[
        supported, "sis_rb_rdef_source_week_end"
    ].lt(output.loc[supported, "week"]).all():
        raise ValueError("SIS RB run-defense feature used target week")
    return output


def attach_sis_rb_rdef(
    panel: pd.DataFrame, strict_prior: pd.DataFrame,
) -> pd.DataFrame:
    # The canonical warehouse training table spells this field ``opponent``;
    # replay/audit frames historically expose the equivalent short name
    # ``opp``.  Resolve that schema difference explicitly and use a private
    # join key so neither input contract is mutated.
    opponent_column = "opponent" if "opponent" in panel else "opp"
    required = {"season", "week", opponent_column, "position"}
    if missing := required - set(panel):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    feature_required = {
        "season", "week", "team", "sis_rb_rdef_source_week_end",
        "sis_rb_rdef_prior_games", SIS_RB_FEATURE,
    }
    if missing := feature_required - set(strict_prior):
        raise ValueError(f"strict-prior SIS RB features lack {sorted(missing)}")
    players = panel.copy()
    players["_sis_opponent"] = players[opponent_column].replace(TEAM_ALIASES)
    features = strict_prior.rename(columns={"team": "_sis_opponent"}).copy()
    keys = ["season", "week", "_sis_opponent"]
    if features.duplicated(keys).any():
        raise ValueError("strict-prior SIS RB run-defense keys are not unique")
    columns = [
        *keys, "sis_rb_rdef_source_week_end", "sis_rb_rdef_prior_games",
        SIS_RB_FEATURE,
    ]
    joined = players.merge(
        features[columns], on=keys, how="left", sort=False,
        validate="many_to_one")
    if len(joined) != len(panel):
        raise ValueError("SIS RB run-defense join changed player row count")
    non_rb = ~joined.position.astype(str).eq("RB")
    joined.loc[non_rb, [
        SIS_RB_FEATURE, "sis_rb_rdef_source_week_end",
        "sis_rb_rdef_prior_games",
    ]] = np.nan
    supported = joined[SIS_RB_FEATURE].notna()
    if supported.any() and not joined.loc[
        supported, "sis_rb_rdef_source_week_end"
    ].lt(joined.loc[supported, "week"]).all():
        raise ValueError("attached SIS RB run-defense feature violates PIT scope")
    return joined.drop(columns="_sis_opponent")


def active_rb_coverage(panel: pd.DataFrame) -> list[dict[str, object]]:
    required = {"season", "position", "was_active", SIS_RB_FEATURE}
    if missing := required - set(panel):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    rbs = panel[
        panel.position.eq("RB") & panel.was_active.fillna(False).astype(bool)]
    output = []
    for season, rows in rbs.groupby("season", sort=True):
        supported = int(rows[SIS_RB_FEATURE].notna().sum())
        output.append({
            "season": int(season), "rows": int(len(rows)),
            "supported_rows": supported,
            "support_rate": float(supported / len(rows)),
        })
    return output


__all__ = [
    "SIS_RB_FEATURE", "SIS_SOURCE_RUN", "SOURCE_HASH_COLUMNS",
    "active_rb_coverage", "attach_sis_rb_rdef",
    "build_strict_prior_sis_rb_rdef", "feature_contract",
]
