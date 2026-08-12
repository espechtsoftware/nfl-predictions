"""Frozen feature-contract helpers for the team-QB-quality TabPFN arm."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


POSITIONS = ("QB", "RB", "WR", "TE")
PASS_CATCHER_POSITIONS = frozenset(("RB", "WR", "TE"))
SCHED_FEATURES = ("net_rest_diff", "body_clock_hour")
TEAM_QB_FEATURE = "team_qb_cpoe_l6"
TEAM_QB_FEATURES = (TEAM_QB_FEATURE, "team_qb_cpoe_cross_season")
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def feature_contract(
    baseline: Sequence[str], feature_law: str, arm: str
) -> list[str]:
    """Return the exact inherited control or two-column treatment contract."""
    if feature_law not in {"base", "sched"}:
        raise ValueError(f"unknown feature law {feature_law!r}")
    if arm not in {"control", "treatment"}:
        raise ValueError(f"unknown arm {arm!r}")
    listed = sorted(baseline)
    if len(listed) != len(set(listed)):
        raise ValueError("baseline feature contract contains duplicates")
    forbidden = {*SCHED_FEATURES, *TEAM_QB_FEATURES}.intersection(listed)
    if forbidden:
        raise ValueError(
            f"baseline feature contract already contains {sorted(forbidden)}")
    inherited = (
        listed if feature_law == "base" else [*listed, *SCHED_FEATURES]
    )
    return inherited if arm == "control" else [*inherited, *TEAM_QB_FEATURES]


def broadcast_team_qb_quality(
    panel: pd.DataFrame, quality: pd.DataFrame
) -> pd.DataFrame:
    """Join the team-week feature and expose it only to RB/WR/TE rows."""
    player_required = {"team", "season", "week", "position"}
    quality_required = {"team", "season", "week", *TEAM_QB_FEATURES}
    if missing := player_required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    if missing := quality_required - set(quality.columns):
        raise ValueError(f"team quality table lacks {sorted(missing)}")
    keys = ["team", "season", "week"]
    players = panel.copy()
    team_quality = quality.copy()
    players["team"] = players["team"].replace(TEAM_ALIASES)
    team_quality["team"] = team_quality["team"].replace(TEAM_ALIASES)
    if team_quality.duplicated(keys).any():
        raise ValueError("team quality keys are not unique")
    joined = players.merge(
        team_quality[keys + list(TEAM_QB_FEATURES)],
        on=keys,
        how="left",
        validate="many_to_one",
    )
    eligible = joined.position.isin(PASS_CATCHER_POSITIONS)
    joined.loc[~eligible, list(TEAM_QB_FEATURES)] = np.nan
    return joined


def feature_coverage(panel: pd.DataFrame) -> list[dict[str, object]]:
    """Return deterministic season/position support rows for audit output."""
    grouped = panel.groupby(["season", "position"], observed=True, sort=True)
    rows: list[dict[str, object]] = []
    for (season, position), group in grouped:
        supported = int(group[TEAM_QB_FEATURE].notna().sum())
        cross_season = int(group["team_qb_cpoe_cross_season"].eq(1).sum())
        rows.append({
            "season": int(season),
            "position": str(position),
            "rows": int(len(group)),
            "supported_rows": supported,
            "support_rate": float(supported / len(group)),
            "cross_season_rows": cross_season,
            "cross_season_rate": float(cross_season / len(group)),
        })
    return rows


def qb_ngs_support(panel: pd.DataFrame) -> list[dict[str, object]]:
    """Stratify existing player-QB CPOE support by activity provenance."""
    required = {"season", "position", "was_active", "qb_cpoe_l6"}
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    qbs = panel[panel.position.eq("QB")].copy()
    qbs["active"] = qbs.was_active.astype(bool)
    grouped = qbs.groupby(["season", "active"], observed=True, sort=True)
    rows: list[dict[str, object]] = []
    for (season, active), group in grouped:
        supported = int(group.qb_cpoe_l6.notna().sum())
        rows.append({
            "season": int(season),
            "active": bool(active),
            "rows": int(len(group)),
            "supported_rows": supported,
            "support_rate": float(supported / len(group)),
        })
    return rows
