"""Operator question 2026-09-30 (HANDOFF 7a3a5764): do professionals run a deliberate contrarian minority, and do
Millionaire wins come from it? Descriptive, 2026 W1-W3 Millionaire fields (private inputs under ~/q11-study; prints
aggregates only, never a user name).

Per lineup (players matched by DK display name to the week's pre-lock T-70 frame):
  primary stack = the QB + >= 1 same-team RB/WR/TE; its game's PRE-LOCK total (the frame's game_total) ranked among
  the slate's games: top third / middle / bottom third; the lineup's share in that game; players outside their
  position's top 24 by the frame's projection (PRE-LOCK); players under 5% REALIZED Millionaire ownership (known at lock,
  descriptive only).
  CONTRARIAN (a): the primary stack in a bottom-third-total game.  (b): >= 3 players outside the projection top 24, or
  >= 4 players under 5% owned.
Reads: (1) share contrarian among the field, the top 1%, the top 0.1% and the winners (rank 1; top 10); per-lineup
top-1% rate contrarian vs not, Wilson 95% intervals, weeks separately. (2) Heavy portfolios (>= 20 entries): top-100
users (best rank <= 100) vs matched mid-field (mean percentile 35-65, best rank > 1000, nearest entry count): the
portfolio's contrarian share; its week-to-week stability for users heavy in two weeks; and whether their top-1% rows
are contrarian more often than their rows are (observed / expected, user-bootstrap 90% interval).
"""
import json, os, sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr
os.environ.setdefault("OMP_NUM_THREADS", "1")
Q = os.path.expanduser("~/q11-study")
sys.path.insert(0, os.path.join(Q, "q", "B"))
import common as C  # noqa: E402
SKILL = ("RB", "WR", "TE")
rng = np.random.default_rng(7)


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, c - h, c + h)


def week_meta(w):
    f = C.load_frame(C.RUNS[w]["t70"])
    f["display_name"] = f.display_name.astype(str).str.strip()
    f["pos"] = f.pos.astype(str)
    f["proj"] = pd.to_numeric(f.mean_projection, errors="coerce").fillna(0.0)
    f["prank"] = f.groupby("pos").proj.rank(ascending=False, method="first")
    g = f.groupby("game_id").game_total.first().astype(float)
    order = g.rank(method="first", ascending=True)       # 1 = lowest total
    n = len(g)
    third = {gid: ("bottom" if r <= n / 3 else ("top" if r > 2 * n / 3 else "middle")) for gid, r in order.items()}
    o = pd.read_csv(os.path.join(Q, "q", "B", "data", "contest_ownership_2026.csv"))
    o = o[o.contest_id.astype(str) == C.RUNS[w]["milly"]]
    own = o.groupby("display_name").pct_drafted.sum()
    meta = {r.display_name: (r.pos, r.team, r.game_id, r.prank, float(own.get(r.display_name, 0.0))) for r in f.itertuples()}
    return meta, third, n


def classify(players, meta, third):
    rows = [meta.get(p) for p in players]
    if any(r is None for r in rows):
        return None
    qbs = [r for r in rows if r[0] == "QB"]
    stack_game, stack_third, game_share = None, None, np.nan
    if qbs:
        q = qbs[0]
        mates = [r for r in rows if r[0] in SKILL and r[1] == q[1]]
        if mates:
            stack_game = q[2]; stack_third = third[q[2]]
            game_share = sum(1 for r in rows if r[2] == q[2]) / 9
    low_proj = sum(1 for r in rows if r[3] > 24)
    low_own = sum(1 for r in rows if r[4] < 5.0)
    return dict(has_stack=stack_game is not None, stack_third=stack_third, game_share=game_share, low_proj=low_proj, low_own=low_own,
                a=stack_third == "bottom", b=(low_proj >= 3) or (low_own >= 4))


