"""What do the persistently better Millionaire players do differently? Skill is measured in OTHER weeks, traits in this week."""
import numpy as np, pandas as pd
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 50)
U = pd.read_parquet("milly_user_weeks.parquet"); U = U[U.n >= 20]
F = pd.read_parquet(__import__("os").environ["FIELD_INPUT"])      # field_model_input.parquet from the 09-28 review's w3_class_model.py
E = pd.read_parquet("entries_all.parquet"); E = E[E.contest_id.isin(["193028206", "195648007", "195905122"])][["week", "entry_id", "user"]]
F = F.merge(E, on=["week", "entry_id"], how="inner")
L = pd.read_parquet("heavy_lineups.parquet")
# portfolio traits per user-week
ent = L.groupby(["week", "user"]).entry_id.nunique().rename("n_ent")
pe = L.groupby(["week", "user", "player"]).entry_id.nunique().rename("c").reset_index().merge(ent.reset_index(), on=["week", "user"])
pe["expo"] = pe.c / pe.n_ent
port = pe.groupby(["week", "user"]).agg(distinct_players=("player", "size"), max_expo=("expo", "max"), top3_expo=("expo", lambda x: x.nlargest(3).mean()),
                                        herf=("expo", lambda x: (x ** 2).sum() / 9)).reset_index()
qb = L[L.slot == "QB"].groupby(["week", "user"]).player.nunique().rename("n_qbs").reset_index()
dst = L[L.slot == "DST"].groupby(["week", "user"]).player.nunique().rename("n_dsts").reset_index()
# lineup-shape traits per user-week (means over their entries)
cols = ["proj_pct", "own_pct", "stack", "bring_back", "max_game", "qb_sal", "te_sal", "rb_sal", "sal_left", "flex_te", "flex_rb", "qb_game_total"]
shape = F.groupby(["week", "user"])[cols].mean().reset_index()
shape["proj_sd_within"] = F.groupby(["week", "user"]).proj_pct.std().values
X = U.merge(shape, on=["week", "user"]).merge(port, on=["week", "user"]).merge(qb, on=["week", "user"]).merge(dst, on=["week", "user"])
# out-of-week skill
rows = []
for w in (1, 2, 3):
    other = U[U.week != w].groupby("user").mean_z.mean().rename("skill_other")
    x = X[X.week == w].merge(other, on="user", how="inner")
    x["q"] = pd.qcut(x.skill_other.rank(method="first"), 5, labels=["bottom fifth", "2", "3", "4", "top fifth"])
    rows.append(x)
X2 = pd.concat(rows)
X2.to_parquet("user_traits.parquet")
g = X2.groupby("q", observed=True).agg(user_weeks=("user", "size"), skill_in_other_weeks=("skill_other", "mean"), z_this_week=("mean_z", "mean"), profitable=("profit", "mean"),
      median_roi=("roi", "median"), entries=("n", "mean"), **{c: (c, "mean") for c in cols}, distinct_players=("distinct_players", "mean"), max_expo=("max_expo", "mean"),
      top3_expo=("top3_expo", "mean"), n_qbs=("n_qbs", "mean"), n_dsts=("n_dsts", "mean"))
print("users with 20+ entries this week and in another week; grouped by their average score in the OTHER weeks"); print(g.round(3).T.to_string())
# which traits predict this-week z after controlling for nothing (Spearman), pooled within week
print("\nSpearman correlation of each trait with OTHER-week skill (within week, averaged):")
tr = cols + ["distinct_players", "max_expo", "top3_expo", "n_qbs", "n_dsts", "n"]
print(pd.Series({c: np.mean([X2[X2.week == w][c].corr(X2[X2.week == w].skill_other, method="spearman") for w in (1, 2, 3)]) for c in tr}).sort_values().round(3).to_string())
