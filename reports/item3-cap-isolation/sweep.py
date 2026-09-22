"""Isolated cap effect: identical pool, statuses, K and contest assignment;
the cap is the only thing that varies. Objective is a second, separate factor."""
import numpy as np, pandas as pd, json
from emax import emax_select

T = np.load("T_inc.npy"); Tv = np.load("T_hs.npy"); rix = np.load("roster_idx.npy")
realized = np.load("cand_realized.npy")
fr = pd.read_parquet("frame.parquet"); cd = pd.read_parquet("cands.parquet")
K, NP = 97, len(fr)

# delivered contest assignment, by book position (ENTER-layout.txt)
LAYOUT = [("milly", 1, 1), ("flea", 2, 24), ("huddle", 25, 25), ("nickel", 26, 30),
          ("pylon", 31, 31), ("satellite", 32, 33), ("supersat1a", 34, 43),
          ("supersat1b", 44, 53), ("supersat1c", 54, 63), ("supersat25a", 64, 79),
          ("supersat25b", 80, 95), ("ffwcsat", 96, 97)]

def mean_greedy(k, caps=None):
    order = np.argsort(-T.mean(axis=1).astype(np.float64), kind="stable")
    counts = np.zeros(NP, dtype=np.int32); book = []
    for i in order:
        if len(book) >= k: break
        r = rix[i]
        if caps is not None and (counts[r] + 1 > caps[r]).any(): continue
        book.append(int(i)); np.add.at(counts, r, 1)
    return book

def summarize(book):
    s = realized[book]
    return dict(n=len(book), mean=round(float(s.mean()), 2), best=round(float(s.max()), 2),
                n150=int((s >= 150).sum()), n170=int((s >= 170).sum()), n194=int((s >= 194).sum()))

def proposal_caps():
    """Week-2 post-mortem study-5 proposal, as written, expressed as book-share caps.
    The majors-rows sub-rule and the >=30% field-ownership exemption are NOT
    applied: per-contest counting is not a book-level cap, and this build had no
    ownership source at all, so the exemption was not computable pre-lock."""
    caps = np.full(NP, int(np.floor(0.30 * K)), dtype=np.int32)
    caps[fr.position.astype(str).eq("DST").to_numpy()] = int(np.floor(0.20 * K))
    rs = fr.report_status.astype(str)
    has_prop = fr.market_points.notna().to_numpy()
    q = rs.eq("Questionable").to_numpy()
    caps[q & has_prop] = int(np.floor(0.10 * K))
    caps[q & ~has_prop] = int(np.floor(0.05 * K))
    caps[rs.eq("Doubtful").to_numpy()] = 0
    return caps

ARMS = [("none", None)] + [(f"{int(f*100)}%", np.full(NP, int(np.floor(f * K)), dtype=np.int32))
                           for f in (0.40, 0.35, 0.30, 0.25, 0.20, 0.15)]
ARMS.append(("proposal", proposal_caps()))

rows, books = [], {}
for label, caps in ARMS:
    for obj, fn in (("dual_emax", lambda c: emax_select(T, Tv, K, caps=c, roster_idx=rix, n_players=NP)[0]),
                    ("mean_greedy", lambda c: mean_greedy(K, c))):
        b = fn(caps)
        books[(obj, label)] = b
        cnt = np.zeros(NP, dtype=np.int32); np.add.at(cnt, rix[b], 1)
        top = fr.display_name.iloc[int(cnt.argmax())]
        rows.append(dict(objective=obj, cap=label, max_exp=int(cnt.max()),
                         top_player=str(top), **summarize(b)))
        print(rows[-1], flush=True)

df = pd.DataFrame(rows)
df.to_csv("cap_sweep.csv", index=False)
json.dump({f"{o}|{c}": [int(x) for x in v] for (o, c), v in books.items()},
          open("books.json", "w"))

# per-contest realized, delivered assignment held fixed
per = []
for (obj, label), b in books.items():
    if len(b) < K: continue
    for name, lo, hi in LAYOUT:
        s = realized[b[lo - 1:hi]]
        per.append(dict(objective=obj, cap=label, contest=name, rows=hi - lo + 1,
                        best=round(float(s.max()), 2), mean=round(float(s.mean()), 2)))
pd.DataFrame(per).to_csv("per_contest.csv", index=False)
print("\n", df.to_string(index=False))
