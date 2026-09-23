"""mean(actual DK - market_points) by position x band, plain / bonus / median / both. The gamma shapes were fitted on
2023-24 only, so 2025 is the out-of-sample season (production HANDOFF de3042c0). Active players, >= 2 markets."""
import os, numpy as np, pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
from nfl_dfs.models import prop_market
S = (2023, 2024, 2025); ARMS = {"plain": ("0", "0"), "bonus": ("0", "1"), "median": ("1", "0"), "both": ("1", "1")}
frames = []
for arm, (med, bon) in ARMS.items():
    os.environ["MARKET_LINE_MEDIAN"], os.environ["MARKET_BONUS_AWARE"] = med, bon
    frames.append(prop_market.market_points(S, minimum_markets=2).set_index(["season", "week", "gsis_id"]).market_points.rename(arm))
act = query_df(f"""SELECT season, week, gsis_id, position, y_dk_points FROM `{settings.features}.player_week_training`
                   WHERE season IN (2023, 2024, 2025) AND was_active""")
d = pd.concat(frames, axis=1, join="inner").reset_index().merge(act, on=["season", "week", "gsis_id"])
d = d[d.position.isin(["QB", "RB", "WR", "TE"])]
d["band"] = pd.cut(d.plain, [6, 10, 14, 18, 99], labels=["6-10", "10-14", "14-18", "18+"], right=False)
for split, g0 in (("FIT 2023-24", d[d.season <= 2024]), ("OUT-OF-SAMPLE 2025", d[d.season == 2025])):
    rows = []
    for (pos, band), g in g0.dropna(subset=["band"]).groupby(["position", "band"], observed=True):
        r = {"pos": pos, "band": band, "n": len(g)}
        for arm in ARMS:
            r[f"bias_{arm}"] = round((g.y_dk_points - g[arm]).mean(), 2)
        r["se"] = round((g.y_dk_points - g.plain).std() / np.sqrt(len(g)), 2)
        for arm in ARMS:
            r[f"mae_{arm}"] = round((g.y_dk_points - g[arm]).abs().mean(), 3)
        rows.append(r)
    print(f"\n=== {split} (player-weeks {len(g0)}) ===")
    print(pd.DataFrame(rows).to_string(index=False))
for s in S:
    g = d[(d.season == s) & d.position.isin(["WR", "RB", "TE"])]
    print(f"{s} WR/RB/TE bias " + "  ".join(f"{a} {(g.y_dk_points - g[a]).mean():+.2f}" for a in ARMS)
          + "  | MAE " + "  ".join(f"{a} {(g.y_dk_points - g[a]).abs().mean():.3f}" for a in ARMS)
          + "  | MSE " + "  ".join(f"{a} {((g.y_dk_points - g[a]) ** 2).mean():.2f}" for a in ARMS) + f"  (n {len(g)})")
# MAE is minimised by the MEDIAN, so a skew-aware MEAN is expected to lose MAE; MSE is the loss a mean should minimise.
print("MAE favours medians; MSE is the proper loss for a mean projection.")
