"""The winnable frontier: P(win) by field size x quality edge, at N=150 entries."""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
rng=np.random.default_rng(3); T=3000; N=150
fr=pd.read_parquet("w1/frame.parquet").reset_index(drop=True); rix=np.load("w1/rix.npy")
own=query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                 WHERE season=2026 AND week=1 GROUP BY 1""")
lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
pa=np.array([lut.get(str(n),np.nan) for n in fr.display_name],float)
ours=np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
field=query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
    WHERE season=2026 AND week=1 AND contest_id='193028206'""").points.to_numpy(float)
EDGES=[0,5,10,15,20,30]
print(f"P(WIN) with N={N} entries, Week-1 lineup quality + edge\n")
print(f"{'field size':>12}" + "".join(f"{'+'+str(e):>9}" for e in EDGES) + "   <- points added per lineup")
for F in (200, 500, 1000, 2500, 5000, 10000, 25000, 100000):
    row=[]
    for e in EDGES:
        o=ours+e
        b=o[rng.integers(0,len(o),size=(T,N))].max(axis=1)
        t=field[rng.integers(0,len(field),size=(T,max(1,min(F-N,60000))))].max(axis=1)
        if F-N>60000: t=t+6.41*np.log((F-N)/60000)
        row.append(100*(b>t).mean())
    print(f"{F:>12,}" + "".join(f"{v:>8.1f}%" for v in row))
pcts=[100*(field<(ours+e).mean()).mean() for e in EDGES]
print(f"{'field pctile':>12}" + "".join(f"{p:>8.0f}%" for p in pcts))
print("""
'+0' is our ACTUAL Week-1 quality. The frontier is where P(win) stops being trivial.
Note the Week-1 pool sat at the 49th field percentile -- a median DFS entry.""")
