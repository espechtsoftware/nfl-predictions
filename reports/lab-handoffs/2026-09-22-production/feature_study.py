"""Per-feature input study for the trained projection model. Criteria fixed before running.

Walk-forward by season (2019-2025 test), model fit on ACTIVE rows (production's
active_training_rows), evaluated on active rows. Drop-one for every NUMERIC_FEATURE,
plus family drops, plus a 3-seed noise floor on the full model.
  helpful   : dropping WORSENS MAE in >=5/7 seasons AND mean dMAE > noise floor
  harmful   : dropping IMPROVES MAE in >=5/7 seasons AND mean -dMAE > noise floor
  otherwise : redundant/neutral
Player-level only: nominates, never deletes (lineup replay governs, per the
depth_rank_delta lesson).
"""
import sys, os, json, time, numpy as np, pandas as pd, lightgbm as lgb
from scipy.stats import spearmanr
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.models import featureset as FS
d=pd.read_parquet("ceiling_panel.parquet"); d=d[d.position.isin(FS.POSITIONS)].copy()
d["y"]=pd.to_numeric(d.y_dk_points,errors="coerce").fillna(0.0)
d=d[d.was_active.astype(bool)].reset_index(drop=True)
Xfull=FS.build_X(d); FEATS=[c for c in Xfull.columns if c!="position"]
print(f"active rows {len(d):,}; features {len(FEATS)}", flush=True)
P=dict(n_estimators=300,learning_rate=0.05,num_leaves=31,min_child_samples=40,subsample=0.8,
       subsample_freq=1,colsample_bytree=0.8,n_jobs=FS.LGB_THREADS,verbose=-1)
SEASONS=list(range(2019,2026))
def auc(s,y):
    r=pd.Series(s).rank().to_numpy(); n1=y.sum(); n0=len(y)-n1
    return (r[y==1].sum()-n1*(n1+1)/2)/(n1*n0) if n1 and n0 else np.nan
def evaluate(cols, seed=20260922):
    res=[]
    for S_ in SEASONS:
        tr=(d.season<S_).to_numpy(); te=(d.season==S_).to_numpy()
        m=lgb.LGBMRegressor(objective="regression",random_state=seed,**P)
        m.fit(Xfull.loc[tr,cols+["position"]],d.y[tr],categorical_feature=["position"])
        p=m.predict(Xfull.loc[te,cols+["position"]]); y=d.y[te].to_numpy()
        res.append((np.abs(p-y).mean(), spearmanr(p,y).statistic, auc(p,(y>=30).astype(int))))
    return np.array(res)   # seasons x [MAE, spearman, AUC30]
t0=time.time()
base=[evaluate(FEATS,seed=s) for s in (20260922,7,11)]
B=base[0]; noise=np.std([b[:,0].mean() for b in base])
floor=max(2*noise, 1e-4)
print(f"baseline MAE {B[:,0].mean():.4f}  spearman {B[:,1].mean():.4f}  AUC30 {B[:,2].mean():.4f}"
      f"  | seed noise sd {noise:.5f} -> floor {floor:.5f}  ({time.time()-t0:.0f}s)", flush=True)
rows=[]
def record(name, cols, kind):
    R=evaluate(cols); dm=R[:,0]-B[:,0]
    rows.append(dict(kind=kind, name=name, dMAE=dm.mean(), worse_in=int((dm>0).sum()),
                     dSpear=(R[:,1]-B[:,1]).mean(), dAUC30=(R[:,2]-B[:,2]).mean()))
    print(f"  {kind:<6}{name:<34} dMAE {dm.mean():+.4f} worse {int((dm>0).sum())}/7  "
          f"dSpear {rows[-1]['dSpear']:+.4f} dAUC30 {rows[-1]['dAUC30']:+.4f}  ({time.time()-t0:.0f}s)", flush=True)
FAM={"vegas":["implied_team_total","spread","game_total","expected_game_script"],
     "production_trail":["dk_points_l4","dk_points_std","dk_points_vol"],
     "salary":[c for c in FEATS if c.startswith("salary")],
     "defense":[c for c in FEATS if "allowed" in c or c.startswith("cb_") or c.startswith("db_") or c=="top_cb_out"]}
for fam,cols in FAM.items():
    cols=[c for c in cols if c in FEATS]
    if cols: record(fam, [c for c in FEATS if c not in cols], "family")
for f in FEATS: record(f, [c for c in FEATS if c!=f], "drop1")
out=pd.DataFrame(rows)
def verdict(r):
    if r.worse_in>=5 and r.dMAE>floor: return "HELPFUL"
    if r.worse_in<=2 and -r.dMAE>floor: return "HARMFUL"
    return "redundant/neutral"
out["verdict"]=out.apply(verdict,axis=1)
out.to_csv("feature_study.csv",index=False)
json.dump(dict(baseline_MAE=float(B[:,0].mean()),floor=float(floor),noise=float(noise)),open("feature_study_meta.json","w"))
print("\n=== VERDICTS ==="); print(out.sort_values("dMAE",ascending=False).to_string(index=False,float_format=lambda v:f"{v:+.4f}"))
