import json, glob, numpy as np, pandas as pd
pd.set_option("display.width", 220)
S = [json.load(open(f)) for f in sorted(glob.glob("pct/*.json"))]
print("slates", len(S))
for book in ("K36", "K144"):
    p = np.array([s[book]["pct"] for s in S]); sc = np.array([s[book]["score"] for s in S]); fm = np.array([s["field_mean"] for s in S]); fsd = np.array([s["field_sd"] for s in S])
    z = (sc - fm[:, None]) / fsd[:, None]
    print(f"\n{book}: rows' average score {sc.mean():.1f} vs the field's {fm.mean():.1f} (field sd {fsd.mean():.1f}); average z {z.mean():+.3f}; sd of our rows' z within a slate {z.std(axis=1).mean():.2f} (the field's is 1.00); sd of the slate-average z across slates {z.mean(axis=1).std():.2f}")
    rows = []
    for lab, q in (("top 50%", .5), ("top 23% (Millionaire cash)", .77), ("top 11%", .89), ("top 5%", .95), ("top 1%", .99), ("top 0.2%", .998), ("top 0.1%", .999)):
        hit = p >= q
        rows.append({"line": lab, "our rows over it": hit.mean(), "x the field's rate": hit.mean() / (1 - q), "weeks with none": (hit.sum(axis=1) == 0).mean(), "rows over it in a median week": np.median(hit.sum(axis=1)),
                     "in the best week": hit.sum(axis=1).max()})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    sl = z.mean(axis=1)
    print("share of weeks in which our average row beat the field's average:", round((sl > 0).mean(), 3), "| slate-average z percentiles:", np.percentile(sl, [10, 25, 50, 75, 90]).round(2).tolist())
