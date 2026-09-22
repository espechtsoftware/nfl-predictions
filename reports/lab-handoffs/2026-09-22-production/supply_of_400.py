"""How many $400-worthy lineups did our pool actually hold, and could we reach them?"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
for tag,wk,rf,cid,K in [("w1",1,"rix.npy","193028206",90),("item3",2,"roster_idx.npy","195648007",97)]:
    fr=pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    cdf=pd.read_parquet(f"{tag}/cands.parquet"); rix=np.load(f"{tag}/{rf}")
    own=query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                     WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
    pa=np.array([lut.get(str(n),np.nan) for n in fr.display_name],float)
    real=np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
    book=np.array(cdf.loc[cdf.book_rank.notna()].sort_values("book_rank").index)
    f=np.sort(query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
        WHERE season=2026 AND week={wk} AND contest_id='{cid}'""").points.to_numpy(float))[::-1]
    n=len(f)
    print(f"\n=== WEEK {wk} === pool {len(real):,}, book {K}, field {n:,}")
    print(f"  {'target finish':<16}{'score':>8}{'IN POOL':>10}{'pool %':>9}{'in book':>9}"
          f"{'P(>=1 in a random K)':>22}")
    for p in (0.01,0.05,0.1,0.25,0.5,1.0):
        thr=f[max(1,int(n*p/100))-1]
        m=(real>=thr).sum(); b=(real[book]>=thr).sum()
        # hypergeometric P(at least one) for a random K-row book
        pk = 1-np.exp(np.sum(np.log(np.maximum(1e-300,(np.arange(K)* -1 + (len(real)-m))/(len(real)-np.arange(K))))) ) if m>0 else 0.0
        print(f"  top {p:<12}%{thr:>8.2f}{m:>10,}{100*m/len(real):>8.2f}%{b:>9}{100*pk:>21.1f}%")
