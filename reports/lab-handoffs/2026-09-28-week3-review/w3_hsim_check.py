"""Did the corrected-hsim selection bank's per-player mean shifts carry information on Sunday?

    cd $W3DIR/run && python w3_hsim_check.py    # the archived run dir + ../pts_w3.csv from w3_field_lines.py
"""
import pandas as pd, numpy as np
f = pd.read_parquet("frame.parquet"); pts = pd.read_csv("../pts_w3.csv").set_index("display_name").fpts
f["actual_dk"] = f.display_name.map(pts)
hs = np.asarray(np.load("corrected_hsim_player_scores.npy", mmap_mode="r")); f["hs_mean"] = hs.mean(axis=1)
f["sh"] = f.hs_mean - f.mean_projection; f["resid"] = f.actual_dk - f.mean_projection
g = f[f.actual_dk.notna() & (f.mean_projection >= 5)]
print("players with served mean >= 5 and a score:", len(g), "| corr(hsim shift, actual - served)", round(g.sh.corr(g.resid), 3),
      "| corr(shift, served mean)", round(g.sh.corr(g.mean_projection), 3))
print("MAE served", round(g.resid.abs().mean(), 2), "| MAE hsim-bank mean", round((g.actual_dk - g.hs_mean).abs().mean(), 2),
      "| mean shift by pos", g.groupby("pos").sh.mean().round(2).to_dict())
pd.set_option("display.width", 200)
print(g.reindex(g.sh.abs().sort_values(ascending=False).index)[["display_name", "pos", "salary", "mean_projection", "hs_mean", "sh", "actual_dk"]].head(12).round(2).to_string())
