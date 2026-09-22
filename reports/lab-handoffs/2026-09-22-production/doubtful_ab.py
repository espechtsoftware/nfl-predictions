"""ISOLATED A/B: exclude DK status 'D' (Doubtful) from the selectable universe.

This is an ELIGIBILITY rule, not the exposure-cap variance trade. It uses only
pre-lock information (the served DK status field). Re-runs the exact dual
expected-max selection with caps[doubtful]=0 and scores both books on realized.
"""
import numpy as np, pandas as pd, sys, importlib.util
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

def emax_mod(tag):
    spec = importlib.util.spec_from_file_location(f"emax_{tag}", f"{tag}/emax.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

for tag, wk, rf, K in [("w1",1,"rix.npy",90), ("item3",2,"roster_idx.npy",97)]:
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    cd = pd.read_parquet(f"{tag}/cands.parquet")
    rix = np.load(f"{tag}/{rf}")
    T  = np.load(f"{tag}/T_inc.npy"); Tv = np.load(f"{tag}/T_hs.npy")
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    pa = np.array([lut.get(str(n), np.nan) for n in fr.display_name], float)
    real = np.where(np.isnan(pa), 0.0, pa)[rix].sum(axis=1)

    st = fr.status.astype(str).str.upper().str.strip()
    print(f"\n=== WEEK {wk} === served DK status counts: "
          f"{dict(st.value_counts().head(8))}")
    doubtful = fr.index[st.isin(["D","DOUBTFUL"])].to_numpy()
    used = np.unique(rix)
    d_used = np.intersect1d(doubtful, used)
    print(f"  Doubtful in frame: {len(doubtful)}, used in pool: {len(d_used)}"
          + (f" -> {list(fr.loc[d_used,'display_name'])}" if len(d_used) else ""))
    if not len(d_used):
        print("  no Doubtful player reaches the pool; rule is a no-op this week")
        continue

    em = emax_mod(tag)
    caps = np.full(len(fr), 10**6, dtype=np.int32); caps[d_used] = 0
    out = em.emax_select(T, Tv, K, caps=caps, roster_idx=rix, n_players=len(fr))
    new = np.asarray(out[0] if isinstance(out, tuple) else out)
    base = np.array(cd.loc[cd.book_rank.notna()].sort_values("book_rank").index)

    def rep(lbl, idx):
        r = real[idx]
        print(f"  {lbl:<22} best {r.max():7.2f}   mean {r.mean():7.2f}   "
              f">=150 {(r>=150).sum():3d}   >=194 {(r>=194).sum():2d}")
    rep("delivered book", base); rep("Doubtful-excluded", new)
    r0, r1 = real[base], real[new]
    print(f"  DELTA                  best {r1.max()-r0.max():+7.2f}   mean {r1.mean()-r0.mean():+7.2f}"
          f"   >=150 {(r1>=150).sum()-(r0>=150).sum():+3d}")
    print(f"  rows changed: {len(set(new.tolist())-set(base.tolist()))} of {K}")
