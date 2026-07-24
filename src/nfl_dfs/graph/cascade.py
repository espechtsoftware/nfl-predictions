"""Injury cascade projection (guide §8.4) — the query that actually pays.

When a starter is ruled out Sunday morning you have minutes to decide who
absorbs his usage. The core move: join injury history to usage history and
measure each teammate's target share WITH vs WITHOUT the injured player.
No public site does this join for you. Works best with 3+ prior absences;
below that, fall back to depth-chart-based redistribution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import networkx as nx
import pandas as pd

from .build import team_of, teammates

log = logging.getLogger(__name__)

MIN_ABSENCES_FOR_HISTORY = 3
# Depth-chart fallback multiplier for candidates sharing the injured
# player's scoring archetype (see analysis/archetypes.py). Mild on purpose:
# a prior, not evidence.
ARCHETYPE_MATCH_BOOST = 1.25


@dataclass
class VacatedUsage:
    gsis_id: str
    avg_targets: float
    avg_rz20_targets: float
    avg_target_share: float


def vacated_usage(usage: pd.DataFrame, out_player: str) -> VacatedUsage:
    """usage: per-game rows [gsis_id, season, week, total_targets,
    rz20_targets, target_share]."""
    mine = usage[usage.gsis_id == out_player]
    return VacatedUsage(
        gsis_id=out_player,
        avg_targets=float(mine.total_targets.mean() or 0),
        avg_rz20_targets=float(mine.rz20_targets.mean() or 0),
        avg_target_share=float(mine.target_share.mean() or 0),
    )


def historical_redistribution(
    usage: pd.DataFrame,
    absences: pd.DataFrame,
    candidates: list[str],
) -> pd.DataFrame:
    """For each candidate: mean target share in weeks the injured player
    missed vs weeks he played. `absences`: [season, week] rows when the
    player was Out. Returns columns share_with, share_without, delta,
    n_without."""
    absent_keys = set(map(tuple, absences[["season", "week"]].to_numpy().tolist()))
    cand = usage[usage.gsis_id.isin(candidates)].copy()
    if cand.empty:
        return pd.DataFrame(
            columns=["gsis_id", "share_with", "share_without", "delta", "n_without"]
        )
    cand["absent"] = [
        (s, w) in absent_keys for s, w in zip(cand.season, cand.week)
    ]
    rows = []
    for gsis_id, grp in cand.groupby("gsis_id"):
        with_ = grp.loc[~grp.absent, "target_share"]
        without = grp.loc[grp.absent, "target_share"]
        rows.append(
            {
                "gsis_id": gsis_id,
                "share_with": float(with_.mean()) if len(with_) else float("nan"),
                "share_without": float(without.mean()) if len(without) else float("nan"),
                "n_without": int(len(without)),
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out.share_without - out.share_with
    return out.sort_values("delta", ascending=False)


def depth_chart_fallback(
    vacated: VacatedUsage, candidates: pd.DataFrame
) -> pd.DataFrame:
    """When absence history is thin: hand the vacated share down the depth
    chart, weighted by current usage (a proxy for readiness). candidates:
    [gsis_id, target_share] current levels."""
    c = candidates.copy()
    total = c.target_share.sum()
    c["weight"] = c.target_share / total if total > 0 else 1.0 / len(c)
    c["delta"] = c.weight * vacated.avg_target_share
    return c.sort_values("delta", ascending=False)[["gsis_id", "delta"]]


def project_vacated_usage(
    G: nx.MultiDiGraph,
    usage: pd.DataFrame,
    injuries: pd.DataFrame,
    out_player: str,
) -> pd.DataFrame:
    """Who inherits an injured player's opportunity, and how much?

    usage:    [gsis_id, season, week, total_targets, rz20_targets, target_share]
    injuries: [gsis_id, season, week, game_status]
    Returns candidates with projected target-share delta, best-evidence first.
    """
    team = team_of(G, out_player)
    candidates = teammates(G, out_player)
    if not candidates:
        log.warning("No competition edges for %s (team %s)", out_player, team)
        return pd.DataFrame(columns=["gsis_id", "delta", "method"])

    vac = vacated_usage(usage, out_player)
    absences = injuries[
        (injuries.gsis_id == out_player) & (injuries.game_status == "Out")
    ][["season", "week"]]

    if len(absences) >= MIN_ABSENCES_FOR_HISTORY:
        hist = historical_redistribution(usage, absences, candidates)
        informative = hist[hist.n_without >= MIN_ABSENCES_FOR_HISTORY].dropna(
            subset=["delta"]
        )
        if not informative.empty:
            return informative.assign(method="history")[
                ["gsis_id", "delta", "share_with", "share_without", "n_without", "method"]
            ]

    current = (
        usage[usage.gsis_id.isin(candidates)]
        .groupby("gsis_id", as_index=False)["target_share"].mean()
    )
    if current.empty:
        return pd.DataFrame(columns=["gsis_id", "delta", "method"])

    # Archetype-aware fallback: when nodes carry scoring-profile labels
    # (analysis.archetypes.annotate_graph), tilt the depth-chart weights
    # toward profile-compatible inheritors — a possession receiver's vacated
    # slot targets flow to another high-floor profile, not a deep threat.
    # The history path above stays unweighted on purpose: measured
    # redistribution beats any prior.
    out_arch = G.nodes[out_player].get("archetype") if out_player in G else None
    method = "depth_chart"
    if out_arch is not None:
        boost = current.gsis_id.map(
            lambda g: ARCHETYPE_MATCH_BOOST
            if g in G and G.nodes[g].get("archetype") == out_arch
            else 1.0
        )
        current = current.assign(target_share=current.target_share * boost)
        method = "depth_chart_archetype"
    return depth_chart_fallback(vac, current).assign(method=method)
