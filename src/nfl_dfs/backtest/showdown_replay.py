"""Showdown Captain Mode season replay: how would our entries have done?

For each Captain Mode slate (default: Thursday/Monday standalone games),
builds the player pool from real FLEX salaries (showdown_salaries_historical,
DiscoveryLab import), projects it, optimizes N entries with the showdown
MILP, and scores them with actual DK points (captain 1.5x).

Projections: model projections for skill positions, matched by normalized
name + position (same rules as 019's salary crosswalk: unique name+position,
else unique name, else unmatched). K/DST/unmatched fall back to the
player's trailing-average actual points (strictly prior weeks) — the same
naive baseline the classic replay uses for DST.

Headline metric: capture = best entry / hindsight-optimal lineup for that
slate, because absolute showdown scores swing with the game environment.
No field/payout simulation — we have no showdown ownership model; this
measures lineup quality, not contest ROI.
"""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from ..optimizer.showdown import CPT_MULT, optimize_many_showdown, optimize_showdown
from . import replay

log = logging.getLogger(__name__)

DEFAULT_DAYS = ("thursday", "monday")
MIN_PRIOR_GAMES_FOR_NAIVE = 2


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z ]", "", str(name).upper()).strip()


def projection_lookup(proj: pd.DataFrame) -> dict:
    """(week, norm_name, position) -> projection, with (week, norm_name)
    fallback when the name is unique that week."""
    by_np: dict = {}
    by_name: dict = {}
    for r in proj.itertuples():
        if pd.isna(r.name):
            continue
        n = _norm(r.name)
        key = (int(r.week), n, str(r.position))
        by_np[key] = None if key in by_np else float(r.proj_points)
        nkey = (int(r.week), n)
        by_name[nkey] = None if nkey in by_name else float(r.proj_points)
    return {"np": by_np, "name": by_name}


def naive_trailing(slate_df: pd.DataFrame) -> pd.Series:
    """Trailing mean of each slate player's own actual points, strictly
    prior weeks, aligned to slate_df rows."""
    df = slate_df.sort_values(["sdio_player_id", "week"])
    trail = (
        df.groupby("sdio_player_id")["dk_points_actual"]
        .transform(lambda s: s.shift(1).expanding(
            min_periods=MIN_PRIOR_GAMES_FOR_NAIVE).mean())
    )
    return trail.reindex(slate_df.index)


def build_pools(slates: pd.DataFrame, proj: pd.DataFrame) -> pd.DataFrame:
    """Attach a projection to every slate player row; rows with no
    projection of any kind are dropped (logged)."""
    lookup = projection_lookup(proj)
    trail = naive_trailing(slates)
    values, sources = [], []
    for i, r in enumerate(slates.itertuples()):
        n = _norm(r.display_name)
        v = None
        if r.position in ("QB", "RB", "WR", "TE"):
            v = lookup["np"].get((int(r.week), n, r.position))
            if v is None:
                v = lookup["name"].get((int(r.week), n))
        if v is not None:
            values.append(v); sources.append("model")
        elif pd.notna(trail.iloc[i]):
            values.append(float(trail.iloc[i])); sources.append("trailing")
        else:
            values.append(np.nan); sources.append("none")
    out = slates.assign(proj=values, proj_source=sources)
    dropped = int(out.proj.isna().sum())
    if dropped:
        log.info("build_pools: dropped %d slate rows with no projection", dropped)
    return out.dropna(subset=["proj"])


def replay_showdown_season(
    slates: pd.DataFrame,
    proj: pd.DataFrame,
    n_entries: int = 20,
    days: tuple[str, ...] = DEFAULT_DAYS,
) -> pd.DataFrame:
    """One row per replayed slate: best/median entry actual score,
    hindsight-optimal score, capture ratio."""
    pools = build_pools(slates, proj)
    if days:
        # operator_day is a date in historical slate payloads and a weekday
        # name in live ones — accept either.
        wanted = {d.lower()[:3] for d in days}
        dt = pd.to_datetime(pools.operator_day, errors="coerce")
        day_names = dt.dt.day_name().fillna(pools.operator_day.astype(str))
        pools = pools[day_names.str.lower().str[:3].isin(wanted)]
    results = []
    for (week, slate_id), grp in pools.groupby(["week", "operator_slate_id"]):
        pool = [
            {"id": int(r.sdio_player_id), "name": r.display_name,
             "pos": r.position, "team": r.team_abbr, "opp": None,
             "game_id": slate_id, "salary": int(r.salary),
             "proj": float(r.proj),
             "actual": float(r.dk_points_actual) if pd.notna(r.dk_points_actual) else 0.0}
            for r in grp.itertuples()
        ]
        if len(pool) < 8 or len({p["team"] for p in pool}) < 2:
            continue
        entries = optimize_many_showdown(pool, n_lineups=n_entries)
        if not entries:
            continue

        def actual_score(lu) -> float:
            return float(CPT_MULT * lu.captain["actual"]
                         + sum(p["actual"] for p in lu.flex))

        scores = [actual_score(lu) for lu in entries]
        optimal = optimize_showdown(pool, objective_col="actual")
        opt_score = actual_score(optimal) if optimal else np.nan
        results.append({
            "week": int(week), "slate_id": slate_id,
            "game": grp.game_teams.iloc[0], "day": grp.operator_day.iloc[0],
            "pool": len(pool),
            "best": max(scores), "median_entry": float(np.median(scores)),
            "optimal": opt_score,
            "capture": max(scores) / opt_score if opt_score else np.nan,
        })
    return pd.DataFrame(results)


def run(season: int = 2025, n_entries: int = 20, days: str = "thu,mon") -> None:
    from ..bq import query_df
    from ..config import settings

    slates = query_df(
        f"""SELECT * FROM `{settings.raw}.showdown_salaries_historical`
            WHERE season = {season}"""
    )
    if slates.empty:
        raise RuntimeError("no showdown slates; run import-discoverylab-showdown")
    panel, _ = replay.load_panel_and_dst(season)
    proj = replay.replay_projections(panel, season, n_sims=8000, seed=0)
    day_tuple = tuple(d.strip() for d in days.split(",") if d.strip())
    res = replay_showdown_season(slates, proj, n_entries=n_entries, days=day_tuple)
    if res.empty:
        raise RuntimeError("no slates matched the day filter")

    print(f"\n=== Showdown Captain Mode replay: {season} "
          f"({len(res)} slates, {n_entries} entries each, days={days}) ===")
    print(res.round(1).to_string(index=False))
    print(f"\nmean best entry: {res.best.mean():.1f}"
          f"  mean optimal: {res.optimal.mean():.1f}"
          f"  mean capture: {res.capture.mean():.1%}"
          f"  median capture: {res.capture.median():.1%}")
    print(f"slates with capture >= 90%: {(res.capture >= 0.9).sum()}/{len(res)}")
