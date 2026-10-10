"""Winner patterns not yet screened (2026-10-10): per-lineup pre-lock features on the W1-4 real fields.

Features (all from the T-70 frame, so pre-lock, except realized ownership used as the chalk measure as earlier screens did):
value-rank concentration (how many players sit in the top decile of projection per dollar within position), minimum
projection (whole lineup and per position), projection rank within position, last-game "hot" players (last game >= 2x /
1.6x the trailing average), late-window count, chalk / sub-5% counts, $8k+ stars, bring-back type (RB vs receiver),
QB+RB mates, games / teams used, salary dispersion, WR / RB spend.
Groups: the field, the top 1% / 0.1% (Millionaire), the top 3 per contest and top 2% (priority satellites), OURS.
Within-user Mantel-Haenszel odds ratios (users with 20+ entries) for the Millionaire; by-contest for the priority contests.
Server-side; user names fingerprinted; aggregates only. PRIVATE inputs stay on the laptop."""
import csv, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery

OUT = Path(__file__).resolve().parent / "winner_patterns_out"; OUT.mkdir(exist_ok=True)
BQ = bigquery.Client(project="nfl-predictions-503414")
CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
OURS = pd.read_csv(CFG["entry_history"], dtype=str)["Entry_Key"].dropna().astype(str).str.strip().tolist()
PRI = {}
with open(Path.home() / "private/regulars-share/shark_share_by_contest.csv") as h:
    for r in csv.DictReader(h):
        if any(k in r["type"] for k in ("FFWC", "$4,444", "$555", "$333")):
            PRI[r["contest_id"]] = r["type"]
log = open(OUT / "run.log", "w")
def say(*a):
    print(*a, flush=True); print(*a, file=log, flush=True)

def actuals_hot(fr, w):
    """last game's DK points vs the trailing average (up to 8 prior games across 2025-26, excluding the last), per gsis_id."""
    ids = fr.gsis_id.dropna().astype(str).unique().tolist()
    q = """SELECT gsis_id, season, week, dk_points FROM `nfl_features.player_week_actuals`
           WHERE gsis_id IN UNNEST(@ids) AND has_stat_line AND ((season = 2025) OR (season = 2026 AND week < @w)) ORDER BY gsis_id, season, week"""
    a = BQ.query(q, job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", ids),
                                                                          bigquery.ScalarQueryParameter("w", "INT64", w)])).to_dataframe()
    hot2, hot16 = {}, {}
    for gid, g in a.groupby("gsis_id"):
        pts = g.dk_points.astype(float).tolist()
        if len(pts) < 4: continue
        last, prior = pts[-1], pts[-9:-1]
        avg = float(np.mean(prior))
        if avg < 3: continue
        hot2[gid] = int(last >= 2.0 * avg); hot16[gid] = int(last >= 1.6 * avg)
    return hot2, hot16

