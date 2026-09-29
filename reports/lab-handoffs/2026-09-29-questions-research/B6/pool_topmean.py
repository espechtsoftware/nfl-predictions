"""Top-36 by projected mean from each run's own candidate pool (the mean-track counterfactual at K=36),
scored with the same actuals as live_books.py. No solver, no simulator: reads candidates.parquet only."""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_books import FRAMES, load_actuals, OUT

def main():
    for tag, (run, line) in FRAMES.items():
        c = pd.read_parquet(run + "/candidates.parquet")
        fr = pd.read_parquet(run + "/frame.parquet")
        actual, _ = load_actuals(tag)
        act_by_id = {i: actual.get(n) for i, n in zip(fr.id, fr.name)}
        proj_by_id = dict(zip(fr.id, fr.proj))
        idcol = [x for x in c.columns if x in ("ids", "player_ids", "players")]
        if tag == "w1" and os.environ.get("DEBUG"):
            print(list(c.columns)); print(c.head(2).T)
        ids = c[idcol[0]]
        pmean = np.array([sum(proj_by_id.get(i, 0.0) for i in row) for row in ids])
        realized = np.array([sum((act_by_id.get(i) or 0.0) for i in row) for row in ids])
        miss = np.array([sum(1 for i in row if act_by_id.get(i) is None) for row in ids])
        for label, key in (("proj_sum", pmean), ("sel_mean", c.sel_mean.to_numpy(dtype=float))):
          order = np.argsort(-key)
          # greedy top-36 by the key with the <=7 overlap cap
          chosen = []
          for j in order:
            s = frozenset(ids.iloc[j])
            if all(len(s & frozenset(ids.iloc[k])) <= 7 for k in chosen):
                chosen.append(j)
            if len(chosen) == 36:
                break
          sc = realized[chosen]
          out = dict(sort_key=label, n=len(chosen), mean=round(float(sc.mean()), 2), best=round(float(sc.max()), 2),
                   share_cash=round(float((sc >= line).mean()), 3), share_150=round(float((sc >= 150).mean()), 3),
                   share_194=round(float((sc >= 194).mean()), 3), missing_actual_slots=int(miss[chosen].sum()),
                   proj_mean=round(float(pmean[chosen].mean()), 2), pool_n=len(c),
                   pool_mean=round(float(realized.mean()), 2), pool_best=round(float(realized.max()), 2),
                   pool_share_cash=round(float((realized >= line).mean()), 3), tag_col=idcol[0])
          if "tag" in c.columns:
            out["pool_mean_by_tag"] = {k: round(float(v), 2) for k, v in pd.Series(realized).groupby(c.tag.values).mean().items()}
          print(tag, out, flush=True)
          p = f"{OUT}/{tag}.json"; r = json.load(open(p)); r[f"pool_top36_{label}"] = out; json.dump(r, open(p, "w"), indent=1)

main()
