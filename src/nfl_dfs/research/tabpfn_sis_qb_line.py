"""Frozen PIT feature helpers for the SIS QB offensive-line TabPFN arm."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


SIS_SOURCE_RUN = "sis-team-context-tranche-1-v1"
SIS_QB_FEATURES = ("sis_qb_pass_bb_l4", "sis_qb_block_pe_l4")
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def feature_contract(baseline: Sequence[str], arm: str) -> list[str]:
    """Return the inherited shared-33 control or fixed two-column treatment."""
    if arm not in {"control", "treatment"}:
        raise ValueError(f"unknown SIS QB line arm {arm!r}")
    listed = sorted(baseline)
    if len(listed) != len(set(listed)):
        raise ValueError("baseline feature contract contains duplicates")
    forbidden = set(SIS_QB_FEATURES).intersection(listed)
    if forbidden:
        raise ValueError(
            f"baseline feature contract already contains {sorted(forbidden)}")
    return listed if arm == "control" else [*listed, *SIS_QB_FEATURES]


def build_strict_prior_sis_qb_line(source: pd.DataFrame) -> pd.DataFrame:
    """Build same-season four-game QB line features, excluding target week."""
    required = {
        "season", "week", "team", "source_run_id",
        "pass_block_blown_blocks", "pass_block_snaps",
        "block_points_earned_per_play",
    }
    if missing := required - set(source.columns):
        raise ValueError(f"SIS QB line source lacks {sorted(missing)}")
    if set(source.source_run_id.dropna().astype(str)) != {SIS_SOURCE_RUN}:
        raise ValueError("SIS QB line source-run identity differs")
    keys = ["season", "week", "team"]
    if source.duplicated(keys).any():
        raise ValueError("SIS QB line source repeats team-week keys")
    rows = source.copy()
    rows["team"] = rows.team.replace(TEAM_ALIASES)
    if rows.duplicated(keys).any():
        raise ValueError("SIS QB line aliases create duplicate team-week keys")
    rows = rows.sort_values(keys).reset_index(drop=True)
    rows["_pass_bb_rate"] = (
        pd.to_numeric(rows.pass_block_blown_blocks, errors="coerce")
        / pd.to_numeric(rows.pass_block_snaps, errors="coerce").replace(0, np.nan)
    )
    rows["_block_pe"] = pd.to_numeric(
        rows.block_points_earned_per_play, errors="coerce")
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_qb_source_week_end"] = grouped.week.shift(1)
    output["sis_qb_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count())
    output[SIS_QB_FEATURES[0]] = grouped["_pass_bb_rate"].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).mean())
    output[SIS_QB_FEATURES[1]] = grouped["_block_pe"].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).mean())
    supported = output[list(SIS_QB_FEATURES)].notna().all(axis=1)
    if supported.any() and not output.loc[
        supported, "sis_qb_source_week_end"
    ].lt(output.loc[supported, "week"]).all():
        raise ValueError("SIS QB line feature used target-week information")
    return output


def attach_sis_qb_line(
    panel: pd.DataFrame, strict_prior: pd.DataFrame,
) -> pd.DataFrame:
    """Join the team-week features while exposing values only on QB rows."""
    required = {"season", "week", "team", "position"}
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    feature_required = {
        "season", "week", "team", "sis_qb_source_week_end",
        "sis_qb_prior_games", *SIS_QB_FEATURES,
    }
    if missing := feature_required - set(strict_prior.columns):
        raise ValueError(f"strict-prior SIS features lack {sorted(missing)}")
    keys = ["season", "week", "team"]
    players = panel.copy()
    players["team"] = players.team.replace(TEAM_ALIASES)
    features = strict_prior.copy()
    features["team"] = features.team.replace(TEAM_ALIASES)
    if features.duplicated(keys).any():
        raise ValueError("strict-prior SIS QB line keys are not unique")
    feature_columns = [
        *keys, "sis_qb_source_week_end", "sis_qb_prior_games",
        *SIS_QB_FEATURES,
    ]
    joined = players.merge(
        features[feature_columns], on=keys, how="left",
        sort=False, validate="many_to_one")
    if len(joined) != len(panel):
        raise ValueError("SIS QB line join changed player row count")
    non_qb = ~joined.position.astype(str).eq("QB")
    joined.loc[non_qb, [
        *SIS_QB_FEATURES, "sis_qb_source_week_end", "sis_qb_prior_games",
    ]] = np.nan
    supported = joined[list(SIS_QB_FEATURES)].notna().all(axis=1)
    if supported.any() and not joined.loc[
        supported, "sis_qb_source_week_end"
    ].lt(joined.loc[supported, "week"]).all():
        raise ValueError("attached SIS QB line feature violates PIT scope")
    return joined


def active_qb_coverage(panel: pd.DataFrame) -> list[dict[str, object]]:
    """Return active-QB support by target season for the mechanical gate."""
    required = {"season", "position", "was_active", *SIS_QB_FEATURES}
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    qbs = panel[
        panel.position.eq("QB") & panel.was_active.fillna(False).astype(bool)
    ]
    output = []
    for season, rows in qbs.groupby("season", sort=True):
        supported = int(rows[list(SIS_QB_FEATURES)].notna().all(axis=1).sum())
        output.append({
            "season": int(season),
            "rows": int(len(rows)),
            "supported_rows": supported,
            "support_rate": float(supported / len(rows)),
        })
    return output


__all__ = [
    "SIS_QB_FEATURES", "SIS_SOURCE_RUN", "active_qb_coverage",
    "attach_sis_qb_line", "build_strict_prior_sis_qb_line",
    "feature_contract",
]
