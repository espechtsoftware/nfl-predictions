#!/usr/bin/env python3
"""The week's tight-end term-block file (the outside reviewer, 10-07 night; the operator: "more testing on the QB tight end
stacks right away", "consider a percentage of our lineups to have a QB tight end stack" and "include a bonus to the tight
end in these types of situations"). The union's --term-block-* vehicle builds N rows on projection + min(tilt x pred_own,
cap); with pred_own = bonus / 0.20, tilt 0.20 and cap = POINTS, the block adds exactly POINTS projected points to every
PASS-CATCHING tight end -- a TE whose frame target_share_l4 is >= --min-share (default 0.15) -- and nothing to anyone else.

    bonus = POINTS if pos == TE and target_share_l4 >= MIN_SHARE [and, with --tough-pass-d, his opponent is in the slate's
            toughest third by epa_per_dropback_allowed_l6]                                       else 0
    --with-cheap adds the cheap rule too: every non-DST player under $4,000 also gets POINTS (one combined file, one cap).

The tough-defense form is the operator's original idea; twelve seasons of history did not support it (TE points do not rise
against tough pass defenses; reports/2026-10-07-week5-options-this-week.md section 6) -- it is offered so it can be tested
directly, not as a recommendation. Output in the cheap / matchup writers' format: dk_player_id, id, display_name, pos, team,
opp, pred_own, bonus_points; every skill player of the frame once, the DST omitted. Refuses (exit 3) a frame without the
needed columns, a missing or duplicated dk_player_id, non-positive POINTS, no player with a bonus, or an existing --out.

    python scripts/te_block_file.py --season 2026 --week 5 --frame <T-70 or A3 frame.parquet> --points 2.0 --out <path>/te2-w5.csv
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


def build(frame: pd.DataFrame, points: float, min_share: float = 0.15, tough_pass_d: bool = False, with_cheap: bool = False) -> pd.DataFrame:
    """The block file's rows; raises ValueError rather than write a file the union would misread."""
    if not points > 0:
        raise ValueError(f"points must be positive (got {points})")
    if "target_share_l4" not in frame.columns:
        raise ValueError("the frame has no target_share_l4 column (pass-catching TEs cannot be identified)")
    fr = frame[frame["pos"].astype(str).isin(SKILL)].copy()
    if fr.empty:
        raise ValueError("the frame holds no skill players")
    ids = pd.to_numeric(fr["dk_player_id"], errors="coerce")
    if ids.isna().any():
        raise ValueError(f"{int(ids.isna().sum())} skill players have no dk_player_id")
    if ids.duplicated().any():
        raise ValueError(f"{int(ids.duplicated().sum())} duplicated dk_player_id values")
    share = pd.to_numeric(fr["target_share_l4"], errors="coerce").fillna(0.0)
    flag = (fr["pos"].astype(str) == "TE") & (share >= min_share)
    if tough_pass_d:
        if "epa_per_dropback_allowed_l6" not in frame.columns:
            raise ValueError("--tough-pass-d needs epa_per_dropback_allowed_l6 in the frame")
        # each team's opponent pass defense: one value per opponent (the frame carries it on the players facing it)
        d = frame.assign(epa=pd.to_numeric(frame["epa_per_dropback_allowed_l6"], errors="coerce")).dropna(subset=["epa"])
        by_opp = d.groupby(d["opp"].astype(str))["epa"].median()
        if len(by_opp) < 6:
            raise ValueError(f"only {len(by_opp)} opponents carry epa_per_dropback_allowed_l6 (the frames have it from Week 3)")
        tough = set(by_opp[by_opp.rank(pct=True, method="first") <= 1 / 3].index)
        flag &= fr["opp"].astype(str).isin(tough)
    if with_cheap:
        sal = pd.to_numeric(fr["salary"], errors="coerce")
        flag |= sal.notna() & (sal < CHEAP_MAX_SALARY)
    bonus = np.where(flag, float(points), 0.0)
    if not (bonus > 0).any():
        raise ValueError("no player carries a bonus (own_bonus would refuse the file as fractions)")
    out = pd.DataFrame({"dk_player_id": ids.astype("int64"), "id": fr.get("id", pd.Series("", index=fr.index)).astype(str),
                        "display_name": fr["display_name"].astype(str), "pos": fr["pos"].astype(str),
                        "team": fr.get("team", pd.Series("", index=fr.index)).astype(str),
                        "opp": fr.get("opp", pd.Series("", index=fr.index)).astype(str),
                        "pred_own": np.round(bonus / TILT, 4), "bonus_points": bonus})
    return out[COLUMNS].reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--points", type=float, default=2.0, help="projected points added per qualifying player (the cap)")
    ap.add_argument("--min-share", type=float, default=0.15, help="a pass-catching TE's minimum frame target_share_l4")
    ap.add_argument("--tough-pass-d", action="store_true", help="only TEs facing the slate's toughest third of pass defenses")
    ap.add_argument("--with-cheap", action="store_true", help="also give every non-DST player under $4,000 the bonus (one combined file)")
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"TE BLOCK FILE REFUSED: {a.out} exists (create-once; remove it deliberately to rewrite)", file=sys.stderr)
        return 3
    try:
        out = build(pd.read_parquet(a.frame), a.points, a.min_share, a.tough_pass_d, a.with_cheap)
    except ValueError as e:
        print(f"TE BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    tes = out[(out.pos == "TE") & (out.bonus_points > 0)].display_name.tolist()
    print(f"TE block file {a.season} W{a.week}: {int((out.bonus_points > 0).sum())} of {len(out)} skill players get +{a.points:g} "
          f"({len(tes)} TEs: {', '.join(tes[:12])}{' ...' if len(tes) > 12 else ''}; tough-pass-D only: {a.tough_pass_d}; with cheap: {a.with_cheap}) "
          f"(frame sha256 {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]}) -> {a.out} (sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
