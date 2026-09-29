"""The ownership term in the capped optimizer's objective: lag, blend and realized (ceiling), 36 slates; realized on the 2022 holdout."""
import json, glob, numpy as np, pandas as pd
pd.set_option("display.width", 250)
S1 = {(s["season"], s["week"]): s for s in (json.load(open(f)) for f in sorted(glob.glob("tilt/*.json")))}
S2 = {(s["season"], s["week"]): s for s in (json.load(open(f)) for f in sorted(glob.glob("tilt2/*.json")))}
keys = sorted(S1); seas = np.array([k[0] for k in keys]); fm = np.array([S1[k]["field_mean"] for k in keys]); fsd = np.array([S1[k]["field_sd"] for k in keys])
arms = {"base": (S1, "base"), "lag10": (S1, "lag10"), "lag20": (S1, "lag20"), "blend05": (S2, "blend05"), "blend10": (S2, "blend10"), "blend20": (S2, "blend20"), "oracle05": (S1, "oracle05"), "oracle10": (S1, "oracle10"), "oracle20": (S1, "oracle20")}
Z, P, rows = {}, {}, []
for name, (src, a) in arms.items():
    p = np.array([src[k]["arms"][a]["pct"] for k in keys]); sc = np.array([src[k]["arms"][a]["score"] for k in keys]); z = (sc - fm[:, None]) / fsd[:, None]; Z[name], P[name] = z, p
    rows.append({"objective": name, "points vs field": (sc - fm[:, None]).mean(), "avg z": z.mean(), "cash line": (p >= .77).mean() / .23, "top 11%": (p >= .89).mean() / .11, "top 5%": (p >= .95).mean() / .05, "top 1%": (p >= .99).mean() / .01,
                 "weekly swing": z.mean(axis=1).std(), "weeks with no top-11% row": ((p >= .89).sum(axis=1) == 0).mean(), "weeks book below field avg": (z.mean(axis=1) < 0).mean()})
print(pd.DataFrame(rows).round(3).to_string(index=False)); rng = np.random.default_rng(5)
for arm in [a for a in arms if a != "base"]:
    for nm, f in (("avg z", lambda a: Z[a].mean(axis=1)), ("rows over the cash line", lambda a: (P[a] >= .77).sum(axis=1)), ("rows over the top-11% line", lambda a: (P[a] >= .89).sum(axis=1))):
        d = f(arm) - f("base"); bs = []
        for _ in range(10000):
            ii = np.concatenate([rng.choice(np.flatnonzero(seas == y), (seas == y).sum()) for y in (2023, 2024)]); bs.append(d[ii].mean())
        print(f"  {arm:<9} {nm:<27} {d.mean():+.3f} [{np.percentile(bs, 5):+.3f}, {np.percentile(bs, 95):+.3f}]  better {int((d > 0).sum())} / worse {int((d < 0).sum())}  by season {d[seas == 2023].mean():+.3f} / {d[seas == 2024].mean():+.3f}")
H = [json.load(open(f)) for f in sorted(glob.glob("tilt2022/*.json"))]
if H:
    fm = np.array([s["field_mean"] for s in H]); fsd = np.array([s["field_sd"] for s in H]); zb = ((np.array([s["arms"]["base"]["score"] for s in H]) - fm[:, None]) / fsd[:, None]).mean(axis=1)
    for arm in ("oracle05", "oracle10", "oracle20"):
        d = ((np.array([s["arms"][arm]["score"] for s in H]) - fm[:, None]) / fsd[:, None]).mean(axis=1) - zb; bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
        print(f"  2022 holdout {arm}: avg z vs base {d.mean():+.3f} [{np.percentile(bs, 5):+.3f}, {np.percentile(bs, 95):+.3f}]")
