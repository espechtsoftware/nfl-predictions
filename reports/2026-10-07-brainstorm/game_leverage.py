"""Game leverage. (A) History 2014-2025, Sunday main-slate games (13:00-16:30 ET kickoffs): how often is the game with the
k-th highest closing total the slate's best stacking game (max over its two teams of QB + top-2 teammates + top opponent,
DK points) or its highest-scoring game (all QB/RB/WR/TE DK points)? (B) 2026 W1-4 real Millionaire fields: QB share by the
game's total rank for the field, the top-1% lineups and our T-70 book. Aggregates only."""
import json, re, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
H = BQ.query("""WITH g AS (SELECT game_id, season, week, home_team, away_team, total_line FROM `nfl_raw.schedules`
     WHERE game_type = 'REG' AND weekday = 'Sunday' AND gametime BETWEEN '13:00' AND '16:30' AND season BETWEEN 2014 AND 2025 AND total_line IS NOT NULL),
  t AS (SELECT game_id, season, week, home_team team, away_team opp, total_line FROM g UNION ALL SELECT game_id, season, week, away_team, home_team, total_line FROM g)
  SELECT t.game_id, t.season, t.week, t.team, t.opp, t.total_line, r.position, a.dk_points FROM t
  JOIN `nfl_features.player_week_actuals` a ON a.season = t.season AND a.week = t.week AND a.team = t.team
  JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
  WHERE r.position IN ('QB', 'RB', 'WR', 'TE')""").to_dataframe()
H["dk_points"] = H.dk_points.astype(float)
def team_stack(g):
    qb = g[g.position == "QB"].dk_points.max(); qb = 0.0 if np.isnan(qb) else qb
    sk = np.sort(g[g.position != "QB"].dk_points.values)[::-1]; return qb + sk[:2].sum(), (sk[0] if len(sk) else 0.0), g.dk_points.sum()
rows = []
for (gid, s, w, team), g in H.groupby(["game_id", "season", "week", "team"]):
    st, top1, tot = team_stack(g); rows.append({"game_id": gid, "season": s, "week": w, "team": team, "opp": g.opp.iloc[0], "total": float(g.total_line.iloc[0]), "st": st, "top1": top1, "tot": tot})
T = pd.DataFrame(rows); o = T[["game_id", "team", "top1"]].rename(columns={"team": "opp", "top1": "opp_top1"})
T = T.merge(o, on=["game_id", "opp"], how="left"); T["stk"] = T.st + T.opp_top1.fillna(0)
G = T.groupby(["game_id", "season", "week"]).agg(total=("total", "first"), stk=("stk", "max"), pts=("tot", "sum")).reset_index()
G = G[G.groupby(["season", "week"]).game_id.transform("size") >= 6]
G["k"] = G.groupby(["season", "week"]).total.rank(ascending=False, method="first").astype(int)
G["best_stack"] = G.stk == G.groupby(["season", "week"]).stk.transform("max"); G["best_pts"] = G.pts == G.groupby(["season", "week"]).pts.transform("max")
G["n_games"] = G.groupby(["season", "week"]).game_id.transform("size")
ns = G.groupby(["season", "week"]).ngroups
A = G.assign(kk=G.k.clip(upper=7)).groupby("kk").agg(slates=("best_stack", "size"), p_best_stack=("best_stack", "mean"), p_best_pts=("best_pts", "mean"), mean_total=("total", "mean")).round(3)
A["fair_share_1_over_n"] = (1 / G.n_games).groupby(G.k.clip(upper=7)).mean().round(3)
print(f"(A) history 2014-2025: {ns} Sunday main slates, {len(G)} games (k = rank by closing total; 7 = 7th or lower)")
print(A.to_string())
for era, X in (("2014-2019", G[G.season <= 2019]), ("2020-2025", G[G.season >= 2020])):
    print(f"  {era}: P(best stack) k=1 {X[X.k == 1].best_stack.mean():.3f}, k=2 {X[X.k == 2].best_stack.mean():.3f}, k=3 {X[X.k == 3].best_stack.mean():.3f}, k>=4 per game {X[X.k >= 4].best_stack.mean():.3f}")
# (B) 2026 fields
out = []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    r = Path(CFG["weeks"][str(w)]["t70_run"]); fr = pd.read_parquet(r / "frame.parquet").drop_duplicates("dk_player_id").copy()
    gt = fr.groupby("game_id").game_total.max().astype(float); kmap = gt.rank(ascending=False, method="first").astype(int).to_dict()
    qb = fr[fr.pos == "QB"].copy(); qb["key"] = qb.display_name.map(canon); qb["k"] = qb.game_id.map(kmap); qmap = dict(zip(qb.key, qb.k))
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    e = BQ.query(f"""SELECT players_key, COUNT(*) n, COUNTIF(rank <= 0.01 * expected_entries) top1, MIN(rank) best FROM (SELECT DISTINCT entry_id, rank, expected_entries, players_key FROM `nfl_raw.contest_entries`
        WHERE contest_id = '{cid}' AND season = 2026 AND week = {w}) GROUP BY 1""").to_dataframe()
    def qk(pk):
        ks = [qmap[canon(n)] for n in str(pk).split("|") if canon(n) in qmap]; return ks[0] if len(ks) == 1 else np.nan
    e["k"] = e.players_key.map(qk)
    b = pd.read_csv(r / "book.csv", dtype=str) if (r / "book.csv").exists() else None
    dk2k = dict(zip(pd.to_numeric(qb.dk_player_id, errors="coerce").astype("Int64").astype(str), qb.k))
    bk = [next((dk2k[v] for v in row if v in dk2k), np.nan) for row in b.values] if b is not None else []
    win_k = e.loc[e.best.idxmin(), "k"]
    for k in range(1, int(max(kmap.values())) + 1):
        out.append({"week": w, "k": k, "field": (e.n * (e.k == k)).sum() / e.n[e.k.notna()].sum(), "top1": (e.top1 * (e.k == k)).sum() / e.top1[e.k.notna()].sum(),
                    "book": np.mean([x == k for x in bk]) if bk else np.nan, "winner": float(win_k == k)})
    print(f"W{w}: field lineups {int(e.n.sum()):,} (QB resolved {e.n[e.k.notna()].sum() / e.n.sum():.3f}); winner's QB from total rank {win_k}; book rows {len(bk)}")
B = pd.DataFrame(out); B["kk"] = B.k.clip(upper=7)
S = B.groupby(["kk", "week"])[["field", "top1", "book"]].sum().groupby("kk").mean()
S["top1_lift_vs_field"] = (S.top1 / S.field).round(2); S["hist_p_best_stack"] = A.p_best_stack; S["book_vs_hist"] = (S.book / S.hist_p_best_stack).round(2); S["field_vs_hist"] = (S.field / S.hist_p_best_stack).round(2)
print("\n(B) 2026 W1-4 mean share of lineups by the QB's game total rank (7 = 7th or lower, summed), vs history's P(best stacking game):")
print(S.round(3).to_string())
print("\nper week, QB share in the top-total game: field / top-1% / book: " + ", ".join(f"W{w} {g.field.iloc[0]:.2f}/{g.top1.iloc[0]:.2f}/{g.book.iloc[0]:.2f}" for w, g in B[B.k == 1].groupby("week")))
