"""Backfill 2022-2025 DraftKings salaries from SportsDataIO.

Fills the RotoGuru-shaped `dk_salaries_historical` table for the seasons
RotoGuru never covered (see the README data deficiency log). Rows flow
through the same name+position GSIS matching in 019_dk_salary_week.sql,
so a successful import heals the salary features for recent training rows
and unlocks real-salary contest replays for 2022-2025.

Endpoint: GET /v3/nfl/scores/json/DfsSlatesByWeek/{season}REG/{week}
Auth: Ocp-Apim-Subscription-Key header (settings.sportsdata_api_key).

Slate selection: DraftKings classic main slate = the DK slate with the
most players that week (their game-type labels vary by era; player count
is the robust discriminator). dk_points stays NULL — actuals come from
our own pbp-derived tables, and 019 never reads it.
"""

from __future__ import annotations

import logging
import time

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import settings

log = logging.getLogger(__name__)

URL = "https://api.sportsdata.io/v3/nfl/scores/json/DfsSlatesByWeek/{season}REG/{week}"

# SportsDataIO position labels -> RotoGuru-era labels used by 019/replay
_POSITION_MAP = {"DST": "Def", "DEF": "Def", "D": "Def"}


def pick_main_dk_slate(slates: list[dict]) -> dict | None:
    dk = [s for s in slates
          if str(s.get("Operator", "")).lower() == "draftkings"
          and s.get("DfsSlatePlayers")]
    if not dk:
        return None
    return max(dk, key=lambda s: len(s["DfsSlatePlayers"]))


def slate_rows(slate: dict, season: int, week: int) -> pd.DataFrame:
    rows = []
    for p in slate.get("DfsSlatePlayers", []):
        name = p.get("OperatorPlayerName") or p.get("PlayerName")
        salary = p.get("OperatorSalary")
        pos = str(p.get("OperatorPosition") or p.get("Position") or "").upper()
        if not name or not salary or not pos:
            continue
        if not (p.get("SlatePlayerID") or p.get("PlayerID")):
            continue  # no usable id -> can't dedupe/group downstream
        rows.append({
            "season": season,
            "week": week,
            # The table's rotoguru_gid landed as INTEGER (autodetect from
            # RotoGuru's numeric GIDs), so these must be numeric too. No
            # collision risk: RotoGuru rows end at 2021, these start at 2022,
            # and 019 only groups gids within a (season, week).
            "rotoguru_gid": int(p.get("SlatePlayerID") or p.get("PlayerID") or 0),
            "display_name": str(name).strip(),
            "position": _POSITION_MAP.get(pos, pos),
            "team_abbr": str(p.get("Team") or "").upper(),
            "home_away": None,
            "opponent": None,
            "dk_points": None,
            "salary": int(salary),
        })
    df = pd.DataFrame(rows)
    return df.drop_duplicates(subset=["rotoguru_gid"]) if not df.empty else df


def fetch_week(season: int, week: int, session: requests.Session) -> pd.DataFrame:
    r = session.get(URL.format(season=season, week=week), timeout=30)
    r.raise_for_status()
    slate = pick_main_dk_slate(r.json())
    if slate is None:
        return pd.DataFrame()
    return slate_rows(slate, season, week)


def run(first_season: int = 2022, last_season: int = 2025) -> None:
    if not settings.sportsdata_api_key:
        raise RuntimeError("SPORTSDATA_API_KEY is not set")
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
                log.info("%s week %s: %d players (main DK slate)",
                         season, week, len(df))
            time.sleep(1.1)  # trial rate limits are unforgiving

    if not frames:
        raise RuntimeError("no slate data returned — check key/trial scope")
    out = pd.concat(frames, ignore_index=True)
    # Sanity: DK salaries live in a known band; scrambled trial data would
    # violate this and must not silently poison the table.
    ok = out.salary.between(2000, 12000)
    if ok.mean() < 0.95:
        raise RuntimeError(
            f"only {ok.mean():.0%} of salaries in the plausible DK range — "
            "trial data may be scrambled; not loading")
    load_dataframe(out, "dk_salaries_historical",
                   write_disposition="WRITE_APPEND")
    log.info("Appended %d salary rows (%s-%s)", len(out), first_season, last_season)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
