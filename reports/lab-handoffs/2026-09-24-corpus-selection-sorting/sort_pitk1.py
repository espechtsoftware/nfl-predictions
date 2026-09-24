import re, numpy as np, pandas as pd
IN = __import__("os").environ["REVIEW_INPUTS"]      # external-review pull_inputs.py output
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
P = pd.read_parquet("players_bed.parquet")
rl = pd.read_csv(f"{IN}/replay_books.csv"); rl["key"] = rl.player.map(norm)
P2 = P[P.pos != "DST"].assign(key=P.name.map(norm)).drop_duplicates(["season", "week", "key"])
low = {}
for (s, w), g in P[P.pos != "DST"].groupby(["season", "week"]):
    n_hi = int(round(0.101 * len(g))); rk = g.own_pred.rank(ascending=False, method="first")     # live rule
    low[(s, w)] = set(g.name[rk > max(n_hi, 1)].map(norm))
rl["is_low"] = [ (pos != "DST") and (k in low.get((s, w), set())) for s, w, k, pos in zip(rl.season, rl.week, rl.key, rl.pos)]
L = rl.groupby(["season", "week", "entry_ix"]).agg(pts=("actual", "sum"), proj=("proj", "sum"), low=("is_low", "sum")).reset_index()
print("entry_ix range per slate:", L.groupby(["season", "week"]).entry_ix.agg(["min", "max"]).drop_duplicates().to_dict("records")[:2])
rows = []
for (s, w), g in L.groupby(["season", "week"]):
    g = g.sort_values("entry_ix"); r = g.pts.to_numpy(); n = len(g)
    orders = {"entry order": np.arange(n), "projection": np.argsort(-g.proj.to_numpy(), kind="stable"),
              "fewest LOW, then entry order": np.lexsort((np.arange(n), g.low.to_numpy())),
              "fewest LOW, then projection": np.lexsort((-g.proj.to_numpy(), g.low.to_numpy()))}
    for k, o in orders.items():
        rr = r[o]
        rows.append({"season": s, "week": w, "order": k, **{f"mean{m}": rr[:m].mean() for m in (1, 10, 20, 40)}, **{f"max{m}": rr[:m].max() for m in (10, 20, 40)}})
D = pd.DataFrame(rows)
print(f"slates {D.groupby(['season','week']).ngroups}; book mean {L.pts.mean():.2f}")
print(D.groupby("order")[[c for c in D.columns if c.startswith(("mean", "max"))]].mean().round(2).to_string())
base = D[D.order == "entry order"].set_index(["season", "week"])
for o in D.order.unique():
    if o == "entry order": continue
    x = D[D.order == o].set_index(["season", "week"])
    print(o, {m: f"{(x[m]-base[m]).mean():+.2f} (t {(x[m]-base[m]).mean()/((x[m]-base[m]).std(ddof=1)/np.sqrt(len(x))):+.1f})" for m in ("mean10", "mean20", "max10", "max20")})
