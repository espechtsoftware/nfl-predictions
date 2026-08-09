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

from ..bq import load_dataframe, query_df
from ..config import settings
from .odds_api_audit import (
    OddsApiRequestError,
    RequestContext,
    persist_request_audits,
    request_json,
)

log = logging.getLogger(__name__)

SPORT = "americanfootball_nfl"
TABLE = "prop_lines"
SHADOW_TABLE = "prop_lines_shadow"
MARKETS = ("player_pass_yds,player_pass_tds,player_rush_yds,"
           "player_reception_yds,player_receptions,player_anytime_td")
# Collection-only markets with genuinely different role/volume information.
# This exact bundle is intentionally fixed rather than environment-tunable;
# it is not consumed by any production model or UI query.
SHADOW_MARKET_KEYS = (
    "player_pass_attempts",
    "player_pass_completions",
    "player_rush_attempts",
    "player_pass_interceptions",
    "player_rush_tds",
    "player_reception_tds",
    "player_pass_rush_yds",
    "player_rush_reception_yds",
    "player_rush_reception_tds",
)
SHADOW_MARKETS = ",".join(SHADOW_MARKET_KEYS)
SNAPSHOT_BEFORE_H = 2   # hours before kickoff
PAUSE_S = 0.35          # stay far under the per-minute rate limit


def _get(
    path: str,
    *,
    audit_rows: list[dict],
    request_kind: str,
    historical: bool = False,
    is_shadow: bool = False,
    season: int | None = None,
    week: int | None = None,
    event_id: str | None = None,
    **params,
) -> dict | list:
    return request_json(
        path,
        api_key=settings.odds_api_key,
        params=params,
        context=RequestContext(
            request_kind=request_kind,
            endpoint=path,
            historical=historical,
            is_shadow=is_shadow,
            season=season,
            week=week,
            event_id=event_id,
            markets=params.get("markets"),
            bookmakers=params.get("bookmakers"),
            regions=params.get("regions"),
        ),
        audit_rows=audit_rows,
    )


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


def _run_historical(first_season: int, last_season: int, opens: bool,
                    markets: str, audit_rows: list[dict]) -> None:
    """opens=True backfills Tuesday 18:00 UTC OPENING lines (movement
    study: open vs the kickoff-2h close already loaded). Open rows are
    identifiable by their exact T18:00:00Z snapshot_ts."""
    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set (add it to .env)")
    if opens:
        try:
            # Fixed predicate — a raw-WHERE parameter here was a loaded
            # gun (security sweep 2026-08-03); opens rows are exactly
            # the T18:00:00Z snapshots.
            d = query_df(f"SELECT DISTINCT season, week FROM "
                         f"`{settings.raw}.{TABLE}` "
                         f"WHERE snapshot_ts LIKE '%T18:00:00Z'")
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
            events = _get(
                f"/historical/sports/{SPORT}/events",
                audit_rows=audit_rows,
                request_kind="historical_events",
                historical=True,
                season=key[0],
                week=key[1],
                date=mid,
                commenceTimeFrom=f"{wk.first_day}T00:00:00Z",
                commenceTimeTo=f"{wk.last_day}T23:59:59Z",
            )
        except OddsApiRequestError as exc:
            log.warning(
                "events snapshot failed for %s (status=%s, error=%s)",
                key, exc.status_code, exc.error_type,
            )
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
                    audit_rows=audit_rows,
                    request_kind="historical_event_odds",
                    historical=True,
                    season=key[0],
                    week=key[1],
                    event_id=str(ev["id"]),
                    date=snap, regions="us", markets=markets,
                    oddsFormat="american", bookmakers="draftkings,fanduel")
            except OddsApiRequestError as exc:
                log.warning(
                    "odds pull failed %s %s (status=%s, error=%s)",
                    key, ev["id"], exc.status_code, exc.error_type,
                )
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


