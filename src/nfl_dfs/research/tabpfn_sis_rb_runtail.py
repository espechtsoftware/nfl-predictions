"""Frozen PIT helpers for the adaptive SIS RB opponent run-tail arm."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


SIS_SOURCE_RUN = "sis-team-run-context-tranche-2-v1"
SIS_RB_RUNTAIL_FEATURES = (
    "sis_rb_def_boom_rate_l4",
    "sis_rb_def_bust_rate_l4",
)
SOURCE_HASH_COLUMNS = (
    "source_original_plan_sha256", "source_recovery_plan_sha256",
    "source_original_state_sha256", "source_recovery_state_sha256",
)
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def feature_contract(baseline: Sequence[str], arm: str) -> list[str]:
    if arm not in {"control", "treatment"}:
        raise ValueError(f"unknown SIS RB run-tail arm {arm!r}")
    listed = sorted(baseline)
    if len(listed) != len(set(listed)):
        raise ValueError("baseline feature contract contains duplicates")
    if forbidden := set(SIS_RB_RUNTAIL_FEATURES).intersection(listed):
        raise ValueError(f"baseline already contains SIS RB run-tail {sorted(forbidden)}")
    return listed if arm == "control" else [*listed, *SIS_RB_RUNTAIL_FEATURES]


def _prior_sum(rows: pd.DataFrame, column: str) -> pd.Series:
    return rows.groupby(["season", "team"], sort=False)[column].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum()
    )


def build_strict_prior_sis_rb_runtail(source: pd.DataFrame) -> pd.DataFrame:
    required = {
        "season", "week", "team", "source_run_id", "rdef_attempts",
        "rdef_boom_rate", "rdef_bust_rate", *SOURCE_HASH_COLUMNS,
    }
    if missing := required - set(source):
        raise ValueError(f"SIS RB run-tail source lacks {sorted(missing)}")
    if set(source.source_run_id.dropna().astype(str)) != {SIS_SOURCE_RUN}:
        raise ValueError("SIS RB run-tail source-run identity differs")
    if source.source_run_id.isna().any():
        raise ValueError("SIS RB run-tail source-run identity is incomplete")
    for column in SOURCE_HASH_COLUMNS:
        if source[column].isna().any() or source[column].nunique() != 1:
            raise ValueError(f"SIS RB run-tail {column} identity differs")
    keys = ["season", "week", "team"]
    rows = source.copy()
    rows["team"] = rows.team.replace(TEAM_ALIASES)
    if rows.duplicated(keys).any():
        raise ValueError("SIS RB run-tail source repeats team-week keys")
    rows = rows.sort_values(keys).reset_index(drop=True)
    rows["_attempts"] = pd.to_numeric(rows.rdef_attempts, errors="coerce")
    if rows._attempts.isna().any() or not np.isfinite(rows._attempts).all() \
            or not rows._attempts.ge(0).all():
        raise ValueError("SIS RB run-tail attempts are invalid")
    for field in ("rdef_boom_rate", "rdef_bust_rate"):
        rows[field] = pd.to_numeric(rows[field], errors="coerce")
        if rows[field].isna().any() or not np.isfinite(rows[field]).all() \
                or not rows[field].between(0, 1).all():
            raise ValueError(f"SIS RB run-tail {field} is outside [0,1]")
    rows["_boom_events"] = rows.rdef_boom_rate * rows._attempts
    rows["_bust_events"] = rows.rdef_bust_rate * rows._attempts
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_rb_runtail_source_week_end"] = grouped.week.shift(1)
    output["sis_rb_runtail_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count()
    )
    denominator = _prior_sum(rows, "_attempts").replace(0, np.nan)
    output[SIS_RB_RUNTAIL_FEATURES[0]] = (
        _prior_sum(rows, "_boom_events") / denominator
    )
    output[SIS_RB_RUNTAIL_FEATURES[1]] = (
        _prior_sum(rows, "_bust_events") / denominator
    )
    supported = output[list(SIS_RB_RUNTAIL_FEATURES)].notna().all(axis=1)
    if supported.any() and not output.loc[
        supported, "sis_rb_runtail_source_week_end"
    ].lt(output.loc[supported, "week"]).all():
        raise ValueError("SIS RB run-tail feature used target week")
    return output


def attach_sis_rb_runtail(
    panel: pd.DataFrame, strict_prior: pd.DataFrame,
) -> pd.DataFrame:
    opponent_column = "opponent" if "opponent" in panel else "opp"
    required = {"season", "week", opponent_column, "position"}
    if missing := required - set(panel):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    feature_required = {
        "season", "week", "team", "sis_rb_runtail_source_week_end",
        "sis_rb_runtail_prior_games", *SIS_RB_RUNTAIL_FEATURES,
    }
    if missing := feature_required - set(strict_prior):
        raise ValueError(f"strict-prior SIS RB run-tail lacks {sorted(missing)}")
    players = panel.copy()
    players["_sis_opponent"] = players[opponent_column].replace(TEAM_ALIASES)
    features = strict_prior.rename(columns={"team": "_sis_opponent"}).copy()
    keys = ["season", "week", "_sis_opponent"]
    if features.duplicated(keys).any():
        raise ValueError("strict-prior SIS RB run-tail keys are not unique")
    columns = [
        *keys, "sis_rb_runtail_source_week_end",
        "sis_rb_runtail_prior_games", *SIS_RB_RUNTAIL_FEATURES,
    ]
    joined = players.merge(
        features[columns], on=keys, how="left", sort=False,
        validate="many_to_one",
    )
    if len(joined) != len(panel):
        raise ValueError("SIS RB run-tail join changed player row count")
    non_rb = ~joined.position.astype(str).eq("RB")
    joined.loc[non_rb, [
        *SIS_RB_RUNTAIL_FEATURES, "sis_rb_runtail_source_week_end",
        "sis_rb_runtail_prior_games",
    ]] = np.nan
    supported = joined[list(SIS_RB_RUNTAIL_FEATURES)].notna().all(axis=1)
    if supported.any() and not joined.loc[
        supported, "sis_rb_runtail_source_week_end"
    ].lt(joined.loc[supported, "week"]).all():
        raise ValueError("attached SIS RB run-tail violates PIT scope")
    return joined.drop(columns="_sis_opponent")


def active_rb_coverage(panel: pd.DataFrame) -> list[dict[str, object]]:
    required = {"season", "position", "was_active", *SIS_RB_RUNTAIL_FEATURES}
    if missing := required - set(panel):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    rbs = panel[
        panel.position.eq("RB") & panel.was_active.fillna(False).astype(bool)
    ]
    output = []
    for season, rows in rbs.groupby("season", sort=True):
        supported = rows[list(SIS_RB_RUNTAIL_FEATURES)].notna().all(axis=1)
        output.append({
            "season": int(season),
            "rows": int(len(rows)),
            "supported_rows": int(supported.sum()),
            "support_rate": float(supported.mean()),
        })
    return output


__all__ = [
    "SIS_RB_RUNTAIL_FEATURES", "SIS_SOURCE_RUN", "SOURCE_HASH_COLUMNS",
    "active_rb_coverage", "attach_sis_rb_runtail",
    "build_strict_prior_sis_rb_runtail", "feature_contract",
]
