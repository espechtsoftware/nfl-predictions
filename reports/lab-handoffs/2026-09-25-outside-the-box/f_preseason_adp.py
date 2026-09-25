import json, re, pandas as pd, numpy as np, warnings
from scipy import stats
warnings.filterwarnings("ignore")
def norm(s):
    s=str(s).lower(); s=re.sub(r"[\.\'’]","",s); s=re.sub(r"-"," ",s)
    s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b","",s); return re.sub(r"\s+"," ",s).strip()
adp=[]
for y in (2022,2023,2024,2025):
    j=json.load(open(f"adp_{y}.json"))
    for p in j["players"]: adp.append((y,norm(p["name"]),p["position"],p["adp"],p["times_drafted"]))
adp=pd.DataFrame(adp,columns=["season","nm","adp_pos","adp","n_drafted"])
sk=pd.read_parquet("ls_skill_analysis.parquet")
d=sk[sk.played & sk.season.between(2022,2025)].copy()
d=d.merge(adp,on=["season","nm"],how="left")
print("ADP coverage among played skill PP>=4:", d.adp.notna().mean().round(3))
d["undrafted"]=d.adp.isna().astype(int); d["ladp"]=np.log(d.adp.fillna(200.0))
def slate_corr(x,a,b,min_n=20):
    out=[]
    for k,g in x.groupby(["season","week"]):
        g=g[[a,b]].dropna()
        if len(g)>=min_n and g[a].nunique()>1: out.append(stats.spearmanr(g[a],g[b])[0])
    out=np.array(out); return f"rho {out.mean():+.3f} t {out.mean()/(out.std(ddof=1)/np.sqrt(len(out))):+.1f} pos {int((out>0).sum())}/{len(out)}"
parts=[]
for k,g in d.groupby(["season","week"]):
    g=g.copy()
    X=np.column_stack([np.ones(len(g)),np.log(g.pp),np.log(g.sal)]+[(g.pos==p).astype(float) for p in ["RB","WR","TE"]])
    b,*_=np.linalg.lstsq(X,g.ladp.values,rcond=None); g["adp_excess"]=-(g.ladp.values-X@b)   # + = drafted EARLIER than weekly projection implies
    parts.append(g)
d=pd.concat(parts)
for lo,hi in [(1,2),(3,4),(5,8),(9,18)]:
    x=d[d.week.between(lo,hi)]
    print(f"weeks {lo}-{hi}: preseason-ADP excess value -> residual vs LineStar PP: {slate_corr(x,'adp_excess','resid')}  n={len(x)}")
x=d[d.week<=4]; x["q"]=x.groupby(["season","week"]).adp_excess.transform(lambda s: pd.qcut(s.rank(method='first'),5,labels=False))
print("weeks 1-4 residual by ADP-excess quintile:", x.groupby("q").resid.mean().round(2).to_dict())
