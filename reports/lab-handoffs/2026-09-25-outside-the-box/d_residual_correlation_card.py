import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
df=pd.read_parquet("ls_main.parquet")
d=df[df.pos.isin(["QB","RB","WR","TE"])&(df.pp>=3)].copy(); d["res"]=d.ps-d.pp
# pre-game roles by salary rank within team & position
d["rk"]=d.groupby(["season","week","team","pos"]).sal.rank(ascending=False,method="first")
role=lambda p,k: d[(d.pos==p)&(d.rk==k)][["season","week","team","opp","res","ps"]]
R={"QB":role("QB",1),"RB1":role("RB",1),"RB2":role("RB",2),"WR1":role("WR",1),"WR2":role("WR",2),"WR3":role("WR",3),"TE1":role("TE",1)}
def pair(a,b,cross=False):
    A=R[a]; B=R[b]
    if cross: m=A.merge(B,left_on=["season","week","team"],right_on=["season","week","opp"],suffixes=("_a","_b"))
    else: m=A.merge(B,on=["season","week","team"],suffixes=("_a","_b"))
    if len(m)<50: return None
    r=np.corrcoef(m.res_a,m.res_b)[0,1]; se=1/np.sqrt(len(m))
    return f"{r:+.3f} (±{1.96*se:.3f}, n={len(m)})"
print("Residual (actual - LineStar projection) correlations, main slates 2022-2026W2")
for a,b in [("QB","WR1"),("QB","WR2"),("QB","TE1"),("QB","RB1"),("WR1","WR2"),("WR1","TE1"),("RB1","RB2"),("RB1","WR1")]:
    print(f"  same team {a}-{b}: {pair(a,b)}")
for a,b in [("QB","QB"),("WR1","WR1"),("QB","WR1"),("RB1","QB"),("RB1","RB1")]:
    print(f"  opponents {a}-opp {b}: {pair(a,b,cross=True)}")
