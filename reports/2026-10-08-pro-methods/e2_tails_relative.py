# Robustness for analysis E: tails relative to the market (boom = actual >= 1.6 x market; bust = actual <= 0.5 x market),
# with market-level DECILE x season-week-position fixed effects (absorbs the level-variance link non-linearly).
from pathlib import Path
import numpy as np, pandas as pd
OUT = Path.home() / "private" / "pro-methods"
m = pd.read_parquet(OUT / "c_hist_modelframe.parquet")
m = m[m.market_points >= 4].copy()
m["boom"] = (m.y_dk_points >= 1.6 * m.market_points).astype(float)
m["bust"] = (m.y_dk_points <= 0.5 * m.market_points).astype(float)
m["dec"] = m.groupby("position").market_points.transform(lambda x: pd.qcut(x.rank(method="first"), 10, labels=False))
m["fe"] = m.swp + "|" + m.dec.astype(str)
print(f"n {len(m)}  boom rate {m.boom.mean():.3f}  bust rate {m.bust.mean():.3f}")
zc = [c for c in m.columns if c.startswith("z::")]
def coef(df, y, x):
    g = df[df[x].notna()]
    xv = g[x] - g.groupby("fe")[x].transform("mean"); yv = g[y] - g.groupby("fe")[y].transform("mean")
    return float((xv * yv).sum() / (xv * xv).sum()) if (xv * xv).sum() > 0 else np.nan
rng = np.random.default_rng(2); weeks = m.sw.unique(); ix = {w: np.flatnonzero(m.sw.values == w) for w in weeks}
rows = []
for x in zc:
    r = {"data point": x[3:]}
    for y in ("boom", "bust"):
        b = coef(m, y, x); bs = [coef(m.iloc[np.concatenate([ix[w] for w in rng.choice(weeks, len(weeks))])], y, x) for _ in range(200)]
        r[f"{y} pp/sd"] = 100 * b; r[f"{y} z"] = b / np.nanstd(bs)
        r[f"{y} 3/3"] = len({np.sign(coef(m[m.season == s], y, x)) for s in (2023, 2024, 2025)}) == 1
    rows.append(r)
R = pd.DataFrame(rows)
R["maxz"] = R[["boom z", "bust z"]].abs().max(axis=1)
pd.set_option("display.width", 250)
print(R.sort_values("maxz", ascending=False).drop(columns="maxz").round(2).head(22).to_string(index=False))
R.to_csv(OUT / "e2_tails_relative.csv", index=False)
