"""Prop lines -> market DK-point projections (the real market for blend.py).

Per (season, week, player): de-vig each over/under pair, convert lines to
means (prop_line_to_mean), price TDs from anytime-TD odds
(lambda = -ln(1 - p)), sum DK scoring. Books averaged after de-vig.
Names matched to gsis_ids via normalized full display name.
"""

from __future__ import annotations

import logging
from datetime import time

import numpy as np
import pandas as pd

from ..bq import query_df
from ..config import settings
from .blend import american_to_prob, devig_two_way, prop_line_to_mean

log = logging.getLogger(__name__)

YARD_PTS = {"player_pass_yds": 0.04, "player_rush_yds": 0.1,
            "player_reception_yds": 0.1}
STANDARD_MARKETS = (
    "player_pass_yds",
    "player_pass_tds",
    "player_rush_yds",
    "player_reception_yds",
    "player_receptions",
    "player_anytime_td",
)


def _norm(s: pd.Series) -> pd.Series:
    from ..names import norm_name

    return s.astype(str).map(norm_name)


def latest_pre_main_lock(
    props: pd.DataFrame,
    schedules: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return the latest standard-prop rows known at Sunday-main lock.

    Historical odds snapshots are event-relative.  A late-afternoon game's
    kickoff-minus-two-hours close occurs after the common 1 p.m. DFS lock, so
    every event in the portfolio must share the schedule-derived first main
    game cutoff.  London and Sunday-night games do not define that cutoff.
    """

    p_needed = {
        "season", "week", "bookmaker", "market", "outcome_name", "player",
        "price", "point", "snapshot_ts",
    }
    s_needed = {
        "season", "week", "gameday", "gametime", "game_type", "weekday",
    }
    if missing := p_needed - set(props.columns):
        raise ValueError(f"prop lines missing {sorted(missing)}")
    if missing := s_needed - set(schedules.columns):
        raise ValueError(f"schedules missing {sorted(missing)}")

    lines = props.copy()
    lines["_snapshot"] = pd.to_datetime(
        lines.snapshot_ts, utc=True, errors="coerce",
    )
    slate = schedules[
        schedules.game_type.eq("REG")
        & schedules.weekday.eq("Sunday")
    ].copy()
    parsed_time = pd.to_datetime(
        slate.gametime.astype(str), format="%H:%M", errors="coerce",
    ).dt.time
    slate = slate[
        parsed_time.map(
            lambda value: (
                value is not pd.NaT
                and pd.notna(value)
                and time(13, 0) <= value < time(19, 0)
            )
        )
    ].copy()
    if slate.empty:
        return lines.iloc[0:0].drop(columns="_snapshot"), {
            "input_rows": int(len(lines)),
            "main_slate_weeks": 0,
            "prelock_rows": 0,
            "postlock_rows_excluded": 0,
        }
    local = pd.to_datetime(
        slate.gameday.astype(str) + " " + slate.gametime.astype(str),
        errors="coerce",
    ).dt.tz_localize(
        "America/New_York", ambiguous="NaT", nonexistent="shift_forward",
    ).dt.tz_convert("UTC")
    slate["_common_lock"] = local
    locks = slate.dropna(subset="_common_lock").groupby(
        ["season", "week"], observed=True,
    )._common_lock.min().rename("_common_lock").reset_index()
    joined = lines.merge(
        locks, on=["season", "week"], how="inner", validate="many_to_one",
    )
    prelock = joined[
        joined._snapshot.notna() & joined._snapshot.lt(joined._common_lock)
    ].copy()
    key = [
        "season", "week", "bookmaker", "market", "player", "point",
        "outcome_name",
    ]
    prelock = prelock.sort_values("_snapshot", kind="stable").drop_duplicates(
        key, keep="last",
    )
    audit = {
        "input_rows": int(len(lines)),
        "main_slate_weeks": int(len(locks)),
        "prelock_rows": int(len(prelock)),
        "postlock_rows_excluded": int(
            (joined._snapshot.notna()
             & joined._snapshot.ge(joined._common_lock)).sum()
        ),
    }
    return prelock.drop(columns=["_snapshot", "_common_lock"]), audit


def market_points(seasons: tuple[int, ...] = (2023, 2024, 2025)) -> pd.DataFrame:
    """(season, week, gsis_id, market_points) from nfl_raw.prop_lines."""
    season_list = ", ".join(str(int(s)) for s in seasons)
    market_list = ", ".join(f"'{market}'" for market in STANDARD_MARKETS)
    props = query_df(
        f"""SELECT season, week, bookmaker, market, outcome_name, player,
                   price, point, snapshot_ts
            FROM `{settings.raw}.prop_lines`
            WHERE season IN ({season_list})
              AND market IN ({market_list})"""
    )
    if props.empty:
        return pd.DataFrame(columns=["season", "week", "gsis_id",
                                     "market_points"])
    schedules = query_df(
        f"""SELECT season, week, gameday, gametime, game_type, weekday
            FROM `{settings.raw}.schedules`
            WHERE season IN ({season_list})"""
    )
    props, cutoff_audit = latest_pre_main_lock(props, schedules)
    log.info(
        "prop market common-lock audit: input=%d weeks=%d prelock=%d "
        "postlock_excluded=%d",
        cutoff_audit["input_rows"], cutoff_audit["main_slate_weeks"],
        cutoff_audit["prelock_rows"], cutoff_audit["postlock_rows_excluded"],
    )
    if props.empty:
        return pd.DataFrame(columns=["season", "week", "gsis_id",
                                     "market_points"])
    # ``weekly_stats`` has no current-season rows before Week 1 has been
    # played. Using it as the sole name authority therefore made a healthy
    # live prop feed resolve zero players during the exact period when the
    # pre-lock projection needs it most. Player identity is not an outcome:
    # combine historical stat spellings with current roster aliases and the
    # already-governed DK-to-GSIS map. The latter two sources also preserve
    # football-name/diminutive spellings such as Cameron/Cam Ward.
    names = query_df(
        f"""SELECT DISTINCT gsis_id, display_name
            FROM (
              SELECT player_id AS gsis_id,
                     player_display_name AS display_name
              FROM `{settings.raw}.weekly_stats`
              WHERE season IN ({season_list})
              UNION DISTINCT
              SELECT gsis_id, full_name AS display_name
              FROM `{settings.raw}.rosters_weekly`
              WHERE season IN ({season_list})
              UNION DISTINCT
              SELECT gsis_id, football_name AS display_name
              FROM `{settings.raw}.rosters_weekly`
              WHERE season IN ({season_list})
              UNION DISTINCT
              SELECT gsis_id, display_name
              FROM `{settings.features}.player_id_map`
            )
            WHERE gsis_id IS NOT NULL
              AND display_name IS NOT NULL
              AND TRIM(display_name) != ''"""
    )
    names["norm"] = _norm(names.display_name)
    # A normalized spelling shared by different GSIS ids is not safe to use.
    # Retain multiple aliases for one player, but never choose arbitrarily
    # between genuinely ambiguous identities.
    norm_cardinality = names.groupby("norm", observed=True).gsis_id.nunique()
    names = names[
        names.norm.map(norm_cardinality).eq(1)
    ].drop_duplicates(["norm", "gsis_id"])
    props["norm"] = _norm(props.player)

    rows = []
    ou = props[props.outcome_name.isin(["Over", "Under"])]
    keys = ["season", "week", "norm", "market", "bookmaker", "point"]
    piv = (ou.pivot_table(index=keys, columns="outcome_name",
                          values="price", aggfunc="first").reset_index())
    # Older seasons can contain only one-way anytime-TD prices (or no prop
    # snapshots at all).  ``pivot_table`` then has no Over/Under columns;
    # keep the two-way component empty while still allowing the TD component
    # below to contribute instead of raising KeyError and relying on the
    # replay's broad fallback.
    if not {"Over", "Under"}.issubset(piv.columns):
        piv = pd.DataFrame(columns=[*keys, "Over", "Under"])
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
    # A pre-prop season, or a week with no rows before the shared lock, is a
    # normal model-only fallback. Constructing a column-less frame here would
    # make the group-bys below raise and trigger replay's broad exception path.
    if not rows:
        return pd.DataFrame(columns=["season", "week", "gsis_id",
                                     "market_points"])
    df = pd.DataFrame(rows)
    # Average books within a market. Resolve aliases before summing markets:
    # two prop spellings can map to one GSIS id (for example Gabe/Gabriel),
    # and returning both rows made callers choose one by arbitrary input
    # order. Alias duplicates of the same market are averaged; distinct
    # markets are then summed once for the documented unique player-week row.
    per_mkt = (df.groupby(["season", "week", "norm", "market"]).pts
               .mean().reset_index())
    # two-stage match (names.py): exact norm, then unambiguous
    # initial-key fallback — catches 'Cameron Ward' vs 'Cam Ward'.
    from ..names import match_map, resolve

    lookup = match_map(dict(zip(names.display_name, names.gsis_id)))
    per_mkt["gsis_id"] = per_mkt.norm.map(
        lambda n: resolve(n, lookup))
    matched = per_mkt[per_mkt.gsis_id.notna()].copy()
    by_market = matched.groupby(
        ["season", "week", "gsis_id", "market"], observed=True,
    ).pts.mean().reset_index()
    out = by_market.groupby(
        ["season", "week", "gsis_id"], observed=True,
    ).pts.sum().rename("market_points").reset_index()
    log.info("prop market: %d player-weeks priced (%.0f%% of prop names "
             "matched)", len(out),
             100 * matched.norm.nunique() / max(per_mkt.norm.nunique(), 1))
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
