#!/usr/bin/env python3
"""The week's PAPER boom-chance block file (the operator 10-10: "Yes, on paper with the 16:50 stop (Recommended)"; study 38
amendment 6z7, MIXT_QA0_BOOMBLOCK8 -- the 8-row paper block in place of the cheap block, 6z4 / 6z6's pattern; the lab
reviewer's design). The union's --term-block-* vehicle builds N rows on projection + min(tilt x pred_own, cap); pred_own =
bonus / 0.20 at tilt 0.20 / cap 2.0 adds the bonus:

    p20   = OUR model's pre-lock probability of 20+ DK points (nfl_predictions.player_projections.p_20_plus) in the LAST
            generation of --season / --week strictly before --as-of, joined to the frame by dk_player_id;
    res   = p20 minus a DEGREE-2 polynomial fit of p20 on the frame's projection (`mean_projection`, the number the book is
            built on: FP's after the override), within position (QB / RB / WR / TE, all salaries), over the frame's players
            with both values; a position with MIN_FIT or fewer such players gets none;
    z     = res standardized within position (pandas' std, ddof 1);
    bonus = clip(1.0 x z, 0, 2) for QB / RB / WR / TE (td_value_block_file.py's scale); no p20 (or no fit) -> 0.

Why degree 2 (the lab reviewer's call, 10-10, before any Week-5 outcome; outcome-blind: the bonus spread by projection band on
Week 4's frame and Week 4's last pre-lock generation). P(20+) is convex in the projection, so a straight line leaves positive
residuals at both ends and the bonus lands on the sub-3-point players -- the opposite of "boom beyond the projection":

    projection band      <= 3    3-6    6-9    9-12   12-15   > 15
    players               93     66     43     29      27     34
    linear:  with bonus   85     12      1      6       6     25    (mean bonus 0.60 / 0.03 / 0.03 / 0.14 / 0.18 / 0.92)
    degree 2: with bonus  54     34     17     18      12     17    (mean bonus 0.11 / 0.12 / 0.32 / 0.62 / 0.39 / 0.56)

Output (plain CSV, the format own_bonus reads; no metadata line): dk_player_id, id, display_name, pos, team, opp, pred_own
(= bonus / 0.20), bonus_points, p_20_plus, proj, z, generated_at; every skill player of the frame once (a bonus of 0 included), the
DST omitted. Refuses (exit 3): an --as-of without a time zone; no generation before --as-of; a generation more than
--max-age-hours (default 36, the lab reviewer's: a missed project-slate run) before --as-of; a
dk_player_id repeated in the generation or the frame; a frame without skill players; a week where no player carries a bonus.

    python reports/2026-10-10-boom/boom_block_file.py --season 2026 --week 5 --frame <the T-70 union frame.parquet> \
        --as-of <UTC, just after Sunday's T-70 projection run> --out <path>/paper-boom-w05.csv
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
TILT = 0.20
SLOPE, CAP = 1.0, 2.0                               # bonus = clip(SLOPE x z, 0, CAP): the td_value scale
MIN_FIT = 5                                         # a position's fit needs more than MIN_FIT players with both values
FIT_DEG = 2                                         # the polynomial degree of p20's fit on the projection (see the docstring)
COLUMNS = ["dk_player_id", "id", "display_name", "pos", "team", "opp", "pred_own", "bonus_points", "p_20_plus", "proj", "z",
           "generated_at"]

P20_SQL = """
WITH g AS (SELECT MAX(generated_at) AS ts FROM `{pred}.player_projections`
           WHERE season = @season AND week = @week AND generated_at < TIMESTAMP(@as_of))
SELECT CAST(p.dk_player_id AS STRING) AS dk_player_id, ANY_VALUE(p.p_20_plus) AS p20, COUNT(*) AS n,
       FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', ANY_VALUE(g.ts)) AS ts
