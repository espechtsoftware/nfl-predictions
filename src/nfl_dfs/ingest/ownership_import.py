"""Import actual contest ownership from a DraftKings contest-standings CSV.

DK's "Export to CSV" on any contest's standings page produces a file with
entry rows on the left and a player summary block on the right; the summary
columns are `Player`, `Roster Position`, `%Drafted`, `FPTS`. That summary —
one row per player with actual ownership — is what we keep.

There is no API for this: export the CSV by hand (or a logged-in fetch)
each week and run `nfl-dfs import-ownership file.csv --season S --week W
--contest-id ID`. One GPP + one cash contest per week is enough to train
an ownership model; see the README data deficiency log.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..bq import load_dataframe

log = logging.getLogger(__name__)

PLAYER_COL = "Player"
REQUIRED = {PLAYER_COL, "%Drafted"}


def parse_standings_csv(path: str | Path) -> pd.DataFrame:
    """Extract the per-player ownership block from a standings export."""
    raw = pd.read_csv(path)
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError(
            f"{path} does not look like a DK contest-standings export; "
            f"missing columns {sorted(missing)}"
        )
    out = raw[raw[PLAYER_COL].notna()].copy()
    out = pd.DataFrame(
        {
            "display_name": out[PLAYER_COL].astype(str).str.strip(),
            "roster_position": out.get("Roster Position"),
            "pct_drafted": pd.to_numeric(
                out["%Drafted"].astype(str).str.rstrip("%"), errors="coerce"
            ),
            "fpts": pd.to_numeric(out.get("FPTS"), errors="coerce"),
        }
    )
    out = out.dropna(subset=["pct_drafted"])
    if out.empty:
        raise ValueError(f"no player ownership rows found in {path}")
    return out.reset_index(drop=True)


def parse_entries_csv(path: str | Path) -> pd.DataFrame:
    """Extract the per-ENTRY rows (left block): every submitted lineup
    with rank and points. This is the joint-structure data the field/
    dupe modeling needs (in-season queue 10a/10b; RTS blueprint) — DK
    purges standings exports after ~4 days, so losing these rows at
    import time loses them forever. `players_key` (sorted, delimited)
    is the duplicate-grouping key; the raw lineup string is kept
    lossless for slot-level parsing later."""
    raw = pd.read_csv(path)
    need = {"Rank", "Lineup"}
    if not need <= set(raw.columns):
        raise ValueError(f"{path}: no entry block (missing {need - set(raw.columns)})")
    e = raw[raw["Lineup"].notna() & raw["Rank"].notna()].copy()
    slots = ("CPT", "FLEX", "QB", "RB", "WR", "TE", "DST", "K")

    def players_of(s: str) -> str:
        t = str(s)
        for tok in slots:
            t = t.replace(f"{tok} ", f"|{tok}|")
        names = [seg.strip() for seg in t.split("|")
                 if seg.strip() and seg.strip() not in slots]
        return "|".join(sorted(names))

    out = pd.DataFrame({
        "rank": pd.to_numeric(e["Rank"], errors="coerce"),
        "entry_id": e.get("EntryId", pd.Series(dtype=str)).astype(str),
        "entry_name": e.get("EntryName", pd.Series(dtype=str)).astype(str),
        "points": pd.to_numeric(e.get("Points"), errors="coerce"),
        "lineup": e["Lineup"].astype(str),
    })
    out["players_key"] = out.lineup.map(players_of)
    return out.dropna(subset=["rank"]).reset_index(drop=True)


def run(
    path: str,
    season: int,
    week: int,
    contest_id: str,
    contest_name: str | None = None,
) -> int:
    df = parse_standings_csv(path)
    df.insert(0, "imported_at", datetime.now(timezone.utc))
    df.insert(1, "season", season)
    df.insert(2, "week", week)
    df.insert(3, "contest_id", contest_id)
    df.insert(4, "contest_name", contest_name or "")
    load_dataframe(df, "contest_ownership", write_disposition="WRITE_APPEND")
    log.info("Imported %d ownership rows for %s wk %s (contest %s)",
             len(df), season, week, contest_id)

    # Entry-level lineups (lossless): failure here must not block the
    # ownership import that the weekly model refit depends on.
    try:
        entries = parse_entries_csv(path)
        entries.insert(0, "imported_at", datetime.now(timezone.utc))
        entries.insert(1, "season", season)
        entries.insert(2, "week", week)
        entries.insert(3, "contest_id", contest_id)
        load_dataframe(entries, "contest_entries",
                       write_disposition="WRITE_APPEND")
        dupes = entries.groupby("players_key").size()
        log.info("Imported %d entries (%d distinct lineups, max dupe %d)",
                 len(entries), len(dupes), int(dupes.max()))
    except Exception:
        log.exception("entry-block import failed; ownership rows kept")
    return len(df)
