"""TabPFN vs the blend in the term, at 100 main rows (the plan with the deep-line supersats held on the main book):
all-row rates, the paired gain with a season-stratified bootstrap, and tickets by contest class under the head layout
(multiples of the field's expectation; the plan's counts are never printed)."""
import json, glob, os, sys, copy, importlib.util
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("el", os.environ["ENTER_LAYOUT_PY"]); el = importlib.util.module_from_spec(spec); sys.modules["el"] = el; spec.loader.exec_module(el)
plan = json.load(open(os.environ["PLAN_FILE"]))
for x in plan:
    x["_deep"] = bool(x.get("deep_line"))
    if x["name"].startswith("supersat") and x.get("track") == "tail":
        x["track"] = "mean"; x["track_override"] = "mean"
r = el.assign_ranks(plan, "head")
main = [(x["_deep"], float(x["line_percentile"]) / 100, list(q)) for x, q in zip(plan, r) if x["track"] == "mean"]
lo = min(min(q) for _, _, q in main); main = [(d, l, [i - lo for i in q]) for d, l, q in main]
W = os.environ["PANEL_DIR"]
rng = np.random.default_rng(9)
def boot(d, seas, n=4000):
    ys = sorted(set(seas)); out = []
    for _ in range(n):
        idx = np.concatenate([rng.choice(np.where(seas == y)[0], (seas == y).sum()) for y in ys]); out.append(d[idx].mean())
    return np.percentile(out, [5, 95])
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
allrows = []; pooled = {}
for d in sys.argv[1:]:
    R = {}
    for f in sorted(glob.glob(f"{W}/{d}/*.json")):
        x = json.load(open(f)); R[(x["season"], x["week"])] = x
    slates = sorted(R); seas = np.array([s[0] for s in slates])
    fm = np.array([R[s]["field_mean"] for s in slates]); fsd = np.array([R[s]["field_sd"] for s in slates])
    Z = {}; T = {}
    for a in R[slates[0]]["arms"]:
        P = np.array([R[s]["arms"][a]["pct"] for s in slates]); SC = np.array([R[s]["arms"][a]["score"] for s in slates])
        Z[a] = ((SC - fm[:, None]) / fsd[:, None]).mean(axis=1)
        for deep in (False, True):
            t = np.array([sum(int((p[q] >= l).sum()) for dd, l, q in main if dd == deep) for p in P], float)
            T[(a, deep)] = (t, sum(len(q) * (1 - l) for dd, l, q in main if dd == deep))
        row = {"bank": d, "arm": a, "pts vs field": round(float((SC.mean(axis=1) - fm).mean()), 2), "p89": round(float((P >= .89).mean() / .11), 2),
               "p95": round(float((P >= .95).mean() / .05), 2), "p99": round(float((P >= .99).mean() / .01), 2), "p99.8": round(float((P >= .998).mean() / .002), 2),
               "shallow x field": round(float(T[(a, False)][0].mean() / T[(a, False)][1]), 2), "deep x field": round(float(T[(a, True)][0].mean() / T[(a, True)][1]), 2),
               "deep: slates with 0": round(float((T[(a, True)][0] == 0).mean()), 2)}
        allrows.append(row)
        pooled.setdefault(a, {"z": [], "seas": [], "ts": [], "td": [], "es": 0, "ed": 0})
    for a in Z:
        pooled[a]["z"] += list(Z[a]); pooled[a]["seas"] += list(seas); pooled[a]["ts"] += list(T[(a, False)][0]); pooled[a]["td"] += list(T[(a, True)][0])
        pooled[a]["es"] += T[(a, False)][1] * len(slates); pooled[a]["ed"] += T[(a, True)][1] * len(slates)
print(pd.DataFrame(allrows).to_string(index=False))
print("\nTabPFN minus the blend, both banks pooled (72 slate-banks):")
seas = np.array(pooled["blend20"]["seas"])
for lab, key, norm in (("avg z per row", "z", None), ("shallow tickets", "ts", "es"), ("deep tickets", "td", "ed")):
    dv = np.array(pooled["tabpfn20"][key]) - np.array(pooled["blend20"][key])
    lo_, hi_ = boot(dv, seas)
    tot_t, tot_b = sum(pooled["tabpfn20"][key]), sum(pooled["blend20"][key])
    extra = f"  totals {tot_b:.0f} -> {tot_t:.0f} ({(tot_t / tot_b - 1) * 100:+.0f}%)" if key != "z" else ""
    print(f"  {lab:16s} {dv.mean():+.3f} [{lo_:+.3f}, {hi_:+.3f}]  up-down {int((dv > 0).sum())}-{int((dv < 0).sum())}  2023 {dv[seas == 2023].mean():+.3f}  2024 {dv[seas == 2024].mean():+.3f}{extra}")
