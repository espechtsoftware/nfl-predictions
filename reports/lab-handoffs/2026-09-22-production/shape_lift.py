"""Per-lineup: does the generator's forced shape (QB+2+ AND bring-back) reach the tail MORE
often than other shapes? Full field, lift = share among top lineups / share of whole field."""
import sys, re, numpy as np, pandas as pd
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
SLOT=re.compile(r"\b(QB|RB|WR|TE|FLEX|DST)\s+")
for tag,wk,cid in [("w1",1,"193028206"),("item3",2,"195648007")]:
    fr=pd.read_parquet(f"{tag}/frame.parquet")
    team=dict(zip(fr.display_name.astype(str),fr.team.astype(str))); opp=dict(zip(fr.display_name.astype(str),fr.opp.astype(str)))
    f=query_df(f"SELECT lineup, points FROM `{settings.raw}.contest_entries` WHERE season=2026 AND week={wk} AND contest_id='{cid}'")
    st=[];bb=[]
    for s in f.lineup:
        p=SLOT.split(s.strip()); L=[(p[i],p[i+1].strip()) for i in range(1,len(p)-1,2)]
        q=next((n for sl,n in L if sl=="QB"),None); qt=team.get(q); qo=opp.get(q)
        st.append(sum(1 for sl,n in L if sl not in("QB","DST") and team.get(n)==qt and qt))
        bb.append(any(sl not in("QB","DST") and team.get(n)==qo and qo for sl,n in L))
    d=pd.DataFrame(dict(points=f.points.to_numpy(float),nstack=st,bring=bb))
    d["form"]=np.where((d.nstack>=2)&d.bring,"QB+2+ with bring-back (OUR ONLY SHAPE)",
                np.where(d.nstack>=2,"QB+2+ no bring-back",np.where(d.nstack==1,"QB+1","naked QB")))
    n=len(d); print(f"\n=== WEEK {wk}: {n:,} field lineups ===")
    th={"top 1%":np.quantile(d.points,0.99),"top 0.1%":np.quantile(d.points,0.999),"top 0.01%":np.quantile(d.points,0.9999)}
    print(f"{'shape':<42}{'field share':>12}" + "".join(f"{k+' lift':>16}" for k in th))
    for s_,g in d.groupby("form"):
        row=f"{s_:<42}{100*len(g)/n:>11.1f}%"
        for k,t in th.items():
            top=d.points>=t; share_top=(top&(d["form"]==s_)).sum()/top.sum(); row+=f"{share_top/(len(g)/n):>11.2f} (n={int((top&(d["form"]==s_)).sum())})"
        print(row)
