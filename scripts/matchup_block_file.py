#!/usr/bin/env python3
"""The week's LIVE matchup term-block file (the operator 10-07: "Please try to tackle the 'matchup bonus' one this week";
the outside reviewer's path: "a capped block like the prior-top one"). The union's --term-block-* vehicle builds N rows on
projection + min(tilt x pred_own, cap); with pred_own = b_matchup / 0.20, tilt 0.20 and cap 2.0 the block adds exactly the
outside reviewer's matchup bonus (Experiment A, make_factor_files.py at review/outside-fill-order-20261006 0ad813b2), the
same b_matchup as study 38's paper arm MIXT_QA0_MATCHUPX (scripts/paper_factor_file.py, whose points-allowed blend this
script imports):

    b_matchup = clip(1.0 x z, 0, 2): z within position, across ALL the frame's skill players (pandas' std, ddof 1, + 1e-9;
    a missing z counts 0), of the opponent's DK points allowed to the position per game, (6 x the prior season's per-game
    mean + this season's sum over weeks < w) / (6 + this season's games), regular season, positions from player_week_role;
    a defense missing from the prior season gets the position mean.

No FP values: the union's --min-proj 1.0 already drops every player FP projects below 1, so the file holds public-data
facts only and is tracked beside the prior-top files. Output (the format own_bonus reads): dk_player_id, id, display_name,
pos, team, opp, pred_own (= b_matchup / 0.20), bonus_points (= b_matchup); every skill player of the frame once (a bonus
of 0 included), the DST omitted. Refuses (exit 3) a frame without skill players, a missing or duplicated dk_player_id, or
a week where no player carries a bonus (own_bonus would read it as fractions).

    python scripts/matchup_block_file.py --season 2026 --week 5 --frame <a Week-5 frame.parquet> --out <path>/matchup-w5.csv
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_factor_file as PF  # noqa: E402  (the approved points-allowed blend and constants, de4f4cb3)

TILT = 0.20
COLUMNS = ["dk_player_id", "id", "display_name", "pos", "team", "opp", "pred_own", "bonus_points"]


def build(frame: pd.DataFrame, allowed: pd.DataFrame, season: int, week: int) -> tuple[pd.DataFrame, int]:
    """The block file's rows and the unmatched-opponent count; raises ValueError rather than write a file the union
    would misread."""
    fr = frame.drop_duplicates("dk_player_id").reset_index(drop=True).copy()
    sk = fr.pos.astype(str).isin(PF.SKILL)
    if not sk.any():
        raise ValueError("the frame has no skill players")
    if fr.loc[sk, "dk_player_id"].isna().any():
        raise ValueError("a skill player has no dk_player_id")
    apg = PF.allowed_per_game(allowed, season, week)
    fr["matchup_raw"] = [apg.get((o, p), np.nan) for o, p in zip(fr.opp.astype(str), fr.pos.astype(str))]
    z = fr[sk].groupby("pos").matchup_raw.transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    out = fr[sk].copy()
    out["bonus_points"] = np.clip(PF.WEIGHTS["matchup"] * z.fillna(0), *PF.CLIPS["matchup"])
    out["pred_own"] = out.bonus_points / TILT
    unmatched = int(out.matchup_raw.isna().sum())
    out["dk_player_id"] = out.dk_player_id.astype("Int64").astype(str)
    out["id"] = out["id"].astype(str)
    for c in ("display_name", "pos", "team", "opp"):
        out[c] = out[c].astype(str)
    out = out[COLUMNS].reset_index(drop=True)
    if out.dk_player_id.duplicated().any():
        raise ValueError(f"dk_player_id repeats: {out.dk_player_id[out.dk_player_id.duplicated()].tolist()[:10]}")
    if not np.isfinite(out[["pred_own", "bonus_points"]].to_numpy(float)).all():
        raise ValueError("a non-finite bonus")
    if float(out.pred_own.max()) <= 1.0:
        raise ValueError("no player carries a matchup bonus (own_bonus would refuse the file as fractions)")
    return out, unmatched


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    allowed = query_df(PF.ALLOWED_SQL.format(features=settings.features), {"prior": a.season - 1, "season": a.season, "week": a.week})
    try:
        out, unmatched = build(pd.read_parquet(a.frame), allowed, a.season, a.week)
    except ValueError as e:
        print(f"MATCHUP BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    out.to_csv(a.out, index=False)
    by_pos = out[out.bonus_points > 0].groupby("pos").size().to_dict()
    print(f"MATCHUP BLOCK FILE: week {a.week}, {len(out)} skill players, {int((out.bonus_points > 0).sum())} with a bonus "
          f"{by_pos}, mean {out.bonus_points.mean():.3f}, unmatched opponents {unmatched}; frame "
          f"{hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]} -> {a.out} (sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
