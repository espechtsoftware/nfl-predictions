"""Real 40+/45+/50+ DK eruptions by position and LineStar projection band (vs the lab law's hard tail cap)."""
import pandas as pd
df=pd.read_parquet("ls_main.parquet")
d=df[df.pos.isin(["QB","RB","WR","TE"])&(df.pp>=5)].copy(); d["band"]=pd.cut(d.pp,[5,10,15,20,30],right=False)
t=d.groupby(["pos","band"],observed=True).agg(n=("ps","size"),p40=("ps",lambda s:(s>=40).mean()),p45=("ps",lambda s:(s>=45).mean()),
     p50=("ps",lambda s:(s>=50).mean()),q99=("ps",lambda s:s.quantile(.99)))
print(t.round(4).to_string())
for p in ["QB","RB","WR","TE"]:
    x=d[d.pos==p].ps; e=x[x>=35]-35; print(p,"n>=35",len(e),"mean excess above 35 %.2f"%e.mean())
a=df[df.pos.isin(["QB","RB","WR","TE"])]
per=a.groupby(["season","week"]).ps
print("per slate: 40+ %.2f, 45+ %.2f"%(per.apply(lambda s:(s>=40).sum()).mean(),per.apply(lambda s:(s>=45).sum()).mean()))
