import numpy as np, pandas as pd
E = pd.read_parquet("entries_paid.parquet"); M = pd.read_csv("contest_meta_all.csv", dtype={"contest_id": str})
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
big = M[M.entries >= 4000].copy(); big["short"] = big.name.str.replace("NFL ", "").str[:40]
E = E[E.contest_id.isin(big.contest_id)].merge(big[["contest_id", "short"]], on="contest_id")
E["cash"] = E.prize > 0
U = E.groupby(["week", "contest_id", "short", "user"]).agg(n=("entry_id", "size"), fees=("fee", "sum"), won=("prize", "sum"), best_pct=("pct", "min"), best_rank=("rank", "min")).reset_index()
U["net"] = U.won - U.fees; U["roi"] = U.won / U.fees - 1; U["profit"] = U.net > 0
print("=== G. Every large contest (4,000+ entries): share of users who made money that week")
print(U.groupby(["week", "short"]).agg(users=("user", "size"), entries=("n", "sum"), max_entries_by_one_user=("n", "max"), share_profitable=("profit", "mean"),
      median_roi=("roi", "median")).round(3).to_string())
# total per user-week across ALL large contests we can see
T = U.groupby(["week", "user"]).agg(contests=("contest_id", "nunique"), n=("n", "sum"), fees=("fees", "sum"), won=("won", "sum"), best_pct=("best_pct", "min")).reset_index()
T["profit"] = T.won > T.fees; T["roi"] = T.won / T.fees - 1
print("\n=== H. Top placers in ANY large contest (top 0.1% of that field): their total result in the OTHER weeks, across every large contest we can see")
rows = []
for w in (1, 2, 3):
    top = U[(U.week == w) & (U.best_pct <= 0.001)].user.unique()
    o = T[(T.week != w) & T.user.isin(top)]
    rows.append({"placed top 0.1% in week": w, "users": len(top), "other user-weeks": len(o), "other weeks that LOST money": (~o.profit).mean(), "median ROI": o.roi.median(),
                 "pooled ROI": o.won.sum() / o.fees.sum() - 1, "median stake in those weeks": o.fees.median()})
print(pd.DataFrame(rows).round(3).to_string(index=False))
print("\n=== I. Users who spent the most (top 200 by total fees across the three weeks, large contests): week-by-week")
tot = T.groupby("user").agg(fees=("fees", "sum"), won=("won", "sum"), weeks=("week", "nunique"), win_weeks=("profit", "sum"))
top = tot[tot.weeks == 3].nlargest(200, "fees")
print("users", len(top), "| median total stake", round(top.fees.median()), "| profitable weeks out of 3:", top.win_weeks.value_counts(normalize=True).sort_index().round(3).to_dict(),
      "| up after three weeks:", round((top.won > top.fees).mean(), 3), "| median 3-week ROI", round((top.won / top.fees - 1).median(), 3), "| pooled ROI", round(top.won.sum() / top.fees.sum() - 1, 3))
print("their 3-week ROI percentiles:", (top.won / top.fees - 1).quantile([.1, .25, .5, .75, .9]).round(2).to_dict())
print("\n=== J. How concentrated is the prize money? (the three Millionaires pooled)")
mm = E[E.short.str.contains("Millionaire")].groupby("user").agg(fees=("fee", "sum"), won=("prize", "sum"))
mm = mm.sort_values("won", ascending=False); tw = mm.won.sum()
for k in (10, 100, 1000): print(f"  the top {k} users by winnings took {100 * mm.won.head(k).sum() / tw:.1f}% of all prize money ({len(mm):,} users)")
print("  users who are ahead after the weeks they played:", round(100 * (mm.won > mm.fees).mean(), 1), "%")
