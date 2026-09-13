"""Follow-up: (1) placeholder-salary artifact in the historical panel, (2) predictability of inactive/DNP at lock."""
import importlib.util, numpy as np, pandas as pd
from nfl2.data import slates
from nfl2.pipeline import slate_frame
frames = []
for s, w in slates("k1"):
    fr = slate_frame(s, w); fr = fr.assign(season=s, week=w); frames.append(fr[["id", "season", "week", "pos", "salary", "mean_projection", "actual", "was_active", "injury_status", "practice_level", "name", "team"]])
P = pd.concat(frames, ignore_index=True); P["salary"] = pd.to_numeric(P.salary, errors="coerce"); P["mean_projection"] = pd.to_numeric(P.mean_projection, errors="coerce")
sk = P[P.pos.isin(["QB", "RB", "WR", "TE"])]
print("== placeholder salaries (< 2500) among skill players in the 89 k1 frames")
print(sk.groupby("season").apply(lambda g: pd.Series({"players": len(g), "sal<2500": int((g.salary < 2500).sum()), "sal<2500 & proj>=5": int(((g.salary < 2500) & (g.mean_projection >= 5)).sum()), "sal<2500 & actual>=10": int(((g.salary < 2500) & (g.actual >= 10)).sum())})).to_string())
low = sk[(sk.salary < 2500) & (sk.mean_projection >= 5)]
print("\nplaceholder-salary players with projection >= 5 (the optimizer's free slots): n", len(low), "| mean projection", round(low.mean_projection.mean(), 1), "| mean actual", round(low.actual.mean(), 1), "| share scoring 0", round((low.actual <= 0).mean(), 3), "| share inactive", round((low.was_active.astype(str) == "False").mean(), 3))
print(low.sort_values("mean_projection", ascending=False).head(12)[["season", "week", "name", "pos", "team", "salary", "mean_projection", "actual", "was_active"]].to_string(index=False))
# (2) inactive/DNP predictability: among skill players with projection >= 8 who ended inactive, injury_status / practice at lock
ina = sk[(sk.mean_projection >= 8) & (sk.was_active.astype(str) == "False")]
print("\n== projected >= 8 but INACTIVE at kickoff:", len(ina), "of", int((sk.mean_projection >= 8).sum()), "such player-weeks")
print("injury_status at lock:", ina.injury_status.fillna("none").value_counts().to_dict())
print("practice_level at lock (1=full):", pd.to_numeric(ina.practice_level, errors="coerce").round(2).value_counts(dropna=False).head(6).to_dict())
flagged = ina.injury_status.fillna("none").str.lower().isin(["out", "doubtful", "questionable", "q", "d", "o", "ir"]) | (pd.to_numeric(ina.practice_level, errors="coerce") < 1)
print("share with ANY lock-time flag (injury designation or limited practice):", round(flagged.mean(), 3))
