#!/usr/bin/env python3
"""Late-game inactive replacement (R4; operator decision 2026-09-28; laptop request D2).

After the late-game inactives (~13:35-13:55 CT), every entered lineup that holds a player now marked out is repaired
in place: the same slot, the best served-mean replacement that fits the salary and the roster rules, chosen from the
players whose game has NOT started. The output is the swap list `apply_swaps.py` expects (ROW:OUT_DD:IN_DD), so the
existing machinery -- fresh-feed check, lock check, roster validation, byte-identical other cells, frozen-map
re-publication through `sunday_swap.sh` -- does the writing. This script never edits an upload itself.

  python scripts/late_inactive_swaps.py --upload <bundle>/ENTER-all-rows-*-KEEPERS.csv --frame <run>/frame.parquet \\
      --snapshot dk-status-<utc>.csv [--now 2026-09-27T18:40:00Z] [--out swaps.json]

`--snapshot` is the live status CSV (`id`, `status`, `game_start`; id = dk_player_id) that `sunday_live_relayout.sh`
writes. A player is OUT when his snapshot status is one of O/OUT/IR/D or he is absent from the snapshot. A replacement
must: play the slot (FLEX takes RB/WR/TE), not already be in the row, not be out, have a game that starts after `now`,
keep the row's salary within [floor, 50000], keep every team at <= 8 players and the row at >= 2 games. Candidates are
ranked by the frame's served projection (`proj`), ties by salary descending. A row with no legal replacement is
reported as UNREPAIRED and the run exits 2 -- never a silent skip.

Prints the swap args on one line (for `sunday_swap.sh`) and writes a receipt JSON with every decision.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
ALLOWED = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "DST": {"DST"}}
OUT_STATUSES = {"O", "OUT", "IR", "D", "DOUBTFUL", "INJURED RESERVE", "SUSPENDED", "PUP", "NA"}


def _ts(v: str) -> datetime | None:
    v = str(v or "").strip()
    if not v:
        return None
    v = v.replace("Z", "+00:00")
    if "." in v:                                    # DraftKings' 7-digit fractions
        head, tail = v.split(".", 1)
        tz = tail[tail.find("+"):] if "+" in tail else "+00:00"
        v = head + tz
    try:
        t = datetime.fromisoformat(v)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def plan_swaps(upload_rows: list[list[str]], frame: pd.DataFrame, snapshot: list[dict], now: datetime,
               min_salary: int = 49000, cap: int = 50000) -> tuple[list[str], dict]:
    """Return (swap args, receipt). frame must carry dk_draftable_id, dk_player_id, pos, team, salary, proj, game_id,
    game_start; upload cells are draftable ids."""
    fr = frame.copy()
    fr["dd"] = fr["dk_draftable_id"].astype(str)
    fr["pid"] = fr["dk_player_id"].astype(str)
    by_dd = fr.set_index("dd")
    status = {str(r["id"]): str(r.get("status") or "").upper().strip() for r in snapshot}
    snap_start = {str(r["id"]): _ts(r.get("game_start")) for r in snapshot}

    def is_out(dd: str) -> bool:
        pid = by_dd.loc[dd, "pid"] if dd in by_dd.index else None
        if pid is None or pid not in status:
            return True                             # absent from the fresh feed: fail closed, treat as out
        return status[pid] in OUT_STATUSES

    def starts(dd: str) -> datetime | None:
        pid = by_dd.loc[dd, "pid"] if dd in by_dd.index else None
        t = snap_start.get(pid) if pid else None
        if t is None and dd in by_dd.index:
            t = _ts(by_dd.loc[dd, "game_start"])
        return t

    swaps: list[str] = []
    receipt: dict = {"now": now.isoformat(), "rows": [], "unrepaired": []}
    for r_i, row in enumerate(upload_rows, 1):
        cells = [c.strip() for c in row[:9]]
        for slot_i, dd in enumerate(cells):
            if not is_out(dd):
                continue
            st = starts(dd)
            if st is not None and st <= now:
                receipt["unrepaired"].append({"row": r_i, "slot": SLOTS[slot_i], "out": dd, "why": "game already started (locked cell)"})
                continue
            row_ids = set(cells)
            row_teams = [by_dd.loc[c, "team"] for c in cells if c in by_dd.index and c != dd]
            row_games = {by_dd.loc[c, "game_id"] for c in cells if c in by_dd.index and c != dd}
            sal_others = sum(int(by_dd.loc[c, "salary"]) for c in cells if c in by_dd.index and c != dd)
            pool = fr[fr["pos"].isin(ALLOWED[SLOTS[slot_i]]) & ~fr["dd"].isin(row_ids)]
            best = None
            for cand in pool.sort_values(["proj", "salary"], ascending=[False, False]).itertuples():
                if is_out(cand.dd):
                    continue
                cs = starts(cand.dd)
                if cs is None or cs <= now:
                    continue
                total = sal_others + int(cand.salary)
                if not (min_salary <= total <= cap):
                    continue
                if row_teams.count(cand.team) + 1 > 8:
                    continue
                if len(row_games | {cand.game_id}) < 2:
                    continue
                best = cand
                break
            if best is None:
                receipt["unrepaired"].append({"row": r_i, "slot": SLOTS[slot_i], "out": dd, "why": "no legal replacement"})
                continue
            swaps.append(f"{r_i}:{dd}:{best.dd}")
            receipt["rows"].append({"row": r_i, "slot": SLOTS[slot_i], "out": dd, "out_name": str(by_dd.loc[dd, "name"]) if dd in by_dd.index else "?",
                                    "in": best.dd, "in_name": str(best.name), "in_proj": float(best.proj), "salary_after": sal_others + int(best.salary)})
            cells[slot_i] = best.dd                 # a second out player in the same row sees the repaired row
    return swaps, receipt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--upload", type=Path, required=True)
    ap.add_argument("--frame", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--now", default=None)
    ap.add_argument("--min-salary", type=int, default=49000)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    rows = [r for r in csv.reader(a.upload.open())][1:]
    frame = pd.read_parquet(a.frame)
    need = {"dk_draftable_id", "dk_player_id", "pos", "team", "salary", "proj", "game_id", "game_start", "name"}
    if not need <= set(frame.columns):
        print(f"frame lacks {sorted(need - set(frame.columns))}", file=sys.stderr)
        return 2
    snapshot = list(csv.DictReader(a.snapshot.open()))
    if not snapshot or not {"id", "status"} <= set(snapshot[0]):
        print("snapshot lacks id/status", file=sys.stderr)
        return 2
    now = _ts(a.now) if a.now else datetime.now(timezone.utc)
    swaps, receipt = plan_swaps(rows, frame, snapshot, now, min_salary=a.min_salary)
    out = a.out or a.upload.with_suffix(".late-swaps.json")
    out.write_text(json.dumps({"swaps": swaps, **receipt}, indent=2) + "\n")
    for r in receipt["rows"]:
        print(f"row {r['row']} {r['slot']}: {r['out_name']} -> {r['in_name']} (proj {r['in_proj']:.1f}, salary {r['salary_after']})")
    for u in receipt["unrepaired"]:
        print(f"UNREPAIRED row {u['row']} {u['slot']} {u['out']}: {u['why']}", file=sys.stderr)
    print(" ".join(swaps))
    print(f"receipt {out}", file=sys.stderr)
    return 2 if receipt["unrepaired"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
