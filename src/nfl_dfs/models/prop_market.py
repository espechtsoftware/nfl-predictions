"""Prop lines -> market DK-point projections (the real market for blend.py).

Per (season, week, player): de-vig each over/under pair, convert lines to
means (prop_line_to_mean), price TDs from anytime-TD odds
(lambda = -ln(1 - p)), sum DK scoring. Books averaged after de-vig.
Names matched to gsis_ids via normalized full display name.
"""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from ..bq import query_df
from ..config import settings
from .blend import american_to_prob, devig_two_way, prop_line_to_mean

log = logging.getLogger(__name__)

YARD_PTS = {"player_pass_yds": 0.04, "player_rush_yds": 0.1,
            "player_reception_yds": 0.1}


def _norm(s: pd.Series) -> pd.Series:
    return (s.astype(str).str.lower()
            .str.replace(r"[^a-z ]", "", regex=True).str.strip())


def market_points(seasons: tuple[int, ...] = (2023, 2024, 2025)) -> pd.DataFrame:
    """(season, week, gsis_id, market_points) from nfl_raw.prop_lines."""
    season_list = ", ".join(str(int(s)) for s in seasons)
    props = query_df(
        f"""SELECT season, week, bookmaker, market, outcome_name, player,
                   price, point FROM `{settings.raw}.prop_lines`
            WHERE season IN ({season_list})
              AND NOT ENDS_WITH(snapshot_ts, 'T18:00:00Z')"""
    )  # closes only: Tuesday opens (T18:00:00Z) are for movement studies
    names = query_df(
        f"""SELECT DISTINCT player_id AS gsis_id,
                   player_display_name AS display_name
            FROM `{settings.raw}.weekly_stats` WHERE season IN ({season_list})"""
    )
    names["norm"] = _norm(names.display_name)
    names = names.drop_duplicates("norm")
    props["norm"] = _norm(props.player)

    rows = []
    ou = props[props.outcome_name.isin(["Over", "Under"])]
    keys = ["season", "week", "norm", "market", "bookmaker", "point"]
    piv = (ou.pivot_table(index=keys, columns="outcome_name",
                          values="price", aggfunc="first").reset_index())
    piv = piv.dropna(subset=["Over", "Under", "point"])
    for r in piv.itertuples():
        p_over, _ = devig_two_way(american_to_prob(r.Over),
                                  american_to_prob(r.Under))
        dist = "poisson" if r.market in ("player_receptions",
                                         "player_pass_tds") else "normal"
        try:
            mean = prop_line_to_mean(float(r.point), p_over, dist)
        except Exception:
            continue
        pts = (YARD_PTS.get(r.market, 0.0) * mean
               + (1.0 if r.market == "player_receptions" else 0.0) * mean
               + (4.0 if r.market == "player_pass_tds" else 0.0) * mean)
        rows.append({"season": r.season, "week": r.week, "norm": r.norm,
                     "market": r.market, "bookmaker": r.bookmaker,
                     "pts": pts})
    td = props[props.market == "player_anytime_td"].copy()
    # One-way market: de-vig by the book's typical anytime-TD hold (~15%).
    td["p"] = (td.price.map(american_to_prob) / 1.15).clip(0.01, 0.95)
    td["pts"] = 6.0 * (-np.log1p(-td.p))
    rows.extend(td[["season", "week", "norm", "market", "bookmaker",
                    "pts"]].to_dict("records"))
    df = pd.DataFrame(rows)
    # Average books within a market, then sum markets per player-week
    per_mkt = (df.groupby(["season", "week", "norm", "market"]).pts
               .mean().reset_index())
    total = (per_mkt.groupby(["season", "week", "norm"]).pts.sum()
             .reset_index().rename(columns={"pts": "market_points"}))
    out = total.merge(names[["norm", "gsis_id"]], on="norm", how="inner")
    log.info("prop market: %d player-weeks priced (%.0f%% of prop names "
             "matched)", len(out), 100 * len(out) / max(len(total), 1))
    return out[["season", "week", "gsis_id", "market_points"]]


def market_ceilings(seasons: tuple[int, ...] = (2025,)) -> pd.DataFrame:
    """(season, week, gsis_id, ceil_spread): DK-pts of market-implied
    ceiling room from alt-line ladders (yards at P(over)=0.10 minus
    median, x0.1). Top-quartile spread booms 21.4% vs 13% (study
    2026-07-30)."""
    season_list = ", ".join(str(int(s)) for s in seasons)
    alt = query_df(
        f"""SELECT season, week, player, market, point, price
            FROM `{settings.raw}.prop_lines`
            WHERE market IN ('player_reception_yds_alternate',
                             'player_rush_yds_alternate')
              AND bookmaker='draftkings' AND outcome_name='Over'
              AND point IS NOT NULL AND season IN ({season_list})""")
    alt["p"] = np.where(alt.price > 0, 100 / (alt.price + 100),
                        -alt.price / (-alt.price + 100))
    alt["norm"] = _norm(alt.player)
    rows = []
    for (s, w, n, m), g in alt.groupby(["season", "week", "norm", "market"]):
        g = g.sort_values("point")
        if len(g) < 3:
            continue
        x, y = g.p.to_numpy(), g.point.to_numpy()
        if x.min() > 0.10:
            p90 = y[-1] + (y[-1] - y[-2]) * (x[-1] - 0.10) / max(
                x[-2] - x[-1], 1e-3)
        else:
            p90 = float(np.interp(0.10, x[::-1], y[::-1]))
        med = (float(np.interp(0.50, x[::-1], y[::-1]))
               if x.max() >= 0.5 else y[0])
        rows.append({"season": s, "week": w, "norm": n,
                     "spread": (p90 - med) * 0.1})
    if not rows:
        return pd.DataFrame(columns=["season", "week", "gsis_id",
                                     "ceil_spread"])
    lad = (pd.DataFrame(rows).groupby(["season", "week", "norm"])
           .spread.sum().reset_index())
    names = query_df(
        f"""SELECT DISTINCT player_id AS gsis_id,
                   player_display_name AS display_name
            FROM `{settings.raw}.weekly_stats`
            WHERE season IN ({season_list})""")
    names["norm"] = _norm(names.display_name)
    out = lad.merge(names.drop_duplicates("norm")[["norm", "gsis_id"]],
                    on="norm", how="inner")
    return out.rename(columns={"spread": "ceil_spread"})[
        ["season", "week", "gsis_id", "ceil_spread"]]
