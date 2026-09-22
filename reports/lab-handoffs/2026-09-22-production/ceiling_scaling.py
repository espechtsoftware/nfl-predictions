"""Can MORE candidates reach the winning line? Measure how pool oracle grows with size.

Subsamples each week's pool at increasing sizes, takes the max realized, and fits
the growth. Then extrapolates how many candidates the observed curve needs to reach
that week's actual Millionaire winning line.
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
rng = np.random.default_rng(20260922)
WIN = {1: 273.98, 2: 232.38}

for tag, wk, rf in [("w1",1,"rix.npy"), ("item3",2,"roster_idx.npy")]:
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    rix = np.load(f"{tag}/{rf}")
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    pa = np.array([lut.get(str(n), np.nan) for n in fr.display_name], float)
    real = np.where(np.isnan(pa), 0.0, pa)[rix].sum(axis=1)
    N = len(real)
    print(f"\n=== WEEK {wk}  pool {N}, oracle {real.max():.2f}, winning line {WIN[wk]:.2f} ===")
    sizes = [s for s in (100,200,400,800,1600,3200,6400,12555) if s <= N]
    xs, ys = [], []
    print(f"  {'n':>7}{'E[max]':>10}{'sd':>7}{'best seen':>11}")
    for s in sizes:
        m = np.array([real[rng.choice(N, s, replace=False)].max() for _ in range(200)])
        print(f"  {s:>7}{m.mean():>10.2f}{m.std():>7.2f}{m.max():>11.2f}")
        xs.append(np.log(s)); ys.append(m.mean())
    # E[max] grows ~ linearly in log n for light-tailed maxima
    b, a = np.polyfit(xs, ys, 1)
    print(f"  fit: E[max] ~ {a:.2f} + {b:.2f}*ln(n)   (R^2 "
          f"{np.corrcoef(xs,ys)[0,1]**2:.4f})")
    need = np.exp((WIN[wk] - a) / b)
    print(f"  --> candidates needed for E[max] to reach {WIN[wk]:.2f}: {need:,.0f}"
          f"  ({need/N:,.0f}x the actual pool)")
