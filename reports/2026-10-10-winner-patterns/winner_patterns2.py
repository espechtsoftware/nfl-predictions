"""Second screen (2026-10-10): the ownership join FIXED (SUM of pct_drafted over a player's roster-position rows), so chalk
counts, ownership sums, the ownership product (duplication) and 'hot and chalky' can be read; hot players by position;
exact copies per lineup; and how the regulars DEAL: for users with 20+ Millionaire entries who also entered a priority
contest (4444 / 555 / 333 / FFWC) the same week, where their priority-contest lineup sits inside their own Millionaire book
(projection percentile, ownership percentile, an exact copy or not). Aggregates only; users fingerprinted server-side."""
import csv, json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery

OUT = Path(__file__).resolve().parent / "winner_patterns2_out"; OUT.mkdir(exist_ok=True)
BQ = bigquery.Client(project="nfl-predictions-503414")
CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
OURS = pd.read_csv(CFG["entry_history"], dtype=str)["Entry_Key"].dropna().astype(str).str.strip().tolist()
PRI = {}
with open(Path.home() / "private/regulars-share/shark_share_by_contest.csv") as h:
    for r in csv.DictReader(h):
        if any(k in r["type"] for k in ("FFWC", "$4,444", "$555", "$333")):
            PRI[r["contest_id"]] = r["type"]
log = open(OUT / "run.log", "w")
def say(*a): print(*a, flush=True); print(*a, file=log, flush=True)

def hot_flags(fr, w):
    """study 65 / 109's flag: the last game is this season's; prior = up to 4 games before it (this + previous season); >= 2
    prior; last >= 2.0 x max(mean, 5)."""
    ids = fr.gsis_id.dropna().astype(str).unique().tolist()
    a = BQ.query("""SELECT gsis_id, season, week, dk_points FROM `nfl_features.player_week_actuals`
                    WHERE gsis_id IN UNNEST(@ids) AND has_stat_line AND ((season = 2025) OR (season = 2026 AND week < @w))
                    ORDER BY gsis_id, season, week""",
                 job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", ids),
                                                                       bigquery.ScalarQueryParameter("w", "INT64", w)])).to_dataframe()
    out = {}
    for gid, g in a.groupby("gsis_id"):
        pts = g.dk_points.astype(float).tolist(); seasons = g.season.astype(int).tolist()
        if seasons[-1] == 2026 and len(pts) >= 3:
            last, prior = pts[-1], pts[-5:-1]
            out[gid] = int(last >= 2.0 * max(float(np.mean(prior)), 5.0))
    return out

