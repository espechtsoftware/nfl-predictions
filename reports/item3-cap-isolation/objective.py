"""For every arm: the selector's OWN objective value (E[max] over the 20,000
dual worlds) beside the realized outcome. The cap can only lower E[max] -- it is
a constraint on the same greedy -- so this prices what the cap costs ex ante
against what it returned ex post on this one slate."""
import numpy as np, pandas as pd, json

T = np.load("T_inc.npy"); Tv = np.load("T_hs.npy")
realized = np.load("cand_realized.npy")
books = json.load(open("books.json"))
W = T.shape[1] + Tv.shape[1]

rows = []
for key, b in books.items():
    obj, cap = key.split("|")
    b = np.array(b)
    emax = (np.maximum.reduce(T[b]).astype(np.float64).sum()
            + np.maximum.reduce(Tv[b]).astype(np.float64).sum()) / W
    p194 = ((np.maximum.reduce(T[b]) >= 194).sum()
            + (np.maximum.reduce(Tv[b]) >= 194).sum()) / W
    s = realized[b]
    rows.append(dict(objective=obj, cap=cap, n=len(b),
                     sim_Emax=round(float(emax), 2), sim_P194=round(float(p194), 4),
                     realized_max=round(float(s.max()), 2), realized_mean=round(float(s.mean()), 2)))

df = pd.DataFrame(rows)
base = df[(df.objective == "dual_emax") & (df.cap == "none")].iloc[0]
df["dEmax_vs_delivered"] = (df.sim_Emax - base.sim_Emax).round(2)
df["dRealizedMax_vs_delivered"] = (df.realized_max - base.realized_max).round(2)
df = df.sort_values(["objective", "sim_Emax"], ascending=[True, False])
df.to_csv("objective_vs_realized.csv", index=False)
print(df.to_string(index=False))
