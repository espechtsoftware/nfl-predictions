import re, numpy as np, pandas as pd
def last(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()).strip()
    return re.sub(r"[^a-z]", "", s.split(" ", 1)[-1] if " " in s else s)
w = pd.read_csv("registry_teams.csv")
P = pd.read_parquet(__import__("os").environ["TESTBED"] + "/players_bed.parquet")
P["last"] = np.where(P.pos == "DST", P.id.astype(str), P.name.map(last))
w["last"] = np.where(w.slot == "DST", "DST_" + w.team.fillna("?").astype(str), w.player.map(last))
rows = []
for (s, k), g in w.groupby(["season", "week"]):
    p = P[(P.season == s) & (P.week == k)]
    if len(g) != 9 or p.own_pred.isna().all() or g.team.isna().any(): continue
    sk = p[p.pos != "DST"]; n_hi = int(round(0.101 * len(sk)))
    rk = sk.own_pred.rank(ascending=False, method="first")
    nonlow = set(sk.loc[rk <= n_hi, "last"] + "|" + sk.loc[rk <= n_hi, "team"].astype(str))
    chalk = set((p.loc[p.own_pred.rank(ascending=False, method="first") <= 15, "last"] + "|" + p.loc[p.own_pred.rank(ascending=False, method="first") <= 15, "team"].astype(str)))
    keys = (g["last"] + "|" + g.team.astype(str)).tolist()
    is_sk = (g.pos != "DST").to_numpy()
    n_low = sum((kk not in nonlow) for kk, sks in zip(keys, is_sk) if sks)
    n_ch = sum(kk in chalk for kk in keys)
    qb = g[g.pos == "QB"]; qt, qo = qb.team.iloc[0], qb.opp.iloc[0]
    stack = int(((g.team == qt) & g.pos.isin(["WR", "TE"])).sum()); bb = int(((g.team == qo) & (g.pos != "DST")).sum())
    games = g.apply(lambda r: "-".join(sorted([str(r.team), str(r.opp)])), axis=1)
    sal = g.salary.sum()
    rows.append({"season": s, "week": k, "n_low": n_low, "n_chalk": n_ch, "house": stack >= 2 and bb >= 1 and sal >= 49000,
                 "relaxed": stack >= 1 and sal >= 49000, "cap4": games.value_counts().max() <= 4, "sal_ok": sal >= 49500})
R = pd.DataFrame(rows)
L2 = (R.n_low <= 2) & (R.n_chalk >= 1) & R.sal_ok; L1 = (R.n_low <= 1) & (R.n_chalk >= 1) & R.sal_ok
print(f"registry winners with predicted ownership and full team match: {len(R)} (seasons {R.season.value_counts().sort_index().to_dict()})")
print(f"  inside L1 region {100*L1.mean():.0f}%, L2 region {100*L2.mean():.0f}%; mean predicted LOW {R.n_low.mean():.2f}")
print(f"  house-legal & cap4 {100*(R.house & R.cap4).mean():.0f}%;  L2 & house & cap4 {100*(L2 & R.house & R.cap4).mean():.0f}%;  "
      f"L2 & QB+1 relaxed & cap4 {100*(L2 & R.relaxed & R.cap4).mean():.0f}%;  L1 & relaxed & cap4 {100*(L1 & R.relaxed & R.cap4).mean():.0f}%")
