"""mean(actual DK - market_points) by position x market band, 2023-25, plain vs MARKET_BONUS_AWARE=1 (active players, >=2 markets)."""
import os, numpy as np, pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
from nfl_dfs.models import prop_market
S = (2023, 2024, 2025)
os.environ["MARKET_BONUS_AWARE"] = "0"; off = prop_market.market_points(S, minimum_markets=2).rename(columns={"market_points": "mkt_off"})
os.environ["MARKET_BONUS_AWARE"] = "1"; on = prop_market.market_points(S, minimum_markets=2).rename(columns={"market_points": "mkt_on"})
act = query_df(f"""SELECT season, week, gsis_id, position, y_dk_points FROM `{settings.features}.player_week_training`
                   WHERE season IN (2023, 2024, 2025) AND was_active""")
d = off.merge(on, on=["season", "week", "gsis_id"]).merge(act, on=["season", "week", "gsis_id"])
d = d[d.position.isin(["QB", "RB", "WR", "TE"])]
d["band"] = pd.cut(d.mkt_off, [6, 10, 14, 18, 99], labels=["6-10", "10-14", "14-18", "18+"], right=False)
print(f"player-weeks {len(d)}; mean bonus added {(d.mkt_on - d.mkt_off).mean():.3f}")
rows = []
for (pos, band), g in d.dropna(subset=["band"]).groupby(["position", "band"], observed=True):
    r_off, r_on = g.y_dk_points - g.mkt_off, g.y_dk_points - g.mkt_on
    rows.append({"pos": pos, "band": band, "n": len(g), "bonus_added": round((g.mkt_on - g.mkt_off).mean(), 2),
                 "bias_off": round(r_off.mean(), 2), "bias_on": round(r_on.mean(), 2), "se": round(r_off.std() / np.sqrt(len(g)), 2),
                 "mae_off": round(r_off.abs().mean(), 2), "mae_on": round(r_on.abs().mean(), 2)})
print(pd.DataFrame(rows).to_string(index=False))
for s in S:
    g = d[(d.season == s) & d.position.isin(["WR", "RB", "TE"])]
    print(f"{s} WR/RB/TE: bias off {(g.y_dk_points - g.mkt_off).mean():+.2f} -> on {(g.y_dk_points - g.mkt_on).mean():+.2f} (n {len(g)})")
