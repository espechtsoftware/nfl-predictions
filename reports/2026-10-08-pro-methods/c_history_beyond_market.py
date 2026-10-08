# PRO METHODS, analysis C (history 2023-25): which pre-lock data points predicted DraftKings points BEYOND the betting
# market (props, nfl_dfs.models.prop_market.market_points, >= 2 scoring markets, the latest pre-main-lock lines)?
# The market is the best historical stand-in for Fantasy Points' projection (in 2026 W4 FP's edge vs props' edge: r 0.85).
# Rows: QB/RB/WR/TE player-weeks that played (was_active) with a market number. Outcome: y_dk_points - market_points.
# Each feature z-scored within season x week x position, fitted alone with season-week-position fixed effects.
# SE: bootstrap over season-weeks (whole weeks resampled), 300 reps; per-season coefficients for stability.
#   cd ~/projects/nfl-predictions && PYTHONPATH=src .venv/bin/python ~/private/pro-methods/c_history_beyond_market.py
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

from nfl_dfs.models.prop_market import market_points

OUT = Path.home() / "private" / "pro-methods"
P = "nfl-predictions-503414"
c = bigquery.Client(project=P)
SEAS = (2022, 2023, 2024, 2025)
cache = OUT / "c_hist_panel.parquet"
if cache.exists():
    h = pd.read_parquet(cache)
else:
    tr = c.query(f"""SELECT * EXCEPT(fp_route_source_season, fp_route_source_week, fp_route_source_sha256)
      FROM `{P}.nfl_features.player_week_training` WHERE season IN {SEAS}""").to_dataframe()
    mk = market_points((2023, 2024, 2025), minimum_markets=2)
    h = tr.merge(mk[["season", "week", "gsis_id", "market_points"]], on=["season", "week", "gsis_id"], how="left")
    h.to_parquet(cache)
for col in h.columns:
    if pd.api.types.is_numeric_dtype(h[col]) and not pd.api.types.is_bool_dtype(h[col]):
        h[col] = h[col].astype(float)
h = h[h.position.isin(["QB", "RB", "WR", "TE"])].copy()
h = h.sort_values(["gsis_id", "season", "week"])

# derived pre-lock data points (strictly prior games)
act = h[h.was_active == 1].copy() if h.was_active.dtype != bool else h[h.was_active].copy()
act["prev_dk"] = act.groupby("gsis_id").y_dk_points.shift(1)
act["prev_beat_mkt"] = (act.y_dk_points - act.market_points).groupby(act.gsis_id).shift(1)
# defence vs position: DK points the opponent allowed to the position per game; prior season and season-to-date
dg = act.groupby(["season", "week", "opponent", "position"], as_index=False).y_dk_points.sum()
dg = dg.sort_values(["season", "opponent", "position", "week"])
dg["dvp_std"] = dg.groupby(["season", "opponent", "position"]).y_dk_points.transform(lambda s: s.shift(1).expanding().mean())
dg["dvp_games"] = dg.groupby(["season", "opponent", "position"]).cumcount()
prior = dg.groupby(["season", "opponent", "position"], as_index=False).y_dk_points.mean().rename(columns={"y_dk_points": "dvp_prev_season"})
prior["season"] += 1
act = act.merge(dg[["season", "week", "opponent", "position", "dvp_std", "dvp_games"]], on=["season", "week", "opponent", "position"], how="left")
act = act.merge(prior, on=["season", "opponent", "position"], how="left")
act.loc[act.dvp_games < 1, "dvp_std"] = np.nan
act["dvp_std_early"] = act.dvp_std.where(act.dvp_games <= 3)           # the 1-3 game samples the regulars distrust
act["usage_l4"] = np.where(act.position == "RB", act.carry_share_l4.fillna(0) + act.target_share_l4.fillna(0), act.target_share_l4)
act["usage_jump"] = np.where(act.position == "RB", act.carry_share_jump.fillna(0) + act.target_share_jump.fillna(0), act.target_share_jump)
act["td_equity"] = np.where(act.position == "RB", act.gl3_carry_share_l4, act.rz20_target_share_l4)
act["allowed_l6_pos"] = np.select([act.position == "QB", act.position == "RB", act.position == "WR", act.position == "TE"],
                                  [act.qb_fp_allowed_adj_l6, act.rb_fp_allowed_adj_l6, act.wr_fp_allowed_adj_l6, act.te_fp_allowed_adj_l6])
