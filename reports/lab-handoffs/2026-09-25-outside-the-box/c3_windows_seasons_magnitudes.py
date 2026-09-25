import re, pandas as pd, numpy as np, warnings
from scipy import stats
warnings.filterwarnings("ignore")
sk=pd.read_parquet("ls_skill_analysis.parquet")
def win(gi):
    m=re.search(r"(\d{1,2}):(\d{2}) (AM|PM)",str(gi))
    if not m: return "other"
    h=int(m.group(1))%12+(12 if m.group(3)=="PM" else 0); mins=h*60+int(m.group(2))  # Pacific
    return "early" if 9*60<=mins<11*60 else ("late" if 12*60<=mins<14*60 else "other")
sk["window"]=sk.gi.map(win)
print("window counts (PT-parsed):",sk.window.value_counts().to_dict())
def slate_corr(d,x,y,min_n=12):
    out=[]
    for k,g in d.groupby(["season","week"]):
        g=g[[x,y]].dropna()
        if len(g)>=min_n and g[x].nunique()>1 and g[y].nunique()>1: out.append(stats.spearmanr(g[x],g[y])[0])
    out=np.array(out); t=out.mean()/(out.std(ddof=1)/np.sqrt(len(out)))
    return f"rho {out.mean():+.3f} t {t:+.1f} pos {int((out>0).sum())}/{len(out)}"
pl=sk[sk.played].copy()
for w in ["early","late"]:
    x=pl[pl.window==w]
    print(f"[{w}] n={len(x)}  T1 excess-actual-own->resid {slate_corr(x,'e_act','resid')} | T2 excess-proj-own {slate_corr(x,'e_proj','resid')} | T3 drift {slate_corr(x,'drift','resid')}")
print("[AVAIL, all rows] drift -> played:", slate_corr(sk,"drift","played"), "| early", slate_corr(sk[sk.window=="early"],"drift","played"), "| late", slate_corr(sk[sk.window=="late"],"drift","played"))
# recency decomposition, per season robustness
r=pl.dropna(subset=["prev_surprise"]).copy()
parts=[]
for k,g in r.groupby(["season","week"]):
    if len(g)<25: continue
    X=np.column_stack([np.ones(len(g)),g.prev_surprise.values]); b,*_=np.linalg.lstsq(X,g.e_act.values,rcond=None)
    g=g.copy(); g["own_rec"]=X@b; g["own_info"]=g.e_act-g.own_rec; g["b_rec"]=b[1]; parts.append(g)
r=pd.concat(parts)
print("\nPer-season: [chase] surprise->excess own | [recency part]->resid | [info part]->resid")
for s,g in r.groupby("season"):
    print(f"  {s}: chase {slate_corr(g,'prev_surprise','e_act',25)} | rec->resid {slate_corr(g,'own_rec','resid',25)} | info->resid {slate_corr(g,'own_info','resid',25)}")
# magnitude of chasing: log-ownership elasticity per 10 pts of last-week surprise
print("\nMedian within-slate slope: +10 pts last-week surprise -> x%.2f relative ownership (beyond projection/salary/value)" % np.exp(10*r.groupby(['season','week']).b_rec.first().median()))
# 2D: recency part vs info part quintiles -> residual
r["q_rec"]=r.groupby(["season","week"]).own_rec.transform(lambda s: pd.qcut(s.rank(method="first"),5,labels=False))
r["q_inf"]=r.groupby(["season","week"]).own_info.transform(lambda s: pd.qcut(s.rank(method="first"),5,labels=False))
print("\nResidual (actual - LineStar projection) by quintile of RECENCY-driven ownership (0=lowest):")
print(r.groupby("q_rec").resid.agg(["mean","count"]).round(2).T.to_string())
print("Residual by quintile of INFORMATION-part ownership:")
print(r.groupby("q_inf").resid.agg(["mean","count"]).round(2).T.to_string())
# boom rates: P(>=25 DK) relative to projection band, by recency quintile, controlling via PP bands
r["boom"]=(r.ps>=25).astype(int); r["ppband"]=pd.cut(r.pp,[4,10,15,20,40])
print("\nBoom rate (>=25 DK) by recency-ownership quintile within projection band:")
print(r.pivot_table(index="ppband",columns="q_rec",values="boom",aggfunc="mean",observed=True).round(3).to_string())
print("\nMean actual ownership (%) by recency quintile:", r.groupby("q_rec").own_act.mean().round(2).to_dict())
