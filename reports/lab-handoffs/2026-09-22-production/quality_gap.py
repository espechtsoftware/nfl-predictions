"""Is our per-lineup quality above or below the field's? Both weeks.

Compares our book and pool against the actual field score distribution, and asks the
equal-draw-count question: at N draws, what does the FIELD's max reach vs OUR pool's?
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
rng = np.random.default_rng(7)

for tag, wk, rf in [("w1",1,"rix.npy"), ("item3",2,"roster_idx.npy")]:
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    cdf = pd.read_parquet(f"{tag}/cands.parquet"); rix = np.load(f"{tag}/{rf}")
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    pa = np.array([lut.get(str(n), np.nan) for n in fr.display_name], float)
    real = np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
    book = np.array(cdf.loc[cdf.book_rank.notna()].sort_values("book_rank").index)
    bs = real[book]
    # biggest contest that week = the Millionaire
    cid = query_df(f"""SELECT contest_id, COUNT(*) n FROM `{settings.raw}.contest_entries`
                       WHERE season=2026 AND week={wk} GROUP BY 1 ORDER BY n DESC LIMIT 1""")
    field = query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
                         WHERE season=2026 AND week={wk}
                         AND contest_id='{cid.contest_id.iloc[0]}'""").points.to_numpy(float)
    print(f"\n=== WEEK {wk}   field {len(field):,} entries ===")
    q = lambda v: 100*(field < v).mean()
    print(f"  field   median {np.median(field):7.2f}  p80 {np.quantile(field,.80):7.2f}  "
          f"p99 {np.quantile(field,.99):7.2f}  max {field.max():7.2f}")
    print(f"  OUR BOOK mean {bs.mean():7.2f} (field pctile {q(bs.mean()):5.1f})   "
          f"best {bs.max():7.2f} (pctile {q(bs.max()):5.1f})")
    print(f"  OUR POOL mean {real.mean():7.2f} (field pctile {q(real.mean()):5.1f})   "
          f"max  {real.max():7.2f} (pctile {q(real.max()):5.1f})")
    top20 = np.quantile(field, 0.80)
    print(f"  rows in the field's top 20% : book {(bs>=top20).sum():3d}/{len(bs)} "
          f"({100*(bs>=top20).mean():4.1f}%)   pool {100*(real>=top20).mean():4.1f}%   "
          f"[an average entry: 20.0%]")
    # equal-draw-count: N draws from the field vs N from our pool
    print(f"  {'N draws':>9}{'field max':>12}{'our pool max':>14}{'deficit':>10}")
    for N in (100, 1000, len(real)):
        fm = np.array([rng.choice(field, N, replace=False).max() for _ in range(300)]).mean()
        om = np.array([real[rng.choice(len(real), N, replace=False)].max() for _ in range(300)]).mean()
        print(f"  {N:>9,}{fm:>12.2f}{om:>14.2f}{om-fm:>+10.2f}")
