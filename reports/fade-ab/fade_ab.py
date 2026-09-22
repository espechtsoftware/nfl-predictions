"""Week-1 regeneration A/B: does restoring the adopted chalk fade improve LEV?

Identical frame, stack, env, dose and solver. The ONLY difference is whether
proj_tourney carries the -25.0 * naive_ownership term the production formula
specifies and that live_week.py has never supplied.
"""
import sys, time, json
import numpy as np, pandas as pd
sys.path.insert(0, "/home/erich/projects/.nfl2-worktrees/week3-live-center/src")
sys.path.insert(0, "/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl2.pipeline import PRODUCTION_ENV, PRODUCTION_STACK, _pool, LEVERAGE_PENALTY
from nfl2.core.lineup import optimize_many
from nfl_dfs.backtest.field import naive_ownership

N_LEV = int(sys.argv[1]) if len(sys.argv) > 1 else 640
fr = pd.read_parquet("frame.parquet")

# base == the delivered proj_tourney: that run was degraded, so proj_tourney IS base.
base = pd.to_numeric(fr.proj_tourney, errors="coerce").fillna(0.0).to_numpy(float)
own = naive_ownership(fr.rename(columns={"proj": "proj"})[["proj", "salary", "pos"]].assign(
    proj=pd.to_numeric(fr.proj, errors="coerce").fillna(0.0)))
faded = base - LEVERAGE_PENALTY * own
print(f"own_est: min={own.min():.5f} max={own.max():.5f} sum={own.sum():.3f} "
      f"(within-position weights, {fr.pos.nunique()} groups)")
print(f"fade size: mean={np.abs(base-faded).mean():.3f} max={np.abs(base-faded).max():.3f} points")

# realized, same source and convention as the cap test
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
own_tbl = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week=1 GROUP BY 1""")
lut = dict(zip(own_tbl.display_name.astype(str), own_tbl.fpts.astype(float)))
pts = {str(i): float(lut.get(str(n), 0.0)) for i, n in zip(fr.id, fr.display_name)}

def run(col_values, label):
    f2 = fr.copy(); f2["proj_tourney"] = col_values
    pool = _pool(f2)
    t0 = time.perf_counter()
    lus = optimize_many(pool, n_lineups=N_LEV, stack=PRODUCTION_STACK,
                        objective_col="proj_tourney", env=dict(PRODUCTION_ENV))
    secs = time.perf_counter() - t0
    scores = np.array([sum(pts.get(str(p["id"]), 0.0) for p in lu.players) for lu in lus])
    print(f"{label:<22} n={len(lus):<4} {secs/60:.1f}min  mean={scores.mean():.2f} "
          f"best={scores.max():.2f}  >=150={(scores>=150).sum()}  >=170={(scores>=170).sum()} "
          f" >=194={(scores>=194).sum()}", flush=True)
    return lus, scores

ctl, s_ctl = run(base,  "CONTROL (as shipped)")
fad, s_fad = run(faded, "FADE (restored)")

ids = lambda lus: {frozenset(str(p["id"]) for p in lu.players) for lu in lus}
overlap = len(ids(ctl) & ids(fad))
print(f"\nrosters shared between arms: {overlap} of {min(len(ctl),len(fad))}")
print(f"delta mean {s_fad.mean()-s_ctl.mean():+.2f}   delta best {s_fad.max()-s_ctl.max():+.2f}"
      f"   delta >=150 {int((s_fad>=150).sum()-(s_ctl>=150).sum()):+d}")
json.dump({"n_lev": N_LEV,
           "control": {"mean": float(s_ctl.mean()), "best": float(s_ctl.max()),
                       "n150": int((s_ctl>=150).sum()), "n170": int((s_ctl>=170).sum())},
           "fade": {"mean": float(s_fad.mean()), "best": float(s_fad.max()),
                    "n150": int((s_fad>=150).sum()), "n170": int((s_fad>=170).sum())},
           "shared_rosters": overlap}, open("fade_ab_w1.json","w"), indent=2)
