"""Selection under regime uncertainty: which selector's WORSE week is best?

Criterion fixed before running: primary = best-lineup finish percentile in that week's
real Millionaire field (what a GPP pays on); rank selectors by their WORSE week (maximin).
Grid fixed in advance: expected-max with a per-player exposure cap in {none,50,40,30,20,15}%,
plus random selection. Same pool, same simulator banks, Doubtful excluded in all arms.
Two slates: this nominates, it cannot establish.
"""
import sys, importlib.util, numpy as np, pandas as pd
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
rng=np.random.default_rng(20260922)
CAPS=[None,0.50,0.40,0.30,0.20,0.15]
rows=[]
for tag,wk,rf,K,cid in [("w1",1,"rix.npy",90,"193028206"),("item3",2,"roster_idx.npy",97,"195648007")]:
    spec=importlib.util.spec_from_file_location(f"em{tag}",f"{tag}/emax.py"); em=importlib.util.module_from_spec(spec); spec.loader.exec_module(em)
    fr=pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True); rix=np.load(f"{tag}/{rf}")
    T=np.load(f"{tag}/T_inc.npy"); Tv=np.load(f"{tag}/T_hs.npy")
    own=query_df(f"SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership` WHERE season=2026 AND week={wk} GROUP BY 1")
    lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
    real=np.where(np.isnan(np.array([lut.get(str(n),np.nan) for n in fr.display_name],float)),0.0,
                  np.array([lut.get(str(n),np.nan) for n in fr.display_name],float))[rix].sum(axis=1)
    field=np.sort(query_df(f"SELECT points FROM `{settings.raw}.contest_entries` WHERE season=2026 AND week={wk} AND contest_id='{cid}'").points.to_numpy(float))
    pct=lambda v: 100*np.searchsorted(field,v,side="right")/len(field)
    top1=np.quantile(field,0.99)
    dbt=fr.index[fr.status.astype(str).str.upper().str.strip().isin(["D","DOUBTFUL"])].to_numpy()
    def score(idx,lab):
        r=real[idx]; rows.append(dict(week=wk,selector=lab,best=r.max(),best_pctile=pct(r.max()),
            mean=r.mean(),n_top1pct=int((r>=top1).sum()),max_exposure=100*np.bincount(rix[idx].ravel(),minlength=len(fr)).max()/K))
    for c in CAPS:
        caps=np.full(len(fr),10**6,np.int32) if c is None else np.full(len(fr),max(1,int(np.ceil(c*K))),np.int32)
        caps[dbt]=0
        o=em.emax_select(T,Tv,K,caps=caps,roster_idx=rix,n_players=len(fr))
        score(np.asarray(o[0] if isinstance(o,tuple) else o), "emax" if c is None else f"emax cap{int(c*100)}%")
    ok=np.where(~np.isin(rix,dbt).any(axis=1))[0]
    R=[real[rng.choice(ok,K,replace=False)] for _ in range(2000)]
    rows.append(dict(week=wk,selector="random (2000 draws, mean)",best=np.mean([r.max() for r in R]),
        best_pctile=np.mean([pct(r.max()) for r in R]),mean=np.mean([r.mean() for r in R]),
        n_top1pct=np.mean([(r>=top1).sum() for r in R]),max_exposure=np.nan))
    print(f"week {wk} done", flush=True)
d=pd.DataFrame(rows)
pd.set_option("display.width",200)
print(d.to_string(index=False,float_format=lambda v:f"{v:.2f}"))
w=d.pivot(index="selector",columns="week",values="best_pctile")
w["WORSE week"]=w.min(axis=1); w["avg"]=w[[1,2]].mean(axis=1)
print("\n=== best-lineup FIELD PERCENTILE by week; ranked by the WORSE week (maximin) ===")
print(w.sort_values("WORSE week",ascending=False).round(2).to_string())
d.to_csv("minimax_selector.csv",index=False)
