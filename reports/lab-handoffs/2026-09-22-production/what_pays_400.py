"""What finish pays $400, and is that score in our pool?"""
import pandas as pd, numpy as np, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

d = pd.read_pickle("dk_history.pkl")
d = d[(d.Entry_Fee>0) & (d.Contest_Entries>50000)].copy()
d["pct_rank"] = 100*d.Place/d.Contest_Entries
c = d[d.won>0].sort_values("pct_rank")
print("=== observed payouts in LARGE fields (>50k), best finishes first ===")
print(c[["Entry_Fee","Contest_Entries","Place","pct_rank","Points","won"]]
      .head(12).to_string(index=False, float_format=lambda v:f"{v:,.3f}"))

# DK Millionaire standard: $20 entry. Infer $ per rank from the observed pairs.
print("\n=== what score reaches which percentile of the real field ===")
POOL={1:236.28, 2:197.26}; BOOK={1:218.40, 2:157.96}
for wk,cid in [(1,"193028206"),(2,"195648007")]:
    f = query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
                     WHERE season=2026 AND week={wk} AND contest_id='{cid}'""").points.to_numpy(float)
    f = np.sort(f)[::-1]; n=len(f)
    print(f"\n  WEEK {wk}  field {n:,}   our pool oracle {POOL[wk]:.2f}   book best {BOOK[wk]:.2f}")
    for p,lbl in [(0.01,"top 0.01% (rank %d)"),(0.05,"top 0.05%"),(0.1,"top 0.1%"),
                  (0.25,"top 0.25%"),(0.5,"top 0.5%"),(1.0,"top 1%")]:
        k=max(1,int(n*p/100)); thr=f[k-1]
        poolok = "POOL CLEARS" if POOL[wk]>=thr else ""
        bookok = "book clears" if BOOK[wk]>=thr else ""
        print(f"    {lbl.split(' (')[0]:<12} rank {k:>7,}  score {thr:7.2f}   {poolok:<12}{bookok}")
    # where our numbers actually land
    pr=lambda v:(f>v).sum()+1
    print(f"    -> pool oracle {POOL[wk]:.2f} = rank {pr(POOL[wk]):,} ({100*pr(POOL[wk])/n:.3f}%)")
    print(f"    -> book best   {BOOK[wk]:.2f} = rank {pr(BOOK[wk]):,} ({100*pr(BOOK[wk])/n:.3f}%)")
