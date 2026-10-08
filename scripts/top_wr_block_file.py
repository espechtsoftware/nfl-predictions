#!/usr/bin/env python3
"""The week's TOP-RECEIVER term-block file (the outside reviewer, 10-08; the operator: "Is there a test we can do
immediately to try to fix this for this week?", after Week 4's winning lineups needed CeeDee Lamb and Nico Collins --
expensive receivers our FP-value optimizer never paid for). The union's --term-block-* vehicle builds N rows on
projection + min(tilt x pred_own, cap); with pred_own = bonus / 0.20, tilt 0.20 and cap = POINTS, the block adds exactly
POINTS projected points to each team's TOP RECEIVER -- the team's highest-salaried WR on the slate (ties: the higher frame
mean_projection, then the id) -- and nothing to anyone else.

    bonus = POINTS if the player is his team's highest-salaried WR in the frame                          else 0
    --with-cheap adds the cheap rule too: every non-DST player under $4,000 also gets POINTS (one combined file, one cap).

Output in the cheap / TE writers' format: dk_player_id, id, display_name, pos, team, opp, pred_own, bonus_points; every
skill player of the frame once, the DST omitted. Refuses (exit 3) a frame without the needed columns, a missing or
duplicated dk_player_id, non-positive POINTS, no player with a bonus, or an existing --out.

    python scripts/top_wr_block_file.py --season 2026 --week 5 --frame <T-70 or A3 frame.parquet> --points 2.0 --out <path>
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


def top_receivers(fr: pd.DataFrame) -> set[str]:
    """Each team's highest-salaried WR (ties: higher mean_projection, then id): their frame ids."""
    w = fr[fr["pos"].astype(str) == "WR"].copy()
    w["sal"] = pd.to_numeric(w["salary"], errors="coerce")
    w["proj"] = pd.to_numeric(w.get("mean_projection", pd.Series(0.0, index=w.index)), errors="coerce").fillna(0.0)
    w = w[w.sal.notna()].sort_values(["team", "sal", "proj", "id"], ascending=[True, False, False, True])
    return set(w.groupby("team").head(1)["id"].astype(str))


def build(frame: pd.DataFrame, points: float, with_cheap: bool = False) -> pd.DataFrame:
    """The block file's rows; raises ValueError rather than write a file the union would misread."""
    if not points > 0:
        raise ValueError(f"points must be positive (got {points})")
    for c in ("dk_player_id", "id", "display_name", "pos", "team", "salary"):
        if c not in frame.columns:
            raise ValueError(f"the frame has no {c} column")
    fr = frame[frame["pos"].astype(str).isin(SKILL)].copy()
    if fr.empty:
        raise ValueError("the frame holds no skill players")
    ids = pd.to_numeric(fr["dk_player_id"], errors="coerce")
    if ids.isna().any():
        raise ValueError(f"{int(ids.isna().sum())} skill players have no dk_player_id")
    if ids.duplicated().any():
        raise ValueError(f"{int(ids.duplicated().sum())} duplicated dk_player_id values")
    flag = fr["id"].astype(str).isin(top_receivers(fr))
    if with_cheap:
        sal = pd.to_numeric(fr["salary"], errors="coerce")
        flag |= sal.notna() & (sal < CHEAP_MAX_SALARY)
    bonus = np.where(flag, float(points), 0.0)
    if not (bonus > 0).any():
        raise ValueError("no player carries a bonus (own_bonus would refuse the file as fractions)")
    out = pd.DataFrame({"dk_player_id": ids.astype("int64"), "id": fr["id"].astype(str),
                        "display_name": fr["display_name"].astype(str), "pos": fr["pos"].astype(str),
                        "team": fr["team"].astype(str), "opp": fr.get("opp", pd.Series("", index=fr.index)).astype(str),
                        "pred_own": np.round(bonus / TILT, 4), "bonus_points": bonus})
    return out[COLUMNS].reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--points", type=float, default=2.0, help="projected points added per qualifying player (the cap)")
    ap.add_argument("--with-cheap", action="store_true", help="also give every non-DST player under $4,000 the bonus (one combined file)")
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"TOP-WR BLOCK FILE REFUSED: {a.out} exists (create-once; remove it deliberately to rewrite)", file=sys.stderr)
        return 3
    try:
        out = build(pd.read_parquet(a.frame), a.points, a.with_cheap)
    except ValueError as e:
        print(f"TOP-WR BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    wr = out[(out.pos == "WR") & (out.bonus_points > 0)]
    print(f"top-WR block file {a.season} W{a.week}: {int((out.bonus_points > 0).sum())} of {len(out)} skill players get +{a.points:g} "
          f"({len(wr)} WRs; with cheap: {a.with_cheap}) (frame sha256 {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]}) -> {a.out} "
          f"(sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
