"""P(we WIN) as a function of contest size F and entries N, from real distributions.

We enter N lineups drawn from our actual pool; the other F-N entries are drawn from
the actual field. We win if our best beats theirs. No modelling assumptions -- both
distributions are the realized ones.
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
rng = np.random.default_rng(11)
TRIALS = 4000

for tag,wk,rf,cid in [("w1",1,"rix.npy","193028206"),("item3",2,"roster_idx.npy","195648007")]:
    fr=pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    cdf=pd.read_parquet(f"{tag}/cands.parquet"); rix=np.load(f"{tag}/{rf}")
    own=query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                     WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
    pa=np.array([lut.get(str(n),np.nan) for n in fr.display_name],float)
    ours=np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
    field=query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
        WHERE season=2026 AND week={wk} AND contest_id='{cid}'""").points.to_numpy(float)
    book=np.array(cdf.loc[cdf.book_rank.notna()].sort_values("book_rank").index)
    delivered=ours[book]
    print(f"\n{'='*84}\n=== WEEK {wk} ===  our pool mean {ours.mean():.1f} / field mean {field.mean():.1f}"
          f"   (pool is at the {100*(field<ours.mean()).mean():.0f}th field pctile)")
    print(f"  {'field size':>11}{'N=20':>9}{'N=90':>9}{'N=150':>9}{'N=500':>9}"
          f"{'N=all pool':>12}   <- P(we win)")
    for F in (100, 500, 2000, 5000, 20000, 150000, 831028):
        row=[]
        for N in (20, 90, 150, 500, len(ours)):
            if N >= F: row.append("  n/a"); continue
            o=ours[rng.integers(0,len(ours),size=(TRIALS,N))].max(axis=1)
            t=field[rng.integers(0,len(field),size=(TRIALS,min(F-N, 60000)))].max(axis=1)
            if F-N > 60000:   # extrapolate the field max for very large F
                extra=np.log((F-N)/60000)
                t=t+6.41*extra
            row.append(f"{100*(o>t).mean():6.1f}%")
        print(f"  {F:>11,}" + "".join(f"{v:>9}" for v in row[:4]) + f"{row[4]:>12}")
    # what the DELIVERED book would do
    print(f"  delivered book (N={len(book)}) best {delivered.max():.2f}; "
          f"pool best {ours.max():.2f}; actual winner {field.max():.2f}")