act["opp_epa_pos"] = np.where(act.position == "RB", act.epa_per_rush_allowed_l6, act.epa_per_dropback_allowed_l6)
act["mkt_per_k"] = act.market_points / (act.salary / 1000.0)
act["mkt_minus_l4"] = act.market_points - act.dk_points_l4                # market above the recent average (recency gap)
act["resid"] = act.y_dk_points - act.market_points
m = act[act.market_points.notna() & act.season.between(2023, 2025)].copy()
m["swp"] = m.season.astype(int).astype(str) + "-" + m.week.astype(int).astype(str) + m.position
m["sw"] = m.season.astype(int).astype(str) + "-" + m.week.astype(int).astype(str)
FEATS = {
    "recency: last game's DK points": "prev_dk", "recency: last game beat the market": "prev_beat_mkt",
    "recency: market above 4-wk average": "mkt_minus_l4", "price: salary change": "salary_delta_wow",
    "usage: target/carry share (4 wk)": "usage_l4", "usage: share jump (last vs 4 wk)": "usage_jump",
    "usage: snap share (4 wk)": "snap_share_l4", "usage: snap share jump": "snap_share_jump",
    "usage: FP route share (4 wk)": "fp_route_share_l4", "usage: FP route share jump": "fp_route_share_jump",
    "usage: air-yards share (4 wk)": "air_yards_share_l4", "usage: WOPR (4 wk)": "wopr_l4", "usage: xFP (4 wk)": "xfp_l4",
    "TD equity: red-zone / goal-line share": "td_equity", "TD equity: end-zone targets (4 wk)": "ez_targets_l4",
    "ceiling: DK points sd": "dk_points_std", "ceiling: aDOT (8 wk)": "adot_l8", "ceiling: deep targets (4 wk)": "deep_targets_l4",
    "efficiency: yards per target (8 wk)": "yards_per_target_l8", "efficiency: separation (4 wk)": "separation_l4",
    "game: team implied total": "implied_team_total", "game: game total": "game_total", "game: spread": "spread",
    "game: expected plays": "expected_plays", "team: pass rate over expected (4 wk)": "proe_l4", "team: pace (4 wk)": "pace_l4",
    "matchup: opp DK allowed to pos, prior season": "dvp_prev_season", "matchup: opp DK allowed to pos, season to date": "dvp_std",
    "matchup: opp DK allowed, season to date, 1-3 games only": "dvp_std_early", "matchup: opp FP allowed adj (6 g)": "allowed_l6_pos",
    "matchup: opp EPA allowed (6 g)": "opp_epa_pos", "matchup: opp pressure rate (6 g)": "opp_pressure_rate_l6",
    "matchup: opp CB yards per target (6 g)": "cb_ypt_allowed_l6", "matchup: top CB out": "top_cb_out",
    "news: vacated team target share": "team_vacated_target_share", "news: vacated capture (targets)": "vacated_capture_tgt",
    "news: depth-chart rank": "depth_rank", "QB: CPOE (6 g)": "qb_cpoe_l6", "weather: wind mph": "wind_mph",
    "market value: market pts per $1k": "mkt_per_k",
}
for lab, col in FEATS.items():
    m[f"z::{lab}"] = m.groupby("swp")[col].transform(lambda x: (x - x.mean()) / x.std() if x.notna().sum() > 2 and x.std() > 0 else x * np.nan)
print(f"history rows (played, with a >= 2-market props number): {len(m)}; seasons {m.season.value_counts().sort_index().to_dict()}")
print(f"market bias (mean actual - market): {m.resid.mean():+.2f}; MAE {m.resid.abs().mean():.2f}")


def coef(df, x):
    g = df[df[x].notna()]
    if len(g) < 200:
        return np.nan, len(g)
    yv = g.resid - g.groupby("swp").resid.transform("mean")
    xv = g[x] - g.groupby("swp")[x].transform("mean")
    return float((xv * yv).sum() / (xv * xv).sum()), len(g)


rng = np.random.default_rng(3)
weeks = m.sw.unique()
idx_by_week = {w: np.flatnonzero(m.sw.values == w) for w in weeks}
rows = []
for lab in FEATS:
    x = f"z::{lab}"
    b, n = coef(m, x)
    bs = []
    for _ in range(300):
        pick = rng.choice(weeks, len(weeks), replace=True)
        bs.append(coef(m.iloc[np.concatenate([idx_by_week[w] for w in pick])], x)[0])
    se = np.nanstd(bs)
    per = {s: coef(m[m.season == s], x)[0] for s in (2023, 2024, 2025)}
    pos = {p: coef(m[m.position == p], x)[0] for p in ("QB", "RB", "WR", "TE")}
    rows.append({"data point": lab, "pts per sd": b, "z": b / se if se > 0 else np.nan, "n": n,
                 "2023": per[2023], "2024": per[2024], "2025": per[2025], "same sign 3/3": len({np.sign(v) for v in per.values() if v == v}) == 1,
                 **{f"{p}": v for p, v in pos.items()}})
R = pd.DataFrame(rows).sort_values("z", key=np.abs, ascending=False)
pd.set_option("display.width", 250)
print("\nBEYOND THE MARKET, 2023-25 (each alone; season-week-position fixed effects; z from whole-week bootstrap)")
print(R.round(2).to_string(index=False))
print(f"\n{len(FEATS)} data points tested: Bonferroni |z| >= {abs(np.round(__import__('scipy').stats.norm.ppf(0.025 / len(FEATS)), 2))}")
R.to_csv(OUT / "c_history_beyond_market.csv", index=False)
m.to_parquet(OUT / "c_hist_modelframe.parquet")
