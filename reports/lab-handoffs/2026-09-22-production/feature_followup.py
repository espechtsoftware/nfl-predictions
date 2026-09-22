"""Follow-ups: (1) order-luck control, (2) drop the 4 nominated features together."""
import sys, numpy as np, pandas as pd, lightgbm as lgb
from scipy.stats import spearmanr
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.models import featureset as FS
d=pd.read_parquet("ceiling_panel.parquet"); d=d[d.position.isin(FS.POSITIONS)].copy()
d["y"]=pd.to_numeric(d.y_dk_points,errors="coerce").fillna(0.0); d=d[d.was_active.astype(bool)].reset_index(drop=True)
X=FS.build_X(d); FEATS=[c for c in X.columns if c!="position"]
P=dict(n_estimators=300,learning_rate=0.05,num_leaves=31,min_child_samples=40,subsample=0.8,subsample_freq=1,
       colsample_bytree=0.8,n_jobs=FS.LGB_THREADS,verbose=-1,random_state=20260922)
def auc(s,y):
    r=pd.Series(s).rank().to_numpy(); n1=y.sum(); n0=len(y)-n1; return (r[y==1].sum()-n1*(n1+1)/2)/(n1*n0)
def ev(Xm, cols):
    R=[]
    for S_ in range(2019,2026):
        tr=(d.season<S_).to_numpy(); te=(d.season==S_).to_numpy()
        m=lgb.LGBMRegressor(objective="regression",**P).fit(Xm.loc[tr,cols+["position"]],d.y[tr],categorical_feature=["position"])
        p=m.predict(Xm.loc[te,cols+["position"]]); y=d.y[te].to_numpy()
        R.append((np.abs(p-y).mean(),spearmanr(p,y).statistic,auc(p,(y>=30).astype(int))))
    return np.array(R)
B=ev(X,FEATS)
# ORDER-LUCK CONTROL: insert inert columns that carry no information but shift column
# positions exactly as a drop would. Any MAE change here is pure order luck.
luck=[]
for k,pos in enumerate((3,11,19,27)):
    Xc=X.copy(); name=f"zz_inert_{k}"; Xc[name]=0.0
    cols=FEATS[:pos]+[name]+FEATS[pos:]
    luck.append((ev(Xc,cols)[:,0]-B[:,0]).mean())
print(f"order-luck control (4 inert-column insertions): dMAE {np.round(luck,4).tolist()}  "
      f"-> |max| {np.max(np.abs(luck)):.4f}")
NOM=["neutral_pass_rate_l6","separation_l4","gl3_carries_smoothed","stacked_box_l4"]
R=ev(X,[c for c in FEATS if c not in NOM]); dm=R[:,0]-B[:,0]
print(f"drop all 4 nominated together: dMAE {dm.mean():+.4f}  improves in {(dm<0).sum()}/7 seasons  "
      f"per-season {np.round(dm,4).tolist()}")
print(f"   dSpearman {(R[:,1]-B[:,1]).mean():+.4f}   dAUC30 {(R[:,2]-B[:,2]).mean():+.4f}")
# coverage of the nominated features -- are they null in early seasons?
for f in NOM:
    cov=d.groupby("season")[f].apply(lambda s: pd.to_numeric(s,errors='coerce').notna().mean())
    print(f"   coverage {f:<24} " + " ".join(f"{int(s)}:{v:.0%}" for s,v in cov.items() if s in (2014,2016,2018,2020,2022,2025)))
