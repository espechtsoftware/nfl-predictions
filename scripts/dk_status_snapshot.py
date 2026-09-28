#!/usr/bin/env python3
"""Fresh DraftKings status snapshot for the afternoon steps (Week 4): `id,status,game_start` for every draftable of the
group, id = dk_player_id -- the file `late_inactive_swaps.py --snapshot` (R4) and `sat_late_swap_live.py --snapshot` read.

`sunday_live_relayout.sh --dry-run` writes the same file, but refuses unless ENTER_ORDER=fewest-low and refuses a bundle
that already carries swaps, so it cannot serve a Week-4 afternoon (greedy order, a swapped bundle). Read-only: one
public DraftKings call, no warehouse write.

    python scripts/dk_status_snapshot.py --group 154078 [--out $OUT/dk-status-<utc>.csv]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def rows_from_draftables(payload: dict) -> dict[str, tuple[str, str]]:
    """{dk_player_id: (status, game_start)}; DK repeats a player per roster slot, the first row wins (same player)."""
    seen: dict[str, tuple[str, str]] = {}
    for d in payload.get("draftables", []):
        pid = str(d.get("playerId"))
        if pid in seen:
            continue
        st = d.get("status"); comp = d.get("competition") or {}
        seen[pid] = ("" if st in (None, "None", "") else str(st), str(comp.get("startTime") or ""))
    return seen


def write_snapshot(seen: dict[str, tuple[str, str]], out: Path) -> None:
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "status", "game_start"])
        w.writerows((k, v[0], v[1]) for k, v in sorted(seen.items()))
    tmp.replace(out)                                    # a reader never sees a half-written snapshot


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--group", type=int, default=int(os.environ["GROUP"]) if os.environ.get("GROUP") else None)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.group is None:
        ap.error("--group (or GROUP from week_env) is required")
    out = a.out or Path(os.environ.get("OUT", ".")) / f"dk-status-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.csv"
    from nfl_dfs.ingest.dk_client import fetch_draftables
    seen = rows_from_draftables(fetch_draftables(a.group))
    if len(seen) < 50:
        print(f"DK status snapshot REFUSED: group {a.group} returned {len(seen)} players", file=sys.stderr)
        return 2
    write_snapshot(seen, out)
    flagged = {s for s, _ in seen.values() if s}
    print(f"DK status snapshot: {len(seen)} players, {sum(1 for s, _ in seen.values() if s)} with a status "
          f"({', '.join(sorted(flagged))}) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
