"""Three dealings of the same books: head (armed), spread as built on integration f0da76d5 (contests of equal size take
the SAME rows), and spread with one offset per contest (equal-size contests interleave). Multiples of the field's
expectation and shares of slates only; the plan's counts and lines are never printed.
    PLAN_FILE=<contests.json> ENTER_LAYOUT_PY=<src/nfl_dfs/inference/enter_layout.py> PANEL_DIR=<dir> python 07_read_layouts.py <shape> <run dir> [<run dir> ...]
    <shape> = filed | routed   (routed: the deep-line supersats held on the main book)"""
import json, glob, os, sys, copy, importlib.util, collections
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("el", os.environ["ENTER_LAYOUT_PY"]); el = importlib.util.module_from_spec(spec); sys.modules["el"] = el; spec.loader.exec_module(el)
plan = json.load(open(os.environ["PLAN_FILE"]))
W = os.environ["PANEL_DIR"]
shape = sys.argv[1]
for x in plan:
    x["_deep"] = bool(x.get("deep_line"))
    if shape == "routed" and x["name"].startswith("supersat") and x.get("track") == "tail":
        x["track"] = "mean"; x["track_override"] = "mean"
main_c = [x for x in plan if x.get("track", "mean") == "mean"]
def ranks_for(name):
    if name in ("head", "spread"):
        r = el.assign_ranks(plan, name)
        r = [rr for x, rr in zip(plan, r) if x.get("track", "mean") == "mean"]
        lo = min(min(q) for q in r); return [[i - lo for i in q] for q in r]
    # spread with one offset per contest: equal-size contests interleave instead of stacking
    head = ranks_for("head"); K = max(max(q) for q in head) + 1
    groups = collections.defaultdict(list)
    for i, x in enumerate(main_c):
        groups[int(x["entries"])].append(i)
    out = [None] * len(main_c)
    for n, members in groups.items():
        G = len(members)
        for g, i in enumerate(members):
            out[i] = [min(K - 1, int((j + (g + 0.5) / G) * K / n)) for j in range(n)]
            assert len(set(out[i])) == n
    return out
LAY = {n: ranks_for(n) for n in ("head", "spread", "spread_offset")}
for n, r in LAY.items():
    use = collections.Counter(i for q in r for i in q)
    print(f"{shape} {n:14s}: rows spanned {max(use) + 1:3d}; distinct rows holding an entry {len(use):3d}; most entries on one row {max(use.values())}")
rng = np.random.default_rng(3)
rows = []
for d in sys.argv[2:]:
    R = {}
    for f in sorted(glob.glob(f"{W}/{d}/*.json")):
        r = json.load(open(f)); R[(r["season"], r["week"])] = r
    slates = sorted(R); arms = list(R[slates[0]]["arms"])
    for a in arms:
        P = np.array([R[s]["arms"][a]["pct"] for s in slates])
        for n, r in LAY.items():
            row = {"bank": d, "arm": a, "layout": n}
            tot = np.zeros(len(slates)); etot = 0.0
            for cls in ("shallow", "deep", "all"):
                sel = [k for k, x in enumerate(main_c) if cls == "all" or x["_deep"] == (cls == "deep")]
                if not sel:
                    continue
                t = np.array([sum(int((p[r[k]] >= float(main_c[k]["line_percentile"]) / 100.0).sum()) for k in sel) for p in P], float)
                e = sum(len(r[k]) * (1 - float(main_c[k]["line_percentile"]) / 100.0) for k in sel)
                row[f"{cls} x field"] = round(float(t.mean() / e), 2); row[f"{cls}: slates with 0"] = round(float((t == 0).mean()), 2)
                row[f"{cls}: sd/mean"] = round(float(t.std() / max(t.mean(), 1e-9)), 2)
            rows.append(row)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
t = pd.DataFrame(rows); print(t.to_string(index=False))
num = [c for c in t.columns if c not in ("bank", "arm", "layout")]
print("\npooled over the banks:"); print(t.groupby(["arm", "layout"], sort=False)[num].mean().round(2).to_string())
