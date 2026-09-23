"""Do prop yardage lines behave like medians (so a symmetric-normal mean under-states yards)? 2023-25 pre-lock lines."""
import numpy as np, pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
from nfl_dfs.models import prop_market as PM
from nfl_dfs.models.blend import american_to_prob, devig_two_way, prop_line_to_mean
from nfl_dfs.names import match_map, resolve
seasons = "2023, 2024, 2025"
props = query_df(f"""SELECT season, week, bookmaker, market, outcome_name, player, price, point, snapshot_ts FROM `{settings.raw}.prop_lines`
                     WHERE season IN ({seasons}) AND market IN ('player_reception_yds','player_rush_yds','player_receptions')""")
sched = query_df(f"SELECT season, week, gameday, gametime, game_type, weekday FROM `{settings.raw}.schedules` WHERE season IN ({seasons})")
props, _ = PM.latest_pre_main_lock(props, sched)
ou = props[props.outcome_name.isin(["Over", "Under"])]
piv = ou.pivot_table(index=["season", "week", "player", "market", "bookmaker", "point"], columns="outcome_name", values="price", aggfunc="first").reset_index().dropna(subset=["Over", "Under"])
piv["p_over"] = [devig_two_way(american_to_prob(o), american_to_prob(u))[0] for o, u in zip(piv.Over, piv.Under)]
piv["implied_mean"] = [prop_line_to_mean(float(l), p, "poisson" if m == "player_receptions" else "normal") for l, p, m in zip(piv.point, piv.p_over, piv.market)]
g = piv.groupby(["season", "week", "player", "market"]).agg(line=("point", "mean"), implied=("implied_mean", "mean"), p_over=("p_over", "mean")).reset_index()
names = query_df(f"SELECT DISTINCT player_id gsis_id, player_display_name display_name FROM `{settings.raw}.weekly_stats` WHERE season IN ({seasons}) AND player_id IS NOT NULL")
lookup = match_map(dict(zip(names.display_name, names.gsis_id)))
g["gsis_id"] = PM._norm(g.player).map(lambda n: resolve(n, lookup))
act = query_df(f"""SELECT season, week, gsis_id, y_rec_yards, y_rush_yards, y_receptions FROM `{settings.features}.player_week_training`
                   WHERE season IN ({seasons}) AND was_active""")
d = g.dropna(subset=["gsis_id"]).merge(act, on=["season", "week", "gsis_id"])
col = {"player_reception_yds": "y_rec_yards", "player_rush_yds": "y_rush_yards", "player_receptions": "y_receptions"}
d["actual"] = [r[col[m]] for m, (_, r) in zip(d.market, d.iterrows())]
pts = {"player_reception_yds": 0.1, "player_rush_yds": 0.1, "player_receptions": 1.0}
for m, gm in d.groupby("market"):
    gm = gm.copy(); gm["band"] = pd.qcut(gm.line, 4, duplicates="drop")
    print(f"\n{m}: n {len(gm)}  actual mean {gm.actual.mean():.2f}  implied mean {gm.implied.mean():.2f}  line {gm.line.mean():.2f}  "
          f"share over the line {(gm.actual > gm.line).mean():.3f} (vs mean de-vigged p_over {gm.p_over.mean():.3f})  "
          f"=> DK pts gap {pts[m]*(gm.actual.mean()-gm.implied.mean()):+.2f}")
    print(gm.groupby("band", observed=True).agg(n=("actual", "size"), line=("line", "mean"), implied=("implied", "mean"), actual=("actual", "mean"), median_actual=("actual", "median")).round(2).to_string())
