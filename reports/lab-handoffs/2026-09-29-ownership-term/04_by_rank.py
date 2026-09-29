import json, glob, os, sys
import numpy as np, pandas as pd
W = os.environ["PANEL_DIR"]          # where 01_panel_term.py wrote its run directories
pd.set_option("display.width", 250)
pool = {}
for d in sys.argv[1:]:
    for f in sorted(glob.glob(f"{W}/{d}/*.json")):
        r = json.load(open(f))
        for a, v in r["arms"].items():
            pool.setdefault(a, []).append((d, r["season"], r["week"], np.array(v["pct"]), (np.array(v["score"]) - r["field_mean"]) / r["field_sd"]))
rows = []
for a, L in pool.items():
    P = np.array([x[3] for x in L]); Z = np.array([x[4] for x in L])
    for name, sl in (("rows 1-4", slice(0, 4)), ("rows 5-12", slice(4, 12)), ("rows 13-24", slice(12, 24)), ("rows 25-36", slice(24, 36)), ("all 36", slice(0, 36))):
        p = P[:, sl]; z = Z[:, sl]
        rows.append({"arm": a, "slate-banks": len(L), "rows": name, "avg z": round(float(z.mean()), 3), "p80": round(float((p >= 0.80).mean() / 0.20), 2), "p89": round(float((p >= 0.89).mean() / 0.11), 2),
                     "p95": round(float((p >= 0.95).mean() / 0.05), 2), "p99": round(float((p >= 0.99).mean() / 0.01), 2)})
t = pd.DataFrame(rows)
for k in ("avg z", "p80", "p89", "p95", "p99"):
    print("\n", k); print(t.pivot(index="arm", columns="rows", values=k)[["rows 1-4", "rows 5-12", "rows 13-24", "rows 25-36", "all 36"]].to_string())
print(t.groupby("arm")["slate-banks"].first().to_dict())
