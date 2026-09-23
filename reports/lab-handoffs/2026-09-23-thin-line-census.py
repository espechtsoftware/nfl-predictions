"""How many main-slate players would trip unmatched_in_feed only because they have a single (<2) priced market?"""
import sys, pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
from nfl_dfs.models import prop_market as PM
from nfl_dfs.names import norm_name
week, group = int(sys.argv[1]), int(sys.argv[2])
slate = query_df(f"""SELECT DISTINCT display_name, position FROM `{settings.raw}.dk_salaries`
                     WHERE draft_group_id = {group} AND position != 'DST'""")
feed = {norm_name(x) for x in PM.prop_feed_player_names(2026, week)}
p1 = PM.market_points((2026,), minimum_markets=1); p1 = p1[p1.week == week]
p2 = PM.market_points((2026,), minimum_markets=2); p2 = p2[p2.week == week]
props = query_df(f"SELECT player, market FROM `{settings.raw}.prop_lines` WHERE season=2026 AND week={week}")
props["n"] = props.player.map(norm_name)
mk = props.groupby("n").market.agg(lambda s: ",".join(sorted(set(s))))
slate["n"] = slate.display_name.map(norm_name)
in_feed = slate[slate.n.isin(feed)]
print(f"week {week} group {group}: slate non-DST {len(slate)}; in feed {len(in_feed)}; priced >=1 {len(p1)}; >=2 {len(p2)}")
print("markets held by slate players in the feed:"); print(in_feed.n.map(mk).value_counts().head(8).to_string())
