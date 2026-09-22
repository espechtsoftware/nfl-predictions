"""Test the laptop's cash-objective proposal: select for P(score >= cash line).

RETROSPECTIVE and deliberately OPTIMISTIC -- it is handed the TRUE realized cash
line, which no pre-lock method would know. If it fails with the answer supplied, it
fails. Compared against the delivered expected-max book and against random draws.
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
rng = np.random.default_rng(20260922)

for tag, wk, rf, cid, K in [("w1",1,"rix.npy","193028206",90),
                            ("item3",2,"roster_idx.npy","195648007",97)]:
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    cdf = pd.read_parquet(f"{tag}/cands.parquet"); rix = np.load(f"{tag}/{rf}")
    T = np.load(f"{tag}/T_inc.npy"); Tv = np.load(f"{tag}/T_hs.npy")
    dual = np.concatenate([T, Tv], axis=1).astype(np.float64)
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    pa = np.array([lut.get(str(n), np.nan) for n in fr.display_name], float)
    real = np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
    field = query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
                         WHERE season=2026 AND week={wk} AND contest_id='{cid}'""").points.to_numpy(float)
    book = np.array(cdf.loc[cdf.book_rank.notna()].sort_values("book_rank").index)
    print(f"\n=== WEEK {wk} ===  pool {len(real)}, K={K}, field {len(field):,}")
    for pct, lbl in [(0.80,"cash line (top 20%)"), (0.50,"field median")]:
        line = np.quantile(field, pct)
        p_sim = (dual >= line).mean(axis=1)          # simulated P(>= line), the objective
        pick = np.argsort(-p_sim)[:K]
        rand = np.array([ (real[rng.choice(len(real),K,replace=False)] >= line).sum()
                          for _ in range(2000) ])
        print(f"  {lbl:<22} = {line:7.2f}")
        print(f"     delivered emax book : {(real[book]>=line).sum():3d}/{K} clear "
              f"({100*(real[book]>=line).mean():5.1f}%)")
        print(f"     cash-objective book : {(real[pick]>=line).sum():3d}/{K} clear "
              f"({100*(real[pick]>=line).mean():5.1f}%)   "
              f"mean sim P {p_sim[pick].mean():.3f}")
        print(f"     random K rows       : {rand.mean():5.1f}/{K} clear "
              f"({100*rand.mean()/K:5.1f}%) +-{rand.std():.1f}")
        print(f"     WHOLE POOL rate     : {100*(real>=line).mean():5.1f}%   "
              f"| P(random >= cash-objective) = {100*(rand >= (real[pick]>=line).sum()).mean():5.1f}%")
