"""Within the regulars' own portfolios (the Milly graph, W1-4): do their top-1% lineups differ BEFORE LOCK from the same
user's other lineups that week? For every user-week with >= 20 lineups and >= 1 top-1% lineup, each lineup-level pre-lock
feature is standardized within the user-week; the mean of the standardized value over the top-1% lineups is the
within-portfolio difference (0 = indistinguishable). 95% interval by bootstrap over user-weeks; sign per week."""
import numpy as np, pandas as pd
from gconn import driver
d = driver()
Q = """MATCH (u:User)-[:ENTERED]->(l:Lineup {week_key: $wk})
WITH u, collect(l) AS ls WHERE size(ls) >= 20 AND any(x IN ls WHERE x.rank_top_1pct)
UNWIND ls AS l
MATCH (l)-[:CONTAINS]->(p:Player)-[:HAS_WEEK]->(pw:PlayerWeek)-[:OF_WEEK]->(:Week {key: $wk})
RETURN u.name AS user, l.key AS lk, l.rank_top_1pct AS top1, l.points AS pts, l.salary AS sal, l.stack AS stack, l.bring_back AS bb,
       l.lbl_qb_game_rank AS qb_game_rank, l.lbl_qb_favourite AS qb_fav, l.lbl_top_game_players AS top_game_players, l.lbl_dual_stack AS dual,
       l.lbl_games AS games, l.lbl_cheap_players AS cheap, l.lbl_salary_left AS sal_left, l.lbl_te_salary AS te_sal, l.lbl_qb_salary AS qb_sal, l.lbl_dst_salary AS dst_sal,
       p.position AS pos, pw.pre_mean_projection AS proj, pw.pre_market_points AS mkt, pw.pre_anytime_td_prob AS td, pw.pre_prior_top1_share AS prior_top,
       pw.pre_rz20_targets_l4 AS rz, pw.pre_ez_targets_l4 AS ez, pw.pre_gl3_carries_l4 AS gl, pw.pre_tds_l4 AS tds4, pw.pre_target_share_l4 AS tsh,
       pw.pre_team_vacated_target_share AS vt, pw.pre_team_vacated_carry_share AS vc, pw.pre_snap_share_l4 AS snap, pw.pre_implied_team_total AS itt,
       pw.pre_salary AS psal, pw.pre_dk_points_std AS vol, pw.pre_fp_route_share_jump AS rjump"""
frames = []
with d.session() as s:
    for wk in sorted(s.run("MATCH (w:Week) RETURN w.key AS k").value()):
        df = pd.DataFrame(s.run(Q, wk=wk).data()); df["week"] = wk; frames.append(df); print(wk, len(df), flush=True)
d.close()
P = pd.concat(frames, ignore_index=True)
P["skill"] = P.pos.isin(["RB", "WR", "TE"])
for c in ("proj", "mkt", "td", "prior_top", "rz", "ez", "gl", "tds4", "tsh", "vt", "vc", "snap", "itt", "psal", "vol", "rjump"):
    P[c] = pd.to_numeric(P[c], errors="coerce")
P["mkt_f"] = P.mkt.fillna(P.proj)
g = P.groupby(["week", "user", "lk"])
L = g.agg(top1=("top1", "first"), pts=("pts", "first"), stack=("stack", "first"), bb=("bb", "first"), qb_game_rank=("qb_game_rank", "first"), qb_fav=("qb_fav", "first"),
          top_game_players=("top_game_players", "first"), dual=("dual", "first"), games=("games", "first"), cheap=("cheap", "first"), sal_left=("sal_left", "first"),
          te_sal=("te_sal", "first"), qb_sal=("qb_sal", "first"), proj=("proj", "sum"), mkt=("mkt_f", "sum"), prior_top=("prior_top", "sum"), vol=("vol", "sum")).reset_index()
sk = P[P.skill].groupby(["week", "user", "lk"]).agg(td=("td", "sum"), rz=("rz", "sum"), ez=("ez", "sum"), gl=("gl", "sum"), tds4=("tds4", "sum"), tsh=("tsh", "mean"),
          vac=("vt", "sum"), vacc=("vc", "sum"), snap=("snap", "mean"), itt=("itt", "mean"), max_sal=("psal", "max"), rjump=("rjump", "mean")).reset_index()
L = L.merge(sk, on=["week", "user", "lk"], how="left")
L["mkt_minus_proj"] = L.mkt - L.proj
for c in ("qb_fav", "dual", "bb"):
    L[c] = L[c].astype(float)
feats = ["proj", "mkt", "mkt_minus_proj", "td", "prior_top", "rz", "ez", "gl", "tds4", "tsh", "vac", "vacc", "snap", "itt", "vol", "rjump",
         "stack", "bb", "dual", "games", "cheap", "sal_left", "te_sal", "qb_sal", "max_sal", "qb_game_rank", "qb_fav", "top_game_players"]
L["uw"] = L.week + "|" + L.user
print(f"\nuser-weeks {L.uw.nunique()}, lineups {len(L):,}, top-1% lineups {int(L.top1.sum())}")
rows = []
rng = np.random.default_rng(7)
uws = L.uw.unique()
for f in feats:
    x = pd.to_numeric(L[f], errors="coerce")
    z = (x - L.groupby("uw")[f].transform("mean")) / (x.groupby(L.uw).transform("std") + 1e-9)
    t = pd.DataFrame({"uw": L.uw, "week": L.week, "z": z, "top1": L.top1.astype(bool)}).dropna()
    per_uw = t[t.top1].groupby("uw").z.mean()
    est = per_uw.mean(); bs = [per_uw.loc[rng.choice(per_uw.index, len(per_uw))].mean() for _ in range(2000)]
    wk = t[t.top1].groupby("week").z.mean().round(2).to_dict()
    rows.append({"feature": f, "within_portfolio_diff_sd": round(est, 3), "lo": round(np.percentile(bs, 2.5), 3), "hi": round(np.percentile(bs, 97.5), 3), "by_week": wk, "n_uw": len(per_uw)})
R = pd.DataFrame(rows).sort_values("within_portfolio_diff_sd", key=abs, ascending=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 90)
print(R.to_string(index=False))
R.to_csv("within_portfolio.csv", index=False)
