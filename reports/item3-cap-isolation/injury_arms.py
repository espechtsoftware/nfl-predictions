"""Item 5: isolate Erich's actual request -- limit injured-player concentration --
from the general exposure cap it was bundled with."""
import numpy as np, pandas as pd, json
from emax import emax_select

T=np.load("T_inc.npy"); Tv=np.load("T_hs.npy"); rix=np.load("roster_idx.npy")
realized=np.load("cand_realized.npy"); pa=np.load("player_actual.npy")
fr=pd.read_parquet("frame.parquet").reset_index(drop=True)
K,NP,W=97,len(fr),20000
fr["has_prop"]=fr.market_points.notna()
sk=fr[fr.position.isin(["QB","RB","WR","TE"])]

def peer_cov(r,band=800,minn=6):
    p=sk[(sk.position==r.position)&(sk.salary.between(r.salary-band,r.salary+band))
         &(sk.report_status.isna())&(sk.display_name!=r.display_name)]
    return float(p.has_prop.mean()) if len(p)>=minn else np.nan

def injury_caps(peer_aware):
    c=np.full(NP,K,dtype=np.int32)
    for i,r in fr.iterrows():
        if pd.isna(r.report_status): continue
        if r.report_status=="Doubtful": c[i]=0; continue
        if r.has_prop: c[i]=int(0.10*K); continue
        if peer_aware:
            cov=peer_cov(r)
            c[i]=int(0.05*K) if (not np.isnan(cov) and cov>=0.8) else int(0.10*K)
        else:
            c[i]=int(0.05*K)
    return c

def run(caps,label):
    b,_=emax_select(T,Tv,K,caps=caps,roster_idx=rix,n_players=NP)
    b=np.array(b); s=realized[b]
    emax=(np.maximum.reduce(T[b]).astype(np.float64).sum()
          +np.maximum.reduce(Tv[b]).astype(np.float64).sum())/W
    cnt=np.zeros(NP,dtype=int); np.add.at(cnt,rix[b],1)
    return dict(arm=label,n=len(b),sim_Emax=round(float(emax),2),
                mean=round(float(s.mean()),2),best=round(float(s.max()),2),
                n150=int((s>=150).sum()),
                mcconkey=int(cnt[fr.index[fr.display_name=="Ladd McConkey"][0]]),
                max_exp=int(cnt.max())), b, cnt

base,bb,cb=run(np.full(NP,K,np.int32),"delivered (no cap)")
a1,b1,c1=run(injury_caps(False),"injury rule, raw no-prop")
a2,b2,c2=run(injury_caps(True),"injury rule, peer-coverage aware")
gen=np.full(NP,int(0.30*K),np.int32); gen[fr.position.eq("DST").to_numpy()]=int(0.20*K)
a3,b3,c3=run(np.minimum(gen,injury_caps(True)),"injury rule + general 30%/DST 20%")
df=pd.DataFrame([base,a1,a2,a3])
df["dEmax"]=(df.sim_Emax-base["sim_Emax"]).round(2)
print(df.to_string(index=False))
df.to_csv("injury_arms.csv",index=False)

LAYOUT=[("milly",1,1),("flea",2,24),("huddle",25,25),("nickel",26,30),("pylon",31,31),
        ("satellite",32,33),("supersat1a",34,43),("supersat1b",44,53),("supersat1c",54,63),
        ("supersat25a",64,79),("supersat25b",80,95),("ffwcsat",96,97)]
mc=fr.index[fr.display_name=="Ladd McConkey"][0]
print("\nMcConkey rows per contest (delivered assignment held fixed):")
out=[]
for name,lo,hi in LAYOUT:
    row={"contest":name,"rows":hi-lo+1}
    for lbl,bk in (("delivered",bb),("injury_peer",b2),("injury+general",b3)):
        row[lbl]=int(sum(mc in set(rix[c]) for c in bk[lo-1:hi]))
    out.append(row)
t=pd.DataFrame(out); print(t.to_string(index=False))
t.to_csv("mcconkey_per_contest.csv",index=False)
print("\ntotals:", {k:int(t[k].sum()) for k in ("delivered","injury_peer","injury+general")})
