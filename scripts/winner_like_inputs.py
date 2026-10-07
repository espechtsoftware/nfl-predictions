#!/usr/bin/env python3
"""The per-player inputs of study 48's winner-likeness score for one T-70 frame (study 48b's order; the operator 10-07:
"Test tonight, aim for Week 5"). Writes a CSV keyed by the frame id:

    id, own_proj, td_l4, td_l8, pass_td_l4, att_l4

* own_proj = FP's PROJECTED ownership for the frame player, from the ownership_fp export the build already makes
  (`pred_own`, a monotone rescale of FP's raw projection, so its ranks are FP's); the score ranks it among the slate's
  QB / RB / WR / TE.
* the lags = REGULAR-season games (weeks 1-18) strictly before (season, week), across seasons, the player's last 4 / 8
  games with a stat line (nfl_features.player_week_actuals): rushing + receiving TDs; the QB's passing TDs and pass
  attempts SUMMED over his last 4 (the lab's definition; NOT the graph layer's mean).
Nothing from the slate's week enters. The frame's own lagged columns are read by the union itself.

    python scripts/winner_like_inputs.py --season 2026 --week 5 --frame <run>/frame.parquet --own <ownership_fp.csv> --out <csv>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

LAG_SQL = """
WITH g AS (
  SELECT gsis_id, COALESCE(rush_tds, 0) + COALESCE(rec_tds, 0) AS tds, COALESCE(pass_tds, 0) AS pass_tds,
         COALESCE(pass_attempts, 0) AS att,
         ROW_NUMBER() OVER (PARTITION BY gsis_id ORDER BY season DESC, week DESC) AS rn
  FROM `{features}.player_week_actuals`
  WHERE has_stat_line AND week <= 18 AND (season < @season OR (season = @season AND week < @week))
)
SELECT gsis_id, SUM(IF(rn <= 4, tds, 0)) AS td_l4, SUM(tds) AS td_l8, SUM(IF(rn <= 4, pass_tds, 0)) AS pass_td_l4,
       SUM(IF(rn <= 4, att, 0)) AS att_l4
FROM g WHERE rn <= 8 GROUP BY gsis_id"""


def build(frame: pd.DataFrame, own: pd.DataFrame, lags: pd.DataFrame) -> pd.DataFrame:
    fr = frame[["id"]].copy()
    fr["id"] = fr["id"].astype(str)
    o = own.assign(id=own["id"].astype(str)).drop_duplicates("id").set_index("id")["pred_own"]
    lg = lags.assign(gsis_id=lags.gsis_id.astype(str)).drop_duplicates("gsis_id").set_index("gsis_id")
    out = fr.assign(own_proj=fr["id"].map(o))
    for c in ("td_l4", "td_l8", "pass_td_l4", "att_l4"):
        out[c] = pd.to_numeric(fr["id"].map(lg[c]), errors="coerce").fillna(0.0) if c in lg.columns else 0.0
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--own", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    frame = pd.read_parquet(a.frame)
    own = pd.read_csv(a.own, dtype={"id": str})
    if "pred_own" not in own.columns or "id" not in own.columns:
        print(f"WINNER INPUTS REFUSED: {a.own} has no id / pred_own columns", file=sys.stderr)
        return 2
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    lags = query_df(LAG_SQL.format(features=settings.features), {"season": a.season, "week": a.week})
    out = build(frame, own, lags)
    skill = frame.pos.astype(str).isin(("QB", "RB", "WR", "TE")).to_numpy()
    cover = float(out.own_proj[skill].notna().mean()) if skill.any() else 0.0
    if cover < 0.9:
        print(f"WINNER INPUTS REFUSED: FP projected ownership covers {cover:.0%} of the frame's skill players (< 90%)",
              file=sys.stderr)
        return 3
    out.to_csv(a.out, index=False)
    print(f"WINNER INPUTS: {len(out)} frame players; FP ownership on {cover:.0%} of skill players; lags for "
          f"{int((out[['td_l8', 'att_l4']].sum(axis=1) > 0).sum())} players -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
