"""Is the simulator's JOINT distribution calibrated? PIT test on real outcomes.

A lineup score is the sum of nine DEPENDENT player outcomes, so the lineup-total
distribution is the joint's signature. For each candidate, find the quantile of its own
simulated distribution that its REALIZED score landed in (probability integral
transform). Calibrated -> uniform on [0,1].

  U-shaped  -> simulator UNDER-disperses: real outcomes land in its tails too often,
               the classic signature of under-modelled positive dependence.
  peaked    -> OVER-disperses (too wide).
  shifted   -> level bias, not a dependence problem.

Retrospective diagnostic on released weeks. No model is fitted.
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

for tag,wk,rf in [("w1",1,"rix.npy"),("item3",2,"roster_idx.npy")]:
    fr=pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True); rix=np.load(f"{tag}/{rf}")
    T=np.load(f"{tag}/T_inc.npy"); Tv=np.load(f"{tag}/T_hs.npy")
    dual=np.concatenate([T,Tv],axis=1).astype(np.float64)
    own=query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                     WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
    pa=np.array([lut.get(str(n),np.nan) for n in fr.display_name],float)
    real=np.where(np.isnan(pa),0.0,pa)[rix].sum(axis=1)
    # PIT: fraction of a candidate's own simulated worlds at or below its realized score
    pit=(dual <= real[:,None]).mean(axis=1)
    print(f"\n{'='*74}\n=== WEEK {wk} ===  {len(real):,} candidates x {dual.shape[1]} worlds")
    print(f"  simulated mean {dual.mean():7.2f}  sd {dual.std():6.2f}   "
          f"realized mean {real.mean():7.2f}  sd {real.std():6.2f}")
    print(f"  per-candidate simulated sd: mean {dual.std(axis=1).mean():.2f}")
    h,_=np.histogram(pit,bins=10,range=(0,1))
    print(f"  PIT decile counts (uniform would be {len(pit)/10:.0f} each):")
    print("   ", "  ".join(f"{v:>5}" for v in h))
    print("   ", "  ".join(f"{100*v/len(pit):>4.1f}%" for v in h))
    lo,hi = (pit<=0.1).mean(), (pit>=0.9).mean()
    mid = ((pit>0.3)&(pit<0.7)).mean()
    print(f"  tails: P(PIT<=0.1)={100*lo:.1f}%  P(PIT>=0.9)={100*hi:.1f}%  "
          f"(uniform: 10% each)   middle 40%: {100*mid:.1f}% (uniform 40%)")
    verdict = ("UNDER-disperses (tails too heavy in reality)" if lo+hi > 0.25
               else "OVER-disperses (reality too central)" if lo+hi < 0.15 else "roughly calibrated spread")
    print(f"  --> {verdict}")
    print(f"  mean PIT {pit.mean():.3f} (0.5 = unbiased level); "
          f"{'sim runs HIGH' if pit.mean()<0.45 else 'sim runs LOW' if pit.mean()>0.55 else 'level ok'}")
    for t in (194,220,250):
        print(f"    P(score>={t}): simulated {100*(dual>=t).mean():6.3f}%   "
              f"realized {100*(real>=t).mean():6.3f}%")
