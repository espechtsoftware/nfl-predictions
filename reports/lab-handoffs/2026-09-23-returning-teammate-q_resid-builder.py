# Builds q_resid.parquet (walk-forward E[pts|played] predictions, 2018-2024) from ceiling_panel.parquet;
# the returning-teammate study reads it. Paths are production scratchpad-relative; adjust before running.
"""Do Questionable players systematically under-run an E[points|played] projection?

Walk-forward by season; model fit on ACTIVE rows (production's active_training_rows),
so it predicts E[pts | played] exactly as served. Residual = realized (0 if did not
play) - prediction, by pre-lock injury designation. Regime-robust only if the Q
residual is negative in essentially every season.
"""
import sys, numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.models import featureset as FS
d=pd.read_parquet("ceiling_panel.parquet"); d=d[d.position.isin(FS.POSITIONS)].copy()
d["y"]=pd.to_numeric(d.y_dk_points,errors="coerce").fillna(0.0)
d["st"]=d.injury_status.fillna("(none)")
d["active"]=d.was_active.astype(bool)
X=FS.build_X(d)
P=dict(n_estimators=400,learning_rate=0.05,num_leaves=31,min_child_samples=40,subsample=0.8,
       subsample_freq=1,colsample_bytree=0.8,n_jobs=FS.LGB_THREADS,verbose=-1,random_state=20260922)
out=[]
for S_ in range(2018,2025):                     # 2025 has no injury_status
    tr=(d.season<S_)&d.active; te=(d.season==S_)
    m=lgb.LGBMRegressor(objective="regression",**P).fit(X[tr.to_numpy()],d.loc[tr,"y"],categorical_feature=["position"])
    t=d.loc[te,["season","st","y","active","salary"]].copy(); t["pred"]=m.predict(X[te.to_numpy()])
    out.append(t); print(f"  fitted {S_}", flush=True)
r=pd.concat(out); r["resid"]=r.y-r.pred; r["ratio_num"]=r.y; r["ratio_den"]=r.pred
keep=["(none)","Questionable","Doubtful","Probable"]
print("\n=== pooled 2018-2024 (served E[pts|played], realized incl. zeros) ===")
g=r[r.st.isin(keep)].groupby("st").agg(n=("y","size"),play=("active","mean"),pred=("pred","mean"),
    real=("y","mean"),resid=("resid","mean"))
g["real/pred"]=(g.real/g.pred).round(3); g["play"]=(100*g.play).round(1)
print(g.round(2).to_string())
print("\n=== Questionable residual MINUS healthy residual, per season (the haircut signal) ===")
per=r[r.st.isin(["(none)","Questionable"])].groupby(["season","st"]).resid.mean().unstack()
per["Q_minus_none"]=per["Questionable"]-per["(none)"]
nq=r[r.st=="Questionable"].groupby("season").size()
per["nQ"]=nq
print(per.round(2).to_string())
neg=(per.Q_minus_none<0).sum()
print(f"\nQ worse than healthy in {neg}/{len(per)} seasons; mean gap {per.Q_minus_none.mean():+.2f}, "
      f"sd {per.Q_minus_none.std():.2f}")
# the multiplicative haircut that would zero the Q bias, fit on data, reported per season
q=r[r.st=="Questionable"]; hq=q.groupby("season").apply(lambda s: s.y.sum()/s.pred.sum())
h0=r[r.st=="(none)"].groupby("season").apply(lambda s: s.y.sum()/s.pred.sum())
print("\nrealized/predicted ratio   Q:", hq.round(3).to_dict())
print("                      healthy:", h0.round(3).to_dict())
print(f"relative Q haircut (Q ratio / healthy ratio): {(hq/h0).round(3).to_dict()}")
print(f"  mean {(hq/h0).mean():.3f}  min {(hq/h0).min():.3f}  max {(hq/h0).max():.3f}")
r.to_parquet("q_resid.parquet")
