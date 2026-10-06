"""Team identity for the dashboard: one canonical code per franchise.

The canonical code is nflverse's (schedules, weekly_stats, team_week_context,
defense_points_against), so the Rams are ``LA``. DraftKings and Fantasy Points
spell them ``LAR``; our own projections carry both spellings in 2026.
"""
from __future__ import annotations

import re

# Same map as ingest.fantasy_points_coverage.TEAM_NAMES (a test pins the two
# together); copied so the dashboard does not import the paid-data ingest.
TEAM_NAMES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
    "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE",
    "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

# Vendor and historical spellings -> canonical nflverse code.
ALIASES = {
    "LAR": "LA", "STL": "LA", "SL": "LA", "JAC": "JAX", "WSH": "WAS",
    "OAK": "LV", "LVR": "LV", "SD": "LAC", "ARZ": "ARI", "BLT": "BAL",
    "CLV": "CLE", "HST": "HOU", "KCC": "KC", "GNB": "GB", "NWE": "NE",
    "NOR": "NO", "SFO": "SF", "TAM": "TB", "WFT": "WAS",
}

# DraftKings names a DST by its nickname ("Vikings").
NICKNAMES = {full.rsplit(" ", 1)[-1]: code for full, code in TEAM_NAMES.items()}

CANONICAL = frozenset(TEAM_NAMES.values())


def canon_team(value: object) -> str | None:
    """Canonical code for a code, alias, full name or DST nickname; None if
    the value is empty or unknown."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "<na>"}:
        return None
    if s in TEAM_NAMES:
        return TEAM_NAMES[s]
    if s in NICKNAMES:
        return NICKNAMES[s]
    u = s.upper()
    if u in CANONICAL:
        return u
    return ALIASES.get(u)


def display_team(code: object) -> str:
    """The spelling shown to the operator (DraftKings': LAR)."""
    c = canon_team(code)
    return {"LA": "LAR"}.get(c or "", c or str(code or ""))


def parse_event_name(event_name: object) -> tuple[str | None, str | None]:
    """odds_snapshots.event_name is "Away Team @ Home Team" in full names."""
    parts = str(event_name or "").split(" @ ")
    if len(parts) != 2:
        return None, None
    return canon_team(parts[0].strip()), canon_team(parts[1].strip())


def norm_name(value: object) -> str:
    """Player-name join key: punctuation and generational suffixes out
    (the same rule as research.milly_ownership.normalize_name)."""
    if value is None:
        return ""
    text = re.sub(r"[^A-Z0-9 ]+", " ", str(value).upper())
    parts = text.split()
    while parts and parts[-1] in {"JR", "SR", "II", "III", "IV", "V"}:
        parts.pop()
    return "".join(parts)
