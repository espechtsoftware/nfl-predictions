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

import json
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..bq import load_dataframe

log = logging.getLogger(__name__)

PLAYER_COL = "Player"
REQUIRED = {PLAYER_COL, "%Drafted"}
SLOT_RE = re.compile(r"(?:^|\s)(CPT|FLEX|QB|RB|WR|TE|DST|K)\s+")


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


def parse_lineup_slots(lineup: str) -> list[dict[str, str]]:
    """Parse a DK lineup into ordered ``[{slot, player}, ...]`` records.

    Splitting at token boundaries preserves names losslessly and works for
    both Classic (nine slots) and Showdown (CPT plus five FLEX slots).
    """
    text = str(lineup).strip()
    matches = list(SLOT_RE.finditer(text))
    slots: list[dict[str, str]] = []
    for ix, match in enumerate(matches):
        end = matches[ix + 1].start() if ix + 1 < len(matches) else len(text)
        player = text[match.end():end].strip()
        if not player:
            raise ValueError(f"empty player after {match.group(1)} in lineup {text!r}")
        slots.append({"slot": match.group(1), "player": player})
    return slots


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
    parsed = e["Lineup"].astype(str).map(parse_lineup_slots)
    bad = parsed.map(len).eq(0)
    if bad.any():
        raise ValueError(f"{int(bad.sum())} entry lineups contained no DK slot tokens")
    roster_sizes = parsed.map(len)
    invalid_sizes = ~roster_sizes.isin([6, 9])
    if invalid_sizes.any():
        examples = e.loc[invalid_sizes, "Lineup"].head(3).tolist()
        raise ValueError(
            f"{int(invalid_sizes.sum())} entries have an unexpected parsed roster "
            f"size (expected 6 Showdown or 9 Classic); examples={examples}"
        )

    out = pd.DataFrame({
        "rank": pd.to_numeric(e["Rank"], errors="coerce"),
        "entry_id": (e["EntryId"].astype(str) if "EntryId" in e
                     else e.index.astype(str)),
        "entry_name": (e["EntryName"].astype(str) if "EntryName" in e
                       else ""),
        "points": pd.to_numeric(e.get("Points"), errors="coerce"),
        "lineup": e["Lineup"].astype(str),
    })
    out["lineup_slots_json"] = parsed.map(json.dumps)
    out["n_players"] = roster_sizes.astype(int)
    out["players_key"] = parsed.map(
        lambda slots: "|".join(sorted(item["player"] for item in slots)))
    out["is_top20"] = out["rank"].le(20)
    out = out.dropna(subset=["rank"]).reset_index(drop=True)
    if out.empty or out["rank"].min() > 1:
        raise ValueError(f"{path}: entry block does not contain the contest winner")
    if not out["is_top20"].any():
        raise ValueError(f"{path}: entry block contains no top-20 entries")
    return out


def run(
    path: str,
    season: int,
    week: int,
    contest_id: str,
    contest_name: str | None = None,
) -> int:
    # Parse and validate BOTH irreplaceable blocks before writing either one.
    # DK standings expire quickly; a successful job must never mean
    # "ownership landed but all entry-level lineup evidence disappeared."
    df = parse_standings_csv(path)
    entries = parse_entries_csv(path)
    imported_at = datetime.now(timezone.utc)
    import_id = hashlib.sha256(
        Path(path).read_bytes()
        + f"|{season}|{week}|{contest_id}".encode()
    ).hexdigest()
    df.insert(0, "imported_at", imported_at)
    df.insert(1, "import_id", import_id)
    df.insert(2, "season", season)
    df.insert(3, "week", week)
    df.insert(4, "contest_id", contest_id)
    df.insert(5, "contest_name", contest_name or "")
    entries.insert(0, "imported_at", imported_at)
    entries.insert(1, "import_id", import_id)
    entries.insert(2, "season", season)
    entries.insert(3, "week", week)
    entries.insert(4, "contest_id", contest_id)
    entries.insert(5, "contest_name", contest_name or "")

    # Entries load first: if its schema/parser contract fails, ownership is
    # not allowed to create a falsely-green import. Both loads still surface
    # normally to Cloud Run on any warehouse error.
    load_dataframe(entries, "contest_entries", write_disposition="WRITE_APPEND")
    load_dataframe(df, "contest_ownership", write_disposition="WRITE_APPEND")
    dupes = entries.groupby("players_key").size()
    log.info(
        "Imported %d entries (%d top-20, %d distinct, max dupe %d) and %d "
        "ownership rows for %s wk %s contest %s",
        len(entries), int(entries.is_top20.sum()), len(dupes), int(dupes.max()),
        len(df), season, week, contest_id,
    )
    return len(df)
