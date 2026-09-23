"""Is the anytime-TD de-vig (fixed 15% hold) too strong? Pre-lock anytime-TD prices 2023-25 (same cutoff and name
resolution as prop_market.market_points) vs realized rush+rec TD >= 1 (player_week_training, active players)."""
import numpy as np, pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
from nfl_dfs.models import prop_market as PM
from nfl_dfs.models.blend import american_to_prob
from nfl_dfs.names import match_map, resolve
seasons = "2023, 2024, 2025"
props = query_df(f"""SELECT season, week, bookmaker, market, outcome_name, player, price, point, snapshot_ts
                     FROM `{settings.raw}.prop_lines` WHERE season IN ({seasons}) AND market = 'player_anytime_td'""")
sched = query_df(f"SELECT season, week, gameday, gametime, game_type, weekday FROM `{settings.raw}.schedules` WHERE season IN ({seasons})")
props, _ = PM.latest_pre_main_lock(props, sched)
names = query_df(f"""SELECT DISTINCT player_id gsis_id, player_display_name display_name FROM `{settings.raw}.weekly_stats`
                     WHERE season IN ({seasons}) AND player_id IS NOT NULL""")
lookup = match_map(dict(zip(names.display_name, names.gsis_id)))
props["norm"] = PM._norm(props.player)
props["p_raw"] = props.price.map(american_to_prob)
g = props.groupby(["season", "week", "norm"]).p_raw.mean().reset_index()
g["gsis_id"] = g.norm.map(lambda n: resolve(n, lookup))
act = query_df(f"""SELECT season, week, gsis_id, position, COALESCE(y_rec_tds,0)+COALESCE(y_rush_tds,0) tds
                   FROM `{settings.features}.player_week_training` WHERE season IN ({seasons}) AND was_active""")
d = g.dropna(subset=["gsis_id"]).merge(act, on=["season", "week", "gsis_id"])
d = d[d.position.isin(["RB", "WR", "TE", "QB"])]
d["hit"] = (d.tds >= 1).astype(float); d["p_model"] = (d.p_raw / 1.15).clip(0.01, 0.95)
d["bin"] = pd.qcut(d.p_raw, 8, duplicates="drop")
print(f"player-weeks {len(d)}; realized TD rate {d.hit.mean():.3f}; mean raw implied {d.p_raw.mean():.3f}; mean de-vigged (/1.15) {d.p_model.mean():.3f}")
print(d.groupby("bin", observed=True).agg(n=("hit", "size"), raw=("p_raw", "mean"), devig=("p_model", "mean"), realized=("hit", "mean")).round(3).to_string())
print("\nimplied hold that matches the realized rate overall:", round(d.p_raw.mean() / d.hit.mean(), 3))
for pos, gg in d.groupby("position"):
    print(f"  {pos}: n {len(gg)} realized {gg.hit.mean():.3f} de-vigged {gg.p_model.mean():.3f} raw {gg.p_raw.mean():.3f} -> TD pts gap {6*(-np.log1p(-gg.hit.mean()) - (-np.log1p(-gg.p_model)).mean()):+.2f}")
