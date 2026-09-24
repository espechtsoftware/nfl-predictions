"""Historical selection/sorting test bed: 107 replay slates (panel 20260811-pitclean-e80-k1-a12ab31)."""
import re, numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
IN = __import__("os").environ["REVIEW_INPUTS"]      # external-review pull_inputs.py output
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
NICK = {"cardinals":"ARI","falcons":"ATL","ravens":"BAL","bills":"BUF","panthers":"CAR","bears":"CHI","bengals":"CIN","browns":"CLE",
 "cowboys":"DAL","broncos":"DEN","lions":"DET","packers":"GB","texans":"HOU","colts":"IND","jaguars":"JAX","chiefs":"KC","raiders":"LV",
 "chargers":"LAC","rams":"LA","dolphins":"MIA","vikings":"MIN","patriots":"NE","saints":"NO","giants":"NYG","jets":"NYJ","eagles":"PHI",
 "steelers":"PIT","49ers":"SF","seahawks":"SEA","buccaneers":"TB","titans":"TEN","commanders":"WAS"}
s = pd.read_parquet("spf_full.parquet").drop_duplicates(["season", "week", "id"])
s["key"] = np.where(s.pos == "DST", s.id.astype(str), s.name.map(norm))
own = pd.read_csv(f"{IN}/milly_own.csv")
own["key"] = [("DST_" + NICK[re.sub(r'[^a-z0-9]', '', n.lower())]) if re.sub(r'[^a-z0-9]', '', n.lower()) in NICK else norm(n)
              for n in own.display_name.astype(str)]
own = own.groupby(["season", "week", "key"]).pct_drafted.max().rename("own_act").reset_index()
s = s.merge(own, on=["season", "week", "key"], how="left")
has = s.groupby(["season", "week"]).own_act.transform("count") > 0
s.loc[has, "own_act"] = s.loc[has, "own_act"].fillna(0.0)
# predicted ownership, leave-one-season-out over the ownership seasons (features are pre-lock only)
s["value"] = s.mean_projection / (s.salary / 1000)
g = s.groupby(["season", "week", "pos"])
s["proj_rank"] = g.mean_projection.rank(ascending=False); s["value_rank"] = g.value.rank(ascending=False)
s["sal_rank"] = g.salary.rank(ascending=False)
s["value_z"] = (s.value - g.value.transform("mean")) / g.value.transform("std")
s["pos_c"] = s.pos.map({"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4})
F = ["pos_c", "salary", "mean_projection", "value", "proj_rank", "value_rank", "sal_rank", "value_z", "implied_team_total", "proj_p90", "market_points"]
tr_all = s[has & s.salary.notna()]
s["own_pred"] = np.nan
for S in sorted(s.season.unique()):
    tr = tr_all[tr_all.season != S]
    m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=40, verbose=-1).fit(tr[F], np.log(tr.own_act + 0.1))
    idx = (s.season == S) & s.salary.notna()
    s.loc[idx, "own_pred"] = np.exp(m.predict(s.loc[idx, F])) - 0.1
chk = s[has & s.own_pred.notna() & (s.mean_projection >= 3)]
print("predicted-vs-actual within-slate Spearman (LOSO):",
      chk.groupby("season").apply(lambda x: np.mean([stats.spearmanr(y.own_pred, y.own_act).correlation for _, y in x.groupby("week")]), include_groups=False).round(3).to_dict())
s.to_parquet("players_bed.parquet")
