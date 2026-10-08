"""Are big-tournament winning scores rising in 2026 (more AI-built systems?)? Millionaire winning scores 2023-2025 (the
repo's dfsarmy-collected winners files) vs 2026 W1-4 (our real standings), adjusted for how high-scoring each slate was:
the mean DK points of the 10 best skill players in that week's Sunday main-slate games (13:00-16:30 ET)."""
import io, subprocess
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client()
def git_csv(path):
    return pd.read_csv(io.StringIO(subprocess.run(["git", "-C", "/home/erich/projects/nfl-predictions", "show", f"origin/production/week3-integration-20260921:{path}"],
                                                  capture_output=True, text=True, check=True).stdout))
w25 = git_csv("reports/2025-milly-winners.csv")[["week", "score"]].assign(season=2025)
r = git_csv("reports/milly_rosters_2023_2024.csv"); w2324 = r.groupby(["season", "week"]).winning_score.first().reset_index().rename(columns={"winning_score": "score"})
W = pd.concat([w2324, w25], ignore_index=True)
w26 = BQ.query("""SELECT week, ANY_VALUE(contest_id) cid, MAX(expected_entries) n, MAX(IF(rank = 1, points, NULL)) score FROM (
  SELECT week, contest_id, expected_entries, rank, points, ROW_NUMBER() OVER (PARTITION BY week ORDER BY expected_entries DESC) rn FROM `nfl_raw.contest_entries` WHERE season = 2026)
  WHERE rn = 1 OR TRUE GROUP BY week, contest_id ORDER BY week""").to_dataframe()
w26 = w26.sort_values("n", ascending=False).groupby("week").head(1).sort_values("week")
W = pd.concat([W, w26[["week", "score"]].assign(season=2026)], ignore_index=True)
W["score"] = pd.to_numeric(W.score, errors="coerce").astype(float)
P = BQ.query("""WITH g AS (SELECT season, week, home_team team FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND weekday = 'Sunday' AND gametime BETWEEN '13:00' AND '16:30' AND season >= 2023
               UNION ALL SELECT season, week, away_team FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND weekday = 'Sunday' AND gametime BETWEEN '13:00' AND '16:30' AND season >= 2023),
  p AS (SELECT a.season, a.week, a.dk_points dk FROM `nfl_features.player_week_actuals` a JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
        JOIN g ON g.season = a.season AND g.week = a.week AND g.team = a.team WHERE r.position IN ('QB', 'RB', 'WR', 'TE') AND a.season >= 2023),
  rk AS (SELECT season, week, dk, ROW_NUMBER() OVER (PARTITION BY season, week ORDER BY dk DESC) rn FROM p)
  SELECT season, week, AVG(dk) top10 FROM rk WHERE rn <= 10 GROUP BY 1, 2""").to_dataframe()
W = W.merge(P, on=["season", "week"], how="left"); W["top10"] = pd.to_numeric(W.top10, errors="coerce").astype(float)
H = W[(W.season <= 2025)].dropna()
b, a = np.polyfit(H.top10, H.score, 1); res = H.score - (a + b * H.top10)
W["expected"] = a + b * W.top10; W["vs_expected"] = W.score - W.expected
pd.set_option("display.width", 200)
print(f"fit on {len(H)} weeks 2023-2025: winning score = {a:.1f} + {b:.2f} x (mean of the slate's top-10 skill scores); residual sd {res.std():.1f}")
print("\nweeks 1-4 by season:"); print(W[W.week <= 4].pivot(index="week", columns="season", values="score").round(1).to_string())
print("\nweeks 1-4, winning score minus what the slate's scoring predicts:"); print(W[W.week <= 4].pivot(index="week", columns="season", values="vs_expected").round(1).to_string())
print("\nseason summaries (all available weeks):"); print(W.groupby("season").agg(weeks=("score", "size"), mean_win=("score", "mean"), mean_vs_expected=("vs_expected", "mean"), slate_top10=("top10", "mean")).round(1).to_string())
print("\n2026 field sizes (largest Millionaire):", dict(zip(w26.week, w26.n)))
