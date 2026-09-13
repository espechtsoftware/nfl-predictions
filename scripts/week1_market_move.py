"""Line-movement ordering shadow (new pre-lock information the simulator never sees).

For a live run dir's book, compares the two most recent prop-line fetches (nfl_raw.prop_lines, mean across
bookmakers) and scores each player by the change in DK-implied points:
  0.1*rec_yds + 0.1*rush_yds + 0.04*pass_yds + 1.0*receptions + 4*pass_tds + 6*P(anytime TD)
Lineup movement = sum over its skill players; ordering descending.  Players whose lines VANISHED between the two
fetches (market pulled them) are flagged; lineups carrying one are listed as a veto candidate set.  Outcome-blind.
Usage: PYTHONPATH=<prod>/src python market_move.py RUN_DIR [--k 30] [--output PATH]"""
import argparse, json, pathlib, re, sys
from collections import Counter
from datetime import UTC, datetime
import numpy as np, pandas as pd
from google.cloud import bigquery
from nfl_dfs.names import norm_name

W = {"player_reception_yds": 0.1, "player_rush_yds": 0.1, "player_pass_yds": 0.04, "player_receptions": 1.0, "player_pass_tds": 4.0}

def implied_prob(american):
    a = float(american); return 100 / (a + 100) if a > 0 else -a / (-a + 100)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--k", type=int, default=30); ap.add_argument("--output"); ap.add_argument("--season", type=int, default=2026); ap.add_argument("--week", type=int, default=1); a = ap.parse_args()
    run = pathlib.Path(a.run); c = bigquery.Client(project="nfl-predictions-503414")
    q = f"""SELECT DATE(pulled_at) AS d, player, market, outcome_name, AVG(point) AS point, AVG(price) AS price
            FROM `nfl-predictions-503414.nfl_raw.prop_lines` WHERE season={a.season} AND week={a.week} GROUP BY d, player, market, outcome_name"""
    L = c.query(q).result().to_dataframe(); days = sorted(L.d.unique())
    if len(days) < 2: sys.exit(f"need two fetch days, have {days}")
    d0, d1 = days[-2], days[-1]
    def implied(df):
        pts = Counter()
        for r in df.itertuples():
            if r.market == "player_anytime_td":
                if str(r.outcome_name).lower().startswith("yes") or r.outcome_name == r.player: pts[r.player] += 6.0 * implied_prob(r.price)
            elif r.market in W and str(r.outcome_name).lower().startswith("over") and pd.notna(r.point): pts[r.player] += W[r.market] * float(r.point)
        return pts
    p0, p1 = implied(L[L.d == d0]), implied(L[L.d == d1])
    delta = {p: p1[p] - p0[p] for p in p0 if p in p1}; vanished = sorted(p for p in p0 if p not in p1 and p0[p] >= 5.0); appeared = sorted(p for p in p1 if p not in p0)
    f = pd.read_parquet(run / "frame.parquet"); f["norm"] = f.display_name.astype(str).map(norm_name)
    by_norm = {}
    for r in f.itertuples(): by_norm.setdefault(r.norm, []).append(str(r.dk_player_id))
    move_by_dk, vanished_dk = {}, set()
    for p, dv in delta.items():
        for dk in by_norm.get(norm_name(p), []): move_by_dk[dk] = dv
    for p in vanished:
        for dk in by_norm.get(norm_name(p), []): vanished_dk.add(dk)
    book = pd.read_csv(run / "book.csv", dtype=str); n = len(book); slots = list(book.columns)
    name = dict(zip(f.dk_player_id.astype(str), f.display_name.astype(str))); pos = dict(zip(f.dk_player_id.astype(str), f.position.astype(str)))
    scores, covered, veto = [], [], []
    for i, row in book.iterrows():
        ids = [str(v) for v in row.tolist()]; skill = [d for d in ids if pos.get(d) != "DST"]
        scores.append(sum(move_by_dk.get(d, 0.0) for d in skill)); covered.append(sum(1 for d in skill if d in move_by_dk))
        if any(d in vanished_dk for d in ids): veto.append(i + 1)
    order = list(np.lexsort((np.arange(n), -np.array(scores))))
    top = [int(i) + 1 for i in order[:a.k]]
    matched_players = sorted({d for d in move_by_dk if d in set(v for row in book.itertuples(index=False) for v in row)})
    out = {"version": "market-move-v1", "run_dir": str(run), "fetch_days": [str(d0), str(d1)], "players_with_delta": len(delta), "book_players_matched": len(matched_players),
           "mean_coverage_per_lineup": float(np.mean(covered)), "frozen_at_utc": datetime.now(UTC).isoformat(),
           "top_movers_up": sorted(((round(v, 2), p) for p, v in delta.items()), reverse=True)[:12], "top_movers_down": sorted(((round(v, 2), p) for p, v in delta.items()))[:12],
           "vanished_from_market": vanished, "appeared": appeared[:20], "ordering_top_k_book_ranks": top, "lineup_move_by_rank": [round(s, 2) for s in scores],
           "veto_candidates_book_ranks": veto}
    path = pathlib.Path(a.output or run / f"market_move_k{a.k}.json"); path.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("lineup_move_by_rank",)}, indent=1)[:3000])

if __name__ == "__main__":
    main()
