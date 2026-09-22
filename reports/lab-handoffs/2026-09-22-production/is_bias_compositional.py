"""Is the simulator's error a uniform LEVEL shift, or compositional?

A uniform shift is harmless to expected-max selection -- it moves every lineup equally.
A shift that grows with the lineup's own simulated score distorts RANKING, and would be
the mechanism behind the regime flip. Test: within a week, does PIT fall as the
simulator's own prediction rises?
"""
import numpy as np, pandas as pd, sys
from scipy.stats import spearmanr
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
for tag,wk,rf in [("w1",1,"rix.npy"),("item3",2,"roster_idx.npy")]:
    fr=pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True); rix=np.load(f"{tag}/{rf}")
    dual=np.concatenate([np.load(f"{tag}/T_inc.npy"),np.load(f"{tag}/T_hs.npy")],axis=1).astype(float)
    own=query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                     WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
    pa=np.array([lut.get(str(n),np.nan) for n in fr.display_name],float)
    real=np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
    smean=dual.mean(axis=1)
    pit=(dual<=real[:,None]).mean(axis=1)
    err=real-smean
    print(f"\n=== WEEK {wk} ===  n={len(real):,}")
    print(f"  overall bias (realized - simulated): {err.mean():+7.2f}   sd {err.std():6.2f}")
    print(f"  corr(sim_mean, PIT)          {np.corrcoef(smean,pit)[0,1]:+.3f}   "
          f"spearman {spearmanr(smean,pit).statistic:+.3f}")
    print(f"  corr(sim_mean, error)        {np.corrcoef(smean,err)[0,1]:+.3f}")
    # decile table: does the bias vary with what the simulator predicted?
    q=pd.qcut(smean,10,labels=False,duplicates="drop")
    t=pd.DataFrame(dict(q=q,sim=smean,real=real,err=err,pit=pit)).groupby("q").mean()
    print(f"  {'decile of sim_mean':<20}{'sim':>9}{'realized':>10}{'bias':>9}{'mean PIT':>10}")
    for i,r in t.iterrows():
        print(f"  {int(i)+1:<20}{r.sim:>9.2f}{r.real:>10.2f}{r.err:>9.2f}{r.pit:>10.3f}")
    spread = t.err.iloc[-1]-t.err.iloc[0]
    print(f"  --> bias changes by {spread:+.2f} pts from the simulator's worst decile to its best")
    print(f"      {'COMPOSITIONAL: ranking is distorted' if abs(spread)>5 else 'roughly a uniform shift: ranking preserved'}")
