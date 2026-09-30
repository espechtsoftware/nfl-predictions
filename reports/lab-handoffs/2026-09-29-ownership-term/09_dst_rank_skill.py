"""Does the DST projection rank DSTs within a slate? Spearman with realized points per slate, and the top-3 projected
DSTs against the cheapest 3, on the 36 panel slates.
    LAB_WT=<lab checkout at fb397d9> python 09_dst_rank_skill.py"""
import sys, os, json
WT = os.environ["LAB_WT"]; sys.path.insert(0, WT + "/src"); sys.path.insert(0, WT + "/experiments")
import numpy as np, pandas as pd
from nfl2.pipeline import slate_frame
rows = [json.loads(l)["result"] for l in open(WT + "/results/l18/results_bank1240.jsonl")]
slates = sorted({(r["season"], r["week"]) for r in rows})
out = []
for season, week in slates:
    fr = slate_frame(season, week).reset_index(drop=True)
    d = fr[fr.pos == "DST"].copy()
    for c in ("mean_projection", "actual", "salary"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["mean_projection", "actual"])
    top = d.nlargest(3, "mean_projection"); cheap = d.nsmallest(3, "salary")
    out.append({"slate": f"{season}-w{week:02d}", "n": len(d), "spearman": d.mean_projection.corr(d.actual, method="spearman"),
                "top3_actual": top.actual.mean(), "cheap3_actual": cheap.actual.mean(), "top3_salary": top.salary.mean(), "cheap3_salary": cheap.salary.mean()})
t = pd.DataFrame(out); pd.set_option("display.width", 200)
print(t.round(2).to_string(index=False))
print("mean Spearman", round(t.spearman.mean(), 3), "| slates > 0:", int((t.spearman > 0).sum()), "of", len(t),
      "| top-3 by projection realize", round(t.top3_actual.mean(), 2), "vs cheapest 3", round(t.cheap3_actual.mean(), 2))
