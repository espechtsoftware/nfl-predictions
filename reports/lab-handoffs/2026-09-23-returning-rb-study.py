"""Carry-side analogue of the returning-teammate study (walk-forward preds 2018-2024, active rows).
Returner: RB with carry_share_l4 >= 0.40 at W, active at W, not active at W-1, active at W-2 or W-3; team played W-1.
Beneficiaries: RB teammates who played W-1. Spiked: carry_share_jump >= 0.10. Compare residual vs all other RB
player-weeks with a W-1 game. Also placebo: returner absent at W-2 but active at W-1 (returned a week earlier)."""
import numpy as np, pandas as pd
d=pd.read_parquet("ceiling_panel.parquet"); q=pd.read_parquet("q_resid.parquet")[["pred","resid"]]
a=d.join(q,how="inner"); a=a[a.was_active.astype(bool)&a.position.eq("RB")].copy()
act=d[d.was_active.astype(bool)][["gsis_id","season","week","team","position","carry_share_l4"]]
key=set(zip(act.gsis_id,act.season,act.week)); tw=set(zip(act.season,act.team,act.week))
r=act[act.position.eq("RB")&(act.carry_share_l4>=0.40)].copy()
def rets(lag):
    x=r[[((g,s,w-lag) not in key) and (((g,s,w-lag-1) in key) or ((g,s,w-lag-2) in key)) and ((s,t,w-lag) in tw) and (lag==1 or (g,s,w-1) in key)
         for g,s,w,t in zip(r.gsis_id,r.season,r.week,r.team)]]
    m={}
    for s,t,w,g in zip(x.season,x.team,x.week,x.gsis_id): m.setdefault((s,t,w),set()).add(g)
    return m,len(x)
a["played_prev"]=[(g,s,w-1) in key for g,s,w in zip(a.gsis_id,a.season,a.week)]
a=a[a.played_prev].copy(); a["spiked"]=a.carry_share_jump.fillna(0)>=0.10
for lag,lab in ((1,"RETURN week"),(2,"PLACEBO (returned a week earlier)")):
    m,n=rets(lag)
    a["ret"]=[((s,t,w) in m) and (g not in m[(s,t,w)]) for s,t,w,g in zip(a.season,a.team,a.week,a.gsis_id)]
    print(f"\n{lab}: {n} returner-weeks")
    for sub,name in ((a,"all RB teammates"),(a[a.spiked],"spiked RB teammates")):
        rr,oo=sub[sub.ret].resid,sub[~sub.ret].resid
        if len(rr)<5: print(f"  {name}: n={len(rr)} too few"); continue
        se=np.sqrt(rr.var()/len(rr)+oo.var()/len(oo))
        per=sub.groupby(["season","ret"]).resid.mean().unstack()
        neg=int(((per[True]-per[False])<0).sum()) if True in per else 0
        print(f"  {name}: n={len(rr)} diff {rr.mean()-oo.mean():+.2f} (se {se:.2f}); negative in {neg}/{per.shape[0]} seasons")

m,_=rets(1)
a["ret"]=[((s,t,w) in m) and (g not in m[(s,t,w)]) for s,t,w,g in zip(a.season,a.team,a.week,a.gsis_id)]
mk=pd.read_parquet("market_bias.parquet")[["gsis_id","season","week","market_points"]].drop_duplicates(["gsis_id","season","week"])
b=a.merge(mk,on=["gsis_id","season","week"],how="inner"); b["y"]=b.resid+b.pred
b["served"]=0.45*b.pred+0.55*b.market_points
print("\nwhere the market exists (2023-24):")
for sub,name in ((b,"all"),(b[b.spiked],"spiked")):
    r_,o_=sub[sub.ret],sub[~sub.ret]
    for col,lab in (("pred","model"),("market_points","market"),("served","served")):
        dr=(r_.y-r_[col]); do=(o_.y-o_[col]); se=np.sqrt(dr.var()/max(len(dr),1)+do.var()/len(do))
        print(f"  {name:6s} n={len(r_):3d} {lab:6s} diff {dr.mean()-do.mean():+.2f} (se {se:.2f})")
