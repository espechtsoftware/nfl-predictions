"""One-time LineStar backfill: 2022-2024 DK salaries + 2022-2025 contest ownership.

Closes the RotoGuru-era gap (README known-gaps: RotoGuru died after 2021;
our own logging starts 2025), which doubles replay coverage, AND imports
real per-contest DK GPP ownership -- the data issue #11's ownership model
was waiting on -- from LineStar's public API
(`GetSalariesV5?sport=1&site=1&periodId=N`; period Ids are sequential,
"Week 1, 2022" = 302). Be-a-good-citizen rules as dk_client: real UA,
one pass, ~1.2s between calls, no retries.

Idempotent: seasons/weeks already present in dk_salaries_historical and
contest_ids already in contest_ownership are skipped.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from ..bq import load_dataframe, query_df
from ..config import settings

log = logging.getLogger(__name__)

API = ("https://www.linestarapp.com/DesktopModules/DailyFantasyApi/API/"
       "Fantasy/GetSalariesV5?sport=1&site=1&periodId={pid}")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research"}
WEEK_RE = re.compile(r"^Week (\d+), (\d{4})$")
SALARY_SEASONS = (2022, 2023, 2024)   # 2014-21 rotoguru, 2025+ our own log
OWNERSHIP_SEASONS = (2022, 2023, 2024, 2025)
PAUSE_S = 1.2


def _fetch(session: requests.Session, pid: int) -> dict:
    r = session.get(API.format(pid=pid), headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def periods(session: requests.Session) -> dict[int, tuple[int, int]]:
    """{periodId: (season, week)} for regular-season weeks."""
    d = _fetch(session, 0)
    out = {}
    for p in d.get("Periods", []):
        m = WEEK_RE.match(p.get("Name", ""))
        if m:
            out[int(p["Id"])] = (int(m.group(2)), int(m.group(1)))
    return out


def salary_rows(payload: dict, season: int, week: int) -> list[dict]:
    sc = json.loads(payload["SalaryContainerJson"])
    rows = []
    for r in sc.get("Salaries", []):
        if not r.get("Name") or not r.get("SAL"):
            continue
        pos = str(r.get("POS", "")).upper()
        pos = "DST" if pos in ("D", "DEF", "DST") else pos
        rows.append({
            "season": season, "week": week,
            "rotoguru_gid": None,
            "display_name": r["Name"], "position": pos,
            "team_abbr": r.get("PTEAM"),
            "home_away": "h" if r.get("PTEAM") == r.get("HTEAM") else "a",
            "opponent": r.get("OTEAM"),
            "dk_points": np.nan,   # LineStar PPG is a projection, not actuals
            "salary": int(r["SAL"]),
        })
    return rows


def ownership_rows(payload: dict, season: int, week: int) -> list[dict]:
    sc = json.loads(payload["SalaryContainerJson"])
    by_pid = {r.get("PID"): r for r in sc.get("Salaries", [])}
    now = datetime.now(timezone.utc)
    rows = []
    for cr in (payload.get("Ownership") or {}).get("ContestResults", []):
        c = cr.get("Contest") or {}
        for o in cr.get("OwnershipData", []):
            p = by_pid.get(o.get("PlayerId"))
            if p is None or o.get("Owned") is None:
                continue
            rows.append({
                "imported_at": now, "season": season, "week": week,
                # contest_ownership.contest_id is STRING (DK CSV heritage)
                "contest_id": str(c.get("ContestId") or ""),
                "contest_name": f"{c.get('ContestName', '')} "
                                f"[{c.get('EntryCount', '?')} entries, "
                                f"${c.get('EntryFee', '?')}]",
                "display_name": p["Name"],
                "roster_position": str(p.get("POS", "")).upper(),
                "pct_drafted": float(o["Owned"]),
                "fpts": np.nan,
            })
    return rows


def run() -> None:
    session = requests.Session()
    pmap = periods(session)
    have_sal = {(int(r.season), int(r.week)) for r in query_df(
        f"SELECT DISTINCT season, week FROM `{settings.raw}.dk_salaries_historical`"
    ).itertuples()}
    try:
        have_own = {str(r.contest_id) for r in query_df(
            f"SELECT DISTINCT contest_id FROM `{settings.raw}.contest_ownership`"
        ).itertuples()}
    except Exception:
        have_own = set()

    sal_all, own_all = [], []
    for pid, (season, week) in sorted(pmap.items()):
        want_sal = season in SALARY_SEASONS and (season, week) not in have_sal
        want_own = season in OWNERSHIP_SEASONS
        if not (want_sal or want_own):
            continue
        time.sleep(PAUSE_S)
        try:
            payload = _fetch(session, pid)
        except requests.HTTPError as exc:
            log.warning("period %d (%s wk %s) failed: %s", pid, season, week, exc)
            continue
        if want_sal:
            rows = salary_rows(payload, season, week)
            sal_all.extend(rows)
            log.info("period %d %s wk%d: %d salary rows", pid, season, week, len(rows))
        if want_own:
            rows = [r for r in ownership_rows(payload, season, week)
                    if r["contest_id"] not in have_own]
            own_all.extend(rows)
            if rows:
                log.info("period %d %s wk%d: %d ownership rows", pid, season, week, len(rows))

    if sal_all:
        load_dataframe(pd.DataFrame(sal_all), "dk_salaries_historical",
                       write_disposition="WRITE_APPEND")
        log.info("loaded %d salary rows", len(sal_all))
    if own_all:
        load_dataframe(pd.DataFrame(own_all), "contest_ownership",
                       write_disposition="WRITE_APPEND")
        log.info("loaded %d ownership rows across %d contests",
                 len(own_all), len({r['contest_id'] for r in own_all}))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
