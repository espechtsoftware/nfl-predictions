#!/usr/bin/env python3
"""The week's PAPER DvP file for study 38 amendment 6c (the operator 10-07: "Yes, paper arm"; OPEN-DEFECTS O-40; the
reviewer's arm MIXT_QA0_DVP, lab production/s38-paper-corun-20261006 @ 0b8c9f9). Paper only: nothing on the money path
reads it.

The recipe (frozen; the reviewer's text, verbatim):
    z = the z-score, within position across the slate's skill players, of the opponent's mean DK points allowed to the
    player's position over the PRIOR 2026 weeks (< w); slope = the OLS slope (with intercept) of (actual DK points -
    FP's T-70 mean) on z, pooled over positions and over every prior 2026 week with an archived T-70 FP capture,
    players with FP >= 5, each week's z as of that week; adj = slope x z. W5: weeks "4"; the FP capture is
    proj_fp-w4.csv 8bba650e.

The file (what the arm reads, lab production/s38-paper-corun-20261006 @ 05acfee; it refuses anything else): one '#'
JSON metadata line (slope, n_slope, weeks, prior_weeks with each week's frame / FP sha256, the target frame / FP sha256,
rows, script sha256), then dk_player_id, gsis_id, pos, opp, z, slope, fp, adj_points, where adj_points is FP's ADJUSTED
mean fp + slope x z and a player FP projects at 0 (not expected to play) stays 0 -- the arm takes the correction
adj_points - fp (= the recipe's adj for FP > 0). Rows: the week's frame skill players with an FP projection and a z,
each once. The script refuses (exit 3: the arm is missing that week -- no improvised slope) a duplicated dk_player_id,
a non-finite slope, a prior week given twice or not before w, or fewer than 30 regression rows.

    python scripts/paper_dvp_file.py --season 2026 --week 5 --frame <w5 T-70 frame.parquet> --fp <w5 T-70 proj_fp csv> \
        --prior 4:<w4 T-70 frame.parquet>:<w4 T-70 proj_fp csv> [--prior 5:...] --out <abs dir>/2026-w05.csv   (the snapshot copies it as paper-dvp-2026-w05.csv)
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
            WHERE season = @season AND week < @week AND gsis_id IS NOT NULL GROUP BY 1)
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
    f = f.drop_duplicates("id")                                         # each player counts once
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
    """The week's rows in the arm's format; raises ValueError rather than write outside it."""
    if not np.isfinite(slope):
        raise ValueError(f"slope {slope} is not finite")
    z = matchup_z(frame, allowed, week)
    f = fp_by_frame_id(frame, fp)
    fr = frame.drop_duplicates("id").set_index(frame.drop_duplicates("id")["id"].astype(str))
    d = pd.DataFrame({"z": z}).join(f[~f.index.duplicated()].rename("fp")).dropna()
    d["gsis_id"] = d.index
    d["dk_player_id"] = fr.loc[d.index, "dk_player_id"].astype("Int64").astype(str).to_numpy()
    d["pos"] = fr.loc[d.index, "pos"].astype(str).to_numpy(); d["opp"] = fr.loc[d.index, "opp"].astype(str).to_numpy()
    dup = d.dk_player_id[d.dk_player_id.duplicated()]
    if len(dup) or (d.dk_player_id == "<NA>").any():
        raise ValueError(f"dk_player_id not unique / missing: {dup.tolist()[:10]}")
    d["slope"] = float(slope)
    d["adj_points"] = np.where(d.fp > 0, d.fp + slope * d.z, d.fp)    # FP's 0 (not expected to play) stays 0
    return d[["dk_player_id", "gsis_id", "pos", "opp", "z", "slope", "fp", "adj_points"]].reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True, help="week w's T-70 frame (the union's frame.parquet)")
    ap.add_argument("--fp", type=Path, required=True, help="week w's T-70 FP capture (OUT's proj_fp-<RUN_TAG>.csv)")
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
        if wk in [u["week"] for u in used]:
            raise SystemExit(f"PAPER DVP REFUSED: prior week {wk} given twice")
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
    weeks = ",".join(str(u["week"]) for u in sorted(used, key=lambda u: u["week"]))
    try:
        out = build(pd.read_parquet(a.frame), pd.read_csv(a.fp), allowed, a.week, slope)
    except ValueError as e:
        print(f"PAPER DVP REFUSED: {e}; the arm is missing this week", file=sys.stderr)
        return 3
    meta = {"study": "38 amendment 6c (paper DvP)", "season": a.season, "week": a.week, "slope": slope, "n_slope": n,
            "weeks": weeks, "prior_weeks": used, "frame_sha256": hashlib.sha256(a.frame.read_bytes()).hexdigest(),
            "fp_sha256": hashlib.sha256(a.fp.read_bytes()).hexdigest(), "rows": len(out),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with a.out.open("w") as h:
        h.write("# " + json.dumps(meta, sort_keys=True) + "\n")
        out.to_csv(h, index=False)
    print(f"PAPER DVP: week {a.week}, slope {slope:+.3f} points per z from {n} prior player-weeks (weeks {weeks}); "
          f"{len(out)} players -> {a.out} (sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
