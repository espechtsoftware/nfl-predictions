# PRO METHODS, analysis E.
# (1) History 2023-25: which data points raise the chance of a BOOM beyond the market (actual >= market + 10 DK points)
#     and of a BUST (actual <= market - 7)? Linear probability, season-week-position fixed effects, the market level
#     (z) as a control, whole-week bootstrap SE. Tournaments pay on the right tail, so a data point can matter here
#     without moving the mean.
# (2) Does Fantasy Points already carry the beyond-market signals (team implied total, game total, spread, wind)?
#     W4 and W5 (pre-lock; no outcomes needed): regress FP - props on each, within position.
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path.home() / "private" / "pro-methods"
m = pd.read_parquet(OUT / "c_hist_modelframe.parquet")
m["boom"] = (m.resid >= 10).astype(float)
m["bust"] = (m.resid <= -7).astype(float)
m["mkt_z"] = m.groupby("swp").market_points.transform(lambda x: (x - x.mean()) / x.std())
print(f"history: boom rate {m.boom.mean():.3f} (actual >= market + 10), bust rate {m.bust.mean():.3f} (<= market - 7); n {len(m)}")
zcols = [c for c in m.columns if c.startswith("z::")]


def coef(df, y, x):
    g = df[df[x].notna() & df.mkt_z.notna()]
    if len(g) < 200:
        return np.nan
    dm = lambda s: s - s.groupby(g.swp).transform("mean")
    X = np.column_stack([dm(g[x]), dm(g.mkt_z)]); Y = dm(g[y])
    b, *_ = np.linalg.lstsq(X, Y.values, rcond=None)
    return b[0]


rng = np.random.default_rng(9)
weeks = m.sw.unique(); ix = {w: np.flatnonzero(m.sw.values == w) for w in weeks}
rows = []
for x in zcols:
    r = {"data point": x[3:]}
    for y in ("boom", "bust"):
        b = coef(m, y, x)
        bs = [coef(m.iloc[np.concatenate([ix[w] for w in rng.choice(weeks, len(weeks))])], y, x) for _ in range(200)]
        se = np.nanstd(bs)
        r[f"{y} pp per sd"] = 100 * b; r[f"{y} z"] = b / se if se else np.nan
        r[f"{y} 3/3"] = len({np.sign(coef(m[m.season == s], y, x)) for s in (2023, 2024, 2025)}) == 1
    rows.append(r)
R = pd.DataFrame(rows).sort_values("boom z", key=np.abs, ascending=False)
pd.set_option("display.width", 250)
print(R.round(2).to_string(index=False))
R.to_csv(OUT / "e_boom_bust_history.csv", index=False)

# (2) FP vs props on the beyond-market signals, W4 (panel) and W5 (pre-lock now)
pan = pd.read_parquet(OUT / "panel.parquet")
w4 = pan[(pan.week == 4) & pan.pos.isin(["QB", "RB", "WR", "TE"]) & pan.props.notna() & pan.fp.notna()].copy()
for c in ("fp", "props", "implied_team_total", "game_total", "spread", "wind_mph"):
    w4[c] = w4[c].astype(float)
w4["gap"] = w4.fp - w4.props
print(f"\nW4 (n {len(w4)} prop-covered): FP - props, mean {w4.gap.mean():+.2f}; slope on each signal (points per sd, within position)")
for s in ("implied_team_total", "game_total", "spread", "wind_mph"):
    z = w4.groupby("pos")[s].transform(lambda x: (x - x.mean()) / x.std())
    g = w4.gap - w4.groupby("pos").gap.transform("mean")
    ok = z.notna()
    print(f"   {s:20s} {np.polyfit(z[ok], g[ok], 1)[0]:+.2f}   (history: the market under-prices this by "
          f"{ {'implied_team_total': '+0.33', 'game_total': '+0.24', 'spread': '-0.22', 'wind_mph': '-0.35'}[s]} per sd)")
