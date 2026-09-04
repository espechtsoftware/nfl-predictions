"""DraftKings public draftgroups API client.

Undocumented, unauthenticated endpoints. Be a good citizen: real User-Agent,
one pass per scheduled run, short timeouts, no retries in tight loops.
Hammering this endpoint is how it gets locked down for everyone.
"""

from __future__ import annotations

import json
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
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research",
    "Accept": "application/json",
}

# DK's own /sites/US-DK/sports/v1/sports lists College Football as sportId=5
# (regionAbbreviatedSportName "CFB"; verified live 2026-07-31). Each entry in
# /draftgroups/v1/'s draftGroups array carries this same sportId at the top
# level — unlike the top-level "sport" string nfl_draft_groups() filters on,
# which 0/180 groups sampled live on that date actually carried (see the
# README's Data deficiency log). sportId is confirmed present and reliable.
CFB_SPORT_ID = 5
NFL_SPORT_ID = 1

# DK tags its off-season Madden simulations as NFL and distinguishes them
# only by league abbreviation (verified live 2026-08-20: 5 of 94 NFL-sportId
# groups were SIM). A simulation is not a slate; the ingest must skip them.
SIM_LEAGUE = "SIM"

# rosterSlotIds seen on showdown slates (CPT/FLEX) differ from classic;
# startTimeSuffix like "(Sun only)" marks the classic main slate variants.
SHOWDOWN_GAME_TYPES = {"Showdown Captain Mode", "Madden Showdown Captain Mode"}

# The only two DK products this pipeline prices. The same live check found
# 62 of 94 NFL groups were Best Ball and a further 9 Snake/Pick6 — snake
# drafts and pick-em, not salary-cap DFS, and ingesting them as slates
# would pollute the salary history the whole system trains on.
SUPPORTED_GAME_TYPES = {"Classic", "Showdown Captain Mode"}


