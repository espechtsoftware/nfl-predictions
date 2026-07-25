"""Late-breaking inactive adjustment: the injury cascade (guide §8.4) wired
into the hourly inference pass.

Injuries reach projections through two complementary layers:

* ``team_week_vacated`` features (018/021/023) carry Wednesday-Friday "Out"
  designations into the feature matrix, so the models learn next-man-up
  bumps from history.
* This module handles what the feature build can't: status flips after
  features were built — the starter ruled out Sunday morning. Players the
  DK slate marks O/IR (or the report lists as Out) get their projections
  zeroed, and their opportunity is redistributed to slate teammates via
  ``graph.cascade.project_vacated_usage`` — measured with/without splits
  when the player has absence history, depth-chart-style weighting when
  history is thin.

The redistribution normalizes over slate teammates, so opportunity that
would really leak to unrosterable players is credited to rosterable ones —
a mild, deliberate overestimate: for DFS the cost of missing the next man
up exceeds the cost of slightly overpricing him.

Runs after the cold-start fill so bumps land on top of role priors instead
of vanishing into NaNs.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..graph.build import build_graph
from ..graph.cascade import project_vacated_usage, vacated_usage

log = logging.getLogger(__name__)

# DK draftable statuses that mean the player will not play. Doubtful ("D")
# is deliberately not here: most doubtful players sit, but zeroing them
# would erase real late-swap decisions; their depressed practice features
# already carry the signal.
OUT_STATUSES = {"O", "OUT", "IR"}

# The carry-side cascade reuses the target-centric machinery by renaming:
# total carries ~ total targets, goal-line carries ~ red zone targets,
# carry share ~ target share.
_RUSH_AS_TARGETS = {
    "total_carries": "total_targets",
    "gl3_carries": "rz20_targets",
    "carry_share": "target_share",
}

_PROJ_ZERO_COLS = ["proj_points", "proj_p10", "proj_p50", "proj_p90",
                   "proj_std", "p_20_plus", "value"]


def find_out_players(feats: pd.DataFrame) -> list[str]:
    """GSIS ids of slate players who won't play: DK status O/IR or an
    injury-report Out designation."""
    status = feats.get("status", pd.Series(index=feats.index, dtype=object))
    dk_out = status.fillna("").astype(str).str.upper().isin(OUT_STATUSES)
    report = feats.get("injury_status", pd.Series(index=feats.index, dtype=object))
    report_out = report.fillna("").astype(str).str.upper().eq("OUT")
    ids = feats.loc[(dk_out | report_out) & feats.gsis_id.notna(), "gsis_id"]
    return sorted(set(ids))


def slate_graph(feats: pd.DataFrame):
    """Minimal player/team graph over the slate: enough for team_of /
    teammates (same team + position group) traversal in the cascade."""
    rosters = pd.DataFrame(
        {
            "gsis_id": feats.get("gsis_id"),
            "name": feats.get("display_name", feats.get("gsis_id")),
            "position": feats.get("position", feats.get("dk_position")),
            "team": feats.get("team", feats.get("team_abbr")),
        }
    ).dropna(subset=["gsis_id", "team"]).drop_duplicates("gsis_id")
    qb_connections = pd.DataFrame(
        columns=["qb", "wr", "team", "targets", "rz_targets", "air_yards", "tds"]
    )
    return build_graph(rosters, qb_connections)


def _bump(feats: pd.DataFrame, rows, col: str, delta: float,
          lo: float = 0.0, hi: float | None = None) -> None:
    if col not in feats.columns:
        return
    base = pd.to_numeric(feats.loc[rows, col], errors="coerce").fillna(0.0) + delta
    feats.loc[rows, col] = base.clip(lower=lo, upper=hi)


def _redistribute(
    feats: pd.DataFrame,
    G,
    usage: pd.DataFrame,
    injuries: pd.DataFrame,
    out_id: str,
    skip: set[str],
    share_col: str,
    wopr_col: str | None,
    smoothed_col: str,
    share_cap: float,
) -> None:
    if usage.empty or out_id not in set(usage.gsis_id):
        return
    plan = project_vacated_usage(G, usage, injuries, out_id)
    if plan.empty:
        return
    vac = vacated_usage(usage, out_id)
    # vacated_usage's `mean() or 0` doesn't catch NaN — guard here so a
    # historyless share can't smear NaN over teammates' features.
    if not np.isfinite(vac.avg_target_share) or vac.avg_target_share <= 0:
        return
    rz_pool = vac.avg_rz20_targets if np.isfinite(vac.avg_rz20_targets) else 0.0
    for row in plan.itertuples():
        if row.gsis_id in skip or pd.isna(row.delta):
            continue
        rows = feats.index[feats.gsis_id == row.gsis_id]
        if rows.empty:
            continue
        frac = row.delta / vac.avg_target_share  # share of the vacated role
        _bump(feats, rows, share_col, row.delta, hi=share_cap)
        if wopr_col:
            _bump(feats, rows, wopr_col, 1.5 * row.delta, hi=1.2)
        _bump(feats, rows, smoothed_col, frac * rz_pool)
        log.info("cascade: %s inherits %+.3f %s from %s (%s)",
                 row.gsis_id, row.delta, share_col, out_id, row.method)


def adjust_for_inactives(
    feats: pd.DataFrame,
    usage_rec: pd.DataFrame,
    usage_rush: pd.DataFrame,
    injuries: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Redistribute out players' opportunity to slate teammates.

    usage_rec:  per-game [gsis_id, season, week, total_targets, rz20_targets,
                target_share] (features.rz_receiving grain)
    usage_rush: per-game [gsis_id, season, week, total_carries, gl3_carries,
                carry_share] (features.rz_rushing grain)
    injuries:   [gsis_id, season, week, game_status]

    Returns the adjusted copy and the out players' gsis ids (their
    projections should be zeroed — see zero_out_projections).
    """
    out_ids = find_out_players(feats)
    if not out_ids:
        return feats, []
    feats = feats.copy()
    G = slate_graph(feats)
    skip = set(out_ids)
    rush = usage_rush.rename(columns=_RUSH_AS_TARGETS)
    for out_id in out_ids:
        _redistribute(feats, G, usage_rec, injuries, out_id, skip,
                      share_col="target_share_l4", wopr_col="wopr_l4",
                      smoothed_col="rz20_targets_smoothed", share_cap=0.5)
        _redistribute(feats, G, rush, injuries, out_id, skip,
                      share_col="carry_share_l4", wopr_col=None,
                      smoothed_col="gl3_carries_smoothed", share_cap=0.85)
    log.info("cascade: adjusted slate for %d inactive(s): %s",
             len(out_ids), ", ".join(out_ids))
    return feats, out_ids


def zero_out_projections(out: pd.DataFrame, out_ids: list[str]) -> pd.DataFrame:
    """A player who won't play projects to zero — after the market blend,
    which knows nothing about a Sunday-morning scratch."""
    if not out_ids:
        return out
    out = out.copy()
    mask = out.gsis_id.isin(out_ids)
    for col in _PROJ_ZERO_COLS:
        if col in out.columns:
            out.loc[mask, col] = 0.0
    return out
