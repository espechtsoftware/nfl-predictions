import numpy as np, pandas as pd, sys
f = pd.read_parquet("lineups.parquet")
f["sal_left"] = 50000 - f.salary
def bins(f):
    return {
        "stack depth (QB + same-team WR/TE)": pd.cut(f["stack"], [-1, 0, 1, 2, 9], labels=["0", "1", "2", "3+"]),
        "bring-backs": pd.cut(f.bringback, [-1, 0, 1, 9], labels=["0", "1", "2+"]),
        "RB with own QB": pd.cut(f.rb_with_qb, [-1, 0, 9], labels=["0", "1+"]),
        "max players from one game": pd.cut(f.max_game, [0, 2, 3, 4, 5, 9], labels=["<=2", "3", "4", "5", "6+"]),
        "distinct games": pd.cut(f.n_games, [0, 4, 5, 6, 9], labels=["<=4", "5", "6", "7+"]),
        "salary left": pd.cut(f.sal_left, [-1, 0, 400, 1000, 99999], labels=["0", "100-400", "500-1000", ">1000"]),
        "players $7k+": pd.cut(f.n_7k, [-1, 0, 1, 2, 3, 9], labels=["0", "1", "2", "3", "4+"]),
        "players <= $4k (skill)": pd.cut(f.n_le4k, [-1, 0, 1, 2, 9], labels=["0", "1", "2", "3+"]),
        "late-window players": pd.cut(f.late, [-1, 2, 4, 6, 9], labels=["0-2", "3-4", "5-6", "7+"]),
        "players < 5% owned (skill)": pd.cut(f.n_own_lt5, [-1, 0, 1, 2, 9], labels=["0", "1", "2", "3+"]),
        "players >= 20% owned": pd.cut(f.n_own_ge20, [-1, 0, 1, 2, 9], labels=["0", "1", "2", "3+"]),
        "DST facing own players": pd.cut(f.dst_vs_own, [-1, 0, 9], labels=["0", "1+"]),
        "FLEX position": f.flex_pos,
        "TEs": f.n_te.astype(str),
    }
tiers = [("top 1%", 0.01), ("top 0.1%", 0.001), ("top 0.01%", 0.0001)]
def table(cids, label):
    print(f"\n######## {label}")
    rows = []
    for cid in cids:
        g = f[f.contest_id == cid]; b = bins(g)
        for feat, s in b.items():
            base = s.value_counts(normalize=True)
            for lab, q in tiers:
                t = s[g.pct <= q].value_counts(normalize=True)
                for k in base.index:
                    rows.append({"feature": feat, "value": str(k), "contest": cid, "tier": lab,
                                 "field": base.get(k, 0), "share": t.get(k, 0), "n_tier": int((g.pct <= q).sum())})
    r = pd.DataFrame(rows); r["lift"] = r.share / r.field
    return r
M = table(["193028206", "195648007"], "Millionaires")
M.to_csv("tier_lifts_milly.csv", index=False)
R = table(["193028208", "195661344"], "replication: Play-Action W1, Flea W2")
R.to_csv("tier_lifts_repl.csv", index=False)
# compact print: field share and lifts at 1% / 0.1% for each week
def show(r, c1, c2):
    p = r.pivot_table(index=["feature", "value"], columns=["contest", "tier"], values=["field", "lift"], aggfunc="first")
    out = pd.DataFrame({
        "W1 field": p[("field", c1, "top 1%")], "W1 L1%": p[("lift", c1, "top 1%")], "W1 L0.1%": p[("lift", c1, "top 0.1%")], "W1 L0.01%": p[("lift", c1, "top 0.01%")],
        "W2 field": p[("field", c2, "top 1%")], "W2 L1%": p[("lift", c2, "top 1%")], "W2 L0.1%": p[("lift", c2, "top 0.1%")], "W2 L0.01%": p[("lift", c2, "top 0.01%")],
    })
    pd.set_option("display.width", 200)
    print(out.round(2).to_string())
show(M, "193028206", "195648007")
print("\nreplication contests (Play-Action W1 158k, Flea W2 83k):")
show(R, "193028208", "195661344")
