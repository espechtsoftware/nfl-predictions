"""Post-selection PLAYER SCORING + RESORT: an independent per-player projected score from several live sources,
aggregated per lineup, and the book re-sorted on it.  Frozen weights (v1); outcome-blind; emitter-compatible output.

Per player (all live at run time):
  prod_proj, prod_p90, prod_p20   production player_projections (latest generated_at): proj_points, proj_p90, p_20_plus
  market_pts                      DK-implied points from the latest prop fetch (yards, receptions, pass TDs, anytime-TD odds)
  market_move                     change vs the previous prop fetch
  inc_q99, hsim_q99               99th percentile of the player's draws under each selection bank of THIS run
  dk_ppg                          prior-season DK points per game (DK feed)
  avail_penalty                   vetting weight from vetting.json if present (hard = excluded from the score's top)
Composite = weighted sum of within-position z-scores (weights frozen below); lineup score = sum over the 9 slots.
Usage: PYTHONPATH=<prod>/src python player_score.py RUN_DIR [--k 30] [--output-dir DIR] [--vetting vetting.json]"""
import argparse, csv, json, pathlib, shutil
from collections import Counter
from datetime import UTC, datetime
import numpy as np, pandas as pd
from google.cloud import bigquery
from nfl_dfs.names import norm_name

SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
W = {"player_reception_yds": 0.1, "player_rush_yds": 0.1, "player_pass_yds": 0.04, "player_receptions": 1.0, "player_pass_tds": 4.0}
WEIGHTS = {"prod_proj": 0.20, "prod_p90": 0.15, "prod_p20": 0.20, "market_pts": 0.20, "market_move": 0.05, "hsim_q99": 0.10, "inc_q99": 0.05, "dk_ppg": 0.05}
AVAIL_WEIGHT = 1.0   # composite z-units per vetting risk point

def implied_prob(a): a = float(a); return 100 / (a + 100) if a > 0 else -a / (-a + 100)

def verify_slice(frame, season, week, what):
    """Every row returned must carry the target slate. Defence in depth.

    The query already filters on season and week, so this can only fire if the
    query is edited wrongly or the table's own columns disagree. That is exactly
    the case worth catching: on 2026-09-20 the query was correct and the CALLER
    supplied the wrong week, and because the downstream join is by player the
    substitution was invisible. Checking the returned data, not just the query
    text, means a wrong slice cannot reach the book however it arrives.
    """
    for column, target in (("season", season), ("week", week)):
        if column not in getattr(frame, "columns", ()):
            raise SystemExit(f"player_score: {what} does not carry a {column} column; cannot verify its identity")
        values = {int(v) for v in frame[column].dropna().unique()}
        if values != {int(target)}:
            raise SystemExit(
                f"player_score: {what} is for {column} {sorted(values)} but this run is "
                f"{column} {target}; refusing to score the book against another slate")


