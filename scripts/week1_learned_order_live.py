"""Apply the leave-one-season-out-validated learned lineup ordering to a LIVE book.
Step A (fit, once, frozen): ridge on 66 within-book-standardised lineup features from the 216 opened D800 books (all
four seasons) -> coefficients saved to learned_ordering_v1.json.
Step B (apply): same features for each lineup of the live book from production player_projections (proj, p10, p90,
std), player_week_inference (usage/environment/availability), and DK-implied market points from the latest prop
fetch; within-book standardisation; score; re-sorted emitter-compatible book + learned_receipt.json.
Usage: fit:   PYTHONPATH=<lab>/src python learned_order_live.py fit
       apply: PYTHONPATH=<prod>/src python learned_order_live.py apply RUN_DIR [--k 30] [--output-dir DIR]"""
import argparse, csv, json, pathlib, shutil, sys
from collections import Counter
from datetime import UTC, datetime
import numpy as np, pandas as pd

MODEL = pathlib.Path("/home/erich/week1-sunday/tools/learned_ordering_v1.json")
COLS = ["mean_projection", "proj_p90", "proj_p10", "proj_std", "proj_tourney", "market_points", "own_est", "dk_points_l4", "dk_points_std", "target_share_l4", "snap_share_l4",
        "implied_team_total", "game_total", "spread", "depth_rank", "practice_level", "is_cold_start", "games_played_prior", "xfp_l4", "wopr_l4", "salary"]
W = {"player_reception_yds": 0.1, "player_rush_yds": 0.1, "player_pass_yds": 0.04, "player_receptions": 1.0, "player_pass_tds": 4.0}

def lineup_features(pl, sk, num, pos, team, game, rank):
    f = {}
    for c in COLS:
        v = num[c].loc[sk] if c != "salary" else num[c].loc[pl]
        f[f"sum_{c}"] = float(v.sum(skipna=True)); f[f"min_{c}"] = float(v.min(skipna=True)) if v.notna().any() else 0.0; f[f"max_{c}"] = float(v.max(skipna=True)) if v.notna().any() else 0.0
    gc = Counter(game[p] for p in pl); tc = Counter(team[p] for p in pl); qb = [p for p in pl if pos[p] == "QB"]
    f["games"] = len(gc); f["max_game"] = max(gc.values()); f["teams"] = len(tc); f["max_team"] = max(tc.values())
    f["qb_mates"] = sum(1 for p in sk if qb and team[p] == team[qb[0]] and pos[p] != "QB"); f["n_rb"] = sum(1 for p in pl if pos[p] == "RB"); f["n_te"] = sum(1 for p in pl if pos[p] == "TE")
    f["greedy_rank"] = float(rank); return f