def run(first_season: int = 2023, last_season: int = 2025,
        opens: bool = False, markets: str = MARKETS) -> None:
    """Run a resumable historical import and persist request-cost audits."""
    audit_rows: list[dict] = []
    try:
        _run_historical(first_season, last_season, opens, markets, audit_rows)
    finally:
        persist_request_audits(audit_rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()


def _event_is_in_window(event: dict, first_day, last_day) -> bool:
    try:
        kickoff = pd.Timestamp(event["commence_time"])
        if kickoff.tzinfo is None:
            kickoff = kickoff.tz_localize("UTC")
        game_day = kickoff.tz_convert("America/New_York").date()
    except (KeyError, TypeError, ValueError):
        return False
    return pd.Timestamp(first_day).date() <= game_day <= pd.Timestamp(last_day).date()


def _shadow_request_allowed(audit_rows: list[dict]) -> bool:
    """Fail closed unless the last response proves the reserve is protected."""
    if not settings.odds_shadow_markets_enabled or not audit_rows:
        return False
    remaining = audit_rows[-1].get("requests_remaining")
    if remaining is None:
        return False
    estimated_cost = len(SHADOW_MARKET_KEYS)  # one region; provider formula
    return remaining - estimated_cost >= settings.odds_shadow_min_remaining


def _load_prop_rows(rows: list[dict], table: str) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    df["commence_time"] = pd.to_datetime(df.commence_time)
    load_dataframe(
        df, f"{settings.raw}.{table}", write_disposition="WRITE_APPEND",
        partition_field="pulled_at" if table == SHADOW_TABLE else None,
    )


def _run_live(audit_rows: list[dict]) -> None:
    """In-season weekly snapshot: current prop lines for upcoming games ->
    prop_lines, plus an isolated quota-guarded shadow when enabled."""
    from ..config import current_season

    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set")
    season = current_season()
    sched = query_df(
        f"""SELECT week AS wk, MIN(gameday) AS first_day,
                   MAX(gameday) AS last_day
            FROM `{settings.raw}.schedules`
            WHERE season = {season}
              AND game_type = 'REG'
              AND gameday >= CAST(CURRENT_DATE() AS STRING)
            GROUP BY week ORDER BY week LIMIT 1""")
    if sched.empty or pd.isna(sched.wk.iloc[0]):
        log.info("No upcoming regular-season week; skipping live props")
        return
    week = int(sched.wk.iloc[0])
    first_day = sched.first_day.iloc[0]
    last_day = sched.last_day.iloc[0]
    events = _get(
        f"/sports/{SPORT}/events",
        audit_rows=audit_rows,
        request_kind="live_events",
        season=season,
        week=week,
    )
    events = [ev for ev in (events or [])
              if _event_is_in_window(ev, first_day, last_day)]
    if not events:
        log.info(
            "No Odds API events in regular-season %s week %s window %s..%s",
            season, week, first_day, last_day,
        )
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[dict] = []
    shadow_rows: list[dict] = []
    shadow_guard_reported = False
    for ev in events or []:
        time.sleep(PAUSE_S)
        try:
            odds = _get(
                f"/sports/{SPORT}/events/{ev['id']}/odds",
                audit_rows=audit_rows,
                request_kind="live_event_props",
                season=season,
                week=week,
                event_id=str(ev["id"]),
                regions="us",
                markets=MARKETS,
                oddsFormat="american",
                bookmakers="draftkings,fanduel",
            )
        except OddsApiRequestError as exc:
            log.warning(
                "live prop pull failed %s (status=%s, error=%s)",
                ev["id"], exc.status_code, exc.error_type,
            )
            continue
        rows.extend(parse_event_odds({"data": odds}, season, week,
                                     snapshot_ts=now))
        if not _shadow_request_allowed(audit_rows):
            if settings.odds_shadow_markets_enabled and not shadow_guard_reported:
                remaining = audit_rows[-1].get("requests_remaining")
                log.info(
                    "Skipping shadow props: remaining=%s, protected reserve=%s",
                    remaining, settings.odds_shadow_min_remaining,
                )
                shadow_guard_reported = True
            continue
        time.sleep(PAUSE_S)
        try:
            shadow_odds = _get(
                f"/sports/{SPORT}/events/{ev['id']}/odds",
                audit_rows=audit_rows,
                request_kind="live_event_props_shadow",
                is_shadow=True,
                season=season,
                week=week,
                event_id=str(ev["id"]),
                regions="us",
                markets=SHADOW_MARKETS,
                oddsFormat="american",
                bookmakers="draftkings,fanduel",
            )
        except OddsApiRequestError as exc:
            log.warning(
                "shadow prop pull failed %s (status=%s, error=%s)",
                ev["id"], exc.status_code, exc.error_type,
            )
            continue
        shadow_rows.extend(
            parse_event_odds(
                {"data": shadow_odds}, season, week, snapshot_ts=now
            )
        )
    _load_prop_rows(rows, TABLE)
    _load_prop_rows(shadow_rows, SHADOW_TABLE)
    log.info(
        "live props: %d base and %d shadow rows for season %s week %s",
        len(rows), len(shadow_rows), season, week,
    )


def run_live() -> None:
    audit_rows: list[dict] = []
    try:
        _run_live(audit_rows)
    finally:
        persist_request_audits(audit_rows)


def check_quota() -> None:
    """Persist current provider quota using The Odds API's free sports call."""
    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set")
    audit_rows: list[dict] = []
    try:
        _get(
            "/sports",
            audit_rows=audit_rows,
            request_kind="quota_check",
        )
    finally:
        persisted = persist_request_audits(audit_rows)
    if not audit_rows or not persisted:
        raise RuntimeError("Odds API quota check did not persist its audit")
    row = audit_rows[-1]
    log.info(
        "Odds API quota: remaining=%s used=%s last=%s",
        row.get("requests_remaining"), row.get("requests_used"),
        row.get("requests_last"),
    )
