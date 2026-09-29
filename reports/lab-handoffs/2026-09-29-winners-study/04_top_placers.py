"""Do the people who place at the top of the Millionaire also lose on a regular basis? Aggregates only; no user names."""
import numpy as np, pandas as pd
E = pd.read_parquet("entries_paid.parquet"); M = pd.read_csv("contest_meta_all.csv", dtype={"contest_id": str})
MILLY = {1: "193028206", 2: "195648007", 3: "195905122"}
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
m = E[E.contest_id.isin(MILLY.values())].copy()
m["cash"] = m.prize > 0
# field z-score of each entry's points within its contest
m["z"] = m.groupby("contest_id").points.transform(lambda x: (x - x.mean()) / x.std())
U = m.groupby(["week", "user"]).agg(n=("entry_id", "size"), fees=("fee", "sum"), won=("prize", "sum"), best_rank=("rank", "min"), best_pct=("pct", "min"),
                                    cash_share=("cash", "mean"), mean_z=("z", "mean"), n_field=("n_field", "first")).reset_index()
U["net"] = U.won - U.fees; U["roi"] = U.won / U.fees - 1; U["profit"] = U.net > 0
U.to_parquet("milly_user_weeks.parquet")
print("=== A. The Millionaire, all users, by week")
print(U.groupby("week").agg(users=("user", "size"), entries=("n", "sum"), share_profitable=("profit", "mean"), share_any_cash=("cash_share", lambda x: (x > 0).mean()),
                            median_roi=("roi", "median"), mean_roi=("roi", "mean")).round(3).to_string())
print("\n=== B. Share of users with a PROFITABLE week, by how many entries they had (the Millionaire)")
U["bucket"] = pd.cut(U.n, [0, 1, 3, 10, 50, 149, 1000], labels=["1", "2-3", "4-10", "11-50", "51-149", "150 (max)"])
b = U.groupby(["bucket", "week"], observed=True).agg(users=("user", "size"), profitable=("profit", "mean"), median_roi=("roi", "median"), pooled_roi=("won", "sum"), fees=("fees", "sum"), mean_z=("mean_z", "mean")).reset_index()
b["pooled_roi"] = b.pooled_roi / b.fees - 1
print(b.drop(columns="fees").round(3).to_string(index=False))

print("\n=== C. Users who placed at the TOP of a Millionaire: how did they do in the OTHER weeks' Millionaires?")
rows = []
for label, cond in [("top 10", lambda u: u.best_rank <= 10), ("top 100", lambda u: u.best_rank <= 100), ("top 1,000", lambda u: u.best_rank <= 1000),
                    ("top 0.1% of the field", lambda u: u.best_pct <= 0.001), ("top 1% of the field", lambda u: u.best_pct <= 0.01)]:
    for w in (1, 2, 3):
        top = U[(U.week == w) & cond(U)]
        other = U[(U.week != w) & U.user.isin(top.user)]
        if len(top) == 0: continue
        per_user = other.groupby("user").agg(weeks=("week", "size"), losing_weeks=("profit", lambda x: (~x).sum()), net=("net", "sum"), fees=("fees", "sum"))
        rows.append({"placed": label, "in week": w, "users": len(top), "their entries that week (median)": top.n.median(), "profitable that week": top.profit.mean(),
                     "played another week": len(per_user), "other user-weeks": len(other), "OTHER weeks that LOST money": (~other.profit).mean(),
                     "other weeks with no cash at all": (other.cash_share == 0).mean(), "median ROI in other weeks": other.roi.median(),
                     "pooled ROI in other weeks": other.won.sum() / other.fees.sum() - 1, "lost in EVERY other week played": (per_user.losing_weeks == per_user.weeks).mean(),
                     "again top 1% in another week": (other.best_pct <= 0.01).mean()})
C = pd.DataFrame(rows); print(C.round(3).to_string(index=False))
print("\npooled over the three weeks:")
print(C.groupby("placed", sort=False).apply(lambda x: pd.Series({"users": x.users.sum(), "other user-weeks": x["other user-weeks"].sum(),
      "OTHER weeks that LOST money": np.average(x["OTHER weeks that LOST money"], weights=x["other user-weeks"]),
      "median ROI in other weeks (avg)": np.average(x["median ROI in other weeks"], weights=x["other user-weeks"]),
      "pooled ROI in other weeks (avg)": np.average(x["pooled ROI in other weeks"], weights=x["other user-weeks"]),
      "again top 1% in another week": np.average(x["again top 1% in another week"], weights=x["other user-weeks"])}), include_groups=False).round(3).to_string())