def nfl_draft_groups(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Upcoming DK NFL draft groups this pipeline can actually price.

    Filter corrected 2026-08-20 against the live endpoint (deficiency log
    row 2026-07-31, which predicted exactly this and prescribed the fix).
    Three facts about the real payload drove it:

    * NO draft group carries a top-level ``sport`` key — the previous
      ``g["sport"] == "NFL"`` test matched zero groups in any season, so
      the hourly slate/salary ingest silently wrote nothing. ``sportId``
      (1=NFL) is the reliable field, mirroring ``cfb_draft_groups``.
    * DK tags Madden simulations as NFL; they are separated by their
      league (``SIM``) and excluded here — a Madden sim is not a slate.
    * Group entries carry only ``gameTypeId``; the human-readable names
      live in the response's sibling ``gameTypes`` array. Resolving that
      lets us keep only the two products the pipeline supports (Classic
      and Showdown Captain Mode) and drop Best Ball / Snake / Pick6,
      which are not salary-cap DFS at all. The resolved name is attached
      as ``gameTypeDescription`` so :func:`classify_slate` — which reads
      that key — classifies correctly instead of calling everything
      classic.
    """
    s = session or requests.Session()
    r = s.get(DK_GROUPS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    payload = r.json()
    names = {
        entry.get("gameTypeId"): entry.get("name")
        for entry in payload.get("gameTypes", [])
    }
    groups = []
    for g in payload.get("draftGroups", []):
        if g.get("sportId") != NFL_SPORT_ID:
            continue
        if g.get("draftGroupState") != "Upcoming":
            continue
        leagues = {
            str(entry.get("leagueAbbreviation", "")).upper()
            for entry in (g.get("leagues") or [])
        }
        if SIM_LEAGUE in leagues:
            continue
        name = g.get("gameTypeDescription") or names.get(g.get("gameTypeId"))
        if name not in SUPPORTED_GAME_TYPES:
            continue
        groups.append({**g, "gameTypeDescription": name})
    return groups


def cfb_draft_groups(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Upcoming DK College Football draft groups (issue #13 item 7).

    Same endpoint and supported salary-cap game types as
    :func:`nfl_draft_groups`, filtered on ``sportId`` instead of the
    top-level ``sport`` string. Group entries carry only ``gameTypeId``, so
    resolve the sibling ``gameTypes`` array and attach the description that
    :func:`classify_slate` requires.
    """
    s = session or requests.Session()
    r = s.get(DK_GROUPS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    payload = r.json()
    names = {
        entry.get("gameTypeId"): entry.get("name")
        for entry in payload.get("gameTypes", [])
    }
    groups = []
    for g in payload.get("draftGroups", []):
        if g.get("sportId") != CFB_SPORT_ID:
            continue
        if g.get("draftGroupState") != "Upcoming":
            continue
        name = g.get("gameTypeDescription") or names.get(g.get("gameTypeId"))
        if name not in SUPPORTED_GAME_TYPES:
            continue
        groups.append({**g, "gameTypeDescription": name})
    return groups


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
    """Every contest DK's lobby currently tags sport=CFB. See ``nfl_contests``
    for the shared off-season-noise caveat; filter with ``contests_frame``'s
    ``draft_group_ids`` using ``cfb_draft_groups()`` IDs."""
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
        # DK serializes competition start times with SEVEN fractional-second
        # digits ("2026-08-22T16:00:00.0000000Z"), which pyarrow refuses to
        # cast to a microsecond BigQuery TIMESTAMP — the load raised
        # ArrowInvalid and the whole hourly ingest died (found 2026-08-20 by
        # running the real job end to end). Parse to real timestamps here so
        # the frame carries a proper dtype rather than raw provider strings.
        df["game_start"] = pd.to_datetime(
            df["game_start"], format="ISO8601", utc=True, errors="coerce"
        )
    return df


CONTEST_COLUMNS = [
    "pulled_at", "contest_id", "draft_group_id", "sport", "name", "game_type",
    "entry_fee", "max_entries", "entry_limit", "entries", "fill_rate",
    "prize_pool", "is_guaranteed", "is_qualifier", "contest_template_id",
    "payout_metadata_json", "overlay_dollars", "start_time",
]


def contests_frame(
    contests: list[dict[str, Any]],
    draft_group_ids: set[int] | None = None,
    sport: str = "NFL",
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

    ``sport`` stamps a ``sport`` column so ``nfl_raw.dk_contest_fills`` can
    hold both NFL and CFB (issue #13 item 7) polls in one append-only
    table; defaults to "NFL" for backward compatibility with the existing
    overlay-detection scaffold's call sites.
    """
    pulled_at = datetime.now(timezone.utc)
    rows = []
    for c in contests:
        dg = c.get("dg")
        if draft_group_ids is not None and dg not in draft_group_ids:
            continue
        entries = c.get("nt")
        max_entries = c.get("m")
        entry_limit = c.get("mec")
        entry_fee = c.get("a")
        prize_pool = c.get("po")
        attrs = c.get("attr", {})
        is_guaranteed = str(attrs.get("IsGuaranteed", "")).lower() == "true"
        is_qualifier = str(attrs.get("IsQualifier", "")).lower() == "true"

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
            "sport": sport,
            "name": c.get("n"),
            "game_type": c.get("gameType"),
            "entry_fee": entry_fee,
            "max_entries": max_entries,
            "entry_limit": entry_limit,
            "entries": entries,
            "fill_rate": fill_rate,
            "prize_pool": prize_pool,
            "is_guaranteed": is_guaranteed,
            "is_qualifier": is_qualifier,
            "contest_template_id": c.get("tmpl"),
            "payout_metadata_json": json.dumps(
                c.get("payoutDescriptionMetadata", []),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "overlay_dollars": overlay,
            "start_time": _parse_dk_date(c.get("sd")),
        })

    if not rows:
        return pd.DataFrame(columns=CONTEST_COLUMNS)

    df = pd.DataFrame(rows)
    for col in (
        "contest_id", "draft_group_id", "max_entries", "entry_limit",
        "entries", "contest_template_id",
    ):
        df[col] = df[col].astype("Int64")
    return df
