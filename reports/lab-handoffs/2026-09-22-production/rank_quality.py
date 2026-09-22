"""Is the Week-2 damage a uniform level shift (harmless to lineup ranking) or
differential error (fatal)? A uniform shift moves every lineup equally.
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
    fr["realized"] = [lut.get(str(n), np.nan) for n in fr.display_name]
    used = np.zeros(len(fr), bool); used[np.unique(rix)] = True
    d = fr[used & fr.realized.notna()].copy()
    d["err"] = d.realized - d.proj
    print(f"\n=== WEEK {wk} === {len(d)} selectable players with a realized score")
    print(f"  mean proj {d.proj.mean():6.2f}   mean realized {d.realized.mean():6.2f}   "
          f"BIAS {d.err.mean():+6.2f}   sd(err) {d.err.std():5.2f}")
    print(f"  Pearson  corr(proj, realized) {np.corrcoef(d.proj,d.realized)[0,1]:+.3f}")
    print(f"  Spearman rank corr            {spearmanr(d.proj,d.realized).statistic:+.3f}   "
          f"<- this is what construction actually uses")
    # after removing a uniform shift, how much error is left?
    resid = d.err - d.err.mean()
    print(f"  sd of error after removing the uniform shift: {resid.std():5.2f}  "
          f"(uniform shift explains {100*(1-(resid.std()/d.err.std())**2):.1f}% of error variance)")
    for pos in ("QB","RB","WR","TE","DST"):
        s = d[d.pos == pos]
        if len(s) > 4:
            print(f"    {pos:<4} n={len(s):>3}  bias {s.err.mean():+6.2f}  "
                  f"spearman {spearmanr(s.proj,s.realized).statistic:+.3f}")