SQL = """WITH m AS (SELECT n, s, p, t, o, g, pr, ow, vp, pk, lt, h2, h16 FROM UNNEST(@names) n WITH OFFSET i
  JOIN UNNEST(@sal) s WITH OFFSET j ON i=j JOIN UNNEST(@pos) p WITH OFFSET k ON i=k
  JOIN UNNEST(@team) t WITH OFFSET a ON i=a JOIN UNNEST(@opp) o WITH OFFSET b ON i=b
  JOIN UNNEST(@game) g WITH OFFSET c ON i=c JOIN UNNEST(@proj) pr WITH OFFSET d ON i=d
  JOIN UNNEST(@own) ow WITH OFFSET e2 ON i=e2 JOIN UNNEST(@vpct) vp WITH OFFSET f ON i=f
  JOIN UNNEST(@prank) pk WITH OFFSET h ON i=h JOIN UNNEST(@late) lt WITH OFFSET l ON i=l
  JOIN UNNEST(@hot2) h2 WITH OFFSET q ON i=q JOIN UNNEST(@hot16) h16 WITH OFFSET r ON i=r),
e0 AS (SELECT DISTINCT contest_id, entry_id, rank, points, FARM_FINGERPRINT(TRIM(SPLIT(entry_name,' (')[OFFSET(0)])) u, players_key,
              entry_id IN UNNEST(@ours) ours
       FROM `nfl_raw.contest_entries` WHERE season=2026 AND week=@w AND contest_id IN UNNEST(@cids) AND points IS NOT NULL),
e AS (SELECT *, COUNT(*) OVER (PARTITION BY contest_id) cnt FROM e0),
x AS (SELECT e.contest_id, e.entry_id, e.u, e.ours, ANY_VALUE(e.rank) rank, ANY_VALUE(e.cnt) cnt, ANY_VALUE(e.points) points,
             ARRAY_AGG(STRUCT(m.s, m.p, m.t, m.o, m.g, m.pr, m.ow, m.vp, m.pk, m.lt, m.h2, m.h16)) pl, COUNT(m.n) matched
      FROM e, UNNEST(SPLIT(e.players_key,'|')) nm LEFT JOIN m ON m.n = nm GROUP BY 1,2,3,4),
y AS (SELECT *, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p='QB') qbt, (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p='QB') qbo,
             (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p='DST') dt, (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p='DST') dop,
             (SELECT ANY_VALUE(z.s) FROM UNNEST(pl) z WHERE z.p='DST') dsts
      FROM x WHERE matched = 9)
SELECT contest_id, entry_id, u, ours, rank, cnt, points,
 (SELECT SUM(z.pr) FROM UNNEST(pl) z) proj,
 (SELECT SUM(z.ow) FROM UNNEST(pl) z) own_sum,
 (SELECT SUM(LN(GREATEST(z.ow, 0.1) / 100)) FROM UNNEST(pl) z) log_own_prod,
 (SELECT COUNTIF(z.ow >= 20) FROM UNNEST(pl) z) n_chalk20,
 (SELECT COUNTIF(z.ow < 5) FROM UNNEST(pl) z) n_sub5,
 (SELECT COUNT(DISTINCT z.g) FROM UNNEST(pl) z) n_games,
 (SELECT COUNT(DISTINCT z.t) FROM UNNEST(pl) z) n_teams,
 (SELECT COUNTIF(z.t = qbt AND z.p IN ('WR','TE')) FROM UNNEST(pl) z) mates_wrte,
 (SELECT COUNTIF(z.t = qbt AND z.p = 'RB') FROM UNNEST(pl) z) mates_rb,
 (SELECT COUNTIF(z.t = qbo AND z.p IN ('WR','TE')) FROM UNNEST(pl) z) bb_wrte,
 (SELECT COUNTIF(z.t = qbo AND z.p = 'RB') FROM UNNEST(pl) z) bb_rb,
 (SELECT COUNTIF(z.t = dop AND z.p != 'DST') FROM UNNEST(pl) z) dst_faces,
 (SELECT COUNTIF(z.t = dt AND z.p = 'RB') FROM UNNEST(pl) z) dst_rb,
 (SELECT COUNTIF(z.vp >= 0.9 AND z.p != 'DST') FROM UNNEST(pl) z) n_topval,
 (SELECT COUNTIF(z.vp >= 0.8 AND z.p != 'DST') FROM UNNEST(pl) z) n_val80,
 (SELECT COUNTIF(z.vp < 0.5 AND z.p != 'DST') FROM UNNEST(pl) z) n_lowval,
 (SELECT COUNTIF(z.pk <= 3 AND z.p != 'DST') FROM UNNEST(pl) z) n_prank3,
 (SELECT MIN(z.pk) FROM UNNEST(pl) z WHERE z.p = 'QB') qb_prank,
 (SELECT MIN(z.pr) FROM UNNEST(pl) z WHERE z.p != 'DST') min_proj,
 (SELECT MIN(z.pr) FROM UNNEST(pl) z WHERE z.p = 'RB') min_rb,
 (SELECT MIN(z.pr) FROM UNNEST(pl) z WHERE z.p = 'WR') min_wr,
 (SELECT MIN(z.pr) FROM UNNEST(pl) z WHERE z.p = 'TE') min_te,
 (SELECT MIN(z.pr) FROM UNNEST(pl) z WHERE z.p = 'QB') qb_proj,
 (SELECT COUNTIF(z.pr < 8 AND z.p != 'DST') FROM UNNEST(pl) z) n_under8,
 (SELECT COUNTIF(z.pr < 10 AND z.p != 'DST') FROM UNNEST(pl) z) n_under10,
 (SELECT COUNTIF(z.h2 = 1) FROM UNNEST(pl) z) n_hot2,
 (SELECT COUNTIF(z.h16 = 1) FROM UNNEST(pl) z) n_hot16,
 (SELECT COUNTIF(z.lt = 1) FROM UNNEST(pl) z) n_late,
 (SELECT COUNTIF(z.s >= 8000 AND z.p != 'DST') FROM UNNEST(pl) z) n_star,
 (SELECT COUNTIF(z.s < 4000 AND z.p != 'DST') FROM UNNEST(pl) z) n_cheap,
 (SELECT SUM(z.s) FROM UNNEST(pl) z WHERE z.p = 'WR') wr_spend,
 (SELECT SUM(z.s) FROM UNNEST(pl) z WHERE z.p = 'RB') rb_spend,
 (SELECT ANY_VALUE(z.s) FROM UNNEST(pl) z WHERE z.p = 'QB') qb_sal, dsts dst_sal,
 (SELECT STDDEV_POP(z.s) FROM UNNEST(pl) z WHERE z.p != 'DST') sal_sd,
 (SELECT SUM(z.s) FROM UNNEST(pl) z) sal_total,
 (SELECT COUNTIF(z.p = 'TE') FROM UNNEST(pl) z) n_te,
 (SELECT COUNTIF(z.p = 'RB') FROM UNNEST(pl) z) n_rb
FROM y"""

