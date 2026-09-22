"""Week-1 out-of-sample: same isolated design as item 3. Cap is the only thing that varies."""
import numpy as np, pandas as pd, sys
sys.path.insert(0, "/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from emax import emax_select
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

T = np.load("T_inc.npy"); Tv = np.load("T_hs.npy"); rix = np.load("rix.npy")
fr = pd.read_parquet("frame.parquet"); cd = pd.read_parquet("cands.parquet")
K, NP = 90, len(fr)

# --- GATE: does the archived-bank rebuild reproduce the DELIVERED week-1 book? ---
delivered = cd.loc[cd.book_rank.notna()].sort_values("book_rank").index.to_numpy()
book, _ = emax_select(T, Tv, K)
ok = bool((np.array(book) == delivered).all())
print(f"GATE exact order match: {ok}   overlap {len(set(book)&set(delivered.tolist()))}/{K}")
if not ok:
    print("gate failed -- no capped arm from these matrices would be comparable; stopping")
    raise SystemExit(1)

# --- realized: DK-scored actuals from the week-1 contest exports ---
own = query_df(f"""SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership`
                   WHERE season=2026 AND week=1 GROUP BY 1""")
lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
names = fr.display_name.astype(str).tolist()
pa = np.array([lut.get(n, np.nan) for n in names], float)
miss = int(np.isnan(pa).sum())
pa0 = np.nan_to_num(pa, nan=0.0)
realized = pa0[rix].sum(axis=1)
print(f"players with no week-1 standings row: {miss}/{NP} (scored 0, as in the week-2 method)")
print(f"pool oracle {realized.max():.2f}   pool >=194: {(realized>=194).sum()}   >=150: {(realized>=150).sum()}")

def summarize(b):
    s = realized[b]
    return dict(n=len(b), mean=round(float(s.mean()),2), best=round(float(s.max()),2),
                n150=int((s>=150).sum()), n170=int((s>=170).sum()))

W = T.shape[1]+Tv.shape[1]
rows=[]
for frac in (None, .40, .35, .30, .25, .20):
    caps = None if frac is None else np.full(NP, int(np.floor(frac*K)), np.int32)
    b,_ = emax_select(T, Tv, K, caps=caps, roster_idx=rix, n_players=NP)
    b=np.array(b); cnt=np.zeros(NP,int); np.add.at(cnt, rix[b], 1)
    emax=(np.maximum.reduce(T[b]).astype(np.float64).sum()+np.maximum.reduce(Tv[b]).astype(np.float64).sum())/W
    rows.append(dict(cap=("none" if frac is None else f"{int(frac*100)}%"),
                     max_exp=int(cnt.max()), sim_Emax=round(float(emax),2), **summarize(b)))
    print(rows[-1], flush=True)
df=pd.DataFrame(rows); base=df.iloc[0]
df["dEmax"]=(df.sim_Emax-base.sim_Emax).round(2); df["dMean"]=(df["mean"]-base["mean"]).round(2)
df["dBest"]=(df.best-base.best).round(2)
df.to_csv("w1_cap_sweep.csv", index=False)
print("\n", df.to_string(index=False))