SQL = """WITH m AS (SELECT n, s, p, t, o, pr, ow, vp, pk, h FROM UNNEST(@names) n WITH OFFSET i
  JOIN UNNEST(@sal) s WITH OFFSET j ON i=j JOIN UNNEST(@pos) p WITH OFFSET k ON i=k
  JOIN UNNEST(@team) t WITH OFFSET a ON i=a JOIN UNNEST(@opp) o WITH OFFSET b ON i=b
  JOIN UNNEST(@proj) pr WITH OFFSET d ON i=d JOIN UNNEST(@own) ow WITH OFFSET e2 ON i=e2
  JOIN UNNEST(@vpct) vp WITH OFFSET f ON i=f JOIN UNNEST(@prank) pk WITH OFFSET g ON i=g JOIN UNNEST(@hot) h WITH OFFSET q ON i=q),
e0 AS (SELECT DISTINCT contest_id, entry_id, rank, points, FARM_FINGERPRINT(TRIM(SPLIT(entry_name,' (')[OFFSET(0)])) u, players_key,
              FARM_FINGERPRINT(players_key) lk, entry_id IN UNNEST(@ours) ours
       FROM `nfl_raw.contest_entries` WHERE season=2026 AND week=@w AND contest_id IN UNNEST(@cids) AND points IS NOT NULL),
e AS (SELECT *, COUNT(*) OVER (PARTITION BY contest_id) cnt, COUNT(*) OVER (PARTITION BY contest_id, lk) copies FROM e0),
x AS (SELECT e.contest_id, e.entry_id, e.u, e.lk, e.ours, ANY_VALUE(e.rank) rank, ANY_VALUE(e.cnt) cnt, ANY_VALUE(e.copies) copies, ANY_VALUE(e.points) points,
             ARRAY_AGG(STRUCT(m.s, m.p, m.t, m.o, m.pr, m.ow, m.vp, m.pk, m.h)) pl, COUNT(m.n) matched
      FROM e, UNNEST(SPLIT(e.players_key,'|')) nm LEFT JOIN m ON m.n = nm GROUP BY 1,2,3,4,5),
y AS (SELECT * FROM x WHERE matched = 9)
SELECT contest_id, entry_id, u, lk, ours, rank, cnt, copies, points,
 (SELECT SUM(z.pr) FROM UNNEST(pl) z) proj,
 (SELECT SUM(z.ow) FROM UNNEST(pl) z) own_sum,
 (SELECT SUM(LN(GREATEST(z.ow, 0.2) / 100)) FROM UNNEST(pl) z) log_own_prod,
 (SELECT COUNTIF(z.ow >= 20) FROM UNNEST(pl) z) n_chalk20,
 (SELECT COUNTIF(z.ow >= 15) FROM UNNEST(pl) z) n_chalk15,
 (SELECT COUNTIF(z.ow < 5 AND z.p != 'DST') FROM UNNEST(pl) z) n_sub5,
 (SELECT COUNTIF(z.ow < 3 AND z.p != 'DST') FROM UNNEST(pl) z) n_sub3,
 (SELECT MAX(z.ow) FROM UNNEST(pl) z) max_own,
 (SELECT COUNTIF(z.h = 1) FROM UNNEST(pl) z) n_hot,
 (SELECT COUNTIF(z.h = 1 AND z.p = 'QB') FROM UNNEST(pl) z) hot_qb,
 (SELECT COUNTIF(z.h = 1 AND z.p = 'RB') FROM UNNEST(pl) z) hot_rb,
 (SELECT COUNTIF(z.h = 1 AND z.p = 'WR') FROM UNNEST(pl) z) hot_wr,
 (SELECT COUNTIF(z.h = 1 AND z.p = 'TE') FROM UNNEST(pl) z) hot_te,
 (SELECT COUNTIF(z.h = 1 AND z.ow >= 10) FROM UNNEST(pl) z) hot_chalk,
 (SELECT COUNTIF(z.h = 1 AND z.ow < 10) FROM UNNEST(pl) z) hot_quiet,
 (SELECT COUNTIF(z.vp >= 0.9 AND z.p != 'DST') FROM UNNEST(pl) z) n_topval,
 (SELECT MIN(z.pk) FROM UNNEST(pl) z WHERE z.p = 'QB') qb_prank,
 (SELECT ANY_VALUE(z.ow) FROM UNNEST(pl) z WHERE z.p = 'QB') qb_own,
 (SELECT COUNTIF(z.s >= 8000 AND z.p != 'DST') FROM UNNEST(pl) z) n_star,
 (SELECT COUNTIF(z.s < 4000 AND z.p != 'DST') FROM UNNEST(pl) z) n_cheap,
 (SELECT STDDEV_POP(z.s) FROM UNNEST(pl) z WHERE z.p != 'DST') sal_sd
FROM y"""

