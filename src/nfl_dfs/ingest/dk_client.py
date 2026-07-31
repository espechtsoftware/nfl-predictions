"""DraftKings public draftgroups API client.

Undocumented, unauthenticated endpoints. Be a good citizen: real User-Agent,
one pass per scheduled run, short timeouts, no retries in tight loops.
Hammering this endpoint is how it gets locked down for everyone.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

log = logging.getLogger(__name__)

DK_GROUPS = "https://api.draftkings.com/draftgroups/v1/"
DK_DRAFTABLES = "https://api.draftkings.com/draftgroups/v1/draftgroups/{gid}/draftables"
DK_CONTESTS = "https://www.draftkings.com/lobby/getcontests?sport=NFL"
DK_CFB_CONTESTS = "https://www.draftkings.com/lobby/getcontests?sport=CFB"
CFB_SPORT = "CFB"
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


def _group_sport(group: dict[str, Any]) -> str | None:
    """DK nests the sport code under ``contestType`` in the current live
    payload (verified 2026-07-31 against ``DK_GROUPS`` — no top-level
    ``sport`` key exists on any draft group today, unlike ``nfl_contests``'
    flat lobby payload). Also checks a top-level ``sport`` key so this
    doesn't silently stop matching if DK's shape reverts."""
    return group.get("sport") or group.get("contestType", {}).get("sport")


def cfb_draft_groups(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """CFB twin of ``nfl_draft_groups``: same undocumented endpoint, no CFB
    draft groups exist yet as of 2026-07-31 (college football preseason) so
    this is unexercised against a live slate — verified only that DK's
    lobby recognizes ``CFB`` as a sport code (``nfl_contests``' sibling
    endpoint returns ``SelectedSport: "CFB"`` for it, vs. null for made-up
    codes)."""
    s = session or requests.Session()
    r = s.get(DK_GROUPS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return [
        g
        for g in r.json().get("draftGroups", [])
        if _group_sport(g) == CFB_SPORT and g.get("draftGroupState") == "Upcoming"
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


def nfl_contests(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Every contest DK's lobby currently tags sport=NFL.

    Verified live (2026-07): this endpoint returns whatever DK's lobby has
    up under the NFL tab year-round, which off-season is Madden simulation
    contests and Best Ball — not real NFL slates. It doesn't separate them
    from real classic/showdown slates by any sport field; filter with
    ``contests_frame(..., draft_group_ids=...)`` using the draft group IDs
    from ``nfl_draft_groups()`` to keep only contests on real games.
    """
    s = session or requests.Session()
    r = s.get(DK_CONTESTS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("Contests", [])


def cfb_contests(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """CFB twin of ``nfl_contests``, same off-season-noise caveat: filter
    with ``contests_frame(..., draft_group_ids=...)`` using
    ``cfb_draft_groups()`` IDs to keep only real CFB slates."""
    s = session or requests.Session()
    r = s.get(DK_CFB_CONTESTS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("Contests", [])


_DK_DATE_RE = re.compile(r"^/Date\((-?\d+)([+-]\d{4})?\)/$")


def _parse_dk_date(value: Any) -> pd.Timestamp | None:
    """Parse DK's ASP.NET-style ``/Date(1785513600000)/`` epoch-ms string.

    The trailing ``+HHMM``/``-HHMM`` offset some payloads carry is the
    serializer's local zone, not a shift to apply — the leading number is
    already a UTC epoch millis, per every other DK timestamp this client
    parses (``game_start`` above is plain ISO 8601 UTC).
    """
    if not isinstance(value, str):
        return None
    m = _DK_DATE_RE.match(value)
    if not m:
        return None
    try:
        return pd.Timestamp(int(m.group(1)), unit="ms", tz="UTC")
    except (ValueError, OverflowError):
        return None


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


CONTEST_COLUMNS = [
    "pulled_at", "contest_id", "draft_group_id", "name", "game_type",
    "entry_fee", "max_entries", "entries", "fill_rate", "prize_pool",
    "is_guaranteed", "overlay_dollars", "start_time",
]


def contests_frame(
    contests: list[dict[str, Any]],
    draft_group_ids: set[int] | None = None,
) -> pd.DataFrame:
    """Flatten DK lobby contest listings into a fill-rate/overlay snapshot.

    ``overlay_dollars`` is the free-EV signal this scaffold exists for: a
    guaranteed ("GTD") contest pays its full prize pool regardless of how
    many entries show up, so if ``entries * entry_fee`` is still short of
    ``prize_pool`` as lock approaches, the field is being subsidized —
    positive expected value for anyone who can still enter. Non-guaranteed
    contests cancel/refund if underfilled instead of being subsidized, so
    they never carry an overlay (0.0, not null — the field is meaningful,
    just always zero).

    ``draft_group_ids``, when given, restricts the result to contests DK
    has tied to one of those draft groups (pass the IDs from
    ``nfl_draft_groups()`` to keep only real NFL slates — see
    ``nfl_contests()`` for why that filter matters).
    """
    pulled_at = datetime.now(timezone.utc)
    rows = []
    for c in contests:
        dg = c.get("dg")
        if draft_group_ids is not None and dg not in draft_group_ids:
            continue
        entries = c.get("nt")
        max_entries = c.get("m")
        entry_fee = c.get("a")
        prize_pool = c.get("po")
        is_guaranteed = str(c.get("attr", {}).get("IsGuaranteed", "")).lower() == "true"

        fill_rate = None
        if entries is not None and max_entries:
            fill_rate = entries / max_entries

        overlay = 0.0
        if is_guaranteed and entries is not None and entry_fee is not None and prize_pool is not None:
            overlay = max(prize_pool - entries * entry_fee, 0.0)

        rows.append({
            "pulled_at": pulled_at,
            "contest_id": c.get("id"),
            "draft_group_id": dg,
            "name": c.get("n"),
            "game_type": c.get("gameType"),
            "entry_fee": entry_fee,
            "max_entries": max_entries,
            "entries": entries,
            "fill_rate": fill_rate,
            "prize_pool": prize_pool,
            "is_guaranteed": is_guaranteed,
            "overlay_dollars": overlay,
            "start_time": _parse_dk_date(c.get("sd")),
        })

    if not rows:
        return pd.DataFrame(columns=CONTEST_COLUMNS)

    df = pd.DataFrame(rows)
    for col in ("contest_id", "draft_group_id", "max_entries", "entries"):
        df[col] = df[col].astype("Int64")
    return df
