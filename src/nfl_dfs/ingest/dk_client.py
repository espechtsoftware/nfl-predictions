"""DraftKings public draftgroups API client.

Undocumented, unauthenticated endpoints. Be a good citizen: real User-Agent,
one pass per scheduled run, short timeouts, no retries in tight loops.
Hammering this endpoint is how it gets locked down for everyone.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

log = logging.getLogger(__name__)

DK_GROUPS = "https://api.draftkings.com/draftgroups/v1/"
DK_DRAFTABLES = "https://api.draftkings.com/draftgroups/v1/draftgroups/{gid}/draftables"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research",
    "Accept": "application/json",
}

# rosterSlotIds seen on showdown slates (CPT/FLEX) differ from classic;
# startTimeSuffix like "(Sun only)" marks the classic main slate variants.
SHOWDOWN_GAME_TYPES = {"Showdown Captain Mode", "Madden Showdown Captain Mode"}


def nfl_draft_groups(session: requests.Session | None = None) -> list[dict[str, Any]]:
    s = session or requests.Session()
    r = s.get(DK_GROUPS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return [
        g
        for g in r.json().get("draftGroups", [])
        if g.get("sport") == "NFL" and g.get("draftGroupState") == "Upcoming"
    ]


def classify_slate(group: dict[str, Any]) -> str:
    if group.get("gameTypeDescription") in SHOWDOWN_GAME_TYPES:
        return "showdown"
    if "Captain" in str(group.get("gameType", "")):
        return "showdown"
    return "classic"


def fetch_draftables(gid: int, session: requests.Session | None = None) -> dict[str, Any]:
    s = session or requests.Session()
    r = s.get(DK_DRAFTABLES.format(gid=gid), headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def draftables_frame(gid: int, slate_type: str, payload: dict[str, Any]) -> pd.DataFrame:
    """Flatten a draftables payload to one row per player."""
    comps = {c["competitionId"]: c for c in payload.get("competitions", [])}
    pulled_at = datetime.now(timezone.utc)

    # DK repeats players across roster slots. On classic slates the repeats
    # are identical; on showdown slates the CPT row carries a 1.5x salary,
    # so keep the cheaper (FLEX) row — the optimizer re-derives CPT cost.
    #
    # Draftable IDs are what DK's bulk-upload parser matches on (the "ID"
    # column of DKSalaries.csv is the draftableId, not the playerId), so
    # keep the kept row's draftableId — and on showdown slates also the CPT
    # row's, because the CPT slot only accepts the CPT-specific ID.
    rows: dict[int, dict[str, Any]] = {}
    for d in payload.get("draftables", []):
        pid = d["playerId"]
        prev = rows.get(pid)
        if prev is not None:
            sal = d.get("salary")
            if sal is not None and (prev["salary"] is None or sal < prev["salary"]):
                # Cheaper repeat = the FLEX row; the row we had was CPT.
                prev["dk_cpt_draftable_id"] = prev["dk_draftable_id"]
                prev["salary"] = sal
                prev["roster_slot"] = str(d.get("rosterSlotId"))
                prev["dk_draftable_id"] = d.get("draftableId")
            elif sal is not None and prev["salary"] is not None and sal > prev["salary"]:
                # Pricier repeat = the CPT row of the player we're keeping.
                prev["dk_cpt_draftable_id"] = d.get("draftableId")
            continue
        comp = comps.get(d.get("competition", {}).get("competitionId"), {})
        ppg = None
        for attr in d.get("draftStatAttributes", []):
            if attr.get("id") == 90:  # DK's own points-per-game figure
                try:
                    ppg = float(attr.get("value"))
                except (TypeError, ValueError):
                    ppg = None
        rows[pid] = {
            "pulled_at": pulled_at,
            "draft_group_id": gid,
            "slate_type": slate_type,
            "dk_player_id": pid,
            "dk_draftable_id": d.get("draftableId"),
            "dk_cpt_draftable_id": None,
            "display_name": d["displayName"],
            "team_abbr": d.get("teamAbbreviation"),
            "position": d.get("position"),
            "salary": d.get("salary"),
            "roster_slot": str(d.get("rosterSlotId")),
            "game_start": comp.get("startTime"),
            "status": d.get("status"),
            "dk_ppg": ppg,
        }
    df = pd.DataFrame(list(rows.values()))
    if not df.empty:
        # Nullable Int64 so BigQuery sees INT64, not FLOAT64 via NaN.
        for col in ("dk_draftable_id", "dk_cpt_draftable_id"):
            df[col] = df[col].astype("Int64")
    return df