FROM `{pred}.player_projections` p JOIN g ON p.generated_at = g.ts
WHERE p.season = @season AND p.week = @week
GROUP BY 1"""


def build(frame: pd.DataFrame, p20: pd.DataFrame, generated_at: str) -> pd.DataFrame:
    """The block file's rows; raises ValueError rather than write a file the union would misread."""
    n = pd.to_numeric(p20["n"], errors="coerce").fillna(1) if "n" in p20.columns else pd.Series(1, index=p20.index)
    if (n > 1).any() or p20.dk_player_id.astype(str).duplicated().any():
        raise ValueError("a dk_player_id repeats in the projection generation")
    fr = frame.copy()
    sk = fr.pos.astype(str).isin(SKILL)
    if not sk.any():
        raise ValueError("the frame has no skill players")
    if fr.loc[sk, "dk_player_id"].isna().any():
        raise ValueError("a skill player has no dk_player_id")
    out = fr[sk].copy()
    out["dk_player_id"] = out.dk_player_id.astype("Int64").astype(str)
    if out.dk_player_id.duplicated().any():
        raise ValueError(f"dk_player_id repeats in the frame: {out.dk_player_id[out.dk_player_id.duplicated()].tolist()[:10]}")
    pm = dict(zip(p20.dk_player_id.astype(str), pd.to_numeric(p20.p20, errors="coerce")))
    out["p20"] = out.dk_player_id.map(pm)
    out["proj"] = pd.to_numeric(out.mean_projection, errors="coerce")
    out["res"] = np.nan
    for pos in SKILL:
        g = out[(out.pos == pos) & out.p20.notna() & out.proj.notna()]
        if len(g) > MIN_FIT:
            b = np.polyfit(g.proj, g.p20, FIT_DEG)
            out.loc[g.index, "res"] = g.p20 - np.polyval(b, g.proj)
    out["z"] = out.groupby("pos").res.transform(lambda v: (v - v.mean()) / v.std())
    out["bonus_points"] = np.clip(SLOPE * out.z.fillna(0.0), 0.0, CAP)
    out["pred_own"] = out.bonus_points / TILT
    out["p_20_plus"] = out.p20
    out["generated_at"] = generated_at
    out["id"] = out["id"].astype(str)
    for c in ("display_name", "pos", "team", "opp"):
        out[c] = out[c].astype(str)
    out = out[COLUMNS].reset_index(drop=True)
    if not np.isfinite(out[["pred_own", "bonus_points"]].to_numpy(float)).all():
        raise ValueError("a non-finite bonus")
    if float(out.pred_own.max()) <= 1.0:
        raise ValueError("no player carries a bonus (own_bonus would refuse the file as fractions)")
    return out


def check_timing(generated_at: str, as_of: str, max_age_hours: float) -> None:
    """Refuses (ValueError) an --as-of without a time zone, a generation at / after --as-of, or one older than the limit."""
    a = pd.Timestamp(as_of)
    if a.tzinfo is None:
        raise ValueError(f"--as-of {as_of} has no time zone (give UTC, e.g. 2026-10-11T15:45:00Z)")
    t = pd.Timestamp(generated_at)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    if t >= a:
        raise ValueError(f"generation {generated_at} is not before --as-of {as_of}")
    if (a - t) > pd.Timedelta(hours=max_age_hours):
        raise ValueError(f"generation {generated_at} is more than {max_age_hours:g} h before --as-of {as_of} (a missed run?)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True)
    ap.add_argument("--as-of", required=True, help="UTC ISO time; the last projection generation strictly before it")
    ap.add_argument("--max-age-hours", type=float, default=36.0, help="refuse a generation older than this before --as-of")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if pd.Timestamp(a.as_of).tzinfo is None:
        print(f"BOOM BLOCK FILE REFUSED: --as-of {a.as_of} has no time zone (give UTC)", file=sys.stderr)
        return 3
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    p20 = query_df(P20_SQL.format(pred=settings.predictions), {"season": a.season, "week": a.week, "as_of": a.as_of})
    if p20.empty or p20.ts.isna().all():
        print(f"BOOM BLOCK FILE REFUSED: no projection generation for {a.season} W{a.week} before {a.as_of}", file=sys.stderr)
        return 3
    ts = str(p20.ts.iloc[0])
    try:
        check_timing(ts, a.as_of, a.max_age_hours)
        out = build(pd.read_parquet(a.frame), p20, ts)
    except ValueError as e:
        print(f"BOOM BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    out.to_csv(a.out, index=False)
    print(f"BOOM BLOCK FILE: week {a.week}, generation {ts} (before {a.as_of}), {len(out)} skill players, "
          f"{int((out.bonus_points > 0).sum())} with a bonus ({int((out.bonus_points >= CAP).sum())} at +{CAP:g}), "
          f"{int(out.p_20_plus.isna().sum())} without a p_20_plus (0); frame {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]} -> {a.out} "
          f"(sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
