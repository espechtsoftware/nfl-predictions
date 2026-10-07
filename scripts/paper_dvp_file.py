#!/usr/bin/env python3
"""The week's PAPER DvP file for study 38 amendment 6c (the operator 10-07: "Yes, paper arm"; the reviewer's frozen
walk-forward recipe; OPEN-DEFECTS O-40). Paper only: nothing on the money path reads it.

The matchup score (point in time): for each QB / RB / WR / TE on week w's T-70 frame, the opponent's mean DK points
allowed to the player's position over the PRIOR weeks of the season (< w), z-scored within position across the slate's
players that have one. The DST gets no adjustment.

The slope (walk-forward): slope_w = the OLS slope (with intercept) of FP's residual (actual DK points - FP's T-70 mean)
on that z, pooled over positions and over every PRIOR week that had an archived T-70 FP capture, players with FP >= 5,
each week's z computed as of that week. W5 uses W4 alone (disclosed: one week); W6 uses W4-W5; ... No cap, no shrinkage.

Output (CSV after one '#' metadata line): dk_player_id, gsis_id, pos, opp, z, slope, fp, adj_points (= fp + slope x z;
a player FP projects at 0 -- not expected to play -- stays 0), for the week's frame players with an FP projection and a z.

    python scripts/paper_dvp_file.py --season 2026 --week 5 --frame <w5 T-70 frame.parquet> --fp <w5 T-70 proj_fp csv> \
        --prior 4:<w4 T-70 frame.parquet>:<w4 T-70 proj_fp csv> [--prior 5:...] --out paper-dvp-w05.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
FP_MIN = 5.0

DVP_SQL = """
WITH pm AS (SELECT gsis_id, ANY_VALUE(position HAVING MAX week) AS position FROM `{raw}.rosters_weekly`
            WHERE season = @season AND gsis_id IS NOT NULL GROUP BY 1)
SELECT s.opponent AS def_team, a.week, pm.position, SUM(a.dk_points) AS fp_allowed
FROM `{features}.player_week_actuals` a
JOIN `{features}.schedule_long` s ON s.team = a.team AND s.season = a.season AND s.week = a.week
JOIN pm ON pm.gsis_id = a.gsis_id
WHERE a.season = @season AND a.week < @week AND pm.position IN ('QB', 'RB', 'WR', 'TE')
GROUP BY 1, 2, 3"""


def fp_by_frame_id(frame: pd.DataFrame, fp: pd.DataFrame) -> pd.Series:
    """FP's T-70 mean per frame id (the proj_fp capture is keyed by dk_draftable_id, as apply_proj_source reads it)."""
    m = dict(zip(fp.dk_draftable_id.astype("Int64").astype(str), pd.to_numeric(fp.fp, errors="coerce")))
    return pd.Series(frame.dk_draftable_id.astype("Int64").astype(str).map(m).to_numpy(), index=frame["id"].astype(str))


def matchup_z(frame: pd.DataFrame, allowed: pd.DataFrame, week: int) -> pd.Series:
    """z of the opponent's mean DK points allowed to the position over weeks < week, within position across the
    frame's skill players that have a value. Index: frame id."""
    prior = allowed[allowed.week < week].groupby(["def_team", "position"]).fp_allowed.mean().rename("dvp").reset_index()
    f = frame[frame.pos.astype(str).isin(SKILL)][["id", "pos", "opp"]].copy()
    f["id"] = f["id"].astype(str)
    f = f.merge(prior, left_on=["opp", "pos"], right_on=["def_team", "position"], how="left")
    z = f.groupby("pos").dvp.transform(lambda s: (s - s.mean()) / s.std(ddof=0) if s.notna().sum() > 1 and s.std(ddof=0) > 0 else s * np.nan)
    return pd.Series(z.to_numpy(), index=f["id"].to_numpy())


