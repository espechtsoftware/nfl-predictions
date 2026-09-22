"""Same decomposition on Week 1 -- does the concentration mechanism replicate?"""
import numpy as np, pandas as pd, re, sys
from collections import Counter
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
SLOT = re.compile(r"\b(QB|RB|WR|TE|FLEX|DST)\s+")
def parse(s):
    p = SLOT.split(s.strip()); return [p[i+1].strip() for i in range(1,len(p)-1,2) if p[i+1].strip()]

for tag, wk, rf, cid in [("w1",1,"rix.npy","193028206"), ("item3",2,"roster_idx.npy","195648007")]:
    f = query_df(f"""SELECT lineup, points FROM `{settings.raw}.contest_entries`
                     WHERE season=2026 AND week={wk} AND contest_id='{cid}'
                     ORDER BY points DESC LIMIT 1000""")
    top = [parse(s) for s in f.lineup]; cnt = Counter(p for L in top for p in L)
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    rix = np.load(f"{tag}/{rf}")
    usage = np.bincount(rix.ravel(), minlength=len(fr)) / len(rix)
    fmap = {}
    for i,n in enumerate(fr.display_name.astype(str)):
        fmap[n]=i; fmap.setdefault(n.split()[-1], i)
    fieldtop = np.array([100*c/len(top) for _,c in cnt.most_common(12)])
    ourtop = np.sort(usage)[::-1][:12]*100
    matched = [(nm, 100*c/len(top), 100*usage[fmap[nm]] if nm in fmap else np.nan)
               for nm,c in cnt.most_common(40)]
    gaps = [g for _,fp,op in matched if not np.isnan(op) for g in [fp-op]]
    nomatch = [nm for nm,_,op in matched if np.isnan(op)]
    print(f"\n=== WEEK {wk} (field top-1,000 of the Millionaire) ===")
    print(f"  field's most-rostered player : {fieldtop[0]:.1f}%   "
          f"our pool's most-used player : {ourtop[0]:.1f}%")
    print(f"  field top-12 exposures : {np.round(fieldtop,0).astype(int).tolist()}")
    print(f"  our   top-12 exposures : {np.round(ourtop,0).astype(int).tolist()}")
    print(f"  mean |field - ours| over their top 40 : {np.mean(np.abs(gaps)):.1f}pp "
          f"| mean signed (field minus ours) : {np.mean(gaps):+.1f}pp")
    print(f"  their top-40 players not in our frame : {len(nomatch)}"
          + (f" {nomatch}" if nomatch else ""))
    # how much of the field's top-1000 roster mass did our pool cover at >=20%?
    cover = [op for _,fp,op in matched if not np.isnan(op) and op >= 20]
    print(f"  of their top 40, how many did our pool roster at >=20% : {len(cover)}")
