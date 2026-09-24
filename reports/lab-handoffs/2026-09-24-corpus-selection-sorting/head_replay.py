"""Replay the adopted Week-3 `head` layout (and the alternatives) on the 107 historical expected-max books.

    cd $TESTBED && ENTER_LAYOUT_PY=<path to src/nfl_dfs/inference/enter_layout.py> python head_replay.py

Uses production's own `assign_ranks` and `fewest_low_order`, so the layout is the one armed for Week 3. The contest
structure (40 contests, 198 entries) is rebuilt from HANDOFF `97defaf9` / `1df6469b` in the order listed there; the
private contests.json may order them differently, which moves unique rows between the non-head contests only. The
injury-flag rule (flagged rows behind clean ones, barred from the head) cannot be replayed: the historical frames carry
no designations. Greedy expected-max is nested, so one 198-lineup book per slate serves every book size (prefixes).
"""
import importlib.util
import os
import numpy as np, pandas as pd

exec(open(os.path.join(os.path.dirname(__file__), "run_sel.py")).read().split("rows, sort_rows, cand_rows = [], [], []")[0])
spec = importlib.util.spec_from_file_location("enter_layout", os.environ["ENTER_LAYOUT_PY"])
EL = importlib.util.module_from_spec(spec); spec.loader.exec_module(EL)
CF = pd.read_parquet("cand_features.parquet")

C = ([dict(name="wildcat", entries=2, keep=2) for _ in range(2)]
     + [dict(name="sat20", entries=1, keep=1) for _ in range(19)]
     + [dict(name="ffwc", entries=4, keep=4)]
     + [dict(name="supersat2", entries=5, keep=5) for _ in range(12)]
     + [dict(name="supersat25hi", entries=17, keep=17) for _ in range(3)]
     + [dict(name="supersat25lo", entries=20, keep=20) for _ in range(3)])
SIZES = [c["entries"] for c in C]
assert len(C) == 40 and sum(SIZES) == 198


def snake(sizes):
    need, rows, r, fwd = list(sizes), [[] for _ in sizes], 0, True
    while any(need):
        for ci in (range(len(sizes)) if fwd else range(len(sizes) - 1, -1, -1)):
            if need[ci]:
                rows[ci].append(r); r += 1; need[ci] -= 1
        fwd = not fwd
    return rows


RANKS = {"sequential": EL.assign_ranks(C, "sequential"), "top": EL.assign_ranks(C, "top"),
         "head": EL.assign_ranks(C, "head"), "snake": snake(SIZES)}
NEED = {k: max(max(r) for r in v) + 1 for k, v in RANKS.items()}
print("distinct rows needed:", NEED)
KMAX = max(NEED.values())

out = []
for (S, Wk), fn in sorted(files.items()):
    c = CF[(CF.season == S) & (CF.week == Wk)].reset_index(drop=True)
    if len(c) < KMAX + 20:
        continue
    T = np.load(fn)["totals"].astype(np.float32)
    b = np.array(demax(T, KMAX)); r = c.actual_score.to_numpy(float)[b]; low = c.n_low.to_numpy()[b]
    for layout, ranks in RANKS.items():
        K = NEED[layout]
        rows = [["L"] * int(n) + ["x"] for n in low[:K]]          # the real order function, fed LOW counts
        orders = {"greedy": list(range(K)),
                  "fewest-low": EL.fewest_low_order(rows, {"L"}, set(), pin_first=True)}
        for oname, perm in orders.items():
            rr = r[:K][perm]
            for ci, rk in enumerate(ranks):
                blk = rr[rk]
                out.append({"season": S, "week": Wk, "scheme": f"{layout} / {oname}", "type": C[ci]["name"],
                            "contest": ci, "n": SIZES[ci], "best": blk.max(), "mean": blk.mean()})
D = pd.DataFrame(out)
print(f"slates {D.groupby(['season', 'week']).ngroups} (pools with >= {KMAX + 20} candidates)")
pd.set_option("display.width", 250)
agg = D.groupby("scheme").apply(lambda x: pd.Series({
    "contest best": x.best.mean(), "contest mean": x["mean"].mean(),
    "entry-weighted mean": np.average(x["mean"], weights=x.n)}), include_groups=False)
print("\naverage over the 40 contests (each weighted equally) and over the 198 entries:")
print(agg.round(2).to_string())
print("\nbest lineup per contest, by contest type (average over contests of the type):")
print(D.pivot_table(index="type", columns="scheme", values="best", aggfunc="mean").round(1).to_string())
print("\naverage lineup per contest, by contest type:")
print(D.pivot_table(index="type", columns="scheme", values="mean", aggfunc="mean").round(1).to_string())


def paired(a, b, cols=("best", "mean")):
    x = D[D.scheme == a].groupby(["season", "week"])[list(cols)].mean()
    y = D[D.scheme == b].groupby(["season", "week"])[list(cols)].mean()
    for m in cols:
        d = x[m] - y[m]; t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
        print(f"  {a:<24} vs {b:<24} {m}: {d.mean():+.2f} (t {t:+.1f}, seasons+ {int((d.groupby(level=0).mean() > 0).sum())}/6)")


print("\npaired (each slate's average over contests; t over slates):")
for a in ("head / fewest-low", "head / greedy", "top / fewest-low", "snake / fewest-low"):
    paired(a, "sequential / greedy")
paired("head / fewest-low", "head / greedy")
paired("head / fewest-low", "top / fewest-low")
