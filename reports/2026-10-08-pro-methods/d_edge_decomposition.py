# PRO METHODS, analysis D: where does the regulars' player-picking edge come from -- following the market (FP/props)
# more faithfully than the crowd, or knowing MORE than the market?
# Edge per lineup (the 10-05 measure) = sum_i (share_group_i - share_rest_i) x (actual_i - mean actual of i's week x
# position x $1k band). Split actual - band mean = (market_i - band market mean) [MARKET part: what the market expected]
# + (actual_i - market_i - band mean of that) [BEYOND part]. Prop-covered players (props as the market, W1-4) and W4
# with FP as the market. Nulls (1,000): the group's tilts shuffled among players of the same week x position x band.
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path.home() / "private" / "pro-methods"
pan = pd.read_parquet(OUT / "panel.parquet")
for c in pan.columns:
    if pd.api.types.is_numeric_dtype(pan[c]) and not pd.api.types.is_bool_dtype(pan[c]):
        pan[c] = pan[c].astype(float)
rng = np.random.default_rng(5)


def decompose(df, mcol, gcol, reps=1000):
    g = df[df[mcol].notna() & df.actual.notna() & df.salary.notna()].copy()
    g["band"] = g.week.astype(str) + g.pos + (g.salary // 1000).astype(int).astype(str)
    g["a_dev"] = g.actual - g.groupby("band").actual.transform("mean")
    g["m_dev"] = g[mcol] - g.groupby("band")[mcol].transform("mean")
    g["b_dev"] = g.a_dev - g.m_dev
    t = (g[gcol] - g.exp_rest).values
    out = {"total": float(t @ g.a_dev.values), "market": float(t @ g.m_dev.values), "beyond": float(t @ g.b_dev.values)}
    # null: shuffle tilts within band
    bands = g.band.values
    groups = [np.flatnonzero(bands == b) for b in np.unique(bands)]
    null = {"total": [], "market": [], "beyond": []}
    for _ in range(reps):
        tt = t.copy()
        for ix in groups:
            tt[ix] = t[rng.permutation(ix)]
        null["total"].append(tt @ g.a_dev.values); null["market"].append(tt @ g.m_dev.values); null["beyond"].append(tt @ g.b_dev.values)
    res = {}
    for k in out:
        nm, ns = np.mean(null[k]), np.std(null[k])
        res[k] = (out[k], nm, ns, float(np.mean(np.array(null[k]) >= out[k])))
    return res, len(g)


def show(title, df, mcol, groups):
    print(f"\n{title}")
    for gname, gcol in groups:
        res, n = decompose(df, mcol, gcol)
        s = "  ".join(f"{k} {v[0]:+.2f} (null {v[1]:+.2f}±{v[2]:.2f}, p {v[3]:.3f})" for k, v in res.items())
        print(f"  {gname:16s} n {n:4d}  {s}")


sk = pan[pan.pos.isin(["QB", "RB", "WR", "TE"])]
G = [("regulars", "exp_reg"), ("top 1% (leaders)", "exp_top1")]
show("W1-4 pooled, props as the market (prop-covered players; points per lineup over 4 weeks)", sk, "props", G)
for w in (1, 2, 3, 4):
    show(f"W{w}, props as the market", sk[sk.week == w], "props", G[:1])
show("W4, FP as the market (all players FP projects)", sk[sk.week == 4], "fp", G)
show("W4, FP as the market, prop-covered players only (same set as props)", sk[(sk.week == 4) & sk.props.notna()], "fp", G[:1])
for p in ("QB", "RB", "WR", "TE"):
    show(f"W1-4 {p}, props as the market", sk[sk.pos == p], "props", G[:1])
