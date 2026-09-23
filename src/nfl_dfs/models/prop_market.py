"""Prop lines -> market DK-point projections (the real market for blend.py).

Per (season, week, player): de-vig each over/under pair, convert lines to
means (prop_line_to_mean), price TDs from anytime-TD odds
(lambda = -ln(1 - p)), sum DK scoring. Books averaged after de-vig.
Names matched to gsis_ids via normalized full display name.
"""

from __future__ import annotations

import logging
import os
from datetime import time

import numpy as np
import pandas as pd

from ..config import settings
from .blend import american_to_prob, devig_two_way, prop_line_to_mean
from scipy import stats


def query_df(sql: str, params: dict | None = None):
    """Read through the ``bq`` module attribute, never a value bound at import.

    Binding ``query_df`` at import time made every call site here invisible to
    ``monkeypatch.setattr(nfl_dfs.bq, "query_df", ...)``, so the offline live
    smokes reached the real warehouse: they passed on a workstation with
    credentials and failed inside Cloud Build with "ProjectId must be
    non-empty" (build of 2026-09-21).  One call site had already been fixed
    this way; this makes the whole module consistent.
    """
    from .. import bq as _bq

    return _bq.query_df(sql, params) if params is not None else _bq.query_df(sql)


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


# Bonus-aware conversion (2026-09-23, external review §3.2 item 2; DEFAULT OFF via MARKET_BONUS_AWARE=1).
# DraftKings pays +3 at 100 rush / 100 receiving / 300 passing yards and -1 per interception; the plain
# conversion prices only the mean yards. With the flag on, each yardage line adds 3 * P(Y >= threshold) under
# the SAME normal the line already implies (mean from prop_line_to_mean, sigma = 0.30 * max(line, 1)), and an
# interceptions market (if the feed carries one) contributes -1 * E[INT] (Poisson). Served WR bias grew with the
# line (+0.8/+0.6 at 6-10 up to +3.0/+1.6 at 18+, 2023/2024) -- the missing bonus. Flag off = byte-identical.
BONUS_AT = {"player_rush_yds": 100.0, "player_reception_yds": 100.0}
# The 300-yard PASSING bonus is deliberately NOT applied (walk-forward 2023-25, laptop 2026-09-23): the plain QB
# conversion is already unbiased (18+ band -0.02) because the missing +3 bonus and the missing -1/INT cancel, and the
# feed has no interceptions market -- adding the bonus alone pushed QB 18+ to -0.67. Apply it only with an INT market.
PASS_BONUS_AT = {"player_pass_yds": 300.0}
INT_MARKET = "player_pass_interceptions"


def bonus_aware() -> bool:
    v = os.environ.get("MARKET_BONUS_AWARE", "0")
    if v not in ("0", "1"):
        raise ValueError(f"MARKET_BONUS_AWARE must be 0 or 1, got {v!r}")
    return v == "1"


def yardage_bonus_points(market: str, line: float, mean: float) -> float:
    """3 * P(Y >= threshold) for a yardage market under the line's implied normal; 0 for other markets."""
    thr = BONUS_AT.get(market)
    if thr is None:
        return 0.0
    sigma = 0.30 * max(float(line), 1.0)
    return float(3.0 * stats.norm.sf(thr, loc=mean, scale=sigma))


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


