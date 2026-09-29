import numpy as np, pandas as pd, os
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
E = pd.read_parquet("entries_paid.parquet"); M = pd.read_csv("contest_meta_all.csv", dtype={"contest_id": str})
X = pd.read_parquet("user_traits.parquet")
MILLY = {1: "193028206", 2: "195648007", 3: "195905122"}
m = E[E.contest_id.isin(MILLY.values())].copy()
print("=== K. How much edge do the skilled have at each payout depth? (their ENTRIES' finish, skill measured in other weeks; the Millionaire)")
rows = []
for q in ("bottom fifth", "3", "top fifth"):
    parts = []
    for w in (1, 2, 3):
        u = X[(X.week == w) & (X.q == q)].user
        parts.append(m[(m.week == w) & m.user.isin(u)])
    e = pd.concat(parts)
    rows.append({"users' skill (other weeks)": q, "entries": len(e), "top 50%": (e.pct <= .5).mean(), "cash (top ~23%)": (e.prize > 0).mean(), "top 10%": (e.pct <= .10).mean(), "top 5%": (e.pct <= .05).mean(),
                 "top 1%": (e.pct <= .01).mean(), "top 0.1%": (e.pct <= .001).mean(), "pooled ROI": e.prize.sum() / e.fee.sum() - 1})
K = pd.DataFrame(rows).set_index("users' skill (other weeks)"); print(K.round(4).to_string())
base = pd.Series({"top 50%": .5, "cash (top ~23%)": (m.prize > 0).mean(), "top 10%": .1, "top 5%": .05, "top 1%": .01, "top 0.1%": .001})
print("as a multiple of the field's rate:"); print((K[base.index] / base).round(2).to_string())

print("\n=== L. The realistic ceiling: users with 20+ entries in all three Millionaires, their three-week average score (z vs the field)")
U = pd.read_parquet("milly_user_weeks.parquet"); P = U[U.n >= 20]; c = P.groupby("user").week.nunique(); T = P[P.user.isin(c[c == 3].index)]
a = T.groupby("user").mean_z.mean()
print("users", len(a), "| percentiles of the 3-week average z:", a.quantile([.1, .25, .5, .75, .9, .95, .99]).round(3).to_dict())
piv = T.pivot_table(index="user", columns="week", values="mean_z"); rho = np.mean([piv[1].corr(piv[2]), piv[1].corr(piv[3]), piv[2].corr(piv[3])])
sd_obs = piv.stack().groupby(level=1).std().mean()
print(f"week-to-week correlation of a user's average score: {rho:.3f}; observed spread of one week's average (sd) {sd_obs:.3f}; implied spread of TRUE skill (sd) {np.sqrt(max(rho, 0)) * sd_obs:.3f} z = about {np.sqrt(max(rho, 0)) * sd_obs * 27:.1f} points per lineup")

print("\n=== M. Our own entries, on the same scale (no names)")
acct = None
for p in (os.environ.get("ACCT_FILE", ""),):          # a private one-line file with our user name; never printed
    if os.path.exists(p): acct = open(p).read().strip(); break
if acct:
    o = E[E.user == acct].copy()
    o["z"] = (o.points - o.contest_id.map(E.groupby("contest_id").points.mean())) / o.contest_id.map(E.groupby("contest_id").points.std())
    g = o.groupby("week").agg(contests=("contest_id", "nunique"), entries=("entry_id", "size"), mean_points=("points", "mean"), mean_z=("z", "mean"), cashed=("prize", lambda x: (x > 0).mean()),
                              fees=("fee", "sum"), won=("prize", "sum"))
    g["roi"] = g.won / g.fees - 1
    print(g.drop(columns=["fees", "won"]).round(3).to_string())
    hv = U[U.n >= 20]
    for w in (1, 2, 3):
        mine = o[(o.week == w) & (o.contest_id == MILLY[w])]
        if len(mine):
            z = ((mine.points - m[m.week == w].points.mean()) / m[m.week == w].points.std()).mean()
            print(f"  week {w} Millionaire: {len(mine)} entries, average z {z:+.3f} -> percentile among users with 20+ entries: {100 * (hv[hv.week == w].mean_z < z).mean():.0f}")
else: print("account file not found; skipped")

print("\n=== N. Field strength by contest (points at each percentile of the field, minus the same week's Millionaire)")
ref = {w: m[m.week == w].points.quantile([.5, .77, .9, .99]) for w in (1, 2, 3)}
rows = []
for cid, g in E.groupby("contest_id"):
    mm = M[M.contest_id == cid].iloc[0]; w = int(mm.week); q = g.points.quantile([.5, .77, .9, .99])
    per = g.groupby("user").size()
    rows.append({"week": w, "contest": mm["name"].replace("NFL ", "")[:44], "fee": mm.fee, "entries": len(g), "paid share": mm.paid_positions / len(g), "p50": q[.5] - ref[w][.5], "p77": q[.77] - ref[w][.77],
                 "p90": q[.9] - ref[w][.9], "p99": q[.99] - ref[w][.99], "share of entries from users with 20+": g.user.map(per).ge(20).mean()})
N = pd.DataFrame(rows)
print(N.groupby(["week", "contest", "fee", "entries"]).agg(n=("p50", "size"), paid_share=("paid share", "mean"), p50=("p50", "mean"), p77=("p77", "mean"), p90=("p90", "mean"), p99=("p99", "mean"),
      heavy=("share of entries from users with 20+", "mean")).round(2).to_string())
