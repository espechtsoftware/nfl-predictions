"""Historical + live player-prop lines from The Odds API -> nfl_raw.prop_lines.

Point-in-time discipline: each game's odds are snapshotted at
commence_time - 2h — strictly pre-lock knowledge, never post-game. Player
props are available historically from May 2023 (seasons 2023+). Cost: the
historical event-odds endpoint bills 10 credits per market per event
(6 markets => 60/event, ~49k credits for three seasons on the 100K plan).

Resumable: (season, week) pairs already present in the table are skipped,
so a crashed or quota-capped run continues where it left off.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from ..bq import load_dataframe, query_df
from ..config import settings

log = logging.getLogger(__name__)

BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
TABLE = "prop_lines"
MARKETS = ("player_pass_yds,player_pass_tds,player_rush_yds,"
           "player_reception_yds,player_receptions,player_anytime_td")
SNAPSHOT_BEFORE_H = 2   # hours before kickoff
PAUSE_S = 0.35          # stay far under the per-minute rate limit


def _get(path: str, **params) -> dict | list:
    params["apiKey"] = settings.odds_api_key
    r = requests.get(f"{BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_event_odds(payload: dict, season: int, week: int,
                     snapshot_ts: str) -> list[dict]:
    """Flatten one historical event-odds payload into prop_lines rows."""
    data = payload.get("data") or {}
    rows = []
    for bk in data.get("bookmakers") or []:
        for m in bk.get("markets") or []:
            for o in m.get("outcomes") or []:
                rows.append({
                    "season": season, "week": week,
                    "event_id": data.get("id"),
                    "commence_time": data.get("commence_time"),
                    "home_team": data.get("home_team"),
                    "away_team": data.get("away_team"),
                    "snapshot_ts": snapshot_ts,
                    "bookmaker": bk.get("key"),
                    "market": m.get("key"),
                    # Over/Under markets: name=Over|Under, description=player.
                    # anytime_td: name=player (no point).
                    "outcome_name": o.get("name"),
                    "player": o.get("description") or o.get("name"),
                    "price": o.get("price"),
                    "point": o.get("point"),
                    "pulled_at": datetime.now(timezone.utc),
                })
    return rows


def _weeks(first_season: int, last_season: int) -> pd.DataFrame:
    return query_df(
        f"""
        SELECT season, week,
               MIN(gameday) AS first_day, MAX(gameday) AS last_day
        FROM `{settings.raw}.schedules`
        WHERE game_type = 'REG' AND season BETWEEN {first_season} AND {last_season}
        GROUP BY season, week ORDER BY season, week
        """
    )


def _done() -> set[tuple[int, int]]:
    try:
        d = query_df(f"SELECT DISTINCT season, week FROM `{settings.raw}.{TABLE}`")
        return {(int(r.season), int(r.week)) for r in d.itertuples()}
    except Exception:
        return set()


ALT_MARKETS = ("player_pass_yds_alternate,player_rush_yds_alternate,"
               "player_reception_yds_alternate,player_receptions_alternate")


def run(first_season: int = 2023, last_season: int = 2025,
        opens: bool = False, markets: str = MARKETS,
        done_filter: str = "") -> None:
    """opens=True backfills Tuesday 18:00 UTC OPENING lines (movement
    study: open vs the kickoff-2h close already loaded). Open rows are
    identifiable by their exact T18:00:00Z snapshot_ts."""
    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set (add it to .env)")
    if opens or done_filter:
        try:
            cond = (done_filter or "snapshot_ts LIKE '%T18:00:00Z'")
            d = query_df(f"SELECT DISTINCT season, week FROM "
                         f"`{settings.raw}.{TABLE}` WHERE {cond}")
            done = {(int(r.season), int(r.week)) for r in d.itertuples()}
        except Exception:
            done = set()
    else:
        done = _done()
    for wk in _weeks(first_season, last_season).itertuples():
        key = (int(wk.season), int(wk.week))
        if key in done:
            continue
        # One events snapshot mid-week lists every game of the week
        mid = (pd.Timestamp(wk.first_day) - timedelta(days=1)).strftime(
            "%Y-%m-%dT12:00:00Z")
        try:
            events = _get(f"/historical/sports/{SPORT}/events", date=mid,
                          commenceTimeFrom=f"{wk.first_day}T00:00:00Z",
                          commenceTimeTo=f"{wk.last_day}T23:59:59Z")
        except requests.HTTPError:
            log.exception("events snapshot failed for %s", key)
            continue
        tuesday = (pd.Timestamp(wk.first_day)
                   - timedelta(days=(pd.Timestamp(wk.first_day).weekday()
                                     - 1) % 7)).strftime("%Y-%m-%d")
        rows: list[dict] = []
        for ev in events.get("data") or []:
            snap = (f"{tuesday}T18:00:00Z" if opens else
                    (pd.Timestamp(ev["commence_time"])
                     - timedelta(hours=SNAPSHOT_BEFORE_H)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"))
            time.sleep(PAUSE_S)
            try:
                odds = _get(
                    f"/historical/sports/{SPORT}/events/{ev['id']}/odds",
                    date=snap, regions="us", markets=markets,
                    oddsFormat="american", bookmakers="draftkings,fanduel")
            except requests.HTTPError as exc:
                log.warning("odds pull failed %s %s: %s", key, ev["id"], exc)
                continue
            rows.extend(parse_event_odds(odds, *key, snapshot_ts=snap))
        if rows:
            df = pd.DataFrame(rows)
            df["commence_time"] = pd.to_datetime(df.commence_time)
            load_dataframe(df, f"{settings.raw}.{TABLE}",
                           write_disposition="WRITE_APPEND")
            log.info("season %s week %s: %d prop rows (%d events)",
                     *key, len(rows), len(events.get("data") or []))
        else:
            log.warning("season %s week %s: no prop rows", *key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()


def run_live() -> None:
    """In-season weekly snapshot: current prop lines for upcoming games ->
    same prop_lines table (season/week resolved from the schedule)."""
    from ..config import current_season

    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set")
    season = current_season()
    sched = query_df(
        f"""SELECT MIN(week) AS wk FROM `{settings.raw}.schedules`
            WHERE season = {season}
              AND gameday >= CAST(CURRENT_DATE() AS STRING)""")
    week = int(sched.wk.iloc[0])
    events = _get(f"/sports/{SPORT}/events")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[dict] = []
    for ev in events or []:
        time.sleep(PAUSE_S)
        try:
            odds = _get(f"/sports/{SPORT}/events/{ev['id']}/odds",
                        regions="us", markets=MARKETS,
                        oddsFormat="american",
                        bookmakers="draftkings,fanduel")
        except requests.HTTPError as exc:
            log.warning("live odds pull failed %s: %s", ev["id"], exc)
            continue
        rows.extend(parse_event_odds({"data": odds}, season, week,
                                     snapshot_ts=now))
    if rows:
        df = pd.DataFrame(rows)
        df["commence_time"] = pd.to_datetime(df.commence_time)
        load_dataframe(df, f"{settings.raw}.{TABLE}",
                       write_disposition="WRITE_APPEND")
        log.info("live props: %d rows for season %s week %s",
                 len(rows), season, week)
