import re, numpy as np, pandas as pd
from scipy import stats
import lightgbm as lgb
IN = __import__("os").environ["REVIEW_INPUTS"]          # the external-review pull_inputs.py output dir
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
spf = pd.read_csv(f"{IN}/spf.csv"); spf["key"] = spf.name.map(norm)
own = pd.read_csv(f"{IN}/milly_own.csv"); own["key"] = own.display_name.map(norm)
own = own.groupby(["season", "week", "key"], as_index=False).pct_drafted.max()
d = spf[spf.salary.notna() & spf.mean_projection.notna()].drop_duplicates(["season", "week", "key"])
d = d.merge(own, on=["season", "week", "key"], how="left")
d = d[d.season.between(2022, 2025)]
wk_has = own.groupby(["season", "week"]).size()
d = d[[ (s, w) in wk_has.index for s, w in zip(d.season, d.week)]]
d["own"] = d.pct_drafted.fillna(0.0)
d["y"] = np.log(d.own + 0.1)
d["value"] = d.mean_projection / (d.salary / 1000)
g = d.groupby(["season", "week", "pos"])
d["proj_rank"] = g.mean_projection.rank(ascending=False); d["value_rank"] = g.value.rank(ascending=False)
d["sal_rank"] = g.salary.rank(ascending=False)
d["value_z"] = (d.value - g.value.transform("mean")) / g.value.transform("std")
d["pos_c"] = d.pos.astype("category").cat.codes
F = ["pos_c", "salary", "mean_projection", "value", "proj_rank", "value_rank", "sal_rank", "value_z", "implied_team_total", "proj_p90", "market_points"]
out = []
for y in (2023, 2024, 2025):
    tr, te = d[d.season < y], d[d.season == y].copy()
    m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=40, verbose=-1).fit(tr[F], tr.y)
    te["pred"] = np.exp(m.predict(te[F])) - 0.1
    r = [stats.spearmanr(x.pred, x.own).correlation for _, x in te[te.mean_projection >= 3].groupby("week")]
    print(f"walk-forward {y}: within-slate Spearman(pred, actual) {np.mean(r):.3f} (min {np.min(r):.2f})")
    out.append(te[["season", "week", "key", "pos", "pred"]])
pd.concat(out).to_csv("own_pred_hist.csv", index=False)
# 2022 in-sample-free? fit 2023-25 -> predict 2022 (backcast, for the book test only)
tr = d[d.season > 2022]; te = d[d.season == 2022].copy()
m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=40, verbose=-1).fit(tr[F], tr.y)
te["pred"] = np.exp(m.predict(te[F])) - 0.1
pd.concat(out + [te[["season", "week", "key", "pos", "pred"]]]).to_csv("own_pred_hist.csv", index=False)
