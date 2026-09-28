import pandas as pd, numpy as np, pulp, time
exec(open(__import__("os").path.join(__import__("os").path.dirname(__file__), "w3_milp.py")).read().split("mean = f.mean_projection")[0])
mean = f.mean_projection.to_numpy(); actual = f.actual_dk.to_numpy(); t0 = time.time()
prev, P, A, PU, SAL = [], [], [], [], []
for k in range(144):
    r = solve(mean, [], prev=prev); prev.append(r); P.append(mean[r].sum()); A.append(actual[r].sum()); PU.append(int((sal[r] <= 4000).sum())); SAL.append(int(sal[r].sum()))
    if k in (0, 29, 59, 99, 143): print(f"  row {k+1}: projected {P[-1]:.1f} | cumulative projected mean {np.mean(P):.1f} | realized mean {np.mean(A):.1f} | {time.time()-t0:.0f}s")
P, A = np.array(P), np.array(A)
from collections import Counter
expo = Counter(i for r in prev for i in r); top5 = [(f.display_name[i], round(100 * n / 144)) for i, n in expo.most_common(5)]
print(f"MILP top-144 diverse by MEAN (overlap<=7, house rules, cap 4, >=49k): projected {P.mean():.1f} | realized {A.mean():.1f} | best {A.max():.1f} | punts/row {np.mean(PU):.2f} | distinct {len(expo)} | top exposures {top5}")
for L in (169.4, 173.8, 176.6, 189.5, 193.0): print(f"   share of rows >= {L}: {100*(A >= L).mean():.1f}%")
pd.DataFrame({"row": range(1, 145), "proj": P, "actual": A, "punts": PU, "salary": SAL, "players": [",".join(f.id[i] for i in r) for r in prev]}).to_csv("milp144.csv", index=False)
