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
    return len(df)
