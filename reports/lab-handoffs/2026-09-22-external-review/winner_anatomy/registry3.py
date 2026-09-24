import re, numpy as np, pandas as pd
IN = __import__("os").environ["REVIEW_INPUTS"]          # the external-review pull_inputs.py output dir
w = pd.read_csv("registry_teams.csv")
rows = []
for (s, k), g in w.groupby(["season", "week"]):
    if len(g) != 9: continue
    ok = g.team.notna().all()
    qb = g[g.pos == "QB"]; qt = qb.team.iloc[0] if len(qb) else None; qo = qb.opp.iloc[0] if len(qb) else None
    sk = g[g.pos != "DST"]
    stack = int(((sk.team == qt) & sk.pos.isin(["WR", "TE"])).sum())
    bb = int((sk.team == qo).sum())
    dst = g[g.pos == "DST"]
    games = g.apply(lambda r: "-".join(sorted([str(r.team), str(r.opp)])), axis=1)
    rbs = sk[sk.pos == "RB"]
    legal = ok and stack >= 2 and bb >= 1 and g.salary.sum() >= 49000 and not (rbs.team.duplicated().any()) and \
        not (len(dst) and (rbs.team == dst.opp.iloc[0]).any())
    rows.append({"season": s, "week": k, "ok": ok, "pts": g.pts.sum(), "salary": g.salary.sum(),
                 "n_7k": int(((sk.salary >= 7000)).sum()), "n_le4k": int((sk.salary <= 4000).sum()),
                 "own_sum": g.own.sum(), "n_lt5": int((sk.own < 5).sum()), "n_ge20": int((g.own >= 20).sum()),
                 "stack": stack, "bringback": bb, "rb_with_qb": int(((sk.team == qt) & (sk.pos == "RB")).sum()),
                 "max_game": games.value_counts().max() if ok else np.nan, "n_games": games.nunique() if ok else np.nan,
                 "two_te": int((g.pos == "TE").sum() >= 2), "house_legal": legal})
W = pd.DataFrame(rows)
print(f"winners: {len(W)} ({W.ok.sum()} fully team-matched), seasons {W.season.value_counts().sort_index().to_dict()}")
print(W.describe().T[["mean", "25%", "50%", "75%"]].round(2).to_string())
print("\nshare of winners by bucket:")
for c, bins_, labs in (("stack", [-1, 0, 1, 2, 9], ["0", "1", "2", "3+"]), ("bringback", [-1, 0, 1, 9], ["0", "1", "2+"]),
                       ("max_game", [0, 2, 3, 4, 5, 9], ["<=2", "3", "4", "5", "6+"]), ("n_lt5", [-1, 0, 1, 2, 9], ["0", "1", "2", "3+"]),
                       ("n_ge20", [-1, 0, 1, 2, 9], ["0", "1", "2", "3+"]), ("n_7k", [-1, 0, 1, 2, 9], ["0", "1", "2", "3+"])):
    x = W[W.ok] if c in ("stack", "bringback", "max_game") else W
    print(f"  {c:<10}", (100 * pd.cut(x[c], bins_, labels=labs).value_counts(normalize=True).sort_index()).round(0).to_dict())
print(f"\nhouse-rule legal (QB+2, bring-back, >=$49k, RB rules): {W[W.ok].house_legal.mean():.2f} of fully matched winners")
# field expectation from full-slate ownership (2023-2025 have milly ownership)
own = pd.read_csv(f"{IN}/milly_own.csv")
spf = pd.read_csv(f"{IN}/spf.csv")[["season", "week", "name", "pos"]]
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
own["key"] = own.display_name.map(norm)
dst_names = set(NICK.lower() for NICK in ["Cardinals","Falcons","Ravens","Bills","Panthers","Bears","Bengals","Browns","Cowboys","Broncos","Lions","Packers","Texans","Colts","Jaguars","Chiefs","Raiders","Chargers","Rams","Dolphins","Vikings","Patriots","Saints","Giants","Jets","Eagles","Steelers","49ers","Seahawks","Buccaneers","Titans","Commanders"])
own["dst"] = own.display_name.str.lower().str.strip().isin(dst_names) | own.roster_position.eq("DST")
exp = own.groupby(["season", "week"]).apply(lambda x: pd.Series({
    "field_lt5": (x.pct_drafted[(x.pct_drafted < 5) & ~x.dst]).sum() / 100,
    "field_ge20": (x.pct_drafted[x.pct_drafted >= 20]).sum() / 100,
    "mass": x.pct_drafted.sum()}), include_groups=False).reset_index()
X = W.merge(exp, on=["season", "week"], how="inner")
print(f"\nslates with both a registry winner and full-slate ownership: {len(X)} (mass check {X.mass.mean():.0f}%)")
print(f"  # skill players under 5%: winners {X.n_lt5.mean():.2f} vs random field lineup {X.field_lt5.mean():.2f}  (winner below field in {(X.n_lt5 < X.field_lt5).sum()}/{len(X)})")
print(f"  # players at 20%+:        winners {X.n_ge20.mean():.2f} vs random field lineup {X.field_ge20.mean():.2f}  (winner above field in {(X.n_ge20 > X.field_ge20).sum()}/{len(X)})")
W.to_csv("registry_features.csv", index=False)
