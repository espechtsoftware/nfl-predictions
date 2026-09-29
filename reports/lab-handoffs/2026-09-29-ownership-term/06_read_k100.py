"""K = 100 (the plan as filed with the deep-line supersats held on the main book): tickets by contest class under the
head and the spread layouts, plain vs the term, both banks; and p99 / p99.8 by row block. Multiples of the field's
expectation only: the plan's counts and lines are never printed."""
import json, glob, os, sys, copy, importlib.util
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("el", os.environ["ENTER_LAYOUT_PY"]); el = importlib.util.module_from_spec(spec); sys.modules["el"] = el; spec.loader.exec_module(el)
plan = json.load(open(os.environ["PLAN_FILE"]))
alt = copy.deepcopy(plan)
for x in alt:
    if x["name"].startswith("supersat") and x.get("track") == "tail":
        x["track"] = "mean"; x["track_override"] = "mean"; x["_deep"] = True
W = os.environ["PANEL_DIR"]
rng = np.random.default_rng(5)
def boot(d, seas, n=4000):
    ys = sorted(set(seas)); out = []
    for _ in range(n):
        idx = np.concatenate([rng.choice(np.where(seas == y)[0], (seas == y).sum()) for y in ys])
        out.append(d[idx].mean())
    return np.percentile(out, [5, 95])
def layout(name):
    ranks = el.assign_ranks(alt, name)
    m = [(bool(x.get("_deep")), float(x["line_percentile"]) / 100.0, list(r)) for x, r in zip(alt, ranks) if x["track"] == "mean"]
    lo = min(min(r) for _, _, r in m)
    return [(d, l, [i - lo for i in r]) for d, l, r in m]
L = {n: layout(n) for n in ("head", "spread")}
for n, m in L.items():
    print(n, "main rows used:", max(max(r) for _, _, r in m) + 1, "| distinct rows holding an entry:", len({i for _, _, r in m for i in r}))
runs = {}
for d in sys.argv[1:]:
    R = {}
    for f in sorted(glob.glob(f"{W}/{d}/*.json")):
        r = json.load(open(f)); R[(r["season"], r["week"])] = r
    runs[d] = R
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
rows = []
for d, R in runs.items():
    slates = sorted(R); seas = np.array([s[0] for s in slates]); arms = list(R[slates[0]]["arms"])
    T = {}
    for a in arms:
        P = np.array([R[s]["arms"][a]["pct"] for s in slates])
        for n, m in L.items():
            for deep in (False, True):
                t = np.array([sum(int((p[r] >= l).sum()) for dd, l, r in m if dd == deep) for p in P], float)
                e = sum(len(r) * (1 - l) for dd, l, r in m if dd == deep)
                T[(a, n, deep)] = (t, e)
    for a in arms:
        for n in L:
            row = {"bank": d, "arm": a, "layout": n}
            for deep, lab in ((False, "shallow"), (True, "deep")):
                t, e = T[(a, n, deep)]; t0, _ = T[(arms[0], "head", deep)]
                dd = (t - t0) / e
                lo_, hi_ = boot(dd, seas) if not (a == arms[0] and n == "head") else (0.0, 0.0)
                row[f"{lab} x field"] = round(float(t.mean() / e), 2); row[f"{lab} vs plain-head"] = f"{dd.mean():+.2f} [{lo_:+.2f},{hi_:+.2f}]"
                row[f"{lab}: slates with 0"] = round(float((t == 0).mean()), 2)
            rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))
blk = []
for d, R in runs.items():
    slates = sorted(R)
    for a in R[slates[0]]["arms"]:
        P = np.array([R[s]["arms"][a]["pct"] for s in slates])
        row = {"bank": d, "arm": a}
        for name, sl in (("1-4", slice(0, 4)), ("5-12", slice(4, 12)), ("13-36", slice(12, 36)), ("37-68", slice(36, 68)), ("69-100", slice(68, 100)), ("all", slice(0, 100))):
            row[f"p99 {name}"] = round(float((P[:, sl] >= 0.99).mean() / 0.01), 2)
        for name, sl in (("1-36", slice(0, 36)), ("37-100", slice(36, 100)), ("all", slice(0, 100))):
            row[f"p99.8 {name}"] = round(float((P[:, sl] >= 0.998).mean() / 0.002), 2)
        blk.append(row)
print(pd.DataFrame(blk).to_string(index=False))
