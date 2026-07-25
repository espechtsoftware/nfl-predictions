"""Backfill real DK salaries from SportsDataIO's DiscoveryLab (personal-use)
API into the RotoGuru-shaped `dk_salaries_historical` table.

History (see the README data deficiency log): RotoGuru died after 2021;
SportsDataIO's commercial trial served scrambled data and quoted thousands.
Their DiscoveryLab personal tier serves REAL salaries — verified 835/835
$100-multiples on the 2025 week-15 main slate — but the free tier covers
only the most recent completed season. 2022-2024 remain gated behind their
paid personal tiers.

Endpoints (free tier, key via SPORTSDATA_API_KEY in .env):
  /api/nfl/fantasy/json/DfsSlatesByWeek/{season}REG/{week}
  /api/nfl/fantasy/json/FantasyDefenseByGame/{season}REG/{week}  (DST actuals)

Slate selection: DraftKings + OperatorGameType == "Classic" + salaries
actually present (the feed includes a giant pseudo-slate whose salaries are
all zero — picking by player count would select it), then most games =
the main slate. DST rows get actual DK points from FantasyDefenseByGame so
contest replays can roster defenses.
"""

from __future__ import annotations

import logging
import time

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import settings

log = logging.getLogger(__name__)

BASE = "https://api.sportsdata.io/api/nfl/fantasy/json"

_POSITION_MAP = {"DST": "Def", "DEF": "Def", "D": "Def"}


def pick_main_classic_slate(slates: list[dict]) -> dict | None:
    """Largest-by-games DK Classic slate whose salaries are populated."""
    candidates = []
    for sl in slates:
        if str(sl.get("Operator", "")).lower() != "draftkings":
            continue
        if str(sl.get("OperatorGameType", "")) != "Classic":
            continue
        players = sl.get("DfsSlatePlayers") or []
        if not players:
            continue
        with_salary = sum(1 for p in players if p.get("OperatorSalary"))
        if with_salary / len(players) >= 0.95:
            candidates.append(sl)
    if not candidates:
        return None
    return max(candidates, key=lambda sl: (sl.get("NumberOfGames") or 0))


def slate_rows(slate: dict, season: int, week: int,
               dst_points: dict[str, tuple[float, str]] | None = None) -> pd.DataFrame:
    rows = []
    for p in slate.get("DfsSlatePlayers", []):
        name = p.get("OperatorPlayerName")
        salary = p.get("OperatorSalary")
        pos = str(p.get("OperatorPosition") or "").upper()
        pid = p.get("SlatePlayerID")
        if pid is None:
            pid = p.get("PlayerID")
        if not name or not salary or not pos or pid is None:
            continue
        pos = _POSITION_MAP.get(pos, pos)
        team = str(p.get("Team") or "").upper()
        dk_points, opponent = (dst_points or {}).get(team, (None, None)) \
            if pos == "Def" else (None, None)
        rows.append({
            "season": season,
            "week": week,
            "rotoguru_gid": int(pid),  # table column is INTEGER (see 7d17bd8)
            "display_name": str(name).strip(),
            "position": pos,
            "team_abbr": team,
            "home_away": None,
            "opponent": opponent,
            "dk_points": dk_points,
            "salary": int(salary),
        })
    df = pd.DataFrame(rows)
    return df.drop_duplicates(subset=["rotoguru_gid"]) if not df.empty else df


def fetch_week(season: int, week: int, session: requests.Session) -> pd.DataFrame:
    r = session.get(f"{BASE}/DfsSlatesByWeek/{season}REG/{week}", timeout=30)
    r.raise_for_status()
    slate = pick_main_classic_slate(r.json())
    if slate is None:
        return pd.DataFrame()
    dst_points: dict[str, tuple[float, str]] = {}
    try:
        rd = session.get(f"{BASE}/FantasyDefenseByGame/{season}REG/{week}", timeout=30)
        rd.raise_for_status()
        for d in rd.json():
            team = str(d.get("Team") or "").upper()
            pts = d.get("FantasyPointsDraftKings")
            if team and pts is not None:
                dst_points[team] = (float(pts), str(d.get("Opponent") or "").upper())
    except Exception as exc:  # noqa: BLE001 - DST actuals are best-effort
        log.warning("%s wk %s: no DST points (%s)", season, week, exc)
    return slate_rows(slate, season, week, dst_points)


def run(first_season: int = 2025, last_season: int = 2025) -> None:
    if not settings.sportsdata_api_key:
        raise RuntimeError("SPORTSDATA_API_KEY is not set (put it in .env)")
    session = requests.Session()
    session.headers["Ocp-Apim-Subscription-Key"] = settings.sportsdata_api_key

    frames = []
    for season in range(first_season, last_season + 1):
        for week in range(1, 19):
            try:
                df = fetch_week(season, week, session)
            except Exception as exc:  # noqa: BLE001 - a missing week is fine
                log.warning("Skipping %s week %s: %s", season, week, exc)
                continue
            if not df.empty:
                frames.append(df)
                log.info("%s week %s: %d players (main classic slate)",
                         season, week, len(df))
            time.sleep(1.1)

    if not frames:
        raise RuntimeError("no slate data returned — check key/tier scope")
    out = pd.concat(frames, ignore_index=True)
    ok = out.salary.between(2000, 12000)
    clean = (out.salary % 100 == 0)
    if ok.mean() < 0.95 or clean.mean() < 0.99:
        raise RuntimeError(
            f"salaries fail integrity checks (band {ok.mean():.0%}, "
            f"$100-multiples {clean.mean():.0%}) — not loading")
    load_dataframe(out, "dk_salaries_historical",
                   write_disposition="WRITE_APPEND")
    log.info("Appended %d salary rows (%s-%s)", len(out), first_season, last_season)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()