def main():
    d = pd.read_parquet(os.path.join(Q, "q11", "milly_fields.parquet"))
    out = {}
    allrows = []
    for w in (1, 2, 3):
        meta, third, ngames = week_meta(w)
        x = d[d.week == w].copy()
        cache = {}
        recs = []
        for key in x.players_key:
            if key not in cache:
                cache[key] = classify(key.split("|"), meta, third)
            recs.append(cache[key])
        ok = np.array([r is not None for r in recs])
        x = x[ok].reset_index(drop=True)
        R = pd.DataFrame([r for r in recs if r is not None])
        x = pd.concat([x, R], axis=1)
        x["top1"] = x["rank"] <= 0.01 * x.n_field; x["top01"] = x["rank"] <= 0.001 * x.n_field
        allrows.append(x)
        res = {"games": ngames, "lineups": int(ok.sum()), "unmatched_lineups": int((~ok).sum()), "with_qb_stack": round(float(x.has_stack.mean()), 3)}
        for grp, m in (("field", np.ones(len(x), bool)), ("top1pct", x.top1.to_numpy()), ("top0.1pct", x.top01.to_numpy()),
                       ("top10", (x["rank"] <= 10).to_numpy()), ("winner", (x["rank"] == 1).to_numpy())):
            g = x[m]
            res[grp] = {"n": int(len(g)), "a_share": round(float(g.a.mean()), 4), "b_share": round(float(g.b.mean()), 4),
                        "stack_third": g.stack_third.value_counts(normalize=True).round(3).to_dict(),
                        "low_proj_mean": round(float(g.low_proj.mean()), 2), "low_own_mean": round(float(g.low_own.mean()), 2),
                        "game_share_mean": round(float(g.game_share.mean()), 3)}
        for flag in ("a", "b"):
            yes = x[x[flag]]; no = x[~x[flag]]
            p1, l1, h1 = wilson(int(yes.top1.sum()), len(yes)); p0, l0, h0 = wilson(int(no.top1.sum()), len(no))
            res[f"top1_rate_{flag}"] = {"contrarian": [round(p1 * 100, 3), round(l1 * 100, 3), round(h1 * 100, 3), int(len(yes))],
                                        "other": [round(p0 * 100, 3), round(l0 * 100, 3), round(h0 * 100, 3), int(len(no))],
                                        "ratio": round(float(p1 / p0), 3) if p0 else None}
        out[f"W{w}"] = res
    X = pd.concat(allrows, ignore_index=True)
    # heavy portfolios
    uw = X.groupby(["week", "user"]).agg(n=("rank", "size"), best=("rank", "min"), pct=("rank", lambda r: 0), a=("a", "mean"), b=("b", "mean"),
                                           top1=("top1", "sum"))
    uw["mean_pct"] = X.assign(p=X["rank"] / X.n_field * 100).groupby(["week", "user"]).p.mean()
    uw = uw.reset_index()
    heavy = uw[uw.n >= 20]
    top = heavy[heavy.best <= 100]; mid_pool = heavy[(heavy.mean_pct.between(35, 65)) & (heavy.best > 1000)]
    used, mid_rows = set(), []
    for _, r in top.sort_values("n", ascending=False).iterrows():
        c = mid_pool[(mid_pool.week == r.week) & (~mid_pool.index.isin(used))]
        if len(c):
            j = (c.n - r.n).abs().idxmin(); used.add(j); mid_rows.append(j)
    mid = mid_pool.loc[mid_rows]
    def dist(g, col):
        v = g[col]
        return {"n": int(len(v)), "mean": round(float(v.mean()), 3), "median": round(float(v.median()), 3),
                "share_users_5_to_15pct": round(float(v.between(0.05, 0.15).mean()), 3), "share_users_0": round(float((v == 0).mean()), 3),
                "p90": round(float(v.quantile(0.9)), 3)}
    out["portfolios"] = {grp: {"a": dist(g, "a"), "b": dist(g, "b")} for grp, g in (("top100", top), ("matched_mid", mid), ("all_heavy", heavy))}
    # stability: users heavy in two weeks
    stab = {}
    for (w1, w2) in ((1, 2), (2, 3), (1, 3)):
        A = heavy[heavy.week == w1].set_index("user"); B = heavy[heavy.week == w2].set_index("user")
        cu = A.index.intersection(B.index)
        stab[f"W{w1}->W{w2}"] = {"users": int(len(cu)), **{f"spearman_{f}": round(float(spearmanr(A.loc[cu, f], B.loc[cu, f])[0]), 3) for f in ("a", "b")},
                                 "both_weeks_5_15pct_a": round(float((A.loc[cu, "a"].between(.05, .15) & B.loc[cu, "a"].between(.05, .15)).mean()), 3)}
    out["stability"] = stab
    # attribution: are heavy users' top-1% rows contrarian more often than their rows are?
    H = X.merge(heavy[["week", "user"]], on=["week", "user"])
    att = {}
    for grp, users in (("top100", top), ("all_heavy", heavy)):
        G = H.merge(users[["week", "user"]], on=["week", "user"])
        per = G.groupby(["week", "user"]).agg(n=("rank", "size"), t=("top1", "sum"), a=("a", "mean"), b=("b", "mean"),
                                               ta=("a", lambda s: 0), tb=("b", lambda s: 0))
        ta = G[G.top1].groupby(["week", "user"]).a.sum(); tb = G[G.top1].groupby(["week", "user"]).b.sum()
        per["ta"] = ta.reindex(per.index).fillna(0); per["tb"] = tb.reindex(per.index).fillna(0)
        per = per[per.t > 0]
        res = {"user_weeks_with_top1": int(len(per)), "top1_rows": int(per.t.sum())}
        for f in ("a", "b"):
            obs = per[f"t{f}"].to_numpy(float); exp = (per[f] * per.t).to_numpy(float)
            ratio = obs.sum() / max(exp.sum(), 1e-9)
            bs = []
            for _ in range(2000):
                i = rng.integers(0, len(per), len(per)); bs.append(obs[i].sum() / max(exp[i].sum(), 1e-9))
            res[f] = {"observed": int(obs.sum()), "expected": round(float(exp.sum()), 1), "ratio": round(float(ratio), 3),
                      "ci90": [round(float(np.percentile(bs, 5)), 3), round(float(np.percentile(bs, 95)), 3)]}
        att[grp] = res
    out["attribution"] = att
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
