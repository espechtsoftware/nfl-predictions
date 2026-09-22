"""NULL TEST for the Doubtful rule: is +26.58/+7.26 special, or does excluding
ANY three comparably-used players move the Week-2 book that much?

Draws random triples matched on pool usage frequency to {Tua, Flowers, Bowers},
re-runs the identical selection, and locates the real result in that distribution.
A rule that is not distinguishable from an arbitrary exclusion is not a lever.
"""
import numpy as np, pandas as pd, sys, importlib.util, time
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

spec = importlib.util.spec_from_file_location("emax_i","item3/emax.py")
em = importlib.util.module_from_spec(spec); spec.loader.exec_module(em)

fr = pd.read_parquet("item3/frame.parquet").reset_index(drop=True)
cd = pd.read_parquet("item3/cands.parquet")
rix = np.load("item3/roster_idx.npy")
T = np.load("item3/T_inc.npy"); Tv = np.load("item3/T_hs.npy")
own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                   WHERE season=2026 AND week=2 GROUP BY 1""")
lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
pa = np.array([lut.get(str(n), np.nan) for n in fr.display_name], float)
real = np.where(np.isnan(pa), 0.0, pa)[rix].sum(axis=1)
K = 97
base = np.array(cd.loc[cd.book_rank.notna()].sort_values("book_rank").index)
b_best, b_mean = real[base].max(), real[base].mean()

usage = np.bincount(rix.ravel(), minlength=len(fr))
st = fr.status.astype(str).str.upper().str.strip()
doubt = fr.index[st.isin(["D","DOUBTFUL"])].to_numpy()
print("target trio usage:", {fr.display_name[i]: int(usage[i]) for i in doubt})

def run(excl):
    caps = np.full(len(fr), 10**6, np.int32); caps[excl] = 0
    o = em.emax_select(T, Tv, K, caps=caps, roster_idx=rix, n_players=len(fr))
    idx = np.asarray(o[0] if isinstance(o, tuple) else o)
    return real[idx].max(), real[idx].mean()

t0 = time.time(); r_best, r_mean = run(doubt); dt = time.time() - t0
print(f"REAL Doubtful trio: best {r_best:.2f} ({r_best-b_best:+.2f})  "
      f"mean {r_mean:.2f} ({r_mean-b_mean:+.2f})   [{dt:.1f}s per selection]")

# candidate pool: players used in the pool, usage within 40% of each target
used = np.where(usage > 0)[0]
used = np.setdiff1d(used, doubt)
N = 120
rng = np.random.default_rng(20260922)
draws = []
for _ in range(N):
    pick = []
    for d in doubt:
        lo, hi = usage[d]*0.6, usage[d]*1.4
        cand = used[(usage[used] >= lo) & (usage[used] <= hi)]
        cand = np.setdiff1d(cand, pick)
        pick.append(rng.choice(cand) if len(cand) else rng.choice(used))
    draws.append(np.array(pick))

res = []
t0 = time.time()
for j, ex in enumerate(draws):
    res.append(run(ex))
    if (j+1) % 20 == 0:
        print(f"  {j+1}/{N} draws, {time.time()-t0:.0f}s elapsed", flush=True)
res = np.array(res)
db, dm = res[:,0]-b_best, res[:,1]-b_mean
print(f"\nNULL ({N} random comparably-used triples excluded):")
print(f"  delta best : mean {db.mean():+7.2f}  sd {db.std():6.2f}  "
      f"P(null >= real {r_best-b_best:+.2f}) = {(db >= r_best-b_best).mean()*100:5.1f}%")
print(f"  delta mean : mean {dm.mean():+7.2f}  sd {dm.std():6.2f}  "
      f"P(null >= real {r_mean-b_mean:+.2f}) = {(dm >= r_mean-b_mean).mean()*100:5.1f}%")
np.save("doubtful_null.npy", res)
