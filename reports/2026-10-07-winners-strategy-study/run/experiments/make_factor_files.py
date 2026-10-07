"""Pre-lock factor bonuses as union bonus files (the ownership-term vehicle: pred_own = bonus / 0.20, so tilt 0.20 adds
exactly `bonus` projected points; negatives are clipped by the union). Weights fixed BEFORE any replay (from the factor
analysis 2026-10-07, not tuned): MATCHUP = clip(1.0 x z(points allowed to the position, 2025 as a 6-game prior + 2026 weeks
before W, within position), 0, 2); VACATED = clip(10 x own-type vacated share (teammates ruled Out, the frame's
team_vacated_*), 0, 3); MARKET = clip(0.5 x (props-implied - projection played), 0, 2); COMBINED = clip(sum, 0, 3).
Skill players only (QB/RB/WR/TE); the projection played: ours W2-3, FP W4."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
out = Path(sys.argv[1]); BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
FP_W4 = Path.home() / ".cache/laptop-agent/rehearsal/inputs/proj_fp-w4.csv"
al = BQ.query("""WITH a AS (SELECT x.season, x.week, x.team, r.position, x.dk_points FROM `nfl_features.player_week_actuals` x
      JOIN `nfl_features.player_week_role` r ON r.gsis_id = x.gsis_id AND r.season = x.season AND r.week = x.week
      WHERE x.season IN (2025, 2026) AND r.position IN ('QB', 'RB', 'WR', 'TE'))
  SELECT a.season, a.week, s.opponent def, a.position, SUM(a.dk_points) pts FROM a JOIN `nfl_features.schedule_long` s ON s.season = a.season AND s.week = a.week AND s.team = a.team
  WHERE s.game_type = 'REG' GROUP BY 1, 2, 3, 4""").to_dataframe()
for w in (2, 3, 4, 5):
    if str(w) not in CFG["weeks"] and w != 5: continue
    if w == 5: continue   # W5 files are built from the W5 frame on the day (no archived W5 T-70 frame yet)
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id").copy()
    fr["proj_played"] = pd.to_numeric(fr.mean_projection, errors="coerce")
    if w == 4:
        fp = pd.read_csv(FP_W4); m = dict(zip(fp.dk_draftable_id.astype("Int64").astype(str), fp.fp)); v = fr.dk_draftable_id.astype("Int64").astype(str).map(m); fr["proj_played"] = np.where(v.notna(), v, fr.proj_played)
    p25 = al[al.season == 2025].groupby(["def", "position"]).pts.mean(); cur = al[(al.season == 2026) & (al.week < w)].groupby(["def", "position"]).pts.agg(["sum", "count"])
    mm = pd.DataFrame({"p25": p25}).join(cur, how="outer").fillna({"sum": 0, "count": 0}); prior = mm.p25.fillna(mm.p25.groupby(level=1).transform("mean"))
    allowed = ((6 * prior + mm["sum"]) / (6 + mm["count"])).to_dict()
    fr["matchup_raw"] = [allowed.get((o, p), np.nan) for o, p in zip(fr.opp.astype(str), fr.pos.astype(str))]
    sk = fr.pos.isin(["QB", "RB", "WR", "TE"])
    z = fr[sk].groupby("pos").matchup_raw.transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    fr["b_matchup"] = 0.0; fr.loc[sk, "b_matchup"] = np.clip(1.0 * z.fillna(0), 0, 2)
    vac = np.where(fr.pos == "RB", fr.team_vacated_carry_share, np.where(fr.pos.isin(["WR", "TE"]), fr.team_vacated_target_share, 0.0))
    fr["b_vacated"] = np.where(sk, np.clip(10 * pd.to_numeric(pd.Series(vac), errors="coerce").fillna(0).values, 0, 3), 0.0)
    mk = pd.to_numeric(fr.market_points, errors="coerce") - fr.proj_played
    fr["b_market"] = np.where(sk, np.clip(0.5 * mk.fillna(0), 0, 2), 0.0)
    fr["b_combined"] = np.clip(fr.b_matchup + fr.b_vacated + fr.b_market, 0, 3)
    for arm in ("matchup", "vacated", "market", "combined"):
        d = pd.DataFrame({"dk_player_id": fr.dk_player_id.astype("Int64"), "display_name": fr.display_name, "pos": fr.pos, "team": fr.team,
                          "pred_own": (fr[f"b_{arm}"] / 0.20).round(4), "bonus_points": fr[f"b_{arm}"].round(3)})
        d.to_csv(out / f"{arm}-w{w}.csv", index=False)
        top = d.sort_values("bonus_points", ascending=False).head(4)
        print(f"W{w} {arm:9s}: {int((d.bonus_points > 0).sum())} players with a bonus; mean over skill {d[d.pos.isin(['QB','RB','WR','TE'])].bonus_points.mean():.2f}; top " + ", ".join(f"{r.display_name} +{r.bonus_points:.1f}" for r in top.itertuples()), flush=True)
