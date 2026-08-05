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
    # THE PREREGISTERED TEST (exactly as documented above; corrected
    # review #5 round 3): statistic = sign(div) x (actual - market)
    # over |div| >= 2, evaluated on the FIRST SIX eligible weeks only
    # (frozen denominator — later weeks are exploratory).
    print("\npreregistered test: sign(div)*(actual-market), |div|>=2, "
          "first 6 eligible weeks")
    hi = d[d.consensus_div.abs() >= 2].copy()
    hi["signed_edge"] = np.sign(hi.consensus_div) * hi.vs_market
    wk = (hi.groupby(["season", "week"])
            .agg(n=("actual", "size"), edge=("signed_edge", "mean")))
    wk = wk[wk.n >= 25]  # eligibility: >=25 qualifying players
    if wk.empty:
        print("  (no eligible weeks yet)")
    else:
        first6 = wk.sort_index().head(6)
        first6["pass"] = first6.edge > 0
        print(first6.round(2).to_string())
        print(f"\nweeks passing: {int(first6['pass'].sum())}/{len(first6)}"
              " (adoption bar: >=4 of 6; do not grade past week 6)")
        if len(wk) > 6:
            print(f"(exploratory later weeks: {len(wk) - 6} — "
                  "not part of the preregistered verdict)")
    corr = np.corrcoef(d.consensus_div, d.vs_market)[0, 1]
    print(f"\nsigned corr(div, actual-market): {corr:+.3f} "
          "(positive = our disagreements carry information)")


if __name__ == "__main__":
    main()
