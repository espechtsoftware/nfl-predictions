"""Market-implied q90 vs our LGB q90, same 2025 player-weeks."""
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

panel = pd.read_parquet(f"{S}/panel.parquet")
names = query_df(f"SELECT gsis_id, ANY_VALUE(full_name) player_name FROM `{settings.raw}.rosters_weekly` GROUP BY gsis_id")
panel = panel.merge(names, on="gsis_id", how="left")
feats = open(f"{S}/features.txt").read().split()
panel["pos_code"] = panel.position.map({p: i for i, p in enumerate(["QB","RB","WR","TE"])})
X_cols = sorted(feats) + ["pos_code"]
for c in X_cols:
    panel[c] = pd.to_numeric(panel[c], errors="coerce")

mk = pd.read_parquet(f"{S}/market_implied.parquet")

def norm(s):
    import re
    s = re.sub(r"[^a-z ]", "", str(s).lower()); p = s.split()
    return (p[0][0] + " " + p[-1]) if len(p) >= 2 else s
panel["key"] = panel.player_name.map(norm)

def pinball(y, qp, q=0.9):
    d = y - qp
    return float(np.mean(np.maximum(q*d, (q-1)*d)))

common = dict(n_estimators=600, learning_rate=0.04, num_leaves=63,
              min_child_samples=40, subsample=0.9, colsample_bytree=0.8,
              n_jobs=4, random_state=7, verbose=-1)
for market, ycol, label in [("player_reception_yds_alternate","y_rec_yards","recv"),
                            ("player_rush_yds_alternate","y_rush_yards","rush")]:
    tr = panel[(panel.season <= 2024) & panel[ycol].notna()]
    q90m = lgb.LGBMRegressor(objective="quantile", alpha=0.9, **common).fit(tr[X_cols], tr[ycol])
    te = panel[(panel.season == 2025) & panel[ycol].notna()].copy()
    te["lgb_q90"] = q90m.predict(te[X_cols])
    m = mk[(mk.market == market) & (mk.season == 2025)].merge(
        te[["key","season","week",ycol,"lgb_q90"]], on=["key","season","week"])
    y = m[ycol].to_numpy(float)
    print(f"== {label} 2025, n={len(m):,} matched ==")
    print(f"  market q90: pinball {pinball(y, m.mkt_q90.to_numpy()):.3f}  cov {np.mean(y <= m.mkt_q90):.3f}")
    print(f"  LGB    q90: pinball {pinball(y, m.lgb_q90.to_numpy()):.3f}  cov {np.mean(y <= m.lgb_q90):.3f}")
    # disagreement leverage check: our q90 far above market q90 = model
    # sees a tail the market doesn't. Does that subset actually boom?
    m["edge"] = m.lgb_q90 - m.mkt_q90
    hi = m[m.edge >= m.edge.quantile(0.8)]
    lo = m[m.edge <= m.edge.quantile(0.2)]
    print(f"  top-20% disagreement (model>market): actual mean {hi[ycol].mean():.1f} vs market med {hi.mkt_med.mean():.1f}")
    print(f"  bot-20% disagreement (market>model): actual mean {lo[ycol].mean():.1f} vs market med {lo.mkt_med.mean():.1f}")
print("PROP_VS_MODEL_DONE", flush=True)
