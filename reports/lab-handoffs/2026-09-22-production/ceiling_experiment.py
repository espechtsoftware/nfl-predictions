"""PREREG-CEILING: does training on P(30+) beat training on the mean, at ranking ceiling?

Design frozen in reports/2026-09-22-prereg-ceiling-model.md at 6e6aef91, BEFORE any arm
was fitted. Runs locally per the operator's standing instruction. Walk-forward by season.
"""
import sys, numpy as np, pandas as pd, lightgbm as lgb
from scipy.stats import spearmanr
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
from nfl_dfs.models import featureset as FS

CACHE = "ceiling_panel.parquet"
import os
if os.path.exists(CACHE):
    d = pd.read_parquet(CACHE)
else:
    d = query_df(f"""SELECT * FROM `{settings.features}.player_week_training`
                     WHERE season BETWEEN 2014 AND 2025 AND salary IS NOT NULL""")
    d.to_parquet(CACHE)
print(f"panel {len(d):,} rows, seasons {d.season.min()}-{d.season.max()}")
d = d[d.position.isin(FS.POSITIONS)].copy()
d["hit30"] = (pd.to_numeric(d.y_dk_points, errors="coerce").fillna(0) >= 30).astype(int)
d["y"] = pd.to_numeric(d.y_dk_points, errors="coerce").fillna(0.0)
print(f"modelled universe {len(d):,}; ceiling games {d.hit30.sum():,} ({100*d.hit30.mean():.2f}%)")

X = FS.build_X(d)
print(f"features {X.shape[1]}")
PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=40,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
              n_jobs=FS.LGB_THREADS, verbose=-1, random_state=20260922)

def auc(score, y):
    s = pd.Series(score); m = s.notna()
    r = s[m].rank(); yy = np.asarray(y)[m.to_numpy()]
    n1, n0 = yy.sum(), (1-yy).sum()
    return (r[yy==1].sum() - n1*(n1+1)/2)/(n1*n0) if n1 and n0 else np.nan

def prec_at(score, y, k=100):
    o = np.argsort(-np.asarray(score, float))[:k]
    return np.asarray(y)[o].mean()

rows=[]
for S_ in range(2018, 2026):
    tr = d.season < S_; te = d.season == S_
    if tr.sum()==0 or te.sum()==0: continue
    Xtr, Xte = X[tr.to_numpy()], X[te.to_numpy()]
    # CEIL -- binary classifier on hit30
    c = lgb.LGBMClassifier(objective="binary", **PARAMS)
    c.fit(Xtr, d.loc[tr,"hit30"], categorical_feature=["position"])
    p_ceil = c.predict_proba(Xte)[:,1]
    # MEAN -- regressor on points, what we do now
    r = lgb.LGBMRegressor(objective="regression", **PARAMS)
    r.fit(Xtr, d.loc[tr,"y"], categorical_feature=["position"])
    p_mean = r.predict(Xte)
    p_sal = pd.to_numeric(d.loc[te,"salary"], errors="coerce").to_numpy(float)
    yte = d.loc[te,"hit30"].to_numpy()
    rows.append(dict(season=S_, n=int(te.sum()), pos=int(yte.sum()),
        CEIL=auc(p_ceil,yte), MEAN=auc(p_mean,yte), SALARY=auc(p_sal,yte),
        p100_CEIL=prec_at(p_ceil,yte), p100_MEAN=prec_at(p_mean,yte),
        p100_SAL=prec_at(np.nan_to_num(p_sal),yte),
        rank_corr=spearmanr(p_ceil,p_mean).statistic))
    print(f"  {S_}: n={te.sum():>6} pos={yte.sum():>4}  CEIL {rows[-1]['CEIL']:.4f}  "
          f"MEAN {rows[-1]['MEAN']:.4f}  SALARY {rows[-1]['SALARY']:.4f}  "
          f"(rank corr CEIL~MEAN {rows[-1]['rank_corr']:.4f})", flush=True)
res=pd.DataFrame(rows); res.to_csv("ceiling_results.csv", index=False)
print("\n=== VACUITY CHECK (must be < 0.99) ===")
print(f"  Spearman(CEIL, MEAN) per season: min {res.rank_corr.min():.4f} "
      f"max {res.rank_corr.max():.4f}  -> "
      f"{'PASS: arms differ' if res.rank_corr.max()<0.99 else 'FAIL: arms are effectively identical'}")
print("\n=== PREREGISTERED CRITERIA ===")
beats_both = ((res.CEIL>res.MEAN)&(res.CEIL>res.SALARY)).sum()
print(f"  1) CEIL beats BOTH in {beats_both}/8 seasons   (need >=6)  "
      f"{'PASS' if beats_both>=6 else 'FAIL'}")
dM, dS = res.CEIL.mean()-res.MEAN.mean(), res.CEIL.mean()-res.SALARY.mean()
print(f"  2) mean AUC margin: vs MEAN {dM:+.4f}, vs SALARY {dS:+.4f}  (need >=+0.005 each)  "
      f"{'PASS' if dM>=0.005 and dS>=0.005 else 'FAIL'}")
worst = (res.CEIL - res[["MEAN","SALARY"]].max(axis=1)).min()
print(f"  3) worst season shortfall {worst:+.4f}  (need > -0.01)  "
      f"{'PASS' if worst>-0.01 else 'FAIL'}")
print(f"\nmean AUC  CEIL {res.CEIL.mean():.4f}  MEAN {res.MEAN.mean():.4f}  SALARY {res.SALARY.mean():.4f}")
print(f"mean precision@100  CEIL {res.p100_CEIL.mean():.3f}  MEAN {res.p100_MEAN.mean():.3f}  "
      f"SALARY {res.p100_SAL.mean():.3f}   (base rate {d.hit30.mean():.4f})")
