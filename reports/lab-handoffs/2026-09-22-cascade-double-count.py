# Reproduce (laptop, 2026-09-22). Run from a worktree at aaf6058f (or 85824fd0) with PYTHONPATH=<wt>/src.
# Inputs, exported with nfl_dfs.bq.query_df into DIR:
#   pwt_2017_2024.parquet      = SELECT * FROM nfl_features.player_week_training WHERE season BETWEEN 2017 AND 2024
#   rz_receiving.parquet       = gsis_id, season, week, total_targets, rz20_targets, target_share  (2021-2024)
#   rz_rushing.parquet         = gsis_id, season, week, total_carries, gl3_carries, carry_share    (2021-2024)
#   player_week_injury.parquet = gsis_id, season, week, injury_status AS game_status               (2021-2024)
# Usage: python this.py DIR <test_season 2022|2023|2024> [full|norush]; writes DIR/dc_<season>_<variant>.parquet
"""Does the inference cascade double-count a starter the feature build already saw as Out?
Walk-forward 2024 (fit 2017-23 active rows, production LightGBM params as in
2026-09-22-next-man-up-walkforward.py). For every 2024 week, every skill player with
injury_status='Out' (report-Out, i.e. priced by team_vacated_* features) is fed to the
REAL cascade_adjust.adjust_for_inactives with usage history strictly before that week.
Compare residuals of the teammates the cascade bumps: model alone vs model+cascade."""
import os, sys, logging, numpy as np, pandas as pd, lightgbm as lgb
from nfl_dfs.models import featureset as FS
from nfl_dfs.inference import cascade_adjust as CA
logging.disable(logging.INFO)
S=sys.argv[1]; TS=int(sys.argv[2]); NORUSH=len(sys.argv)>3 and sys.argv[3]=="norush"
d=pd.read_parquet(f"{S}/pwt_2017_2024.parquet"); d=d[d.position.isin(FS.POSITIONS)].reset_index(drop=True)
d["y"]=pd.to_numeric(d.y_dk_points,errors="coerce").fillna(0.0)
rec=pd.read_parquet(f"{S}/rz_receiving.parquet"); rush=pd.read_parquet(f"{S}/rz_rushing.parquet"); inj=pd.read_parquet(f"{S}/player_week_injury.parquet")
act=d.was_active.astype(bool)
P=dict(n_estimators=300,learning_rate=0.05,num_leaves=31,min_child_samples=40,subsample=0.8,subsample_freq=1,
       colsample_bytree=0.8,n_jobs=FS.LGB_THREADS,verbose=-1,random_state=20260922)
X=FS.build_X(d); cols=list(X.columns)
tr=(d.season<TS)&act
m=lgb.LGBMRegressor(objective="regression",**P).fit(X[tr],d.y[tr],categorical_feature=["position"])
key=lambda x: x.season*100+x.week
out=[]
for w in sorted(d[d.season==TS].week.unique()):
    wk=d[(d.season==TS)&(d.week==w)].copy()
    wk["status"]=""   # report-Out only: the case the vacated features already price
    k=TS*100+w; lo=(TS-1)*100
    fa,ids=CA.adjust_for_inactives(wk, rec[(key(rec)<k)&(key(rec)>lo)], (rush.iloc[0:0] if NORUSH else rush[(key(rush)<k)&(key(rush)>lo)]), inj[(key(inj)<=k)&(key(inj)>lo)])
    a=act.loc[wk.index]
    xb=FS.build_X(wk[a]); xa=FS.build_X(fa.loc[wk.index[a]])
    changed=(xb[["target_share_l4","carry_share_l4","wopr_l4","rz20_targets_smoothed","gl3_carries_smoothed"]].fillna(-9)
             !=xa[["target_share_l4","carry_share_l4","wopr_l4","rz20_targets_smoothed","gl3_carries_smoothed"]].fillna(-9)).any(axis=1)
    out.append(pd.DataFrame({"week":w,"position":wk.position[a],"y":wk.y[a],"pb":m.predict(xb),"pa":m.predict(xa),
                             "changed":changed.values,"vac":(wk.team_vacated_target_share[a].fillna(0)+wk.team_vacated_carry_share[a].fillna(0)).values>0,
                             "n_out":len(ids)}))
o=pd.concat(out); o["rb"]=o.y-o.pb; o["ra"]=o.y-o.pa; o["bump"]=o.pa-o.pb
o.to_parquet(f"{S}/dc_{TS}_{'norush' if NORUSH else 'full'}.parquet")
print(f"{TS} weeks {o.week.nunique()}, report-Out sources/week mean {o.groupby('week').n_out.first().mean():.1f}")
c=o[o.changed]
print(f"\nteammates bumped by the cascade: n={len(c)} (with team_vacated>0: {c.vac.mean():.0%})")
print(f"  mean pred bump {c.bump.mean():+.2f}   resid model-only {c.rb.mean():+.2f}   resid model+cascade {c.ra.mean():+.2f}")
print(f"  MAE model-only {c.rb.abs().mean():.3f}   model+cascade {c.ra.abs().mean():.3f}")
print("\nby position:"); print(c.groupby("position").agg(n=("y","size"),bump=("bump","mean"),resid_model=("rb","mean"),resid_casc=("ra","mean")).round(2).to_string())
r=c[c.pb>=6]
print(f"\nrosterable (model pred >= 6): n={len(r)} bump {r.bump.mean():+.2f} resid model {r.rb.mean():+.2f} -> cascade {r.ra.mean():+.2f}; MAE {r.rb.abs().mean():.3f} -> {r.ra.abs().mean():.3f}")
# bootstrap by week for the resid difference
rng=np.random.default_rng(0); wks=c.week.unique(); g={w:c[c.week==w] for w in wks}; bs=[]
for _ in range(2000):
    s=pd.concat([g[w] for w in rng.choice(wks,len(wks))]); bs.append(s.ra.abs().mean()-s.rb.abs().mean())
print(f"week-bootstrap 90% CI of MAE(cascade)-MAE(model): [{np.percentile(bs,5):+.3f}, {np.percentile(bs,95):+.3f}]")
