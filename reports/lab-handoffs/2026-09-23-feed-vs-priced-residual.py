"""Residual trips under e457560b: slate players with >=2 raw feed markets whose resolved id prices < 2 markets."""
import sys, pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
from nfl_dfs.models import prop_market as PM
from nfl_dfs.names import norm_name, match_map, resolve
week, group = int(sys.argv[1]), int(sys.argv[2])
raw = query_df(f"""SELECT player, COUNT(DISTINCT market) nm, STRING_AGG(DISTINCT market) mk FROM `{settings.raw}.prop_lines`
                   WHERE season=2026 AND week={week} AND market IN ({", ".join(repr(m) for m in PM.STANDARD_MARKETS)}) GROUP BY 1""")
feed2 = raw[raw.nm >= 2].copy(); feed2["n"] = feed2.player.map(norm_name)
slate = query_df(f"SELECT DISTINCT display_name FROM `{settings.raw}.dk_salaries` WHERE draft_group_id={group} AND position!='DST'")
sl = set(slate.display_name.map(norm_name))
on = feed2[feed2.n.isin(sl)].copy()
priced = PM.market_points((2026,), minimum_markets=1, with_counts=True); priced = priced[priced.week == week]
cnt = dict(zip(priced.gsis_id, priced.market_count))
names = query_df(f"SELECT DISTINCT player_id gsis_id, player_display_name display_name FROM `{settings.raw}.weekly_stats` WHERE season>=2024 AND player_id IS NOT NULL")
lk = match_map(dict(zip(names.display_name, names.gsis_id)))
on["gsis"] = on.n.map(lambda x: resolve(x, lk)); on["priced_n"] = on.gsis.map(cnt)
thin = on[on.gsis.notna() & (on.priced_n.fillna(0) < 2)]
print(f"week {week} group {group}: slate players with >=2 raw markets {len(on)}; resolved but priced <2: {len(thin)}")
print(thin[["player", "mk", "priced_n"]].to_string(index=False) if len(thin) else "")