frames = []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name").copy()
    fr["salary"] = pd.to_numeric(fr.salary).astype(int)
    fr["proj"] = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0)
    skill = fr.pos.isin(["QB", "RB", "WR", "TE"]) & (fr.proj >= 3)
    fr["vpct"] = np.nan
    fr.loc[skill, "vpct"] = (fr.loc[skill, "proj"] / fr.loc[skill, "salary"]).groupby(fr.loc[skill, "pos"]).rank(pct=True)
    fr["vpct"] = fr.vpct.fillna(0.0)
    fr["prank"] = fr.groupby("pos").proj.rank(ascending=False, method="min")
    gs = pd.to_datetime(fr.game_start, utc=True)
    fr["late"] = (gs.dt.hour >= 20).astype(int)          # 16:00 ET or later
    hot2, hot16 = actuals_hot(fr, w)
    fr["hot2"] = fr.gsis_id.astype(str).map(hot2).fillna(0).astype(int)
    fr["hot16"] = fr.gsis_id.astype(str).map(hot16).fillna(0).astype(int)
    milly = CFG["weeks"][str(w)]["millionaire_contest"]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{milly}' GROUP BY 1").to_dataframe()
    om = dict(zip(own.display_name, pd.to_numeric(own.own, errors="coerce").fillna(0.0)))
    cs = BQ.query(f"SELECT contest_id, ANY_VALUE(contest_name) nm, COUNT(DISTINCT entry_id) n FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1").to_dataframe()
    pri = cs[cs.contest_id.astype(str).isin(PRI)].contest_id.astype(str).tolist()
    say(f"W{w}: frame {len(fr)} players; hot2 {int(fr.hot2.sum())} hot16 {int(fr.hot16.sum())} late {int(fr.late.sum())}; priority contests {len(pri)}")
    params = [bigquery.ScalarQueryParameter("w", "INT64", w), bigquery.ArrayQueryParameter("ours", "STRING", OURS),
              bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()),
              bigquery.ArrayQueryParameter("sal", "INT64", fr.salary.tolist()), bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()),
              bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()), bigquery.ArrayQueryParameter("opp", "STRING", fr.opp.astype(str).tolist()),
              bigquery.ArrayQueryParameter("game", "STRING", fr.game_id.astype(str).tolist()), bigquery.ArrayQueryParameter("proj", "FLOAT64", fr.proj.astype(float).tolist()),
              bigquery.ArrayQueryParameter("own", "FLOAT64", [float(om.get(n, 0.0)) for n in fr.display_name]),
              bigquery.ArrayQueryParameter("vpct", "FLOAT64", fr.vpct.astype(float).tolist()), bigquery.ArrayQueryParameter("prank", "FLOAT64", fr.prank.astype(float).tolist()),
              bigquery.ArrayQueryParameter("late", "INT64", fr.late.tolist()), bigquery.ArrayQueryParameter("hot2", "INT64", fr.hot2.tolist()),
              bigquery.ArrayQueryParameter("hot16", "INT64", fr.hot16.tolist())]
    for kind, cids in (("milly", [milly]), ("priority", pri)):
        if not cids: continue
        d = BQ.query(SQL, job_config=bigquery.QueryJobConfig(query_parameters=params + [bigquery.ArrayQueryParameter("cids", "STRING", cids)])).to_dataframe()
        d["week"] = w; d["kind"] = kind; frames.append(d)
        say(f"  {kind}: {len(d):,} lineups with 9 matched players; ours {int(d.ours.sum())}; contests {d.contest_id.nunique()}")
