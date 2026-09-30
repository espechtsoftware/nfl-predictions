"""What the saved books would do in a double-up (pays 1.8x to the top 44% of the field: a row needs the field's 56th
percentile). Reads the run directories of 01_panel_term.py.
    PANEL_DIR=<dir> python 10_double_up_read.py tilt3 tilt3b k100a k100b"""
import sys, os, json, glob
import numpy as np, pandas as pd
W = os.environ["PANEL_DIR"]
rows = []
for d in sys.argv[1:]:
    R = [json.load(open(f)) for f in sorted(glob.glob(f"{W}/{d}/*.json"))]
    for a in R[0]["arms"]:
        P = np.array([r["arms"][a]["pct"] for r in R])
        rows.append({"run": d, "arm": a, "K": P.shape[1], "P(row >= p50)": round(float((P >= 0.50).mean()), 3), "P(row >= p56)": round(float((P >= 0.56).mean()), 3),
                     "double-up ROI": f"{(1.8 * (P >= 0.56).mean() - 1) * 100:+.0f}%", "slates with under half the rows cashing": round(float(((P >= 0.56).mean(axis=1) < 0.5).mean()), 2)})
pd.set_option("display.width", 200); print(pd.DataFrame(rows).to_string(index=False))
