"""Is the QB over-projection concentrated in cheap backups who never play?

If so the fix is availability conditioning -- the same repair as the Doubtful rule --
and it is the one systematic, both-weeks defect the data supports.
"""
import numpy as np, pandas as pd, sys
from scipy.stats import spearmanr
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

for tag, wk, rf in [("w1",1,"rix.npy"), ("item3",2,"roster_idx.npy")]:
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    rix = np.load(f"{tag}/{rf}")
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    fr["realized_raw"] = [lut.get(str(n), np.nan) for n in fr.display_name]
    fr["played"] = fr.realized_raw.notna() & (fr.realized_raw > 0)
    fr["realized"] = fr.realized_raw.fillna(0.0)
    used = np.zeros(len(fr), bool); used[np.unique(rix)] = True
    usage = np.bincount(rix.ravel(), minlength=len(fr)) / len(rix)
    fr["usage"] = usage
    q = fr[used & (fr.pos == "QB")].copy()
    q["err"] = q.realized - q.proj
    print(f"\n=== WEEK {wk} === selectable QBs: {len(q)}")
    for lbl, m in [("cheap  (<=$4,600)", q.salary <= 4600),
                   ("mid    ($4,601-6,000)", (q.salary > 4600) & (q.salary <= 6000)),
                   ("premium (>$6,000)", q.salary > 6000)]:
        s = q[m]
        if not len(s): continue
        sp = spearmanr(s.proj, s.realized).statistic if len(s) > 3 else np.nan
        print(f"  {lbl:<22} n={len(s):>3}  played {100*s.played.mean():5.1f}%  "
              f"proj {s.proj.mean():5.2f}  realized {s.realized.mean():5.2f}  "
              f"BIAS {s.err.mean():+6.2f}  pool usage {100*s.usage.sum():5.1f}%"
              + (f"  spearman {sp:+.3f}" if np.isfinite(sp) else ""))
    # what QB bias remains once never-played QBs are dropped?
    p = q[q.played]
    print(f"  --> QBs who actually played: n={len(p)}  BIAS {p.err.mean():+.2f}"
          f"   (all selectable QBs: {q.err.mean():+.2f})")
    dead = q[~q.played]
    print(f"  --> never-played QBs: n={len(dead)}  mean proj {dead.proj.mean():5.2f}  "
          f"total pool usage {100*dead.usage.sum():.1f}% of lineups")