D = pd.concat(frames, ignore_index=True)
for c in D.columns:
    if c not in ("contest_id", "entry_id", "kind", "ours", "u"):
        D[c] = pd.to_numeric(D[c], errors="coerce")
D["pct"] = D["rank"] / D["cnt"]
D["bb_type"] = np.select([(D.bb_wrte >= 1), (D.bb_rb >= 1) & (D.bb_wrte == 0)], ["receiver", "rb_only"], "none")
D.drop(columns=["entry_id"]).to_parquet(OUT / "lineups.parquet")      # local only (fingerprinted users; no names)

FEATS = ["proj", "points", "own_sum", "log_own_prod", "n_chalk20", "n_sub5", "n_games", "n_teams", "mates_wrte", "mates_rb", "bb_wrte", "bb_rb",
         "dst_faces", "dst_rb", "n_topval", "n_val80", "n_lowval", "n_prank3", "qb_prank", "min_proj", "min_rb", "min_wr", "min_te", "qb_proj",
         "n_under8", "n_under10", "n_hot2", "n_hot16", "n_late", "n_star", "n_cheap", "wr_spend", "rb_spend", "qb_sal", "dst_sal", "sal_sd", "sal_total", "n_te", "n_rb"]

def group_table(X, groups):
    rows = []
    for name, mask in groups.items():
        g = X[mask]
        r = {"group": name, "lineups": len(g)}
        for f in FEATS: r[f] = round(float(g[f].mean()), 3) if len(g) else np.nan
        r["bb_rb_only_share"] = round(float((g.bb_type == "rb_only").mean()), 3) if len(g) else np.nan
        r["bb_receiver_share"] = round(float((g.bb_type == "receiver").mean()), 3) if len(g) else np.nan
        r["min_proj<8 share"] = round(float((g.min_proj < 8).mean()), 3) if len(g) else np.nan
        r["min_proj<10 share"] = round(float((g.min_proj < 10).mean()), 3) if len(g) else np.nan
        r["hot2>=1 share"] = round(float((g.n_hot2 >= 1).mean()), 3) if len(g) else np.nan
        r["topval>=3 share"] = round(float((g.n_topval >= 3).mean()), 3) if len(g) else np.nan
        r["star>=1 share"] = round(float((g.n_star >= 1).mean()), 3) if len(g) else np.nan
        rows.append(r)
    return pd.DataFrame(rows)