# --- Showdown slates (Captain Mode replay data) ----------------------------

SHOWDOWN_TABLE = "showdown_salaries_historical"


def showdown_slate_rows(slates: list[dict], season: int, week: int,
                        actuals: dict[int, float],
                        dst_points: dict[str, tuple[float, str]]) -> pd.DataFrame:
    """All DK Captain Mode slates for a week -> one row per slate player,
    FLEX salary, with actual DK points joined by SportsDataIO PlayerID
    (skill + K) or team (DST). Actual points come from SDIO for scoring
    consistency across positions our models don't cover."""
    rows = []
    for sl in slates:
        if str(sl.get("Operator", "")).lower() != "draftkings":
            continue
        if str(sl.get("OperatorGameType", "")) != "Showdown Captain Mode":
            continue
        players = sl.get("DfsSlatePlayers") or []
        with_sal = [p for p in players if p.get("OperatorSalary")]
        if len(players) == 0 or len(with_sal) / len(players) < 0.95:
            continue
        teams = sorted({str(p.get("Team") or "").upper() for p in with_sal} - {""})
        for p in with_sal:
            pos = str(p.get("OperatorPosition") or "").upper()
            team = str(p.get("Team") or "").upper()
            sdio_id = p.get("PlayerID")
            if pos in _POSITION_MAP:  # DST
                actual = (dst_points.get(team) or (None, None))[0]
            else:
                actual = actuals.get(sdio_id)
            rows.append({
                "season": season, "week": week,
                "operator_slate_id": sl.get("OperatorSlateID"),
                "operator_day": sl.get("OperatorDay"),
                "game_teams": "@".join(teams),
                "sdio_player_id": sdio_id,
                "display_name": str(p.get("OperatorPlayerName") or "").strip(),
                "position": _POSITION_MAP.get(pos, pos),
                "team_abbr": team,
                "salary": int(p["OperatorSalary"]),
                "dk_points_actual": actual,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["operator_slate_id", "sdio_player_id"])


def run_showdown(first_season: int = 2025, last_season: int = 2025) -> None:
    """Land every Captain Mode slate (salaries + actual points) for the
    season(s) into nfl_raw.showdown_salaries_historical."""
    if not settings.sportsdata_api_key:
        raise RuntimeError("SPORTSDATA_API_KEY is not set (put it in .env)")
    session = requests.Session()
    session.headers["Ocp-Apim-Subscription-Key"] = settings.sportsdata_api_key

    frames = []
    for season in range(first_season, last_season + 1):
        for week in range(1, 19):
            try:
                r = session.get(f"{BASE}/DfsSlatesByWeek/{season}REG/{week}", timeout=30)
                r.raise_for_status()
                slates = r.json()
                ra = session.get(f"{BASE}/PlayerGameStatsByWeek/{season}REG/{week}",
                                 timeout=30)
                ra.raise_for_status()
                actuals = {x.get("PlayerID"): x.get("FantasyPointsDraftKings")
                           for x in ra.json()
                           if x.get("PlayerID") is not None
                           and x.get("FantasyPointsDraftKings") is not None}
                dst_points: dict[str, tuple[float, str]] = {}
                rd = session.get(f"{BASE}/FantasyDefenseByGame/{season}REG/{week}",
                                 timeout=30)
                rd.raise_for_status()
                for d in rd.json():
                    team = str(d.get("Team") or "").upper()
                    pts = d.get("FantasyPointsDraftKings")
                    if team and pts is not None:
                        dst_points[team] = (float(pts), str(d.get("Opponent") or "").upper())
                df = showdown_slate_rows(slates, season, week, actuals, dst_points)
            except Exception as exc:  # noqa: BLE001 - a missing week is fine
                log.warning("Skipping showdown %s week %s: %s", season, week, exc)
                continue
            if not df.empty:
                frames.append(df)
                log.info("%s week %s: %d showdown slate-player rows "
                         "(%d slates)", season, week, len(df),
                         df.operator_slate_id.nunique())
            time.sleep(1.1)

    if not frames:
        raise RuntimeError("no showdown slate data returned")
    out = pd.concat(frames, ignore_index=True)
    clean = (out.salary % 100 == 0)
    if clean.mean() < 0.99:
        raise RuntimeError(
            f"only {clean.mean():.0%} of salaries are $100 multiples — "
            "scrambled data; not loading")
    covered = out.dk_points_actual.notna()
    log.info("actual-points coverage: %.0f%%", 100 * covered.mean())
    load_dataframe(out, SHOWDOWN_TABLE, write_disposition="WRITE_APPEND")
    log.info("Appended %d showdown rows (%s-%s)", len(out), first_season, last_season)
