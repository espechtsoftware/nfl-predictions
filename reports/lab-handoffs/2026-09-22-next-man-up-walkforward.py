"""Does the model under-predict a backup promoted past a ruled-out starter?
Walk-forward, fit on active rows (production), 2022+ era only (the feature cannot exist
earlier). Then: add eff_rank/promoted as features and measure MAE vs the order-luck floor."""
import sys, numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.models import featureset as FS
d=pd.read_parquet("ceiling_panel.parquet"); d=d[d.position.isin(FS.POSITIONS)].copy().reset_index(drop=True)
d["y"]=pd.to_numeric(d.y_dk_points,errors="coerce").fillna(0.0)
d["unavail"]=d.injury_status.fillna("").isin(["Out","Doubtful"])
g=d[d.depth_rank.notna()].sort_values(["season","week","team","position","depth_rank"])
above=g.groupby(["season","week","team","position"]).unavail.transform(lambda s: s.cumsum().shift(fill_value=0))
d["above_unavail"]=0.0; d.loc[above.index,"above_unavail"]=above.astype(float)
d["eff_rank"]=d.depth_rank-d.above_unavail
d["promoted"]=((d.above_unavail>0)&~d.unavail).astype(float)
act=d.was_active.astype(bool).to_numpy()
X=FS.build_X(d); F=[c for c in X.columns if c!="position"]
X["eff_rank"]=d.eff_rank; X["promoted"]=d.promoted
P=dict(n_estimators=300,learning_rate=0.05,num_leaves=31,min_child_samples=40,subsample=0.8,subsample_freq=1,
       colsample_bytree=0.8,n_jobs=FS.LGB_THREADS,verbose=-1,random_state=20260922)
def run(cols):
    preds={}
    for S_ in (2023,2024):
        tr=((d.season<S_).to_numpy())&act; te=((d.season==S_).to_numpy())&act
        m=lgb.LGBMRegressor(objective="regression",**P).fit(X.loc[tr,cols+["position"]],d.y[tr],categorical_feature=["position"])
        preds[S_]=pd.Series(m.predict(X.loc[te,cols+["position"]]),index=d.index[te])
    return pd.concat(preds.values())
base=run(F)
t=d.loc[base.index].assign(pred=base, resid=lambda x: x.y-x.pred)
print("=== BASELINE model residual (realized - predicted), active players, 2023-24 ===")
print(t.groupby(t.promoted.astype(bool)).agg(n=("resid","size"),pred=("pred","mean"),real=("y","mean"),resid=("resid","mean")).round(2).to_string())
print("\nby position, PROMOTED only:")
print(t[t.promoted==1].groupby("position").agg(n=("resid","size"),pred=("pred","mean"),real=("y","mean"),resid=("resid","mean")).round(2).to_string())
new=run(F+["eff_rank","promoted"])
for S_ in (2023,2024):
    idx=d.index[(d.season==S_).to_numpy()&act]
    mb=np.abs(base.loc[idx]-d.y[idx]).mean(); mn=np.abs(new.loc[idx]-d.y[idx]).mean()
    pm=d.promoted[idx]==1
    print(f"\n{S_}: overall MAE base {mb:.4f} new {mn:.4f} (d {mn-mb:+.4f}; order-luck floor 0.0052)"
          f"  | promoted-only MAE base {np.abs(base.loc[idx][pm]-d.y[idx][pm]).mean():.3f} "
          f"new {np.abs(new.loc[idx][pm]-d.y[idx][pm]).mean():.3f}  resid base {(d.y[idx][pm]-base.loc[idx][pm]).mean():+.2f} "
          f"new {(d.y[idx][pm]-new.loc[idx][pm]).mean():+.2f}")