frames = []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name").copy()
    fr["salary"] = pd.to_numeric(fr.salary).astype(int)
    fr["proj"] = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0)
    skill = fr.pos.isin(["QB", "RB", "WR", "TE"]) & (fr.proj >= 3)
    fr["vpct"] = 0.0
    fr.loc[skill, "vpct"] = (fr.loc[skill, "proj"] / fr.loc[skill, "salary"]).groupby(fr.loc[skill, "pos"]).rank(pct=True)
    fr["prank"] = fr.groupby("pos").proj.rank(ascending=False, method="min")
    fr["hot"] = fr.gsis_id.astype(str).map(hot_flags(fr, w)).fillna(0).astype(int)
    milly = CFG["weeks"][str(w)]["millionaire_contest"]
    own = BQ.query(f"SELECT display_name, SUM(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{milly}' GROUP BY 1").to_dataframe()
    om = dict(zip(own.display_name, pd.to_numeric(own.own, errors="coerce").fillna(0.0)))
    matched = sum(1 for n in fr.display_name if n in om)
    cs = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1").to_dataframe()
    pri = cs[cs.contest_id.astype(str).isin(PRI)].contest_id.astype(str).tolist()
    say(f"W{w}: frame {len(fr)}; ownership rows {len(own)}, frame names matched {matched}; hot players {int(fr.hot.sum())}; priority contests {len(pri)}")
    params = [bigquery.ScalarQueryParameter("w", "INT64", w), bigquery.ArrayQueryParameter("ours", "STRING", OURS),
              bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()),
              bigquery.ArrayQueryParameter("sal", "INT64", fr.salary.tolist()), bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()),
              bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()), bigquery.ArrayQueryParameter("opp", "STRING", fr.opp.astype(str).tolist()),
              bigquery.ArrayQueryParameter("proj", "FLOAT64", fr.proj.astype(float).tolist()),
              bigquery.ArrayQueryParameter("own", "FLOAT64", [float(om.get(n, 0.0)) for n in fr.display_name]),
              bigquery.ArrayQueryParameter("vpct", "FLOAT64", fr.vpct.astype(float).tolist()), bigquery.ArrayQueryParameter("prank", "FLOAT64", fr.prank.astype(float).tolist()),
              bigquery.ArrayQueryParameter("hot", "INT64", fr.hot.tolist())]
    for kind, cids in (("milly", [milly]), ("priority", pri)):
        if not cids: continue
        d = BQ.query(SQL, job_config=bigquery.QueryJobConfig(query_parameters=params + [bigquery.ArrayQueryParameter("cids", "STRING", cids)])).to_dataframe()
        d["week"] = w; d["kind"] = kind; frames.append(d)
        say(f"  {kind}: {len(d):,} lineups; ours {int(d.ours.sum())}; mean own_sum {pd.to_numeric(d.own_sum).mean():.1f}")
D = pd.concat(frames, ignore_index=True)
for c in D.columns:
    if c not in ("contest_id", "entry_id", "kind", "ours", "u", "lk"):
        D[c] = pd.to_numeric(D[c], errors="coerce")
D["pct"] = D["rank"] / D["cnt"]; D["uw"] = D.week.astype(str) + "|" + D.u.astype(str)
D["exp_copies"] = np.exp(D.log_own_prod) * D.cnt          # expected copies in the contest from the ownership product
D["dup"] = (D.copies >= 2).astype(int)
D.drop(columns=["entry_id"]).to_parquet(OUT / "lineups2.parquet")

pd.set_option("display.width", 320); pd.set_option("display.max_columns", 60); pd.set_option("display.max_rows", 300)
FE = ["proj", "points", "own_sum", "max_own", "n_chalk20", "n_chalk15", "n_sub5", "n_sub3", "log_own_prod", "exp_copies", "dup", "copies",
      "n_hot", "hot_qb", "hot_rb", "hot_wr", "hot_te", "hot_chalk", "hot_quiet", "n_topval", "qb_prank", "qb_own", "n_star", "n_cheap", "sal_sd"]
def gt(X, groups):
    rows = []
    for name, mask in groups.items():
        g = X[mask]; r = {"group": name, "n": len(g)}
        for f in FE: r[f] = round(float(g[f].mean()), 3) if len(g) else np.nan
        rows.append(r)
    return pd.DataFrame(rows).set_index("group").T

M = D[D.kind == "milly"].copy()
say("\n=== MILLIONAIRE by week: field / top 1% / top 0.1% / OURS (ownership realized, SUM over roster rows) ===")
for w, X in M.groupby("week"):
    say(f"-- W{w}"); say(gt(X, {"field": X.pct <= 1, "top 1%": X.pct <= 0.01, "top 0.1%": X.pct <= 0.001, "OURS": X.ours}).to_string())
P = D[D.kind == "priority"].copy(); P["top3"] = P["rank"] <= 3
say("\n=== PRIORITY CONTESTS pooled and by week: field / top 2% / top 3 / OURS ===")
say(gt(P, {"field": P.pct <= 1, "top 2%": P.pct <= 0.02, "top 3": P.top3, "OURS": P.ours}).to_string())
for w, X in P.groupby("week"):
    say(f"-- W{w}"); say(gt(X, {"field": X.pct <= 1, "top 2%": X.pct <= 0.02, "top 3": X["rank"] <= 3, "OURS": X.ours}).loc[["n", "own_sum", "n_chalk20", "n_sub5", "exp_copies", "dup", "n_hot", "hot_chalk", "hot_quiet", "qb_own", "proj", "points"]].to_string())

