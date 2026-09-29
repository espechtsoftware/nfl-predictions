import numpy as np, pandas as pd
U = pd.read_parquet("milly_user_weeks.parquet")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
print("=== D. Heavy Millionaire players (100+ entries in a week): the distribution of one week's result (ROI = winnings / fees - 1)")
H = U[U.n >= 100]
q = H.groupby("week").roi.quantile([.05, .10, .25, .50, .75, .90, .95, .99]).unstack().round(2)
q["users"] = H.groupby("week").size(); q["share profitable"] = H.groupby("week").profit.mean().round(3); q["pooled ROI"] = (H.groupby("week").won.sum() / H.groupby("week").fees.sum() - 1).round(3)
q["share of all prize money they won"] = (H.groupby("week").won.sum() / U.groupby("week").won.sum()).round(3); q["share of entries"] = (H.groupby("week").n.sum() / U.groupby("week").n.sum()).round(3)
print(q.to_string())

print("\n=== E. Users with 20+ entries in ALL THREE Millionaires: how many weeks were profitable?")
P = U[U.n >= 20]; cnt = P.groupby("user").week.nunique(); three = cnt[cnt == 3].index
T = P[P.user.isin(three)]
g = T.groupby("user").agg(win_weeks=("profit", "sum"), fees=("fees", "sum"), won=("won", "sum"), mean_z=("mean_z", "mean"), n=("n", "mean"))
g["roi3"] = g.won / g.fees - 1
print("users:", len(g), "| profitable weeks out of 3:", (g.win_weeks.value_counts(normalize=True).sort_index().round(3)).to_dict())
print("up after three weeks:", round((g.roi3 > 0).mean(), 3), "| median 3-week ROI", round(g.roi3.median(), 3), "| pooled ROI", round(g.won.sum() / g.fees.sum() - 1, 3))
for lab, sub in (("150-max in all three", T[T.n >= 150].groupby("user").filter(lambda x: len(x) == 3)),):
    gg = sub.groupby("user").agg(win_weeks=("profit", "sum"), fees=("fees", "sum"), won=("won", "sum"))
    print(f"{lab}: users {len(gg)} | profitable weeks: {gg.win_weeks.value_counts(normalize=True).sort_index().round(3).to_dict()} | up after 3 weeks {((gg.won - gg.fees) > 0).mean():.3f} | median 3-week ROI {(gg.won / gg.fees - 1).median():.3f}")

print("\n=== F. Is there persistent SKILL? Users with 20+ entries in both weeks: correlation of their average lineup score (z vs the field)")
piv = P.pivot_table(index="user", columns="week", values="mean_z"); roi = P.pivot_table(index="user", columns="week", values="roi")
for a, b in ((1, 2), (1, 3), (2, 3)):
    x = piv[[a, b]].dropna(); r = roi.loc[x.index, [a, b]]
    print(f"  weeks {a} vs {b}: users {len(x)} | corr(mean z) {x[a].corr(x[b]):+.3f} (Spearman {x[a].corr(x[b], method='spearman'):+.3f}) | corr(ROI) {r[a].corr(r[b], method='spearman'):+.3f}")
# top decile by mean z in week a: what happened in week b
rows = []
for a, b in ((1, 2), (1, 3), (2, 3), (2, 1), (3, 1), (3, 2)):
    x = P[P.week == a].copy(); x["dec"] = pd.qcut(x.mean_z.rank(method="first"), 10, labels=False)
    y = P[P.week == b].set_index("user")
    for d_, lab in ((9, "top tenth by average score"), (0, "bottom tenth")):
        u = x[x.dec == d_].user; yy = y.loc[y.index.intersection(u)]
        rows.append({"ranked in week": a, "group": lab, "their avg z that week": x[x.dec == d_].mean_z.mean(), "result in week": b, "users": len(yy), "avg z": yy.mean_z.mean(),
                     "profitable": yy.profit.mean(), "median ROI": yy.roi.median(), "pooled ROI": yy.won.sum() / yy.fees.sum() - 1})
print(pd.DataFrame(rows).round(3).to_string(index=False))
