"""Diagnose a historical slate where the served-projection book scored far below the market book."""
import os, sys
os.environ.setdefault("OMP_NUM_THREADS", "1")
import pandas as pd
from nfl2 import data, pipeline
season, week = int(sys.argv[1]), int(sys.argv[2])
fr = data.dev_only(pipeline.slate_frame(season, week))
fr["mkt"] = fr.market_points
cols = ["name", "pos", "team", "opp", "salary", "proj", "mean_projection", "proj_tourney", "mkt", "model_points_pre", "dk_points_l4", "actual"]
print("top 25 by served proj"); print(fr.sort_values("proj", ascending=False)[cols].head(25).to_string())
print("top 15 by market"); print(fr[fr.mkt.notna()].sort_values("mkt", ascending=False)[cols].head(15).to_string())
print("corr proj/actual", fr[["proj", "actual"]].corr().iloc[0, 1], "market/actual", fr[["mkt", "actual"]].corr().iloc[0, 1],
      "n actual==0 & proj>8", int(((fr.actual == 0) & (fr.proj > 8)).sum()), "of proj>8", int((fr.proj > 8).sum()))
print("games", sorted(fr.game_id.unique()))
cheap = fr[(fr.salary <= 4000) & (fr.pos != "DST")]
print("<=4k skill rows", len(cheap), "proj==mean_projection", int((cheap.proj.round(4) == cheap.mean_projection.round(4)).sum()),
      "proj==proj_tourney", int((cheap.proj.round(4) == cheap.proj_tourney.round(4)).sum()),
      "mean proj %.2f mean_projection %.2f model_pre %.2f actual %.2f" % (cheap.proj.mean(), cheap.mean_projection.mean(), cheap.model_points_pre.mean(), cheap.actual.mean()))
rich = fr[(fr.salary > 4000) & (fr.pos != "DST")]
print(">4k skill rows", len(rich), "proj==mean_projection", int((rich.proj.round(4) == rich.mean_projection.round(4)).sum()))
