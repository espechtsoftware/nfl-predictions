"""Market-implied player distributions from alternate prop lines
(research round 10). No new model — de-vig DK's alternate-line ladders
into implied P(over x) curves, then backtest the market's implied
median and q90 against actuals, head-to-head with our quick-LGB q90.

Method: latest pre-kick snapshot per (player, week, market); pair
Over/Under at the same point when both exist (pairwise de-vig:
p = inv(over) / (inv(over) + inv(under))), else single-sided with the
book's typical ~5% one-way margin removed. Enforce monotonicity of
P(over x) in x (isotonic-style pooling), interpolate implied median and
q90. Score on matched panel actuals (y_rec_yards / y_rush_yards).
"""
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"

MARKETS = {"player_reception_yds_alternate": ("y_rec_yards", "recv"),
           "player_rush_yds_alternate": ("y_rush_yards", "rush")}

props = query_df(f"""
  WITH latest AS (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY season, week, market, player, CAST(point AS STRING), outcome_name
      ORDER BY snapshot_ts DESC) rn
    FROM `{settings.raw}.prop_lines`
    WHERE market IN ('player_reception_yds_alternate',
                     'player_rush_yds_alternate')
      AND bookmaker = 'draftkings' AND TIMESTAMP(snapshot_ts) < TIMESTAMP(commence_time)
  )
  SELECT season, week, market, player, point, outcome_name, price
  FROM latest WHERE rn = 1""")
print(f"prop rows {len(props):,}")


def implied_curve(g):
    """P(over point) ladder for one player-week-market, de-vigged."""
    def imp(american):
        a = float(american)
        return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)

    pts = []
    for pt, gg in g.groupby("point"):
        inv = {r.outcome_name: imp(r.price) for r in gg.itertuples()}
        if "Over" in inv and "Under" in inv:
            p = inv["Over"] / (inv["Over"] + inv["Under"])
        elif "Over" in inv:
            p = inv["Over"] / 1.05
        else:
            continue
        pts.append((pt, min(max(p, 1e-4), 1 - 1e-4)))
    if len(pts) < 3:
        return None
    pts.sort()
    x = np.array([p[0] for p in pts])
    y = np.array([p[1] for p in pts])
    # enforce monotone nonincreasing P(over x) via cummin
    y = np.minimum.accumulate(y)
    return x, y


def q_from_curve(x, y, q):
    """quantile: smallest x where P(over x) <= 1-q (P(X<=x) >= q)."""
    tgt = 1 - q
    if y[-1] > tgt:   # tail beyond ladder: extrapolate geometrically
        return x[-1] + (x[-1] - x[0]) * 0.15
    if y[0] <= tgt:
        return x[0]
    return float(np.interp(tgt, y[::-1], x[::-1]))


panel = pd.read_parquet(f"{S}/panel.parquet")
names = query_df(f"""
  SELECT gsis_id, ANY_VALUE(full_name) player_name
  FROM `{settings.raw}.rosters_weekly` GROUP BY gsis_id""")
panel = panel.merge(names, on="gsis_id", how="left")


def norm(s):
    import re
    s = re.sub(r"[^a-z ]", "", str(s).lower())
    p = s.split()
    return (p[0][0] + " " + p[-1]) if len(p) >= 2 else s


rows = []
for (season, week, market, player), g in props.groupby(
        ["season", "week", "market", "player"]):
    c = implied_curve(g)
    if c is None:
        continue
    x, y = c
    rows.append({"season": season, "week": week, "market": market,
                 "player": player, "n_pts": len(x),
                 "mkt_med": q_from_curve(x, y, 0.5),
                 "mkt_q90": q_from_curve(x, y, 0.9)})
mk = pd.DataFrame(rows)
mk["key"] = mk.player.map(norm)
panel["key"] = panel.player_name.map(norm)
print(f"implied curves: {len(mk):,} player-weeks "
      f"(median ladder size {mk.n_pts.median():.0f})")


def pinball(y, qp, q):
    d = y - qp
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


for market, (ycol, label) in MARKETS.items():
    m = mk[mk.market == market].merge(
        panel[["key", "season", "week", ycol, "position"]],
        on=["key", "season", "week"])
    m = m[m[ycol].notna()]
    y = m[ycol].to_numpy(float)
    med, q90 = m.mkt_med.to_numpy(), m.mkt_q90.to_numpy()
    print(f"\n== {label}: n={len(m):,} matched player-weeks ==")
    print(f"  market median: MAE {np.abs(y - med).mean():.2f}  "
          f"P(y<=med)={np.mean(y <= med):.3f}")
    print(f"  market q90:  pinball90 {pinball(y, q90, .9):.3f}  "
          f"P(y<=q90)={np.mean(y <= q90):.3f}")
mk.to_parquet(f"{S}/market_implied.parquet", index=False)
print("\nPROP_IMPLIED_DONE", flush=True)