def resolve_season_week(run, season_flag=None, week_flag=None):
    """Resolve the slate from the run's own receipt; never guess.

    A defaulted week is the defect this guards. On 2026-09-21 every Week-2 composite
    ordering was found to have scored Week-2 lineups against the LAST WEEK-1
    projection batch and Week-1 props, because --week defaulted to 1 and the Sunday
    caller omitted the flag. The projection join is by player, not by week, so it
    succeeded silently and the receipt's coverage block read a healthy 134 of 149.
    80% of the ordering weight was stale and nothing in the output said so.

    The run receipt is the authority. A flag may only confirm it, never supply it.
    """
    receipt = pathlib.Path(run) / "receipt.json"
    if not receipt.is_file():
        raise SystemExit(f"player_score: {receipt} is missing; cannot establish which slate this run is for")
    try:
        data = json.loads(receipt.read_text())
    except (ValueError, OSError) as exc:
        raise SystemExit(f"player_score: cannot read {receipt}: {exc}") from exc
    season, week = data.get("season"), data.get("week")
    if season is None or week is None:
        raise SystemExit(f"player_score: {receipt} does not carry both season and week")
    season, week = int(season), int(week)
    for name, flag, found in (("season", season_flag, season), ("week", week_flag, week)):
        if flag is not None and int(flag) != found:
            raise SystemExit(
                f"player_score: --{name} {flag} contradicts the run receipt's {name} {found}; "
                f"refusing to score {run} against the wrong slate")
    return season, week


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--k", type=int, default=30); ap.add_argument("--output-dir"); ap.add_argument("--vetting"); ap.add_argument("--season", type=int, default=None); ap.add_argument("--week", type=int, default=None); a = ap.parse_args()
    run = pathlib.Path(a.run); season, week = resolve_season_week(run, a.season, a.week)
    out = pathlib.Path(a.output_dir or (str(run) + "-composite")); out.mkdir(parents=True, exist_ok=True)
    f = pd.read_parquet(run / "frame.parquet"); f["dk"] = f.dk_player_id.astype(str); f["fid"] = f.id.astype(str)
    idx = {fid: k for k, fid in enumerate(f.fid)}; dk2fid = dict(zip(f.dk, f.fid)); name = dict(zip(f.dk, f.display_name.astype(str))); pos = dict(zip(f.dk, f.position.astype(str)))
    gsis = dict(zip(f.dk, f.gsis_id.astype(str))); ppg = dict(zip(f.dk, pd.to_numeric(f.get("dk_ppg"), errors="coerce"))) if "dk_ppg" in f.columns else {}
    with (run / "book.csv").open(newline="") as h: rows = list(csv.reader(h))
    assert tuple(rows[0]) == SLOTS; book = rows[1:]; n = len(book); players = sorted({v for r in book for v in r})
    inc = np.load(run / "incumbent_player_scores.npy"); hs = np.load(run / "corrected_hsim_player_scores.npy")
    c = bigquery.Client(project="nfl-predictions-503414")
    ids = sorted({gsis[d] for d in players if gsis.get(d) not in (None, "None", "nan", "")})
    prod = c.query("""SELECT gsis_id, dk_player_id, proj_points, proj_p90, p_20_plus, position, generated_at, season, week FROM `nfl-predictions-503414.nfl_predictions.player_projections`
                      WHERE season=@s AND week=@w AND generated_at=(SELECT MAX(generated_at) FROM `nfl-predictions-503414.nfl_predictions.player_projections` WHERE season=@s AND week=@w)""",
                   job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", season), bigquery.ScalarQueryParameter("w", "INT64", week)])).result().to_dataframe()
    if prod.empty: raise SystemExit(f"player_score: no production projection batch for season {season} week {week}; refusing to score a book against nothing")
    verify_slice(prod, season, week, "projection batch")
    by_gsis = prod.drop_duplicates("gsis_id").set_index(prod.drop_duplicates("gsis_id").gsis_id.astype(str)); by_dk = prod.drop_duplicates("dk_player_id").set_index(prod.drop_duplicates("dk_player_id").dk_player_id.astype(str))
    L = c.query("""SELECT DATE(pulled_at) AS d, ANY_VALUE(season) AS season, ANY_VALUE(week) AS week, player, market, outcome_name, AVG(point) AS point, AVG(price) AS price FROM `nfl-predictions-503414.nfl_raw.prop_lines`
                   WHERE season=@s AND week=@w GROUP BY d, player, market, outcome_name""",
                job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", season), bigquery.ScalarQueryParameter("w", "INT64", week)])).result().to_dataframe()
    if L.empty: raise SystemExit(f"player_score: no prop lines for season {season} week {week}; refusing to score a book against nothing")
    verify_slice(L, season, week, "prop lines")
    days = sorted(L.d.unique())
    def implied(df):
        pts = Counter()
        for r in df.itertuples():
            if r.market == "player_anytime_td":
                if str(r.outcome_name).lower().startswith("yes") or r.outcome_name == r.player: pts[r.player] += 6.0 * implied_prob(r.price)
            elif r.market in W and str(r.outcome_name).lower().startswith("over") and pd.notna(r.point): pts[r.player] += W[r.market] * float(r.point)
        return pts
    p1 = implied(L[L.d == days[-1]]) if days else Counter(); p0 = implied(L[L.d == days[-2]]) if len(days) >= 2 else Counter()
    m1 = {norm_name(p): v for p, v in p1.items()}; m0 = {norm_name(p): v for p, v in p0.items()}
    vet = json.load(open(a.vetting)) if a.vetting and pathlib.Path(a.vetting).exists() else None
    vet_w = {k: v.get("weight", 0.0) for k, v in (vet or {}).get("player_flags", {}).items()}
    rows_ = []
    for d in players:
        g = gsis.get(d); pr = by_gsis.loc[g] if g in by_gsis.index else (by_dk.loc[d] if d in by_dk.index else None)
        nn = norm_name(name[d]); r_ = {"dk": d, "name": name[d], "pos": pos[d], "prod_proj": float(pr.proj_points) if pr is not None else np.nan, "prod_p90": float(pr.proj_p90) if pr is not None else np.nan,
              "prod_p20": float(pr.p_20_plus) if pr is not None and pd.notna(pr.p_20_plus) else np.nan, "market_pts": m1.get(nn, np.nan) if pos[d] != "DST" else np.nan,
              "market_move": (m1[nn] - m0[nn]) if (nn in m1 and nn in m0) else np.nan, "inc_q99": float(np.quantile(inc[idx[dk2fid[d]]], .99)), "hsim_q99": float(np.quantile(hs[idx[dk2fid[d]]], .99)),
              "dk_ppg": float(ppg.get(d)) if ppg and pd.notna(ppg.get(d)) else np.nan, "avail_penalty": float(vet_w.get(name[d], 0.0))}
        rows_.append(r_)
    P = pd.DataFrame(rows_)
    P["group"] = P.pos.where(P.pos != "DST", "DST")
    comp = np.zeros(len(P)); used = np.zeros(len(P))
    for col, w in WEIGHTS.items():
        z = pd.Series(np.nan, index=P.index)
        for grp, gi in P.groupby("group").groups.items():
            v = P.loc[gi, col].astype(float); sd = v.std()
            if v.notna().sum() >= 3 and sd and sd > 0: z.loc[gi] = (v - v.mean()) / sd
        P[f"z_{col}"] = z; ok = z.notna(); comp[ok] += w * z[ok]; used[ok] += w
    P["composite"] = np.where(used > 0, comp / np.maximum(used, 1e-9), 0.0) - AVAIL_WEIGHT * P.avail_penalty.clip(upper=5.0)
    P["hard"] = P.avail_penalty >= 100
    score = dict(zip(P.dk, P.composite)); hard = dict(zip(P.dk, P.hard))
    lineup_scores = [sum(score[d] for d in r) for r in book]; lineup_hard = [any(hard[d] for d in r) for r in book]
    order = sorted(range(n), key=lambda i: (lineup_hard[i], -lineup_scores[i], i))
    with (out / "book.csv").open("w", newline="") as h:
        wr = csv.writer(h); wr.writerow(SLOTS); [wr.writerow(book[i]) for i in order]
    shutil.copy(run / "frame.parquet", out / "frame.parquet"); shutil.copy(run / "receipt.json", out / "source_receipt.json")
    P.sort_values("composite", ascending=False).round(3).to_csv(out / "player_scores.csv", index=False)
    LS = pd.DataFrame({"source_rank": range(1, n + 1), "lineup_score": np.round(lineup_scores, 3), "hard": lineup_hard}); LS["composite_pos"] = [order.index(i) + 1 for i in range(n)]
    LS.to_csv(out / "lineup_scores.csv", index=False)
    top_before, top_after = set(range(a.k)), set(order[:a.k])
    rec = {"version": "player-score-v1", "source_run": str(run), "k": a.k, "weights": WEIGHTS, "avail_weight": AVAIL_WEIGHT, "prop_fetch_days": [str(x) for x in days[-2:]],
           "season": season, "week": week, "week_source": "run receipt", "target_identity": {"season": season, "week": week, "run": str(run)},
           "projection_batch": {"generated_at": str(prod.generated_at.max()), "rows": int(len(prod))},
           "prop_batch": {"days": [str(d) for d in days], "rows": int(len(L))}, "projection_generated_at": str(prod.generated_at.max()) if "generated_at" in prod.columns else None, "players": len(P), "coverage": {c_: int(P[c_].notna().sum()) for c_ in WEIGHTS},
           "order_source_ranks": [i + 1 for i in order], "demoted_out_of_top_k": sorted(i + 1 for i in top_before - top_after), "promoted_into_top_k": sorted(i + 1 for i in top_after - top_before),
           "overlap_top_k_with_greedy": len(top_before & top_after), "built_utc": datetime.now(UTC).isoformat()}
    (out / "composite_receipt.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k_: v for k_, v in rec.items() if k_ != "order_source_ranks"}, indent=1)); print("book ->", out / "book.csv")
    print("top 10 players by composite:", P.sort_values("composite", ascending=False).head(10)[["name", "pos", "composite", "prod_proj", "market_pts", "prod_p20"]].round(2).to_string(index=False))

if __name__ == "__main__":
    main()