def lineup_features_vec(lineups, fr, num, ranks):
    """Vectorised twin of lineup_features: `lineups` is a list of player-id lists (9 each), `fr` the slate frame indexed
    by id, `num` {col: Series aligned to fr.index}, `ranks` the greedy rank per lineup (0 when unknown)."""
    import warnings
    ids = list(fr.index); ix = {p: i for i, p in enumerate(ids)}; pos = fr.pos.astype(str).to_numpy(); team = fr.team.astype(str).to_numpy(); game = fr.game_id.astype(str).to_numpy()
    idx = np.array([[ix[p] for p in lu] for lu in lineups]); n = len(lineups); f = {}
    skill = np.isin(pos[idx], ["QB", "RB", "WR", "TE"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for c in COLS:
            V = pd.to_numeric(num[c], errors="coerce").to_numpy(dtype=float)[idx]
            if c != "salary": V = np.where(skill, V, np.nan)
            f[f"sum_{c}"] = np.nansum(V, axis=1); mn = np.nanmin(V, axis=1); mx = np.nanmax(V, axis=1)
            allnan = np.isnan(V).all(axis=1); f[f"min_{c}"] = np.where(allnan, 0.0, mn); f[f"max_{c}"] = np.where(allnan, 0.0, mx)
    G = game[idx]; T = team[idx]; P = pos[idx]
    f["games"] = np.array([len(set(r)) for r in G]); f["max_game"] = np.array([max(Counter(r).values()) for r in G])
    f["teams"] = np.array([len(set(r)) for r in T]); f["max_team"] = np.array([max(Counter(r).values()) for r in T])
    qbteam = np.array([T[i][P[i] == "QB"][0] if (P[i] == "QB").any() else "" for i in range(n)])
    f["qb_mates"] = np.array([int(((T[i] == qbteam[i]) & (P[i] != "QB") & skill[i]).sum()) if qbteam[i] else 0 for i in range(n)])
    f["n_rb"] = (P == "RB").sum(axis=1); f["n_te"] = (P == "TE").sum(axis=1); f["greedy_rank"] = np.asarray(ranks, dtype=float)
    return pd.DataFrame(f)

def ridge(X, y, lam=30.0):
    Xb = np.column_stack([X, np.ones(len(X))]); A = Xb.T @ Xb + lam * np.eye(Xb.shape[1]); A[-1, -1] -= lam; return np.linalg.solve(A, Xb.T @ y)

def fit():
    import importlib.util
    from nfl2.pipeline import slate_frame
    spec = importlib.util.spec_from_file_location("r", "/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/scripts/prereg094_report.py")
    r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
    books, meta = r._load(["114b940r1-20260913T042316Z", "114b941r1-20260913T042615Z", "114b942r1-20260913T053219Z"])
    d = pd.DataFrame(books["D800_DEMAX"]); d["rank"] = pd.to_numeric(d["rank"]); d["actual"] = pd.to_numeric(d["actual"])
    feats = {}
    for (s, w), g in d.groupby(["season", "week"]):
        fr = slate_frame(int(s), int(w)); fr = fr.set_index(fr.id.astype(str)); num = {c: pd.to_numeric(fr.get(c), errors="coerce") for c in COLS}
        pos = fr.pos.astype(str); team = fr.team.astype(str); game = fr.game_id.astype(str)
        lus = [[p for p in row.players.split(",") if p in fr.index] for _, row in g.iterrows()]
        Fg = lineup_features_vec(lus, fr, num, g["rank"].to_numpy()); Fg.index = g.index; feats[(s, w)] = Fg
    F = pd.concat(feats.values()).loc[d.index].fillna(0.0); fcols = list(F.columns); d = d.join(F); key = ["season", "week", "bank"]
    d.to_parquet(pathlib.Path("/home/erich/week1-sunday/pool-level/books216_features.parquet"))
    Z = d.groupby(key)[fcols].transform(lambda x: (x - x.mean()) / (x.std() + 1e-9)).fillna(0.0)
    y = d.groupby(key)["actual"].transform(lambda x: (x - x.mean()) / (x.std() + 1e-9)).to_numpy()
    w = ridge(Z.to_numpy(), y)
    pcols = [c for c in fcols if c != "greedy_rank"]; wp = ridge(Z[pcols].to_numpy(), y)
    MODEL.write_text(json.dumps({"features_pool": pcols, "coef_pool": [float(v) for v in wp[:-1]], "intercept_pool": float(wp[-1]),"version": "learned-ordering-v1", "fitted_utc": datetime.now(UTC).isoformat(), "training": "216 D800_DEMAX books (PREREG-094 cohort, 2021-2024), within-book standardised ridge lam=30",
                                 "loso_top30_vs_greedy": {"2021": -2.35, "2022": -0.47, "2023": 1.72, "2024": 5.17}, "features": fcols, "coef": [float(v) for v in w[:-1]], "intercept": float(w[-1])}, indent=1) + "\n")
    print("model saved", MODEL, "features", len(fcols))

def apply(run, k, output_dir):
    from google.cloud import bigquery
    from nfl_dfs.names import norm_name
    m = json.loads(MODEL.read_text()); fcols = m["features"]; coef = np.array(m["coef"])
    run = pathlib.Path(run); out = pathlib.Path(output_dir or (str(run) + "-learned")); out.mkdir(parents=True, exist_ok=True)
    f = pd.read_parquet(run / "frame.parquet"); f["dk"] = f.dk_player_id.astype(str)
    with (run / "book.csv").open(newline="") as h: rows = list(csv.reader(h))
    book = rows[1:]; n = len(book); dks = sorted({v for r in book for v in r}); ff = f[f.dk.isin(dks)].set_index("dk")
    gsis = ff.gsis_id.astype(str); ids = sorted({g for g in gsis if g not in ("None", "nan", "")})
    c = bigquery.Client(project="nfl-predictions-503414"); jc = lambda: bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", 2026), bigquery.ScalarQueryParameter("w", "INT64", 1), bigquery.ArrayQueryParameter("ids", "STRING", ids)])
    pr = c.query("""SELECT gsis_id, dk_player_id, proj_points, proj_p10, proj_p90, proj_std, position FROM `nfl-predictions-503414.nfl_predictions.player_projections`
                    WHERE season=@s AND week=@w AND generated_at=(SELECT MAX(generated_at) FROM `nfl-predictions-503414.nfl_predictions.player_projections` WHERE season=@s AND week=@w)""", job_config=jc()).result().to_dataframe()
    pr["dk"] = pr.dk_player_id.astype(str); pr = pr.drop_duplicates("dk").set_index("dk")
    pw = c.query("""SELECT gsis_id, dk_points_l4, dk_points_std, target_share_l4, snap_share_l4, implied_team_total, game_total, spread, depth_rank, practice_level, is_cold_start, games_played_prior, xfp_l4, wopr_l4
                    FROM `nfl-predictions-503414.nfl_features.player_week_inference` WHERE season=@s AND week=@w AND gsis_id IN UNNEST(@ids)""", job_config=jc()).result().to_dataframe().drop_duplicates("gsis_id").set_index("gsis_id")
    L = c.query("""SELECT player, market, outcome_name, AVG(point) AS point, AVG(price) AS price FROM `nfl-predictions-503414.nfl_raw.prop_lines` WHERE season=@s AND week=@w
                   AND DATE(pulled_at)=(SELECT MAX(DATE(pulled_at)) FROM `nfl-predictions-503414.nfl_raw.prop_lines` WHERE season=@s AND week=@w) GROUP BY player, market, outcome_name""", job_config=jc()).result().to_dataframe()
    mp = Counter()
    for r_ in L.itertuples():
        if r_.market == "player_anytime_td":
            if str(r_.outcome_name).lower().startswith("yes") or r_.outcome_name == r_.player: a_ = float(r_.price); mp[norm_name(r_.player)] += 6.0 * (100 / (a_ + 100) if a_ > 0 else -a_ / (-a_ + 100))
        elif r_.market in W and str(r_.outcome_name).lower().startswith("over") and pd.notna(r_.point): mp[norm_name(r_.player)] += W[r_.market] * float(r_.point)
    # per-player feature frame indexed by dk id
    P = pd.DataFrame(index=ff.index)
    for src, col in (("proj_points", "mean_projection"), ("proj_p10", "proj_p10"), ("proj_p90", "proj_p90"), ("proj_std", "proj_std")): P[col] = pd.to_numeric(pr[src].reindex(ff.index), errors="coerce")
    P["proj_tourney"] = P["mean_projection"]; P["own_est"] = np.nan; P["salary"] = pd.to_numeric(ff.salary, errors="coerce")
    P["market_points"] = [mp.get(norm_name(nm), np.nan) if ps != "DST" else np.nan for nm, ps in zip(ff.display_name.astype(str), ff.position.astype(str))]
    for col in ("dk_points_l4", "dk_points_std", "target_share_l4", "snap_share_l4", "implied_team_total", "game_total", "spread", "depth_rank", "practice_level", "is_cold_start", "games_played_prior", "xfp_l4", "wopr_l4"):
        P[col] = pd.to_numeric(pw[col].reindex(gsis.values).to_numpy(), errors="coerce") if col in pw.columns else np.nan
    num = {c_: P[c_] for c_ in COLS}; pos = ff.position.astype(str); team = ff.team.astype(str); game = ff.game_id.astype(str)
    feats = []
    for i, row in enumerate(book):
        pl = list(row); sk = [p for p in pl if pos[p] in ("QB", "RB", "WR", "TE")]; feats.append(lineup_features(pl, sk, num, pos, team, game, i + 1))
    F = pd.DataFrame(feats).reindex(columns=fcols).fillna(0.0); Z = ((F - F.mean()) / (F.std() + 1e-9)).fillna(0.0)
    score = Z.to_numpy() @ coef; order = list(np.argsort(-score, kind="stable"))
    with (out / "book.csv").open("w", newline="") as h:
        wr = csv.writer(h); wr.writerow(rows[0]); [wr.writerow(book[i]) for i in order]
    shutil.copy(run / "frame.parquet", out / "frame.parquet"); shutil.copy(run / "receipt.json", out / "source_receipt.json")
    coverage = {c_: int(P[c_].notna().sum()) for c_ in COLS}
    rec = {"version": m["version"], "source_run": str(run), "k": k, "loso_top30_vs_greedy": m["loso_top30_vs_greedy"], "feature_coverage_players": coverage, "players": len(P),
           "order_source_ranks": [int(i) + 1 for i in order], "overlap_top_k_with_greedy": len(set(range(k)) & set(int(i) for i in order[:k])), "built_utc": datetime.now(UTC).isoformat(),
           "top_feature_contributions": {fc: round(float(v), 3) for fc, v in sorted(zip(fcols, np.abs(Z.to_numpy()).mean(axis=0) * np.abs(coef)), key=lambda kv: -kv[1])[:10]}}
    (out / "learned_receipt.json").write_text(json.dumps(rec, indent=1) + "\n"); pd.DataFrame({"source_rank": range(1, n + 1), "score": np.round(score, 4), "learned_pos": [order.index(i) + 1 for i in range(n)]}).to_csv(out / "lineup_scores.csv", index=False)
    print(json.dumps({k_: v for k_, v in rec.items() if k_ != "order_source_ranks"}, indent=1)); print("book ->", out / "book.csv")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["fit", "apply"]); ap.add_argument("run", nargs="?"); ap.add_argument("--k", type=int, default=30); ap.add_argument("--output-dir"); a = ap.parse_args()
    fit() if a.mode == "fit" else apply(a.run, a.k, a.output_dir)
