"""What per-lineup quality EDGE would make winning possible?

Shifts our whole pool distribution by delta and recomputes P(win) against the real
field. Answers: how much better would every lineup have to be?
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
rng=np.random.default_rng(5); T=3000
fr=pd.read_parquet("w1/frame.parquet").reset_index(drop=True)
rix=np.load("w1/rix.npy")
own=query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                 WHERE season=2026 AND week=1 GROUP BY 1""")
lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
pa=np.array([lut.get(str(n),np.nan) for n in fr.display_name],float)
ours=np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
field=query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
    WHERE season=2026 AND week=1 AND contest_id='193028206'""").points.to_numpy(float)
print(f"Week 1. Our pool mean {ours.mean():.1f} (field {field.mean():.1f}); "
      f"field max {field.max():.2f}, {len(field):,} entries\n")
print(f"{'edge (pts/lineup)':<20}{'our pool mean':>15}{'field pctile':>14}"
      f"{'P(win) N=150':>15}{'P(win) N=500':>15}")
for dlt in (0,5,10,20,30,40,50,60):
    o = ours + dlt
    pct = 100*(field < o.mean()).mean()
    row=[]
    for N in (150,500):
        b=o[rng.integers(0,len(o),size=(T,N))].max(axis=1)
        t=field[rng.integers(0,len(field),size=(T,60000))].max(axis=1)+6.41*np.log(831028/60000)
        row.append(100*(b>t).mean())
    print(f"{dlt:<20}{o.mean():>15.1f}{pct:>13.0f}%{row[0]:>14.1f}%{row[1]:>14.1f}%")
print("""
Reading: 'edge' adds that many points to EVERY lineup we build. Our Week-1 pool was
already at the 49th field percentile -- i.e. the average lineup we generate is a
median DFS entry. The edge column says what it would take to win the Millionaire.""")