pd.set_option("display.width", 320); pd.set_option("display.max_columns", 80); pd.set_option("display.max_rows", 200)
M = D[D.kind == "milly"].copy()
say("\n=== MILLIONAIRE, W1-4 pooled: group means (pre-lock features; ownership realized) ===")
G = group_table(M, {"field": M.pct <= 1.0, "top 10%": M.pct <= 0.10, "top 1%": M.pct <= 0.01, "top 0.1%": M.pct <= 0.001, "top 100": M["rank"] <= 100, "OURS": M.ours})
say(G.set_index("group").T.to_string())
G.to_csv(OUT / "milly_groups.csv", index=False)
say("\n=== MILLIONAIRE by week: top 1% vs field vs ours (selected) ===")
sel = ["n_topval", "n_val80", "n_prank3", "min_proj", "n_under8", "n_hot2", "n_hot16", "n_late", "n_star", "n_chalk20", "n_sub5", "n_games", "mates_rb", "sal_sd", "wr_spend", "qb_prank", "proj", "points"]
for w, X in M.groupby("week"):
    t = group_table(X, {"field": X.pct <= 1.0, "top 1%": X.pct <= 0.01, "OURS": X.ours})[["group", "lineups"] + sel]
    say(f"-- W{w}"); say(t.set_index("group").T.to_string())
    t.assign(week=w).to_csv(OUT / f"milly_groups_w{w}.csv", index=False)
say("\n=== MILLIONAIRE: bring-back type among lineups with a bring-back (share) ===")
for name, mask in {"field": M.pct <= 1.0, "top 1%": M.pct <= 0.01, "top 0.1%": M.pct <= 0.001, "OURS": M.ours}.items():
    g = M[mask & (M.bb_type != "none")]
    say(f"{name:>9}: n {len(g):>7,}  receiver bring-back {float((g.bb_type=='receiver').mean()):.3f}  RB-only {float((g.bb_type=='rb_only').mean()):.3f}")

P = D[D.kind == "priority"].copy()
if len(P):
    say("\n=== PRIORITY CONTESTS (4444 / 555 / 333 / FFWC), W1-4 pooled: group means ===")
    P["top3"] = P["rank"] <= 3
    GP = group_table(P, {"field": P.pct <= 1.0, "top 10%": P.pct <= 0.10, "top 2%": P.pct <= 0.02, "top 3 per contest": P.top3, "OURS": P.ours})
    say(GP.set_index("group").T.to_string()); GP.to_csv(OUT / "priority_groups.csv", index=False)
    say("\n=== PRIORITY: bring-back type among lineups with a bring-back ===")
    for name, mask in {"field": P.pct <= 1.0, "top 2%": P.pct <= 0.02, "top 3": P.top3, "OURS": P.ours}.items():
        g = P[mask & (P.bb_type != "none")]
        say(f"{name:>9}: n {len(g):>7,}  receiver bring-back {float((g.bb_type=='receiver').mean()):.3f}  RB-only {float((g.bb_type=='rb_only').mean()):.3f}")

