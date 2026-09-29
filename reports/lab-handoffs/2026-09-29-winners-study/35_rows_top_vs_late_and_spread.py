"""Row position in the capped optimizer's 144-row sequence: the 2023-24 pattern, its 2022 holdout, and the spread test."""
import json, glob, numpy as np, pandas as pd
pd.set_option("display.width", 220)
def load(d): return [json.load(open(f)) for f in sorted(glob.glob(d + "/*.json"))]
A, H = load("pct"), load("pct2022"); rng = np.random.default_rng(11)
def bands(S, label):
    p = np.array([s["K144"]["pct"] for s in S]); rows = []
    for a, b in ((0, 36), (36, 72), (72, 108), (108, 144)):
        P = p[:, a:b]; rows.append({"rows": f"{a+1}-{b}", "cash line": (P >= .77).mean() / .23, "top 11%": (P >= .89).mean() / .11, "top 5%": (P >= .95).mean() / .05, "top 1%": (P >= .99).mean() / .01})
    print(f"\n{label} ({len(S)} slates), multiples of the field's rate"); print(pd.DataFrame(rows).round(3).to_string(index=False)); return p
pa, ph = bands(A, "2023-24 (where the pattern was found)"), bands(H, "2022 (holdout)")
for lab, P in (("2022 holdout", ph), ("all 53 slates", np.vstack([pa, ph]))):
    for q, nm in ((.89, "top 11%"), (.95, "top 5%"), (.99, "top 1%")):
        d = (P[:, 108:144] >= q).mean(axis=1) - (P[:, 0:36] >= q).mean(axis=1); bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(20000)]
        print(f"  {lab}: rows 109-144 minus rows 1-36 at the {nm}: {d.mean():+.4f} [90% {np.percentile(bs, 5):+.4f}, {np.percentile(bs, 95):+.4f}]")
S = A + H; p = np.array([s["K144"]["pct"] for s in S]); seas = np.array([s["season"] for s in S]); rows = []
for N in (5, 20):
    top = np.arange(N); spread = np.linspace(0, 143, N).round().astype(int)
    for q, nm in ((.77, "cash line"), (.89, "top 11%"), (.95, "top 5%"), (.99, "top 1%")):
        a, b = (p[:, top] >= q), (p[:, spread] >= q); d = (b.sum(axis=1) > 0).astype(float) - (a.sum(axis=1) > 0).astype(float)
        rows.append({"entries": N, "line": nm, "hits/week top": a.sum(axis=1).mean(), "hits/week spread": b.sum(axis=1).mean(), "weeks with a hit, top": (a.sum(axis=1) > 0).mean(), "spread": (b.sum(axis=1) > 0).mean(),
                     "gained": int((d > 0).sum()), "lost": int((d < 0).sum()), "by season": " / ".join(f"{d[seas == y].mean():+.2f}" for y in (2022, 2023, 2024))})
print("\nN entries from the top of the sequence vs spread evenly over it, all 53 slates"); print(pd.DataFrame(rows).round(3).to_string(index=False))
