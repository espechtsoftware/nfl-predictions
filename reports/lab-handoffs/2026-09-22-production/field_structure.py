"""(a) Does lev ever reach the winning tail? (b) Field structure of 232+/250+ Millionaire lineups."""
import sys, re, numpy as np, pandas as pd
from collections import Counter
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
SLOT=re.compile(r"\b(QB|RB|WR|TE|FLEX|DST)\s+")
def parse(s):
    p=SLOT.split(s.strip()); return [(p[i],p[i+1].strip()) for i in range(1,len(p)-1,2) if p[i+1].strip()]
for tag,wk,rf,cid in [("w1",1,"rix.npy","193028206"),("item3",2,"roster_idx.npy","195648007")]:
    fr=pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True); cd=pd.read_parquet(f"{tag}/cands.parquet"); rix=np.load(f"{tag}/{rf}")
    own=query_df(f"SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership` WHERE season=2026 AND week={wk} GROUP BY 1")
    lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
    real=np.nan_to_num(np.array([lut.get(str(n),np.nan) for n in fr.display_name],float))[rix].sum(axis=1)
    fam=cd.tag.astype(str).str.extract(r"^([a-z_]+)")[0].to_numpy()
    print(f"\n=== WEEK {wk} (a) the winning tail, by generator ===")
    for t in (200,210,220,230):
        print(f"   >= {t}: boom {int(((fam=='boom')&(real>=t)).sum()):>4}   lev {int(((fam=='lev')&(real>=t)).sum()):>4}")
    team=dict(zip(fr.display_name.astype(str),fr.team.astype(str))); opp=dict(zip(fr.display_name.astype(str),fr.opp.astype(str)))
    sal=dict(zip(fr.display_name.astype(str),fr.salary.astype(float)))
    # DST names in the field are team nicknames; map via frame rows where pos==DST
    dstmap={str(n).split()[-1]:str(t) for n,t,p in zip(fr.display_name,fr.team,fr.pos) if str(p)=="DST"}
    f=query_df(f"SELECT lineup, points FROM `{settings.raw}.contest_entries` WHERE season=2026 AND week={wk} AND contest_id='{cid}' AND points>=200")
    rows=[]
    for s,pts in zip(f.lineup,f.points):
        L=parse(s); qb=[n for sl,n in L if sl=="QB"]
        if not qb: continue
        q=qb[0]; qt=team.get(q); qo=opp.get(q)
        mates=[n for sl,n in L if sl not in("QB","DST") and team.get(n)==qt]
        bring=[n for sl,n in L if sl not in("QB","DST") and team.get(n)==qo]
        spent=sum(sal.get(n, sal.get(n,0)) for sl,n in L if sl!="DST")+sum(sal.get(next((x for x in fr.display_name if str(x).endswith(n)),""),0) for sl,n in L if sl=="DST")
        rows.append(dict(points=pts,nstack=len(mates),bringback=len(bring)>0,left=50000-spent))
    d=pd.DataFrame(rows)
    print(f"=== WEEK {wk} (b) real Millionaire field, lineups >= 200 (n={len(d)}) ===")
    for lo in (200,232,250):
        x=d[d.points>=lo]
        if not len(x): continue
        print(f"   >= {lo}: n={len(x):>5}  naked QB {100*(x.nstack==0).mean():5.1f}%  QB+1 {100*(x.nstack==1).mean():5.1f}%  "
              f"QB+2 {100*(x.nstack==2).mean():5.1f}%  QB+3+ {100*(x.nstack>=3).mean():5.1f}%  | no bring-back {100*(~x.bringback).mean():5.1f}%  "
              f"| salary left median ${x.left.median():.0f}, >= $400 {100*(x.left>=400).mean():.0f}%")
    print(f"   our generator: 100% QB+2 or more, 100% bring-back (constraints)")
