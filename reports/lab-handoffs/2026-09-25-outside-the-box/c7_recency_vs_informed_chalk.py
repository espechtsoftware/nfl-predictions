"""Among the 15 most-owned players per slate: recency-inflated chalk vs information-driven chalk."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
sk=pd.read_parquet("ls_skill_analysis.parquet")
r=sk[sk.played].dropna(subset=["prev_surprise"]).copy(); parts=[]
for k,g in r.groupby(["season","week"]):
    if len(g)<25: continue
    X=np.column_stack([np.ones(len(g)),g.prev_surprise.values]); b,*_=np.linalg.lstsq(X,g.e_act.values,rcond=None)
    g=g.copy(); g["own_rec"]=X@b-b[0]; parts.append(g)
r=pd.concat(parts); c=r[r.groupby(["season","week"]).own_act.rank(ascending=False)<=15].copy()
c["rec_hi"]=c.own_rec>=c.groupby(["season","week"]).own_rec.transform("median"); c["boom25"]=c.ps>=25
print(c.groupby("rec_hi").agg(n=("ps","size"),own=("own_act","mean"),pp=("pp","mean"),ps=("ps","mean"),resid=("resid","mean"),
      boom25=("boom25","mean"),prev_surprise=("prev_surprise","mean")).round(3).to_string())
d=c.groupby(["season","week","rec_hi"]).agg(res=("resid","mean"),b=("boom25","mean")).unstack()
dd=(d["res"][True]-d["res"][False]).dropna(); db=(d["b"][True]-d["b"][False]).dropna()
print("paired resid diff %+.2f (t %+.1f); boom25 diff %+.3f (t %+.1f)"%(dd.mean(),dd.mean()/(dd.std(ddof=1)/np.sqrt(len(dd))),db.mean(),db.mean()/(db.std(ddof=1)/np.sqrt(len(db)))))
