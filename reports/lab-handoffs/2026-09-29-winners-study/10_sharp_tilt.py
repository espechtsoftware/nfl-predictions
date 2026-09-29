"""Do the skilled players' PLAYER choices carry information beyond our projection and the field's ownership?"""
import numpy as np, pandas as pd
from google.cloud import bigquery
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
X = pd.read_parquet("user_traits.parquet"); L = pd.read_parquet("heavy_lineups.parquet")
FE = pd.read_parquet("field_expo.parquet"); PB = pd.read_parquet("proj_batches.parquet"); OP = pd.read_parquet("own_pts.parquet")
last = PB.sort_values("generated_at").groupby(["week", "display_name"]).tail(1).rename(columns={"display_name": "player", "proj_points": "proj"})[["week", "player", "position", "salary", "proj", "proj_p90"]]
rows = []
for w in (1, 2, 3):
    x = X[X.week == w]
    ent = L[L.week == w].groupby("user").entry_id.nunique()
    def expo(users):
        l = L[(L.week == w) & L.user.isin(users)]
        e = l.groupby(["user", "player"]).entry_id.nunique().reset_index(name="c"); e["x"] = e.c / e.user.map(ent)
        return e.groupby("player").x.sum() / len(users)                     # user-weighted mean exposure
    s, b, mid = expo(x[x.q == "top fifth"].user), expo(x[x.q == "bottom fifth"].user), expo(x[x.q.isin(["2", "3", "4"])].user)
    d = FE[FE.week == w].set_index("player").join(s.rename("sharp")).join(b.rename("weak")).join(mid.rename("mid")).fillna(0).reset_index()
    d = d.merge(last[last.week == w], on=["week", "player"], how="inner").merge(OP[OP.week == w].rename(columns={"display_name": "player"})[["player", "fpts"]], on="player", how="left")
    d["fpts"] = d.fpts.fillna(0); rows.append(d)
D = pd.concat(rows); D = D[(D.proj >= 5)].copy()
eps = 0.003
D["resid"] = D.fpts - D.proj; D["lfield"] = np.log(D.field_expo + eps); D["tilt_sharp"] = np.log((D.sharp + eps) / (D.field_expo + eps)); D["tilt_weak"] = np.log((D.weak + eps) / (D.field_expo + eps))
D["sharp_vs_weak"] = np.log((D.sharp + eps) / (D.weak + eps))
D.to_parquet("player_tilts.parquet")
from scipy import stats
def partial(y, x, ctrl):
    A = np.column_stack([np.ones(len(ctrl))] + [ctrl[c] for c in ctrl.columns]); 
    ry = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]; rx = x - A @ np.linalg.lstsq(A, x, rcond=None)[0]
    r = np.corrcoef(ry, rx)[0, 1]; n = len(y); t = r * np.sqrt((n - A.shape[1] - 1) / (1 - r * r)); return r, t
print("players with our projection >= 5; residual = official points - our last pre-lock projection")
for w in (1, 2, 3, "all"):
    d = D if w == "all" else D[D.week == w]
    wk = pd.get_dummies(d.week, prefix="w", drop_first=True).astype(float) if w == "all" else pd.DataFrame(index=d.index)
    base = pd.concat([d[["proj"]], wk], axis=1); own = pd.concat([d[["proj", "lfield"]], wk], axis=1)
    out = {"week": w, "n": len(d),
           "field ownership | projection": partial(d.resid.to_numpy(), d.lfield.to_numpy(), base),
           "SHARP tilt | projection, field ownership": partial(d.resid.to_numpy(), d.tilt_sharp.to_numpy(), own),
           "weak tilt | projection, field ownership": partial(d.resid.to_numpy(), d.tilt_weak.to_numpy(), own),
           "sharp vs weak | projection, field ownership": partial(d.resid.to_numpy(), d.sharp_vs_weak.to_numpy(), own)}
    print({k: (v if not isinstance(v, tuple) else f"r {v[0]:+.3f} (t {v[1]:+.1f})") for k, v in out.items()})
# size of the effect: residual by sharp-tilt tercile, within week
D["tq"] = D.groupby("week").tilt_sharp.transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=["sharps most UNDER", "2", "3", "4", "sharps most OVER"]))
print("\nresidual by how much the skilled players over- or under-weight a player relative to the field:")
print(D.groupby("tq", observed=True).agg(n=("resid", "size"), proj=("proj", "mean"), field_own=("field_expo", "mean"), sharp_own=("sharp", "mean"), weak_own=("weak", "mean"), actual=("fpts", "mean"), resid=("resid", "mean"),
      se=("resid", lambda x: x.std() / np.sqrt(len(x)))).round(3).to_string())
print(D.groupby(["week", "tq"], observed=True).resid.mean().unstack().round(2).to_string())
# what explains the sharp tilt from things known before lock
c = bigquery.Client(project="nfl-predictions-503414")
ms = c.query("""SELECT week, generated_at, display_name player, market_points, model_points_pre, model_weight, source FROM `nfl-predictions-503414.nfl_predictions.market_source_log`
   WHERE season = 2026 AND week IN (2, 3) QUALIFY ROW_NUMBER() OVER (PARTITION BY week, display_name ORDER BY generated_at DESC) = 1""").to_dataframe()
ms = ms[ms.generated_at <= pd.Timestamp("2026-09-27 17:00:00", tz="UTC")]
d = D.merge(ms, on=["week", "player"], how="left")
d["mkt_minus_model"] = d.market_points - d.model_points_pre; d["value"] = d.proj / (d.salary / 1000)
sat = PB.sort_values("generated_at").groupby(["week", "display_name"]).head(1).rename(columns={"display_name": "player", "proj_points": "proj_first"})[["week", "player", "proj_first"]]
d = d.merge(sat, on=["week", "player"], how="left"); d["proj_change"] = d.proj - d.proj_first
print("\nwhat the sharp tilt correlates with (Spearman, within week, averaged):")
print(pd.Series({k: np.nanmean([d[d.week == w][k].corr(d[d.week == w].tilt_sharp, method="spearman") for w in (1, 2, 3) if d[d.week == w][k].notna().sum() > 30])
      for k in ["proj", "salary", "value", "lfield", "proj_p90", "mkt_minus_model", "proj_change"]}).round(3).to_string())
d.to_parquet("player_tilts2.parquet")
