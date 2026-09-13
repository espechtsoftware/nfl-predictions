"""Human-readable per-lineup sheet for a live_week book: names, salary, structure, both laws' mean/q99/P>=220,
positions under the coverage-220 / novelty / world-leader orderings (from an ordering_shadows JSON), Sunday
line-movement score and vanished-player veto flag (from a market_move JSON).  Outcome-blind.
Usage: python book_sheet.py RUN_DIR --shadows JSON [--market JSON] [--banks-from DIR] --output PREFIX"""
import argparse, json, pathlib
from collections import Counter
import numpy as np, pandas as pd

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--shadows", required=True); ap.add_argument("--market"); ap.add_argument("--banks-from"); ap.add_argument("--output", required=True); a = ap.parse_args()
    run = pathlib.Path(a.run); bsrc = pathlib.Path(a.banks_from or run)
    f = pd.read_parquet(bsrc / "frame.parquet"); idx = {str(i): k for k, i in enumerate(f.id.astype(str))}
    dk2id = dict(zip(f.dk_player_id.astype(str), f.id.astype(str))); name = dict(zip(f.dk_player_id.astype(str), f.display_name.astype(str)))
    game = dict(zip(f.dk_player_id.astype(str), f.game_id.astype(str))); sal = dict(zip(f.dk_player_id.astype(str), pd.to_numeric(f.salary, errors="coerce").fillna(0)))
    book = pd.read_csv(run / "book.csv", dtype=str); n = len(book)
    inc = np.load(bsrc / "incumbent_player_scores.npy"); hs = np.load(bsrc / "corrected_hsim_player_scores.npy")
    rows = []
    sh = json.load(open(a.shadows)); pos_of = {k: {r: i + 1 for i, r in enumerate(v["book_ranks"])} for k, v in sh["orderings"].items()}  # top-k only
    full_pos = {}
    for k in ("cov220_hsim", "cov220_inc", "cov200_dual", "nov_ladder", "world_leader", "broad", "hsim_p220"):
        if k in sh["orderings"]: full_pos[k] = pos_of[k]
    mk = json.load(open(a.market)) if a.market else None
    for i, row in book.iterrows():
        ids = [str(v) for v in row.tolist()]; fids = [dk2id[d] for d in ids]
        Mi = inc[[idx[p] for p in fids]].sum(axis=0); Mh = hs[[idx[p] for p in fids]].sum(axis=0)
        gc = Counter(game[d] for d in ids)
        r = {"rank": i + 1, "lineup": " | ".join(name[d] for d in ids), "salary": int(sum(sal[d] for d in ids)), "games": len(gc), "max_game": max(gc.values()),
             "inc_mean": round(float(Mi.mean()), 1), "inc_q99": round(float(np.quantile(Mi, .99)), 1), "inc_p220": round(float((Mi >= 220).mean()), 4),
             "hsim_mean": round(float(Mh.mean()), 1), "hsim_q99": round(float(np.quantile(Mh, .99)), 1), "hsim_p220": round(float((Mh >= 220).mean()), 4)}
        for k, pos in full_pos.items(): r[f"pos_{k}"] = pos.get(i + 1, "")
        if mk:
            r["move_sun_vs_sat"] = mk["lineup_move_by_rank"][i] if i < len(mk["lineup_move_by_rank"]) else ""; r["veto_vanished_line"] = "VETO" if (i + 1) in mk.get("veto_candidates_book_ranks", []) else ""
            r["pos_market_move"] = (mk["ordering_top_k_book_ranks"].index(i + 1) + 1) if (i + 1) in mk["ordering_top_k_book_ranks"] else ""
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(a.output + ".csv", index=False)
    with open(a.output + ".md", "w") as h:
        h.write(f"# Lineup sheet — {run.name} (positions are within the top-{sh['k']} of each ordering; blank = outside)\n\n")
        cols = list(df.columns); h.write("| " + " | ".join(cols) + " |\n|" + "|".join("---" for _ in cols) + "|\n")
        for r in df.itertuples(index=False): h.write("| " + " | ".join(str(v) for v in r) + " |\n")
    print(a.output + ".csv", len(df), "rows |", "columns:", list(df.columns))

if __name__ == "__main__":
    main()