def mh(X, ex, ref, out, strat="uw"):
    Z = X[ex | ref].assign(E=ex[ex | ref].astype(int), o=X.loc[ex | ref, out].astype(int))
    g = Z.groupby([strat, "E"]).o.agg(["size", "sum"]).reset_index()
    s = g.pivot_table(index=strat, columns="E", values=["size", "sum"], fill_value=0)
    for col in (("size", 0), ("size", 1), ("sum", 0), ("sum", 1)):
        if col not in s.columns: s[col] = 0
    a = s[("sum", 1)]; b = s[("size", 1)] - a; c = s[("sum", 0)]; d_ = s[("size", 0)] - c; n = a + b + c + d_
    num = (a * d_ / n.replace(0, np.nan)).fillna(0); den = (b * c / n.replace(0, np.nan)).fillna(0)
    return num.sum() / den.sum() if den.sum() > 0 else np.nan
EXPO = {
    "2+ chalk (>= 20% owned) vs <= 1": lambda X: (X.n_chalk20 >= 2, X.n_chalk20 <= 1),
    "0 chalk (>= 20%) vs 1+": lambda X: (X.n_chalk20 == 0, X.n_chalk20 >= 1),
    "3+ sub-5% skill vs <= 1": lambda X: (X.n_sub5 >= 3, X.n_sub5 <= 1),
    "2+ sub-3% skill vs 0": lambda X: (X.n_sub3 >= 2, X.n_sub3 == 0),
    "0 sub-3% vs 1": lambda X: (X.n_sub3 == 0, X.n_sub3 == 1),
    "ownership sum above own median (chalkier)": lambda X: (X.own_sum > X.groupby("uw").own_sum.transform("median"), X.own_sum <= X.groupby("uw").own_sum.transform("median")),
    "ownership sum >= 130 vs < 100": lambda X: (X.own_sum >= 130, X.own_sum < 100),
    "expected copies >= 1 vs < 0.2": lambda X: (X.exp_copies >= 1, X.exp_copies < 0.2),
    "an exact copy exists vs unique": lambda X: (X.dup == 1, X.dup == 0),
    "QB owned >= 15% vs < 5%": lambda X: (X.qb_own >= 15, X.qb_own < 5),
    "1+ hot RB vs 0": lambda X: (X.hot_rb >= 1, X.hot_rb == 0),
    "1+ hot WR/TE vs 0": lambda X: ((X.hot_wr + X.hot_te) >= 1, (X.hot_wr + X.hot_te) == 0),
    "1+ hot QB vs 0": lambda X: (X.hot_qb >= 1, X.hot_qb == 0),
    "1+ hot & chalky (>= 10% owned) vs 0 hot": lambda X: (X.hot_chalk >= 1, X.n_hot == 0),
    "1+ hot & quiet (< 10% owned) vs 0 hot": lambda X: ((X.hot_quiet >= 1) & (X.hot_chalk == 0), X.n_hot == 0),
    "QB rank 9+ vs rank 1-3": lambda X: (X.qb_prank >= 9, X.qb_prank <= 3),
    "QB rank 4-8 vs rank 1-3": lambda X: ((X.qb_prank >= 4) & (X.qb_prank <= 8), X.qb_prank <= 3),
}
def mh_table(X, outs, label, strat="uw"):
    rows = []
    for name, fn in EXPO.items():
        ex, ref = fn(X); ex = ex.fillna(False).astype(bool); ref = ref.fillna(False).astype(bool)
        r = {"feature (vs reference)": name}
        for oname, mask in outs.items():
            X["_o"] = mask.astype(int); r[oname] = round(mh(X, ex, ref, "_o", strat), 2)
        wk = []
        for w, Xw in X.groupby("week"):
            exw, refw = fn(Xw); exw = exw.fillna(False).astype(bool); refw = refw.fillna(False).astype(bool)
            Xw = Xw.copy(); Xw["_o"] = list(outs.values())[0][Xw.index].astype(int)
            e = mh(Xw, exw, refw, "_o", strat); wk.append(f"{e:.2f}" if e == e else "nan")
        r[f"{list(outs)[0]} by week"] = "/".join(wk); r["exposed share"] = round(float(ex[ex | ref].mean()), 3) if (ex | ref).sum() else np.nan
        rows.append(r)
    T = pd.DataFrame(rows); say(f"\n=== {label} ==="); say(T.to_string(index=False)); return T
