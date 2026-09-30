"""Q11 part 2b (production, 2026-09-30): for a 1-entry contest, is the row better taken as OUR pool's top-mean row or as
a chalk-core row -- the near-top-mean row with the highest PRE-LOCK predicted ownership sum? Pre-lock-computable; scored
here in hindsight on W1-W3 (W2's pool is the Wednesday 12,559 build; pre-lock ownership as in q11_emulation.prelock_own).
Also, within each pool's 200 highest-mean rows: Spearman(pre-lock ownership sum, realized) and the realized mean by
ownership tercile. Prints aggregates only."""
import json, os, sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import q11_emulation as E  # noqa: E402
C = E.C
W2_POOL = "/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w02/20260916T165251953256Z-e7255e9/candidates.parquet"


def load_w2():
    f = C.attach_realized(C.load_frame(C.RUNS[2]["t70"]), 2)
    c = pd.read_parquet(W2_POOL)
    idx = {k: i for i, k in enumerate(f["id"])}
    keep = c.players.map(lambda s: all(p in idx for p in s.split(",")))
    c = c[keep].reset_index(drop=True)
    return f, np.array([[idx[p] for p in s.split(",")] for s in c.players]), dict(rows=int(len(c)), dropped=int((~keep).sum()))


def main():
    fq = {int(r.week): dict(qs=np.array(r.qs), mean=float(r.mean)) for r in pd.read_pickle(os.path.join(E.Q, "q11", "field_quantiles.pkl")).itertuples()}
    out = {}
    for w, source in ((1, "linestar"), (2, "linestar"), (3, "sets"), (3, "linestar")):
        f, rix, meta = load_w2() if w == 2 else E.load(w)
        own, _, cover = E.prelock_own(w, f, source)
        P = f.proj.to_numpy(float); R = f.realized.to_numpy(float)
        mean = P[rix].sum(1); orow = own[rix].sum(1); real = R[rix].sum(1)
        pct = lambda x: round(float((fq[w]["qs"] <= x).mean() * 100), 1)  # noqa: E731
        top = int(np.argmax(mean))
        res = dict(pool_rows=meta["rows"], own_cover=round(cover, 3),
                   top_mean=dict(proj=round(float(mean[top]), 1), own_pre=round(float(orow[top]), 1), realized=round(float(real[top]), 1), field_pct=pct(real[top])))
        for delta in (2.0, 4.0):
            near = np.where(mean >= mean[top] - delta)[0]
            ch = int(near[np.argmax(orow[near])])
            res[f"chalk_within_{delta:g}"] = dict(candidates=int(len(near)), proj=round(float(mean[ch]), 1), own_pre=round(float(orow[ch]), 1),
                                                  realized=round(float(real[ch]), 1), field_pct=pct(real[ch]))
        t200 = np.argsort(-mean)[:200]
        terc = pd.qcut(orow[t200], 3, labels=["low", "mid", "high"])
        res["top200"] = dict(spearman_own_realized=round(float(spearmanr(orow[t200], real[t200])[0]), 3),
                             realized_by_own_tercile=pd.Series(real[t200]).groupby(np.asarray(terc)).mean().round(1).to_dict(),
                             field_mean=round(fq[w]["mean"], 1))
        out[f"W{w}-{source}"] = res
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
