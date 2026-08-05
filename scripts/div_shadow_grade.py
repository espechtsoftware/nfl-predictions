"""Grade the DIV_TILT shadow log (Addendum 82). Run after 4-6 weeks
of 2026 slates:

  python scripts/div_shadow_grade.py

Joins predictions.div_shadow (written automatically by every
run-projections) against realized DK points and answers the ONLY
question that justifies reviving DIV_TILT: do players where OUR
pre-blend projection diverges from the prop market outperform the
market line IN THE DIVERGENCE DIRECTION, consistently across weeks?

Adoption bar (pre-registered): the |div| >= 2 buckets must beat the
market line in the divergence direction in >= 4 of the first 6 graded
weeks, on >= 25 players/week. Anything less: the signal stays a
display-only flag (/market page) forever.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings


def main() -> None:
    d = query_df(f"""
      WITH latest AS (
        SELECT *, ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC) rn
        FROM `{settings.predictions}.div_shadow`)
      SELECT l.season, l.week, l.gsis_id, l.display_name, l.position,
             l.our_points, l.market_points, l.blend_points,
             l.consensus_div, a.dk_points AS actual
      FROM latest l
      JOIN `{settings.features}.player_week_actuals` a
        USING (gsis_id, season, week)
      WHERE l.rn = 1""")
    if d.empty:
        print("no graded rows yet — shadow log has no completed weeks")
        return
    d["vs_market"] = d.actual - d.market_points
    d["vs_blend"] = d.actual - d.blend_points
    d["bucket"] = pd.cut(d.consensus_div, [-99, -2, -0.5, 0.5, 2, 99],
                         labels=["div<=-2", "-2..-0.5", "flat",
                                 "0.5..2", "div>=2"])
    print(f"graded player-weeks: {len(d)}  weeks: "
          f"{d.groupby(['season', 'week']).ngroups}")
    g = d.groupby("bucket", observed=True).agg(
        n=("actual", "size"),
        actual_vs_market=("vs_market", "mean"),
        actual_vs_blend=("vs_blend", "mean"))
    print(g.round(2).to_string())
    # the adoption test: signed divergence must predict signed
    # market error, week by week
    print("\nper-week: does the div>=+2 bucket beat the market line?")
    wk = (d[d.consensus_div >= 2]
          .groupby(["season", "week"])
          .agg(n=("actual", "size"), edge=("vs_market", "mean")))
    if wk.empty:
        print("  (no high-divergence players yet)")
    else:
        wk["pass"] = (wk.edge > 0) & (wk.n >= 25)
        print(wk.round(2).to_string())
        print(f"\nweeks passing: {int(wk['pass'].sum())}/{len(wk)} "
              "(adoption bar: >=4 of first 6)")
    corr = np.corrcoef(d.consensus_div, d.vs_market)[0, 1]
    print(f"\nsigned corr(div, actual-market): {corr:+.3f} "
          "(positive = our disagreements carry information)")


if __name__ == "__main__":
    main()
