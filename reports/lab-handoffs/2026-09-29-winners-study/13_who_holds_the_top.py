import numpy as np, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
E = pd.read_parquet("entries_paid.parquet"); U = pd.read_parquet("milly_user_weeks.parquet")
MILLY = {1: "193028206", 2: "195648007", 3: "195905122"}
m = E[E.contest_id.isin(MILLY.values())].merge(U[["week", "user", "n"]], on=["week", "user"])
m["bucket"] = pd.cut(m.n, [0, 1, 3, 10, 50, 149, 1000], labels=["1 entry", "2-3", "4-10", "11-50", "51-149", "150 (max)"])
print("=== O. Who holds the top places? Share of finishes by how many entries the user had that week (three Millionaires pooled)")
rows = {}
for lab, mask in (("all entries", m["rank"] > 0), ("top 1%", m.pct <= .01), ("top 1,000", m["rank"] <= 1000), ("top 100", m["rank"] <= 100), ("top 10", m["rank"] <= 10)):
    rows[lab] = m[mask].bucket.value_counts(normalize=True).sort_index()
print((pd.DataFrame(rows) * 100).round(1).to_string())
print("\nusers by bucket (share of all users):", (U.assign(b=pd.cut(U.n, [0, 1, 3, 10, 50, 149, 1000], labels=["1 entry", "2-3", "4-10", "11-50", "51-149", "150 (max)"])).b.value_counts(normalize=True).sort_index() * 100).round(2).to_dict())

print("\n=== P. The three $1M winners and the 30 top-10 finishers: every OTHER Millionaire week they played")
for lab, k in (("the three winners (rank 1)", 1), ("top-3 finishers", 3), ("top-10 finishers", 10)):
    tops = m[m["rank"] <= k][["week", "user"]].drop_duplicates()
    o = U.merge(tops.rename(columns={"week": "w_top"}), on="user"); o = o[o.week != o.w_top]
    print(f"  {lab}: users {tops.user.nunique()} | other weeks played {len(o)} | entries in those weeks (median) {o.n.median():.0f} | weeks that lost money {(~o.profit).mean():.0%} | "
          f"median result {o.roi.median():+.0%} of the stake | best other-week finish (median rank) {o.best_rank.median():.0f}")

print("\n=== Q. The 50 users who won the most over the three weeks: how many of their weeks were profitable?")
t = U.groupby("user").agg(weeks=("week", "size"), win_weeks=("profit", "sum"), fees=("fees", "sum"), won=("won", "sum")); t["net"] = t.won - t.fees
top = t.nlargest(50, "net")
print("weeks played:", top.weeks.value_counts().sort_index().to_dict(), "| profitable weeks among those who played all three:", top[top.weeks == 3].win_weeks.value_counts().sort_index().to_dict())
print("share of their weeks that were profitable:", round(top.win_weeks.sum() / top.weeks.sum(), 3), "| median total stake", round(top.fees.median()))
print("\n=== R. What one good week is worth: for heavy players (100+ entries), the share of their three-week winnings that came from their single best week")
h = U[U.n >= 100]; c = h.groupby("user").week.nunique(); h3 = h[h.user.isin(c[c == 3].index)]
s = h3.groupby("user").won.agg(lambda x: x.max() / x.sum() if x.sum() > 0 else np.nan)
print("users", s.notna().sum(), "| median share from the best week", round(s.median(), 3), "| 25th-75th percentile", s.quantile([.25, .75]).round(3).tolist())