# ---- Mantel-Haenszel odds ratios -------------------------------------------------------------------------------------
EXPO = {
    "3+ top-decile-value players vs <= 1": lambda X: (X.n_topval >= 3, X.n_topval <= 1),
    "5+ top-quintile-value players vs <= 3": lambda X: (X.n_val80 >= 5, X.n_val80 <= 3),
    "2+ below-median-value players vs 0": lambda X: (X.n_lowval >= 2, X.n_lowval == 0),
    "3+ top-3-projected-at-position vs <= 1": lambda X: (X.n_prank3 >= 3, X.n_prank3 <= 1),
    "QB top-3 projected vs rank 7+": lambda X: (X.qb_prank <= 3, X.qb_prank >= 7),
    "min projection >= 8 vs < 8": lambda X: (X.min_proj >= 8, X.min_proj < 8),
    "min projection >= 10 vs < 8": lambda X: (X.min_proj >= 10, X.min_proj < 8),
    "no player under 8 (RB/WR/TE) vs 2+": lambda X: (X.n_under8 == 0, X.n_under8 >= 2),
    "1+ hot player (last game >= 2x avg) vs 0": lambda X: (X.n_hot2 >= 1, X.n_hot2 == 0),
    "2+ hot players (>= 1.6x) vs 0": lambda X: (X.n_hot16 >= 2, X.n_hot16 == 0),
    "3+ late-window players vs <= 1": lambda X: (X.n_late >= 3, X.n_late <= 1),
    "0 late-window players vs 2+": lambda X: (X.n_late == 0, X.n_late >= 2),
    "2+ chalk (>= 20% owned) vs <= 1": lambda X: (X.n_chalk20 >= 2, X.n_chalk20 <= 1),
    "3+ sub-5% owned vs <= 1": lambda X: (X.n_sub5 >= 3, X.n_sub5 <= 1),
    "1+ $8k+ star vs 0": lambda X: (X.n_star >= 1, X.n_star == 0),
    "2+ $8k+ stars vs 0": lambda X: (X.n_star >= 2, X.n_star == 0),
    "receiver bring-back vs RB-only bring-back": lambda X: (X.bb_type == "receiver", X.bb_type == "rb_only"),
    "QB + his RB (1+) vs 0": lambda X: (X.mates_rb >= 1, X.mates_rb == 0),
    "5+ games vs <= 4": lambda X: (X.n_games >= 5, X.n_games <= 4),
    "7+ teams vs <= 5": lambda X: (X.n_teams >= 7, X.n_teams <= 5),
    "salary spread top third vs bottom third": lambda X: (X.sal_sd >= X.groupby("week").sal_sd.transform(lambda s: s.quantile(2/3)), X.sal_sd <= X.groupby("week").sal_sd.transform(lambda s: s.quantile(1/3))),
    "WR spend >= $20k vs < $18k": lambda X: (X.wr_spend >= 20000, X.wr_spend < 18000),
    "projection above own median (reference)": lambda X: (X.proj > X.groupby("uw").proj.transform("median"), X.proj <= X.groupby("uw").proj.transform("median")),
}
def mh(X, ex, ref, out, strat):
    Z = X[ex | ref].assign(E=ex[ex | ref].astype(int), o=X.loc[ex | ref, out].astype(int))
    g = Z.groupby([strat, "E"]).o.agg(["size", "sum"]).reset_index()
    s = g.pivot_table(index=strat, columns="E", values=["size", "sum"], fill_value=0)
    for col in (("size", 0), ("size", 1), ("sum", 0), ("sum", 1)):
        if col not in s.columns: s[col] = 0
    a = s[("sum", 1)]; b = s[("size", 1)] - a; c = s[("sum", 0)]; d_ = s[("size", 0)] - c; n = a + b + c + d_
    num, den = (a * d_ / n.replace(0, np.nan)).fillna(0), (b * c / n.replace(0, np.nan)).fillna(0)
    return (num.sum() / den.sum()) if den.sum() > 0 else np.nan, int((ex | ref).sum()), float(ex[ex | ref].mean())

def mh_table(X, strat, outs, label):
    rows = []
    for name, fn in EXPO.items():
        ex, ref = fn(X); ex = ex.fillna(False).astype(bool); ref = ref.fillna(False).astype(bool)
        r = {"feature (vs reference)": name}
        for oname, mask in outs.items():
            X["_o"] = mask.astype(int)
            est, n, share = mh(X, ex, ref, "_o", strat)
            r[oname] = round(est, 2) if est == est else np.nan
        wk = []
        for w, Xw in X.groupby("week"):
            exw, refw = fn(Xw); exw = exw.fillna(False).astype(bool); refw = refw.fillna(False).astype(bool)
            Xw = Xw.copy(); Xw["_o"] = list(outs.values())[0][Xw.index].astype(int)
            e, _, _ = mh(Xw, exw, refw, "_o", strat); wk.append(f"{e:.2f}" if e == e else "nan")
        r[f"{list(outs)[0]} by week"] = "/".join(wk); r["n compared"] = n; r["exposed share"] = round(share, 3)
        rows.append(r)
    T = pd.DataFrame(rows); say(f"\n=== {label} ==="); say(T.to_string(index=False)); return T