def market_points(
    seasons: tuple[int, ...] = (2023, 2024, 2025),
    *,
    minimum_markets: int = 1,
    prefer_ids: set[str] | frozenset[str] | None = None,
) -> pd.DataFrame:
    """Return market-point sums from ``nfl_raw.prop_lines``.

    ``prefer_ids`` (2026-09-21, Week-2 post-mortem): the GSIS ids of the
    slate being projected.  A normalized spelling shared by several GSIS ids
    is still never chosen arbitrarily, but when exactly ONE of the colliding
    ids is on the slate that id is the spelling's identity.  Week 2 2026:
    "justin jefferson" collided with a roster-only rookie of the same name,
    the WR lost his prop lines, and the blend substituted his one-game DK PPG
    (31.2) as the market at 55% weight.  Replay callers pass nothing and keep
    the exact prior behaviour.

    ``minimum_markets`` is a completeness boundary, not a name-matching
    threshold.  Historical analyses retain the one-market default because
    some old snapshots contain only anytime-touchdown prices.  Live callers
    require at least two distinct scoring markets before treating the sum as
    a usable whole-player proxy; otherwise a TD component of roughly three
    points can be mistaken for a complete fantasy-point expectation.
    """
    if minimum_markets < 1:
        raise ValueError("minimum_markets must be at least 1")
    bonus = bonus_aware()
    season_list = ", ".join(str(int(s)) for s in seasons)
    markets = STANDARD_MARKETS + ((INT_MARKET,) if bonus else ())
    market_list = ", ".join(f"'{market}'" for market in markets)
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
    ambiguous = names[names.norm.map(norm_cardinality).gt(1)]
    names = names[
        names.norm.map(norm_cardinality).eq(1)
    ].drop_duplicates(["norm", "gsis_id"])
    props["norm"] = _norm(props.player)
    resolved_by_slate = 0
    if prefer_ids and len(ambiguous):
        prefer = {str(i) for i in prefer_ids}
        on_slate = ambiguous[ambiguous.gsis_id.astype(str).isin(prefer)]
        slate_cardinality = on_slate.groupby("norm", observed=True).gsis_id.nunique()
        keep = on_slate[on_slate.norm.map(slate_cardinality).eq(1)]
        keep = keep.drop_duplicates(["norm", "gsis_id"])
        resolved_by_slate = int(keep.norm.nunique())
        names = pd.concat([names, keep], ignore_index=True)
    still_ambiguous = sorted(
        set(ambiguous.norm) - set(names.norm)
    )
    in_feed = [n for n in still_ambiguous if n in set(props.norm)]
    log.info(
        "prop market names: %d ambiguous spellings, %d resolved by the slate, "
        "%d still ambiguous of which %d appear in the prop feed%s",
        int(ambiguous.norm.nunique()), resolved_by_slate,
        len(still_ambiguous), len(in_feed),
        (": " + ", ".join(in_feed[:12])) if in_feed else "",
    )

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
                                         "player_pass_tds", INT_MARKET) else "normal"
        try:
            mean = prop_line_to_mean(float(r.point), p_over, dist)
        except Exception:
            continue
        pts = (YARD_PTS.get(r.market, 0.0) * mean
               + (1.0 if r.market == "player_receptions" else 0.0) * mean
               + (4.0 if r.market == "player_pass_tds" else 0.0) * mean)
        if bonus:
            pts += yardage_bonus_points(r.market, float(r.point), mean)
            if r.market == INT_MARKET:
                pts = -1.0 * mean
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
    ).agg(market_points=("pts", "sum"),
          market_count=("market", "nunique")).reset_index()
    complete = out[out.market_count >= minimum_markets].copy()
    log.info("prop market: %d player-weeks priced, %d meet >=%d-market "
             "completeness (%.0f%% of prop names matched)", len(out),
             len(complete), minimum_markets,
             100 * matched.norm.nunique() / max(per_mkt.norm.nunique(), 1))
    return complete[["season", "week", "gsis_id", "market_points"]]


def prop_feed_player_names(season: int, week: int, minimum_markets: int = 2) -> set[str]:
    """Raw prop-feed player names for the week with at least ``minimum_markets``
    distinct scoring markets, matched or not.

    The live paths compare these against the slate: a slate player whose
    spelling is in the feed but received no market stops the run
    (``inference.market_source``).  Read through the ``bq`` module attribute
    so offline smokes that stub ``bq.query_df`` see an empty feed.

    ``minimum_markets`` must equal the live ``market_points`` completeness
    boundary (2).  2026-09-23: the name list counted a player with only an
    anytime-TD price as "in the feed", while ``market_points`` requires two
    markets, so every TD-only slate player (236 on Wednesday of Week 3, and
    hundreds of depth players on any Sunday) tripped the name-match guard and
    stopped ``project-slate``.  A real spelling mismatch (the Jefferson case: a
    fully priced player whose id did not resolve) is still caught.
    """
    if minimum_markets < 1:
        raise ValueError("minimum_markets must be at least 1")
    market_list = ", ".join(f"'{market}'" for market in STANDARD_MARKETS)
    df = query_df(
        f"""SELECT player
            FROM `{settings.raw}.prop_lines`
            WHERE season = {int(season)} AND week = {int(week)}
              AND market IN ({market_list})
            GROUP BY player
            HAVING COUNT(DISTINCT market) >= {int(minimum_markets)}"""
    )
    if df is None or df.empty or "player" not in df.columns:
        return set()
    return {str(p) for p in df.player.dropna() if str(p).strip()}


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
