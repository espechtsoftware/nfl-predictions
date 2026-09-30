"""Player level, the 36 panel slates: the served projection (0.45 model / 0.55 market) against the market alone among
priced skill players projected >= 8 -- error, bias and the residual of each source's own top 25 (the optimizer's curse).
    LAB_WT=<lab checkout at fb397d9> python 08_projection_vs_market.py"""
import sys, os, json
WT = os.environ["LAB_WT"]; sys.path.insert(0, WT + "/src"); sys.path.insert(0, WT + "/experiments")
import numpy as np, pandas as pd
from nfl2.pipeline import slate_frame
rows = [json.loads(l)["result"] for l in open(WT + "/results/l18/results_bank1240.jsonl")]
slates = sorted({(r["season"], r["week"]) for r in rows})
out = []
for season, week in slates:
    fr = slate_frame(season, week).reset_index(drop=True)
    sk = fr[fr.pos.isin(["QB", "RB", "WR", "TE"])].copy()
    for c in ("mean_projection", "market_points", "model_points_pre", "actual"):
        sk[c] = pd.to_numeric(sk[c], errors="coerce")
    core = sk[sk.market_points.notna() & sk.actual.notna() & (sk.mean_projection >= 8)]
    def top_resid(col, n=25):
        t = core.nlargest(n, col); return float((t.actual - t[col]).mean())
    out.append({"slate": f"{season}-w{week:02d}", "n": len(core), "mae_served": float((core.mean_projection - core.actual).abs().mean()),
                "mae_market": float((core.market_points - core.actual).abs().mean()), "mae_model": float((core.model_points_pre - core.actual).abs().mean()),
                "bias_served": float((core.actual - core.mean_projection).mean()), "bias_market": float((core.actual - core.market_points).mean()),
                "top25_served_resid": top_resid("mean_projection"), "top25_market_resid": top_resid("market_points"), "corr": float(core.mean_projection.corr(core.market_points))})
t = pd.DataFrame(out); pd.set_option("display.width", 250)
print(t.round(2).to_string(index=False)); print(t.drop(columns="slate").mean().round(3).to_string())
print("slates where the market's error is lower:", int((t.mae_market < t.mae_served).sum()), "of", len(t))
