"""Reads saved panel runs: equal-row rates at fixed lines, the paired average z against the run's own base, and the
head-layout tickets of the Week-4 mean-track plan (private plan file, never printed)."""
import json, glob, os, sys, importlib.util
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("el", os.environ["ENTER_LAYOUT_PY"])     # src/nfl_dfs/inference/enter_layout.py; el = importlib.util.module_from_spec(spec); sys.modules["el"] = el; spec.loader.exec_module(el)
plan = json.load(open(os.environ["PLAN_FILE"]))     # the week's private plan; never printed, never committed
ranks = el.assign_ranks(plan, "head")
mean_c = [(float(x["line_percentile"]) / 100.0, list(r)) for x, r in zip(plan, ranks) if x["track"] == "mean"]
lo = min(min(r) for _, r in mean_c); mean_c = [(l, [i - lo for i in r]) for l, r in mean_c]
field_tix = sum(len(r) * (1 - l) for l, r in mean_c)
W = os.environ["PANEL_DIR"]          # where 01_panel_term.py wrote its run directories
rng = np.random.default_rng(11)
def boot(d, seas, n=4000):
    ys = sorted(set(seas)); out = []
    for _ in range(n):
        idx = np.concatenate([rng.choice(np.where(seas == y)[0], (seas == y).sum()) for y in ys])
        out.append(d[idx].mean())
    return np.percentile(out, [5, 95])
for d in sys.argv[1:]:
    R = {}
    for f in sorted(glob.glob(f"{W}/{d}/*.json")):
        r = json.load(open(f)); R[(r["season"], r["week"])] = r
    slates = sorted(R); seas = np.array([s[0] for s in slates])
    arms = list(R[slates[0]]["arms"])
    print(f"\n=== {d}: {len(slates)} slates; arms {arms}")
    rows = []
    for a in arms:
        P = np.array([R[s]["arms"][a]["pct"] for s in slates]); SC = np.array([R[s]["arms"][a]["score"] for s in slates])
        fm = np.array([R[s]["field_mean"] for s in slates]); fsd = np.array([R[s]["field_sd"] for s in slates])
        z = ((SC - fm[:, None]) / fsd[:, None]).mean(axis=1)
        PB = np.array([R[s]["arms"][arms[0]]["pct"] for s in slates]); SB = np.array([R[s]["arms"][arms[0]]["score"] for s in slates])
        zb = ((SB - fm[:, None]) / fsd[:, None]).mean(axis=1)
        dz = z - zb; lo_, hi_ = boot(dz, seas) if a != arms[0] else (0, 0)
        tix = np.array([sum(int((p[r] >= l).sum()) for l, r in mean_c) for p in P], float)
        tb = np.array([sum(int((p[r] >= l).sum()) for l, r in mean_c) for p in PB], float)
        dt = tix - tb; tl, th = boot(dt, seas) if a != arms[0] else (0, 0)
        row = {"arm": a, "pts vs field": round(float((SC.mean(axis=1) - fm).mean()), 2), "cash(p80)": round(float((P >= 0.80).mean() / 0.20), 2), "p89": round(float((P >= 0.89).mean() / 0.11), 2),
               "p95": round(float((P >= 0.95).mean() / 0.05), 2), "p99": round(float((P >= 0.99).mean() / 0.01), 2), "p99.8": round(float((P >= 0.998).mean() / 0.002), 2),
               "dz": round(float(dz.mean()), 3), "dz90": f"[{lo_:+.3f},{hi_:+.3f}]", "up-down": f"{int((dz > 0).sum())}-{int((dz < 0).sum())}",
               "dz23": round(float(dz[seas == 2023].mean()), 3), "dz24": round(float(dz[seas == 2024].mean()), 3),
               "head tix": round(float(tix.mean()), 2), "x field": round(float(tix.mean() / field_tix), 2), "d tix": round(float(dt.mean()), 2), "dt90": f"[{tl:+.2f},{th:+.2f}]",
               "tix up-down": f"{int((dt > 0).sum())}-{int((dt < 0).sum())}", "wk0": round(float((tix == 0).mean()), 2), "below avg wk": round(float((z < 0).mean()), 2),
               "shared": round(float(np.mean([R[s]["arms"][a]["shared_with_base"] for s in slates])), 1)}
        if "proj_sum" in R[slates[0]]["arms"][a]:
            row["proj/row"] = round(float(np.mean([np.mean(R[s]["arms"][a]["proj_sum"]) for s in slates])), 2)
            row["pred own/row"] = round(float(np.mean([np.mean(R[s]["arms"][a]["pred_own_sum"]) for s in slates])), 1)
            row["real own/row"] = round(float(np.mean([np.mean(R[s]["arms"][a]["real_own_sum"]) for s in slates])), 1)
        rows.append(row)
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40)
    print(pd.DataFrame(rows).to_string(index=False))
