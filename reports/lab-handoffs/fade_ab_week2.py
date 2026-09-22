"""Week-2 chalk-fade A/B. Two arms, identical frame/pool/stack/env/dose.
Only difference: whether proj_tourney carries the 25*naive_ownership fade."""
import json, sys, time
import numpy as np, pandas as pd

N = int(sys.argv[1]) if len(sys.argv) > 1 else 16
D = "/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/results/live/2026-w02/20260919T151024628419Z-2dc116c"
sys.path.insert(0, "/home/erich/projects/.nfl-predictions-worktrees/laptop-agent-intro-20260922/src")

from nfl_dfs.backtest.field import naive_ownership
from nfl_dfs.bq import query_df
import nfl2.pipeline as P
from nfl2.core.lineup import optimize_many

fr = pd.read_parquet(f"{D}/frame.parquet").reset_index(drop=True)
rec = json.load(open(f"{D}/receipt.json"))
assert rec["inputs"]["proj_tourney"]["formula_id"] == "degraded_no_ownership_punt_p90_v1", "not degraded"
assert float(rec["inputs"]["proj_tourney"]["penalty"]) == 0.0
base = fr["proj_tourney"].to_numpy(float).copy()          # degraded run => shipped column IS base
own = naive_ownership(fr[["pos", "proj", "salary"]])
assert not np.isnan(own).any(), "naive_ownership produced NaN"
LEV_PEN = P.LEVERAGE_PENALTY
faded = base - LEV_PEN * own
print(f"N={N}  LEVERAGE_PENALTY={LEV_PEN}  fade: mean={LEV_PEN*own.mean():.3f} max={LEV_PEN*own.max():.3f}")

def run(col_values, tag):
    f = fr.copy(); f["proj_tourney"] = col_values
    pool = P._pool(f)
    t0 = time.perf_counter()
    lus = optimize_many(pool, n_lineups=N, stack=P.PRODUCTION_STACK,
                        objective_col="proj_tourney", env=dict(P.PRODUCTION_ENV))
    print(f"  {tag}: {len(lus)} lineups in {time.perf_counter()-t0:.1f}s", flush=True)
    return lus

ctrl = run(base, "control")
fade = run(faded, "faded  ")

own_df = query_df("""SELECT display_name, MAX(fpts) fpts
                     FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                     WHERE season=2026 AND week=2 GROUP BY 1""")
lut = dict(zip(own_df.display_name.astype(str), own_df.fpts.astype(float)))
pts = np.array([lut.get(str(n), np.nan) for n in fr.display_name], float)
missing = int(np.isnan(pts).sum()); pts = np.nan_to_num(pts, nan=0.0)
idx = {str(i): k for k, i in enumerate(fr.id.astype(str))}

def ids(lu):
    """nfl2 Lineup exposes .ids (list[str] of player ids)."""
    return tuple(sorted(str(p) for p in lu.ids))

def score(lus, tag):
    rosters = [ids(l) for l in lus]
    s = np.array([sum(pts[idx[p]] for p in r) for r in rosters])
    per_lu_miss = np.array([sum(1 for p in r if str(fr.display_name[idx[p]]) not in lut)
                            for r in rosters])
    clean = s[per_lu_miss == 0]
    print(f"{tag:8s} mean={s.mean():7.2f}  best={s.max():7.2f}  >=150={int((s>=150).sum()):4d}  "
          f">=170={int((s>=170).sum()):4d}  missing-slots={int(per_lu_miss.sum())}  "
          f"clean-lineups={len(clean)}  clean-mean={(clean.mean() if len(clean) else float('nan')):7.2f}")
    return rosters, s, per_lu_miss

print(f"\nplayers with no week-2 standings row: {missing}/{len(fr)}")
rc, sc, mc = score(ctrl, "control")
rf, sf, mf = score(fade, "faded")
shared = len(set(rc) & set(rf))
print(f"\nshared rosters: {shared}/{N}  ({100*shared/N:.1f}%)   "
      f"delta mean={sf.mean()-sc.mean():+.2f}  delta best={sf.max()-sc.max():+.2f}")
