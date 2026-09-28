"""Mini replay on the LineStar main-slate panel: top-mean books built from RAW projections vs band-CALIBRATED projections
(walk-forward isotonic E[actual|proj] by position) vs calibrated + a ceiling term (kappa * residual sd by pos x band).
DK Classic rules, $49k-50k, 20 lineups per slate per arm, pairwise overlap <= 7. Scores with realized points."""
import pandas as pd, numpy as np, pulp, warnings, sys
from sklearn.isotonic import IsotonicRegression
warnings.filterwarnings("ignore")
KAPPA=float(sys.argv[1]) if len(sys.argv)>1 else 0.35
df=pd.read_parquet("ls_main.parquet")
df=df[df.pp.notna()&df.ps.notna()&(df.pp>=0.5)].copy()
BANDS=[0,4,8,12,16,20,60]
def fit_cal(train):
    cal={}; sd={}
    for p,g in train.groupby("pos"):
        ir=IsotonicRegression(out_of_bounds="clip").fit(g.pp.values,g.ps.values); cal[p]=ir
        g=g.assign(res=g.ps-g.pp,band=pd.cut(g.pp,BANDS,right=False))
        sd[p]=g.groupby("band",observed=True).res.std().to_dict()
    return cal,sd
def build_book(fr,score_col,n=20,max_shared=7):
    idx=list(fr.index); pos=fr.pos.to_dict(); sal=fr.sal.to_dict(); sc=fr[score_col].to_dict()
    books=[]
    for b in range(n):
        m=pulp.LpProblem("lu",pulp.LpMaximize); x={i:pulp.LpVariable(f"x{i}",cat="Binary") for i in idx}
        m+=pulp.lpSum(sc[i]*x[i] for i in idx)
        m+=pulp.lpSum(x.values())==9
        m+=pulp.lpSum(sal[i]*x[i] for i in idx)<=50000; m+=pulp.lpSum(sal[i]*x[i] for i in idx)>=49000
        P=lambda p:[i for i in idx if pos[i]==p]
        m+=pulp.lpSum(x[i] for i in P("QB"))==1; m+=pulp.lpSum(x[i] for i in P("DST"))==1
        for p,lo,hi in (("RB",2,3),("WR",3,4),("TE",1,2)):
            m+=pulp.lpSum(x[i] for i in P(p))>=lo; m+=pulp.lpSum(x[i] for i in P(p))<=hi
        for prev in books: m+=pulp.lpSum(x[i] for i in prev)<=max_shared
        m.solve(pulp.PULP_CBC_CMD(msg=0,timeLimit=20))
        if pulp.LpStatus[m.status]!="Optimal": break
        books.append([i for i in idx if x[i].value()>0.5])
    return books
rows=[]
for season in (2023,2024,2025,2026):
    train=df[df.season<season]; cal,sd=fit_cal(train)
    for week,fr in df[df.season==season].groupby("week"):
        fr=fr.copy()
        fr["cal"]=[float(cal[p].predict([v])[0]) if p in cal else v for p,v in zip(fr.pos,fr.pp)]
        band=pd.cut(fr.pp,BANDS,right=False)
        fr["sig"]=[sd.get(p,{}).get(b,7.0) if pd.notna(b) else 7.0 for p,b in zip(fr.pos,band)]
        fr["sig"]=fr.sig.fillna(7.0); fr["ceil"]=fr.cal+KAPPA*fr.sig
        for arm,col in (("RAW","pp"),("CAL","cal"),("CEIL","ceil")):
            bk=build_book(fr,col)
            if len(bk)<20: print("short",season,week,arm,len(bk)); 
            tot=np.array([fr.loc[b,"ps"].sum() for b in bk]); proj=np.array([fr.loc[b,"pp"].sum() for b in bk])
            rows.append(dict(season=season,week=week,arm=arm,mean=tot.mean(),best=tot.max(),ge170=(tot>=170).sum(),ge190=(tot>=190).sum(),
                             proj_raw=proj.mean(),n=len(bk)))
r=pd.DataFrame(rows); r.to_csv(f"cal_replay_k{KAPPA}.csv",index=False)
print(f"kappa={KAPPA}; slates {r.groupby(['season','week']).ngroups}")
print(r.groupby("arm")[["mean","best","ge170","ge190","proj_raw"]].mean().round(2).to_string())
w=r.pivot_table(index=["season","week"],columns="arm",values=["mean","best","ge170","ge190"])
for arm in ("CAL","CEIL"):
    for m in ("mean","best","ge170","ge190"):
        d=w[m][arm]-w[m]["RAW"]; t=d.mean()/(d.std(ddof=1)/np.sqrt(len(d)))
        bys=d.groupby(level=0).mean().round(2).to_dict()
        print(f"{arm}-RAW {m:5s}: {d.mean():+.2f} (t {t:+.1f}, wins {int((d>0).sum())}/{int((d<0).sum())}) by season {bys}")
# calibration curve summary for the last fit
cal,sd=fit_cal(df[df.season<2026])
print("\ncalibration E[actual|proj] fitted on 2022-25, at proj = 8/12/16/20/24:")
for p in ("QB","RB","WR","TE","DST"):
    if p in cal: print(" ",p,[round(float(cal[p].predict([v])[0]),1) for v in (8,12,16,20,24)])