MM = M[M.groupby("uw").uw.transform("size") >= 20].copy()
mh_table(MM, {"top 1%": MM.pct <= 0.01, "top 4%": MM.pct <= 0.04, "top 10%": MM.pct <= 0.10}, "MILLIONAIRE within user-week (20+ entries)").to_csv(OUT / "milly_mh2.csv", index=False)
P["cw"] = P.contest_id.astype(str)
mh_table(P, {"top 2%": P.pct <= 0.02, "top 5%": P.pct <= 0.05, "top 10%": P.pct <= 0.10}, "PRIORITY by contest", strat="cw").to_csv(OUT / "priority_mh2.csv", index=False)

# ---- how the regulars deal: the same user's priority-contest lineup inside his own Millionaire book --------------------
say("\n=== DEALING: users with 20+ Millionaire entries who also entered a priority contest the same week ===")
rows = []
for w in sorted(D.week.unique()):
    Mw = M[(M.week == w)]; Pw = P[P.week == w]
    big_users = set(Mw.groupby("u").u.transform("size")[lambda s: s >= 20].index.map(lambda i: Mw.u[i]))
    big_users = set(Mw[Mw.groupby("u").u.transform("size") >= 20].u)
    both = Pw[Pw.u.isin(big_users)]
    if both.empty: say(f"W{w}: none"); continue
    for _, r in both.iterrows():
        book = Mw[Mw.u == r.u]
        rows.append({"week": w, "u": r.u, "pri_rank_pct": r.pct, "pri_top3": int(r["rank"] <= 3), "pri_top10pct": int(r.pct <= 0.10),
                     "copy_of_milly_row": int((book.lk == r.lk).any()),
                     "proj_pctile_in_book": float((book.proj < r.proj).mean()), "own_pctile_in_book": float((book.own_sum < r.own_sum).mean()),
                     "copies_pctile_in_book": float((book.exp_copies < r.exp_copies).mean()),
                     "proj_minus_book_mean": float(r.proj - book.proj.mean()), "own_minus_book_mean": float(r.own_sum - book.own_sum.mean()),
                     "book_n": len(book), "pri_proj": r.proj, "pri_own": r.own_sum, "pri_exp_copies": r.exp_copies, "pri_stars": r.n_star, "pri_hot": r.n_hot})
R = pd.DataFrame(rows)
if len(R):
    say(f"priority-contest lineups by multi-entry Millionaire users: {len(R)} (users {R.u.nunique()}), weeks {sorted(R.week.unique())}")
    say("mean over those lineups:"); say(R.drop(columns=["u"]).mean(numeric_only=True).round(3).to_string())
    say("by week:"); say(R.groupby("week")[["copy_of_milly_row", "proj_pctile_in_book", "own_pctile_in_book", "copies_pctile_in_book", "proj_minus_book_mean", "own_minus_book_mean"]].mean().round(3).to_string())
    say("the ones that finished top 3 vs the rest:"); say(R.groupby("pri_top3")[["copy_of_milly_row", "proj_pctile_in_book", "own_pctile_in_book", "copies_pctile_in_book", "pri_exp_copies", "pri_stars", "pri_hot"]].mean().round(3).to_string())
    say("the ones that finished top 10% vs the rest:"); say(R.groupby("pri_top10pct")[["copy_of_milly_row", "proj_pctile_in_book", "own_pctile_in_book", "copies_pctile_in_book", "pri_exp_copies"]].mean().round(3).to_string())
    say("distribution of proj_pctile_in_book (where in his own book the satellite lineup sits by projection):")
    say(pd.cut(R.proj_pctile_in_book, [-0.01, 0.2, 0.4, 0.6, 0.8, 1.0]).value_counts().sort_index().to_string())
# duplication of OUR entries vs the top finishers
say("\n=== DUPLICATION: exact copies in the contest (share of lineups with >= 2 copies) ===")
for kind, X in (("milly", M), ("priority", P)):
    for name, mask in {"field": X.pct <= 1, "top 1%": X.pct <= 0.01, "top 3": X["rank"] <= 3, "OURS": X.ours}.items():
        g = X[mask]
        if len(g): say(f"{kind:>8} {name:>7}: n {len(g):>8,}  dup share {float(g.dup.mean()):.3f}  mean copies {g.copies.mean():.2f}  mean exp_copies {g.exp_copies.mean():.2f}  own_sum {g.own_sum.mean():.1f}")
say("done")
