"""Does the served DK status field predict underperformance vs projection?

The Doubtful rule is only a lever if 'D' systematically busts -- otherwise the
Week-2 gain is hindsight about three players. Tests every served status across
both weeks on realized-minus-projection, and reports the play rate.
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

allrows = []
for tag, wk, rf in [("w1",1,"rix.npy"), ("item3",2,"roster_idx.npy")]:
    fr = pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True)
    rix = np.load(f"{tag}/{rf}")
    own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                       WHERE season=2026 AND week={wk} GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
    fr["realized"] = [lut.get(str(n), np.nan) for n in fr.display_name]
    fr["played"] = fr.realized.notna()
    fr["week"] = wk
    fr["used"] = False
    fr.loc[np.unique(rix), "used"] = True
    fr["st"] = fr.status.astype(str).str.upper().str.strip().replace({"NONE":"(none)","NAN":"(none)"})
    allrows.append(fr[["week","display_name","pos","st","salary","proj","realized","played","used"]])
d = pd.concat(allrows, ignore_index=True)
d = d[d.used]                                   # only players the generator could actually use
d["resid"] = d.realized.fillna(0.0) - d.proj    # non-play counts as 0, which is the money truth

print("SELECTABLE players only (appear in >=1 pool lineup), both weeks pooled\n")
g = d.groupby("st").agg(n=("proj","size"), play_rate=("played","mean"),
                        proj=("proj","mean"), realized0=("realized", lambda s: s.fillna(0).mean()),
                        resid=("resid","mean"))
g["play_rate"] = (g.play_rate*100).round(1)
print(g.round(2).to_string())

print("\nper week:")
for wk in (1,2):
    s = d[d.week==wk].groupby("st").agg(n=("proj","size"), play=("played","mean"),
                                        resid=("resid","mean"))
    s["play"] = (s.play*100).round(1)
    print(f"  week {wk}:"); print(s.round(2).to_string().replace("\n","\n    "))

print("\nthe three Week-2 Doubtful players individually:")
w2 = d[(d.week==2) & (d.st=="D")]
print(w2[["display_name","pos","salary","proj","realized","played","resid"]].to_string(index=False))
print("\nthe Week-1 Doubtful players:")
w1 = d[(d.week==1) & (d.st=="D")]
print(w1[["display_name","pos","salary","proj","realized","played","resid"]].to_string(index=False))

# Q as the larger sample
q = d[d.st=="Q"]
print(f"\nQuestionable (n={len(q)}, both weeks): play rate {q.played.mean()*100:.1f}%, "
      f"mean resid {q.resid.mean():+.2f} vs (none) {d[d.st=='(none)'].resid.mean():+.2f}")
