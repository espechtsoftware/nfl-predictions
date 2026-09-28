"""Historical test of the 'market floor' (post-mortem Q6) at the player level, on the 107-slate replay panel.

    cd $TESTBED && python w3_market_floor.py      # needs spf_full.parquet from the 09-24 review's pull_testbed.py
"""
import pandas as pd, numpy as np
s = pd.read_parquet("spf_full.parquet")
s = s[(s.pos != "DST") & s.market_points.notna() & s.model_points_pre.notna() & (s.mean_projection >= 5)].copy()
s["actual"] = s.actual.fillna(0)
s["gap"] = s.model_points_pre - s.market_points
s["resid_served"] = s.actual - s.mean_projection
s["resid_market"] = s.actual - s.market_points
s["bin"] = pd.cut(s.gap, [-99, -3, -1, 1, 3, 99], labels=["model <= mkt-3", "mkt-3..mkt-1", "within 1", "mkt+1..mkt+3", "model >= mkt+3"])
pd.set_option("display.width", 200)
def summ(x):
    return pd.Series({"n": len(x), "seasons": x.season.nunique(), "actual - served": x.resid_served.mean(),
                      "se": x.resid_served.std(ddof=1) / np.sqrt(len(x)), "actual - market": x.resid_market.mean(),
                      "MAE served": x.resid_served.abs().mean(), "MAE market": x.resid_market.abs().mean()})
print("players with a market price and served mean >= 5, seasons", sorted(s.season.unique()))
print(s.groupby("bin", observed=True).apply(summ, include_groups=False).round(2).to_string())
s["floor"] = np.where(s.market_points - s.mean_projection >= 1, (s.market_points + s.mean_projection) / 2, s.mean_projection)
print("MAE served", round((s.actual - s.mean_projection).abs().mean(), 3), "| with the market floor", round((s.actual - s.floor).abs().mean(), 3),
      "| market only", round(s.resid_market.abs().mean(), 3), "| rows touched", int((s.market_points - s.mean_projection >= 1).sum()), "of", len(s))
