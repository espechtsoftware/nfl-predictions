"""EXACT additive decomposition of our pool mean vs the full field mean.

pool_mean = sum_p usage_p * realized_p  (usage_p = share of lineups holding p; sums to 9)
Same for the field. The difference decomposes player-by-player with no residual, so
the question 'why were we 23 points behind' has an exact answer.
"""
import numpy as np, pandas as pd, re, sys
from collections import Counter
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
SLOT = re.compile(r"\b(QB|RB|WR|TE|FLEX|DST)\s+")
def parse(s):
    p = SLOT.split(s.strip()); return [p[i+1].strip() for i in range(1,len(p)-1,2) if p[i+1].strip()]

for tag, wk, rf, cid in [("w1",1,"rix.npy","193028206"), ("item3",2,"roster_idx.npy","195648007")]:
    fl = query_df(f"""SELECT lineup FROM `{settings.raw}.contest_entries`
                      WHERE season=2026 AND week={wk} AND contest_id='{cid}'""")
    L = [parse(s) for s in fl.lineup]
    n_f = len(L); fc = Counter(p for r in L for p in r)
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    rix = np.load(f"{tag}/{rf}")
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    usage = np.bincount(rix.ravel(), minlength=len(fr)) / len(rix)
    names = fr.display_name.astype(str).to_numpy()
    proj = fr.proj.to_numpy(float)
    ours = {names[i]: usage[i] for i in range(len(fr)) if usage[i] > 0}
    theirs = {p: c/n_f for p, c in fc.items()}
    allp = set(ours) | set(theirs)
    rows = []
    for p in allp:
        r = lut.get(p, np.nan)
        rows.append(dict(player=p, ours=ours.get(p,0.0), theirs=theirs.get(p,0.0),
                         realized=0.0 if np.isnan(r) else r,
                         proj=proj[list(names).index(p)] if p in ours else np.nan))
    d = pd.DataFrame(rows)
    d["contrib"] = (d.ours - d.theirs) * d.realized
    pm, fm = (d.ours*d.realized).sum(), (d.theirs*d.realized).sum()
    print(f"\n=== WEEK {wk} ===  our pool mean {pm:.2f}   full field mean {fm:.2f}   "
          f"gap {pm-fm:+.2f}   (sum of contribs {d.contrib.sum():+.2f})")
    d["err"] = d.realized - d.proj
    print("  WORST for us (we were under-exposed to a scorer, or over-exposed to a bust):")
    w = d.reindex(d.contrib.abs().sort_values(ascending=False).index).head(12)
    print(w[["player","ours","theirs","proj","realized","err","contrib"]]
          .to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    ov = d[(d.ours > d.theirs)]; un = d[(d.ours < d.theirs)]
    print(f"  total from OVER-exposure (ours>theirs): {ov.contrib.sum():+.2f}   "
          f"from UNDER-exposure: {un.contrib.sum():+.2f}")
    sel = d[d.ours > 0].copy()
    wgt_err = (sel.ours * sel.err).sum()
    print(f"  exposure-weighted projection error over OUR pool: {wgt_err:+.2f} points/lineup"
          f"   (mean |err| {sel.err.abs().mean():.2f})")