def walk_forward_slope(prior: list[tuple[int, pd.DataFrame, pd.DataFrame, pd.Series]], allowed: pd.DataFrame) -> tuple[float | None, int]:
    """prior: (week, frame, fp capture, actual DK points by frame id). Pooled OLS slope of (actual - FP) on z, players
    with FP >= 5 and a z and an actual; returns (slope, n)."""
    xs, ys = [], []
    for week, frame, fp, actual in prior:
        z = matchup_z(frame, allowed, week)
        f = fp_by_frame_id(frame, fp)
        d = pd.DataFrame({"z": z}).join(f.rename("fp")).join(actual.rename("y"))
        d = d.dropna()
        d = d[d.fp >= FP_MIN]
        xs.append(d.z.to_numpy()); ys.append((d.y - d.fp).to_numpy())
    x = np.concatenate(xs) if xs else np.array([]); y = np.concatenate(ys) if ys else np.array([])
    if len(x) < 30:
        return None, int(len(x))
    return float(np.polyfit(x, y, 1)[0]), int(len(x))


def build(frame: pd.DataFrame, fp: pd.DataFrame, allowed: pd.DataFrame, week: int, slope: float) -> pd.DataFrame:
    z = matchup_z(frame, allowed, week)
    f = fp_by_frame_id(frame, fp)
    fr = frame.drop_duplicates("id").set_index(frame.drop_duplicates("id")["id"].astype(str))
    d = pd.DataFrame({"z": z}).join(f.rename("fp")).dropna()
    d["gsis_id"] = d.index
    d["dk_player_id"] = fr.loc[d.index, "dk_player_id"].astype("Int64").astype(str).to_numpy()
    d["pos"] = fr.loc[d.index, "pos"].astype(str).to_numpy(); d["opp"] = fr.loc[d.index, "opp"].astype(str).to_numpy()
    d["slope"] = slope
    d["adj_points"] = np.where(d.fp > 0, d.fp + slope * d.z, d.fp)    # FP's 0 (not expected to play) stays 0
    return d[["dk_player_id", "gsis_id", "pos", "opp", "z", "slope", "fp", "adj_points"]].reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--fp", type=Path, required=True)
    ap.add_argument("--prior", action="append", default=[], help="WEEK:FRAME:FP_CSV of a prior week with an archived T-70 FP capture")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    allowed = query_df(DVP_SQL.format(raw=settings.raw, features=settings.features), {"season": a.season, "week": a.week})
    acts = query_df(f"SELECT gsis_id, week, dk_points FROM `{settings.features}.player_week_actuals` "
                    f"WHERE season = @season AND week < @week", {"season": a.season, "week": a.week})
    prior, used = [], []
    for spec in a.prior:
        wk, fpath, cpath = spec.split(":", 2)
        wk = int(wk)
        if wk >= a.week:
            raise SystemExit(f"PAPER DVP REFUSED: prior week {wk} is not before week {a.week}")
        frame_v = pd.read_parquet(fpath); fp_v = pd.read_csv(cpath)
        act_v = acts[acts.week == wk].assign(gsis_id=lambda d: d.gsis_id.astype(str)).set_index("gsis_id").dk_points
        prior.append((wk, frame_v, fp_v, act_v))
        used.append({"week": wk, "frame_sha256": hashlib.sha256(Path(fpath).read_bytes()).hexdigest(),
                     "fp_sha256": hashlib.sha256(Path(cpath).read_bytes()).hexdigest()})
    slope, n = walk_forward_slope(prior, allowed)
    if slope is None:
        print(f"PAPER DVP REFUSED: {n} prior player-weeks with FP >= {FP_MIN} (< 30): no slope; the arm is missing this week",
              file=sys.stderr)
        return 3
    out = build(pd.read_parquet(a.frame), pd.read_csv(a.fp), allowed, a.week, slope)
    meta = {"study": "38 amendment 6c (paper DvP)", "season": a.season, "week": a.week, "slope": slope, "n_slope": n,
            "prior_weeks": used, "frame_sha256": hashlib.sha256(a.frame.read_bytes()).hexdigest(),
            "fp_sha256": hashlib.sha256(a.fp.read_bytes()).hexdigest(), "rows": len(out),
            "note": "W5's slope rests on one week (W4)" if [u["week"] for u in used] == [4] else ""}
    with a.out.open("w") as h:
        h.write("# " + json.dumps(meta, sort_keys=True) + "\n")
        out.to_csv(h, index=False)
    print(f"PAPER DVP: week {a.week}, slope {slope:+.3f} points per z from {n} prior player-weeks "
          f"(weeks {[u['week'] for u in used]}); {len(out)} players -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
