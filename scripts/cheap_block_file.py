#!/usr/bin/env python3
"""The week's cheap-player term-block file (the outside reviewer, 10-07: the Milly graph's within-portfolio finding --
the regulars' top-1% lineups carried more sub-$4,000 players in all four 2026 weeks -- and the 8-row block replay on
W2-4, ahead of LIVE in all three weeks at +2 and +4; reports/2026-10-07-graph-cheap-players-finding.md). The union's
--term-block-* vehicle builds N rows on projection + min(tilt x pred_own, cap); with pred_own = bonus / 0.20, tilt 0.20
and cap = POINTS the block adds exactly POINTS projected points to every non-DST player under $4,000 and nothing to
anyone else (a preference, not a mandate; the expensive players are not ruled out).

    bonus = POINTS if pos in (QB, RB, WR, TE) and salary < 4000 else 0

Public data only (DraftKings salaries and positions from the frame); no vendor values. Output (the format own_bonus
reads, the same columns as matchup_block_file.py): dk_player_id, id, display_name, pos, team, opp, pred_own, bonus_points;
every skill player of the frame once (a bonus of 0 included), the DST omitted. Refuses (exit 3) a frame without skill
players, a missing or duplicated dk_player_id, a non-positive POINTS, or a week where no player carries a bonus.

    python scripts/cheap_block_file.py --season 2026 --week 5 --frame <a Week-5 frame.parquet> --points 2.0 --out <path>/cheap2-w5.csv
    (the union then: --term-block-rows 8 --term-block-source <file> --term-block-tilt 0.20 --term-block-cap-points 2.0)
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TILT = 0.20
CHEAP_MAX_SALARY = 4000
SKILL = ("QB", "RB", "WR", "TE")
COLUMNS = ["dk_player_id", "id", "display_name", "pos", "team", "opp", "pred_own", "bonus_points"]


def build(frame: pd.DataFrame, points: float) -> pd.DataFrame:
    """The block file's rows; raises ValueError rather than write a file the union would misread."""
    if not points > 0:
        raise ValueError(f"points must be positive (got {points})")
    fr = frame[frame["pos"].astype(str).isin(SKILL)].copy()
    if fr.empty:
        raise ValueError("the frame holds no skill players")
    ids = pd.to_numeric(fr["dk_player_id"], errors="coerce")
    if ids.isna().any():
        raise ValueError(f"{int(ids.isna().sum())} skill players have no dk_player_id")
    if ids.duplicated().any():
        raise ValueError(f"{int(ids.duplicated().sum())} duplicated dk_player_id values")
    sal = pd.to_numeric(fr["salary"], errors="coerce")
    bonus = np.where(sal.notna() & (sal < CHEAP_MAX_SALARY), float(points), 0.0)
    if not (bonus > 0).any():
        raise ValueError("no player carries a cheap bonus (own_bonus would refuse the file as fractions)")
    out = pd.DataFrame({"dk_player_id": ids.astype("int64"), "id": fr.get("id", pd.Series(index=fr.index, dtype=str)).astype(str),
                        "display_name": fr["display_name"].astype(str), "pos": fr["pos"].astype(str),
                        "team": fr.get("team", pd.Series(index=fr.index, dtype=str)).astype(str),
                        "opp": fr.get("opp", pd.Series(index=fr.index, dtype=str)).astype(str),
                        "pred_own": np.round(bonus / TILT, 4), "bonus_points": bonus})
    return out[COLUMNS].reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--points", type=float, default=2.0, help="projected points added per sub-$4,000 non-DST player (the cap)")
    a = ap.parse_args(argv)
    try:
        out = build(pd.read_parquet(a.frame), a.points)
    except ValueError as e:
        print(f"CHEAP BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"cheap block file {a.season} W{a.week}: {int((out.bonus_points > 0).sum())} of {len(out)} skill players get +{a.points:g} "
          f"(frame sha256 {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]}) -> {a.out} (sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
