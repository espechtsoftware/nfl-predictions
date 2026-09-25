import re, pandas as pd, numpy as np, warnings
from scipy import stats
warnings.filterwarnings("ignore")
sk=pd.read_parquet("ls_skill_analysis.parquet")
pl=sk[sk.played].copy()
def slate_corr(d,x,y,min_n=25):
    out=[]
    for k,g in d.groupby(["season","week"]):
        g=g[[x,y]].dropna()
        if len(g)>=min_n and g[x].nunique()>1: out.append(stats.spearmanr(g[x],g[y])[0])
    out=np.array(out); t=out.mean()/(out.std(ddof=1)/np.sqrt(len(out)))
    return f"rho {out.mean():+.3f} t {t:+.1f} pos {int((out>0).sum())}/{len(out)}"
# look-ahead sanity: LineStar projection accuracy by season
print("LineStar projection accuracy by season (played, PP>=4): corr(PP,PS), MAE")
for s,g in pl.groupby("season"): print(f"  {s}: r={np.corrcoef(g.pp,g.ps)[0,1]:.3f} MAE={np.abs(g.ps-g.pp).mean():.2f} n={len(g)}")
# PRE-LOCK usable decomposition: projected-ownership excess split into recency vs rest
r=pl.dropna(subset=["prev_surprise"]).copy(); parts=[]
for k,g in r.groupby(["season","week"]):
    if len(g)<25: continue
    X=np.column_stack([np.ones(len(g)),g.prev_surprise.values])
    b,*_=np.linalg.lstsq(X,g.e_proj.values,rcond=None); g=g.copy(); g["proj_rec"]=X@b; g["proj_info"]=g.e_proj-g.proj_rec
    b2,*_=np.linalg.lstsq(X,g.e_act.values,rcond=None); g["act_rec"]=X@b2; g["act_info"]=g.e_act-g.act_rec
    r2=np.corrcoef(g.prev_surprise,g.e_act)[0,1]**2; g["r2_rec"]=r2; parts.append(g)
r=pd.concat(parts)
print("\nShare of excess actual ownership variance explained by last-week surprise (median R^2 per slate): %.3f" % r.groupby(["season","week"]).r2_rec.first().median())
print("[PRE-LOCK] non-recency part of LineStar PROJECTED ownership excess -> residual:", slate_corr(r,"proj_info","resid"))
print("[PRE-LOCK] recency part of projected ownership excess -> residual:", slate_corr(r,"proj_rec","resid"))
print("[PRE-LOCK] predicted recency-chase of ACTUAL ownership (fitted from prev_surprise) is known pre-lock; its ownership lift vs LineStar projected ownership:")
# does the crowd chase MORE than LineStar's ownership projection anticipates?  regress drift (act beyond projected own) on prev_surprise
print("   drift (actual own beyond LineStar projected own) ~ last-week surprise:", slate_corr(r,"prev_surprise","drift"))
# busts and booms last week: ownership vs fair and residual this week
r["lw"]=pd.cut(r.prev_surprise,[-99,-8,-3,3,8,99],labels=["bust<=-8","-8..-3","-3..3","3..8","boom>=8"])
t=r.groupby("lw",observed=True).agg(n=("resid","size"),resid=("resid","mean"),excess_log_own=("e_act","mean"),drift=("drift","mean"),own=("own_act","mean"),own_proj=("own_proj","mean"))
t["own_mult_vs_fair"]=np.exp(t.excess_log_own); print("\nBy last-week surprise band (played skill, PP>=4):"); print(t.round(3).to_string())
# DST check
d=sk[(sk.pos.isin(["DST","D"]))].copy()
print("\nDST rows:",len(d))
