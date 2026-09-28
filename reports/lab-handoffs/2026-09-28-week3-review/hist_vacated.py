import pandas as pd, numpy as np
dc = pd.read_parquet("depth.parquet"); b = pd.read_parquet("base.parquet")[["season", "week", "gsis_id", "rs", "ps", "off"]]
S = pd.read_parquet("../sel/spf_full.parquet"); S = S[S.pos.isin(["RB", "WR", "TE"])].copy()
bed = pd.read_parquet("../sel/players_bed.parquet")[["season", "week", "gsis_id", "own_act", "own_pred"]]
# one depth rank per player-week (min over formations)
d1 = dc.groupby(["season", "week", "team", "gsis_id", "position"], as_index=False).depth.min()
d1 = d1.merge(b, on=["season", "week", "gsis_id"], how="left"); d1["rs"] = d1.rs.fillna("None")
# teams/positions whose depth-1 player is OUT/Doubtful on the final report
starters = d1[d1.depth == 1]
out_units = starters[starters.rs.isin(["Out", "Doubtful"])][["season", "week", "team", "position"]].drop_duplicates()
out_units["starter_out"] = True
d1 = d1.merge(out_units, on=["season", "week", "team", "position"], how="left"); d1["starter_out"] = d1.starter_out.fillna(False)
m = S.merge(d1[["season", "week", "gsis_id", "depth", "starter_out", "rs"]], on=["season", "week", "gsis_id"], how="inner")
m = m.merge(bed, on=["season", "week", "gsis_id"], how="left")
m["actual"] = m.actual.fillna(0); m["resid"] = m.actual - m.mean_projection
m = m[m.rs.isin(["None", "Questionable"])]                     # the beneficiary himself is not out
m["own_ratio"] = (m.own_act + 0.1) / (m.own_pred + 0.1)
pd.set_option("display.width", 220)
def s(x): return pd.Series({"n": len(x), "seasons": x.season.nunique(), "proj": x.mean_projection.mean(), "actual": x.actual.mean(), "actual - proj": x.resid.mean(),
                            "se": x.resid.std(ddof=1) / np.sqrt(max(len(x), 2)), "own_act": x.own_act.mean(), "own vs model (median ratio)": x.own_ratio.median()})
print("replay panel (2019, 2021-24 where depth charts exist) — same-position teammates when the depth-1 starter is OUT/Doubtful vs not")
print(m.groupby(["depth", "starter_out"]).apply(s, include_groups=False).round(2).to_string())
print("\nby position, depth-2 players only:")
print(m[m.depth == 2].groupby(["pos", "starter_out"]).apply(s, include_groups=False).round(2).to_string())
print("\ndepth-2 with starter out, by season (actual - proj):")
print(m[(m.depth == 2) & m.starter_out].groupby("season").resid.agg(["mean", "count"]).round(2).to_string())
print("\ndepth-2 with starter out, by projection band:")
m["band"] = pd.cut(m.mean_projection, [0, 5, 10, 15, 60])
print(m[(m.depth == 2) & m.starter_out].groupby("band", observed=True).apply(s, include_groups=False).round(2).to_string())