M["uw"] = M.week.astype(str) + "|" + M.u.astype(str)
big = M.groupby("uw").uw.transform("size") >= 20
MM = M[big].copy()
T1 = mh_table(MM, "uw", {"top 1%": MM.pct <= 0.01, "top 4%": MM.pct <= 0.04, "top 10%": MM.pct <= 0.10}, "MILLIONAIRE: within user-week MH odds ratios (users with 20+ entries)")
T1.to_csv(OUT / "milly_mh_within_user.csv", index=False)
if len(P):
    P["uw"] = P.week.astype(str) + "|" + P.u.astype(str); P["cw"] = P.contest_id.astype(str)
    T2 = mh_table(P, "cw", {"top 2%": P.pct <= 0.02, "top 5%": P.pct <= 0.05, "top 10%": P.pct <= 0.10}, "PRIORITY CONTESTS: by-contest MH odds ratios (controls the field)")
    T2.to_csv(OUT / "priority_mh_by_contest.csv", index=False)
    Pu = P[P.groupby("uw").uw.transform("size") >= 3].copy()
    T3 = mh_table(Pu, "uw", {"top 5%": Pu.pct <= 0.05, "top 10%": Pu.pct <= 0.10, "top 20%": Pu.pct <= 0.20}, "PRIORITY CONTESTS: within user-week MH (users with 3+ priority lineups)")
    T3.to_csv(OUT / "priority_mh_within_user.csv", index=False)

# ---- projection vs points by value concentration (the optimizer's-curse check) --------------------------------------
say("\n=== MILLIONAIRE: realized points minus projection, by number of top-decile-value players in the lineup ===")
M["gap"] = M.points - M.proj
t = M.groupby(["week", pd.cut(M.n_topval, [-1, 0, 1, 2, 3, 9], labels=["0", "1", "2", "3", "4+"])], observed=True).agg(n=("gap", "size"), proj=("proj", "mean"), points=("points", "mean"), gap=("gap", "mean"), top1=("pct", lambda s: float((s <= 0.01).mean()))).round(2)
say(t.to_string())
say("\n=== MILLIONAIRE: OURS vs field, projection and points by week ===")
say(M.groupby(["week", "ours"]).agg(n=("gap", "size"), proj=("proj", "mean"), points=("points", "mean"), gap=("gap", "mean"), n_topval=("n_topval", "mean"), n_prank3=("n_prank3", "mean")).round(2).to_string())
say("\n=== MILLIONAIRE: min projection and hot players, distribution by group ===")
for name, mask in {"field": M.pct <= 1.0, "top 1%": M.pct <= 0.01, "top 0.1%": M.pct <= 0.001, "OURS": M.ours}.items():
    g = M[mask]
    say(f"{name:>9}: n {len(g):>7,} | min_proj p10/p50/p90 {g.min_proj.quantile(.1):.1f}/{g.min_proj.quantile(.5):.1f}/{g.min_proj.quantile(.9):.1f} | share min<8 {float((g.min_proj<8).mean()):.3f} min<10 {float((g.min_proj<10).mean()):.3f} | "
        f"min_rb {g.min_rb.mean():.1f} min_wr {g.min_wr.mean():.1f} min_te {g.min_te.mean():.1f} qb {g.qb_proj.mean():.1f} | hot2 {g.n_hot2.mean():.2f} (share>=1 {float((g.n_hot2>=1).mean()):.3f}) hot16 {g.n_hot16.mean():.2f}")
say("\ndone")
