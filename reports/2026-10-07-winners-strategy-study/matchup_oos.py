"""Out-of-sample check of the matchup finding on 2023-2025 (none of today's analysis touched these seasons), from the weekly
stats (nfl_features.player_week_actuals, player_week_role, schedule_long). Pre-lock, for season s and week w:
  matchup  = the opponent's DK points allowed to the position per game: the prior season as a 6-game prior + season s weeks < w
  expected = the player's own DK points per game: the prior season as a 6-game prior + season s weeks < w (a naive projection)
Explosion = actual >= expected + 10 and >= 1.8x expected (expected >= 5). Test: explosion rate by matchup tercile within
expected tercile; logistic explosion ~ z(expected) + z(matchup), per season and for weeks 1-4. Usage: matchup_oos.py OUT_DIR"""
import sys
from pathlib import Path
import numpy as np, pandas as pd, numpy.linalg as la
from google.cloud import bigquery
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); BQ = bigquery.Client()
d = BQ.query("""SELECT x.gsis_id, x.season, x.week, x.team, s.opponent opp, r.position pos, x.dk_points
  FROM `nfl_features.player_week_actuals` x
  JOIN `nfl_features.player_week_role` r ON r.gsis_id = x.gsis_id AND r.season = x.season AND r.week = x.week
  JOIN `nfl_features.schedule_long` s ON s.season = x.season AND s.week = x.week AND s.team = x.team
  WHERE x.season BETWEEN 2022 AND 2025 AND x.week BETWEEN 1 AND 18 AND s.game_type = 'REG' AND r.position IN ('QB','RB','WR','TE') AND x.dk_points IS NOT NULL""").to_dataframe()
d["season"] = d.season.astype(int); d["week"] = d.week.astype(int); print("rows", len(d), d.groupby("season").size().to_dict(), flush=True)
allow = d.groupby(["season", "week", "opp", "pos"]).dk_points.sum().reset_index().rename(columns={"opp": "def"})
rows = []
for s in (2023, 2024, 2025):
    prev_def = allow[allow.season == s - 1].groupby(["def", "pos"]).dk_points.mean()
    prev_ply = d[d.season == s - 1].groupby("gsis_id").dk_points.mean()
    cur_def = allow[allow.season == s]; cur_ply = d[d.season == s]
    for w in range(2 if False else 1, 19):
        cd = cur_def[cur_def.week < w].groupby(["def", "pos"]).dk_points.agg(["sum", "count"])
        m = pd.DataFrame({"p": prev_def}).join(cd, how="outer").fillna({"sum": 0, "count": 0}); pr = m.p.fillna(m.p.groupby(level=1).transform("mean"))
        mval = ((6 * pr + m["sum"]) / (6 + m["count"]))
        cp = cur_ply[cur_ply.week < w].groupby("gsis_id").dk_points.agg(["sum", "count"])
        x = cur_ply[cur_ply.week == w].copy()
        if x.empty: continue
        x["matchup"] = [mval.get((o, p), np.nan) for o, p in zip(x.opp, x.pos)]
        pp = x.gsis_id.map(prev_ply); cs = x.gsis_id.map(cp["sum"]).fillna(0); cn = x.gsis_id.map(cp["count"]).fillna(0)
        x["expected"] = np.where(pp.notna(), (6 * pp.fillna(0) + cs) / (6 + cn), np.where(cn > 0, cs / cn.clip(lower=1), np.nan))
        rows.append(x)
X = pd.concat(rows, ignore_index=True); X = X[(X.expected >= 5) & X.matchup.notna()].copy()
X["boom"] = (X.dk_points >= X.expected + 10) & (X.dk_points >= 1.8 * X.expected)
grp = X.groupby(["season", "week", "pos"])
X["mz"] = grp.matchup.transform(lambda v: (v - v.mean()) / (v.std() + 1e-9)); X["ez"] = grp.expected.transform(lambda v: (v - v.mean()) / (v.std() + 1e-9))
print(f"player-weeks with expected >= 5: {len(X):,}; explosion base rate {X.boom.mean():.1%}; by season {X.season.value_counts().sort_index().to_dict()}", flush=True)
def terc(col, labels):
    r = X.groupby(["season", "week"])[col].rank(pct=True, method="first"); return np.select([r <= 1/3, r <= 2/3], labels[:2], labels[2])
X["et"] = terc("ez", ["low", "mid", "high"]); X["mt"] = terc("mz", ["hard", "mid", "soft"])
t = (X.pivot_table(index="et", columns="mt", values="boom", aggfunc="mean") * 100).reindex(index=["low", "mid", "high"], columns=["hard", "mid", "soft"])
print("\nexplosion rate (%) by expected-points tercile (rows) x matchup tercile (cols), 2023-2025:"); print(t.round(1).to_string())
print("\nby position (hard / mid / soft matchup):")
for p in ("QB", "RB", "WR", "TE"):
    r = (X[X.pos == p].groupby("mt").boom.mean() * 100).reindex(["hard", "mid", "soft"]); print(f"  {p}: {r['hard']:.1f}% / {r['mid']:.1f}% / {r['soft']:.1f}%  (n {int((X.pos == p).sum()):,})")
def fit(g):
    Z = np.column_stack([np.ones(len(g)), g.ez, g.mz]); y = g.boom.astype(float).values; b = np.zeros(3)
    for _ in range(60):
        pr = 1 / (1 + np.exp(-Z @ b)); H = Z.T @ (Z * (pr * (1 - pr))[:, None]) + 1e-6 * np.eye(3); b += la.solve(H, Z.T @ (y - pr))
    return b, np.sqrt(np.diag(la.inv(H)))
print("\nlogistic: explosion ~ z(expected) + z(matchup), within season-week-position")
for s in (2023, 2024, 2025):
    b, se = fit(X[X.season == s]); print(f"  {s}: matchup {b[2]:+.3f} (z {b[2]/se[2]:+.1f}, odds ratio per sd {np.exp(b[2]):.2f}); n {int((X.season == s).sum()):,}")
b, se = fit(X); print(f"  pooled 2023-25: matchup {b[2]:+.3f} (z {b[2]/se[2]:+.1f}), odds ratio per sd {np.exp(b[2]):.2f}")
b, se = fit(X[X.week <= 4]); print(f"  weeks 1-4 only (the prior season carries the measure): matchup {b[2]:+.3f} (z {b[2]/se[2]:+.1f}), n {int((X.week <= 4).sum()):,}")
X.to_csv(out / "matchup_oos.csv", index=False)
