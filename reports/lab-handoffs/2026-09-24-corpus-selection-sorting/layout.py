import glob, re, numpy as np, pandas as pd
exec(open(__import__("os").path.join(__import__("os").path.dirname(__file__), "run_sel.py")).read().split("rows, sort_rows, cand_rows = [], [], []")[0])
CF = pd.read_parquet("cand_features.parquet")
SIZES = [1, 23, 1, 5, 1, 2, 10, 10, 10, 16, 16, 2]          # Week-2 contests in payout order (97 entries)
NB = sum(SIZES)


def snake_rows(sizes):
    """Unique lineups per contest, dealt one row per contest per round in payout order, reversing each round."""
    need, rows, r, fwd = list(sizes), [[] for _ in sizes], 0, True
    while any(need):
        for ci in (range(len(sizes)) if fwd else range(len(sizes) - 1, -1, -1)):
            if need[ci]:
                rows[ci].append(r); r += 1; need[ci] -= 1
        fwd = not fwd
    return rows


SNAKE = snake_rows(SIZES)
out = []
for (S, Wk), fn in sorted(files.items()):
    z = np.load(fn); T = z["totals"].astype(np.float32)
    c = CF[(CF.season == S) & (CF.week == Wk)].reset_index(drop=True)
    if len(c) < NB + 20: continue
    b = np.array(demax(T, NB)); r = c.actual_score.to_numpy(float)[b]
    sm = c.sim_mean.to_numpy()[b]; low = c.n_low.to_numpy()[b]
    orders = {"greedy": np.arange(NB), "fewest LOW, then greedy": np.lexsort((np.arange(NB), low))}
    for oname, o in orders.items():
        rr = r[o]
        for layout in ("sequential", "snake", "top"):
            cur = 0
            for ci, n in enumerate(SIZES):
                blk = rr[cur:cur + n] if layout == "sequential" else rr[SNAKE[ci]] if layout == "snake" else rr[:n]
                if layout == "sequential": cur += n
                out.append({"season": S, "week": Wk, "scheme": f"{layout} / {oname}", "contest": ci, "n": n,
                            "best": blk.max(), "mean": blk.mean()})
D = pd.DataFrame(out)
print(f"slates {D.groupby(['season','week']).ngroups}")
p = D.groupby(["scheme", "contest"]).agg(n=("n", "first"), best=("best", "mean"), mean=("mean", "mean")).reset_index()
pd.set_option("display.width", 250)
print(p.pivot(index="contest", columns="scheme", values="best").assign(n=p.groupby("contest").n.first()).round(1).to_string())
print("\naverage over contests (each contest weighted equally) and over entries:")
agg = D.groupby("scheme").apply(lambda x: pd.Series({"contest best": x.best.mean(), "contest mean": x["mean"].mean(),
                                                     "entry-weighted mean": np.average(x["mean"], weights=x.n)}), include_groups=False)
print(agg.round(2).to_string())
print("\nsnake: book ranks each contest receives:", {ci: [r + 1 for r in rows[:3]] + (["..."] if len(rows) > 3 else []) for ci, rows in enumerate(SNAKE)})
base = D[D.scheme == "sequential / greedy"].groupby(["season", "week"])[["best", "mean"]].mean()
print("paired vs sequential / greedy (each slate's average over contests; t over slates):")
for s in sorted(D.scheme.unique()):
    if s == "sequential / greedy": continue
    x = D[D.scheme == s].groupby(["season", "week"])[["best", "mean"]].mean()
    for m in ("best", "mean"):
        d = x[m] - base[m]; t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
        print(f"  {s:<38} {m}: {d.mean():+.2f} (t {t:+.1f}, seasons+ {int((d.groupby(level=0).mean() > 0).sum())}/6)")
