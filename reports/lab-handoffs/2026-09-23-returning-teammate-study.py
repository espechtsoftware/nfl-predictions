"""Does the model over-project teammates when a top receiver RETURNS from a one-or-more week absence?
Walk-forward E[pts|played] predictions (q_resid, 2018-2024), active rows only.
Returner R at (team, W): WR/TE/RB, target_share_l4 >= 0.18 at W, active at W, NOT active at W-1, active in W-2 or W-3.
Beneficiaries B: WR/TE/RB teammates of R active at W-1 and at W (so the team played W-1: no bye).
Compare residual (actual - pred) of B in return weeks vs all other WR/TE/RB player-weeks with a W-1 game;
and the SPIKED subset (target_share_jump >= 0.05: the player's last-week share rose), the Bateman case."""
import numpy as np, pandas as pd
d=pd.read_parquet("ceiling_panel.parquet"); q=pd.read_parquet("q_resid.parquet")[["pred","resid"]]
a=d.join(q,how="inner"); a=a[a.was_active.astype(bool)&a.position.isin(["WR","TE","RB"])].copy()
act=d[d.was_active.astype(bool)][["gsis_id","season","week","team","position","target_share_l4"]]
key=set(zip(act.gsis_id,act.season,act.week))
teamweeks=set(zip(act.season,act.team,act.week))
ret=act[act.position.isin(["WR","TE","RB"])&(act.target_share_l4>=0.18)].copy()
ret["was_out_prev"]=[(g,s,w-1) not in key for g,s,w in zip(ret.gsis_id,ret.season,ret.week)]
ret["was_in_before"]=[((g,s,w-2) in key) or ((g,s,w-3) in key) for g,s,w in zip(ret.gsis_id,ret.season,ret.week)]
ret["team_played_prev"]=[(s,t,w-1) in teamweeks for s,t,w in zip(ret.season,ret.team,ret.week)]
R=ret[ret.was_out_prev&ret.was_in_before&ret.team_played_prev]
rset={}
for s,t,w,g in zip(R.season,R.team,R.week,R.gsis_id): rset.setdefault((s,t,w),set()).add(g)
print(f"returns of a >=18% target-share player after an absence: {len(R)} (seasons {sorted(R.season.unique())})")
a["played_prev"]=[(g,s,w-1) in key for g,s,w in zip(a.gsis_id,a.season,a.week)]
a=a[a.played_prev]
a["ret_week"]=[((s,t,w) in rset) and (g not in rset[(s,t,w)]) for s,t,w,g in zip(a.season,a.team,a.week,a.gsis_id)]
a["spiked"]=a.target_share_jump.fillna(0)>=0.05
def show(sub,label):
    g=sub.groupby(["season","ret_week"]).resid.agg(["mean","size"]).unstack()
    diff=(g["mean"][True]-g["mean"][False])
    print(f"\n{label}: residual (actual - pred), teammates in a RETURN week minus all others")
    print(pd.DataFrame({"n_return":g["size"][True],"return":g["mean"][True].round(2),"others":g["mean"][False].round(2),"diff":diff.round(2)}).to_string())
    r=sub[sub.ret_week].resid; o=sub[~sub.ret_week].resid
    se=np.sqrt(r.var()/len(r)+o.var()/len(o))
    print(f"  pooled diff {r.mean()-o.mean():+.2f} (se {se:.2f}); negative in {int((diff<0).sum())}/{len(diff)} seasons")
show(a,"ALL WR/TE/RB teammates")
show(a[a.spiked],"SPIKED teammates (last-week target share up >= 5 pts)")
show(a[a.spiked&a.position.eq("WR")],"SPIKED WRs")

# served-like check where the prop market exists (2023-24, >=2 markets): served = 0.45*pred + 0.55*market
mk=pd.read_parquet("market_bias.parquet")[["gsis_id","season","week","market_points"]].drop_duplicates(["gsis_id","season","week"])
b=a.merge(mk,on=["gsis_id","season","week"],how="inner")
b["served"]=0.45*b.pred+0.55*b.market_points; b["y"]=b.resid+b.pred; b["res_s"]=b.y-b.served; b["res_m"]=b.y-b.market_points
for lab,sub in (("all teammates",b),("spiked",b[b.spiked])):
    r,o=sub[sub.ret_week],sub[~sub.ret_week]
    for col,name in (("resid","model"),("res_m","market"),("res_s","served")):
        se=np.sqrt(r[col].var()/len(r)+o[col].var()/len(o))
        print(f"  [{lab}, market available, n_return={len(r)}] {name:7s} diff {r[col].mean()-o[col].mean():+.2f} (se {se:.2f})")
