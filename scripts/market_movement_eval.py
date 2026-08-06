"""Workstream E §11.1: does prop-market MOVEMENT (open -> last
pre-lock) or cross-book DISPERSION carry information our projection
does not already have?

Strictly point-in-time: only snapshots taken BEFORE the game's
commence_time are eligible, and the "latest" line is the last such
snapshot — never a closing line stamped after the decision cutoff.

Gate (plan §11.5 step 2): movement/dispersion must improve held-out
player residuals. If it does not, it cannot justify a feature, a
scenario family, or wider distributions.

  python scripts/market_movement_eval.py
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from nfl_dfs.bq import query_df  # noqa: E402

MARKETS = ("player_pass_yds", "player_rush_yds", "player_reception_yds",
           "player_receptions", "player_anytime_td")


def load():
    return query_df("""
      WITH pl AS (
        SELECT season, week, player, market, bookmaker, point, price,
               snapshot_ts, commence_time,
               ROW_NUMBER() OVER (
                 PARTITION BY season, week, player, market, bookmaker
                 ORDER BY snapshot_ts ASC) AS rn_first,
               ROW_NUMBER() OVER (
                 PARTITION BY season, week, player, market, bookmaker
                 ORDER BY snapshot_ts DESC) AS rn_last
        FROM `nfl_raw.prop_lines`
        WHERE point IS NOT NULL
          AND SAFE_CAST(snapshot_ts AS TIMESTAMP) < SAFE_CAST(commence_time AS TIMESTAMP)
          AND season BETWEEN 2023 AND 2025),
      agg AS (
        SELECT season, week, player, market,
               AVG(IF(rn_first = 1, point, NULL)) AS open_pt,
               AVG(IF(rn_last = 1, point, NULL)) AS last_pt,
               STDDEV(IF(rn_last = 1, point, NULL)) AS book_sd,
               COUNT(DISTINCT IF(rn_last = 1, bookmaker, NULL)) AS n_books,
               COUNT(DISTINCT snapshot_ts) AS n_snaps
        FROM pl GROUP BY season, week, player, market)
      SELECT * FROM agg WHERE open_pt IS NOT NULL AND last_pt IS NOT NULL
    """)


def main():
    mv = load()
    print(f"market rows: {len(mv):,} "
          f"({mv.season.min()}-{mv.season.max()})")
    mv["move"] = mv.last_pt - mv.open_pt
    mv["move_pct"] = mv.move / mv.open_pt.replace(0, np.nan)

    # our stored projections vs actuals, joined by name (edge join —
    # names.py normalization, same as every other market path)
    # OUR historical projections = the canonical panel's immutable
    # player snapshot (point-in-time by construction; the live
    # player_projections table has no 2023-25 history).
    proj = query_df("""
      SELECT season, week, name AS player, gsis_id,
             proj AS proj_points, actual
      FROM `nfl_predictions.slate_player_features`
      WHERE panel_run_id = '20260805-hf5' AND season BETWEEN 2023 AND 2025
        AND actual IS NOT NULL""")
    if proj.empty:
        print("no stored projections for 2023-2025 — falling back to the "
              "market's own predictive check (movement vs realized yards)")
        return market_only(mv)

    from nfl_dfs.names import norm_name
    mv["key"] = mv.player.map(norm_name)
    proj["key"] = proj.player.map(norm_name)
    piv = mv.pivot_table(index=["season", "week", "key"], columns="market",
                         values=["move", "book_sd"], aggfunc="mean")
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    d = proj.merge(piv.reset_index(), on=["season", "week", "key"],
                   how="inner")
    print(f"joined player-weeks: {len(d):,}")
    d["resid"] = d.actual - d.proj_points

    print("\ncorrelation of market movement/dispersion with OUR residual:")
    for c in sorted(d.columns):
        if c.startswith(("move_", "book_sd_")) and d[c].notna().sum() > 300:
            r = np.corrcoef(d[c].fillna(0), d.resid)[0, 1]
            print(f"  {c:<34} n={int(d[c].notna().sum()):>6}  "
                  f"corr {r:+.4f}")

    # decile check on the strongest movement market
    best = max((c for c in d.columns if c.startswith("move_")
                and d[c].notna().sum() > 300),
               key=lambda c: abs(np.corrcoef(d[c].fillna(0), d.resid)[0, 1]),
               default=None)
    if best:
        q = pd.qcut(d[best].fillna(0), 5, duplicates="drop")
        print(f"\nresidual by {best} quintile:")
        print(d.groupby(q, observed=True).resid.agg(["mean", "size"]).round(2)
              .to_string())


def market_only(mv):
    print("\nmovement magnitude by market (sanity):")
    print(mv.groupby("market").agg(
        n=("move", "size"), mean_abs_move=("move", lambda s: s.abs().mean()),
        mean_book_sd=("book_sd", "mean")).round(3).to_string())


if __name__ == "__main__":
    main()
