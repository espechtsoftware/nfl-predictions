"""Simulator calibration at the cash line, whole pool, both weeks.
Bin candidates by simulated P(>= line); compare to the realized rate in each bin."""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
for tag, wk, rf, cid in [("w1",1,"rix.npy","193028206"), ("item3",2,"roster_idx.npy","195648007")]:
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    rix = np.load(f"{tag}/{rf}")
    dual = np.concatenate([np.load(f"{tag}/T_inc.npy"), np.load(f"{tag}/T_hs.npy")],axis=1).astype(float)
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    pa = np.array([lut.get(str(n), np.nan) for n in fr.display_name], float)
    real = np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
    field = query_df(f"""SELECT points FROM `{settings.raw}.contest_entries`
                         WHERE season=2026 AND week={wk} AND contest_id='{cid}'""").points.to_numpy(float)
    line = np.quantile(field, 0.80)
    p = (dual >= line).mean(axis=1); hit = (real >= line).astype(float)
    print(f"\n=== WEEK {wk} === cash line {line:.2f}; pool overall predicted "
          f"{p.mean():.3f} vs realized {hit.mean():.3f}")
    print(f"  {'decile of sim P':<18}{'n':>7}{'mean sim P':>12}{'realized rate':>15}")
    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    for b in sorted(pd.unique(q)):
        m = q == b
        print(f"  {b+1:<18}{m.sum():>7}{p[m].mean():>12.3f}{hit[m].mean():>15.3f}")
    from scipy.stats import spearmanr
    print(f"  Spearman(sim P, realized hit) = {spearmanr(p, hit).statistic:+.3f}")
