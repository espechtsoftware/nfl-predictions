"""Human-readable per-lineup sheet for a live_week book: names, salary, structure, both laws' mean/q99/P>=220,
positions under the coverage-220 / novelty / world-leader orderings (from an ordering_shadows JSON), Sunday
line-movement score and vanished-player veto flag (from a market_move JSON).  Outcome-blind.
Usage: python book_sheet.py RUN_DIR --shadows JSON [--market JSON] [--banks-from DIR] --output PREFIX"""
import argparse, json, pathlib
from collections import Counter
import numpy as np, pandas as pd

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--shadows"); ap.add_argument("--market"); ap.add_argument("--banks-from"); ap.add_argument("--output", required=True); a = ap.parse_args()
    run = pathlib.Path(a.run); bsrc = pathlib.Path(a.banks_from or run)
    f = pd.read_parquet(bsrc / "frame.parquet"); idx = {str(i): k for k, i in enumerate(f.id.astype(str))}
    dk2id = dict(zip(f.dk_player_id.astype(str), f.id.astype(str))); name = dict(zip(f.dk_player_id.astype(str), f.display_name.astype(str)))
    game = dict(zip(f.dk_player_id.astype(str), f.game_id.astype(str))); sal = dict(zip(f.dk_player_id.astype(str), pd.to_numeric(f.salary, errors="coerce").fillna(0)))
    book = pd.read_csv(run / "book.csv", dtype=str); n = len(book)
    inc = np.load(bsrc / "incumbent_player_scores.npy"); hs = np.load(bsrc / "corrected_hsim_player_scores.npy")
    rows = []
    full_pos = {}; sh = {"k": "n/a"}
    if a.shadows:
        sh = json.load(open(a.shadows)); pos_of = {k: {r: i + 1 for i, r in enumerate(v["book_ranks"])} for k, v in sh["orderings"].items()}  # top-k only
        for k in ("cov220_hsim", "cov220_inc", "cov200_dual", "nov_ladder", "world_leader", "broad", "hsim_p220"):
            if k in sh["orderings"]: full_pos[k] = pos_of[k]
    # learned-score outputs: paid-book positions (for the paid run) or per-lineup scores (for a learned shadow book dir)
    learned, lscores = {}, None
    for lj in pathlib.Path("/home/erich/week1-sunday").glob("learned-*/paid_book_positions.json"):
        try:
            rec = json.load(open(lj))
            if pathlib.Path(rec.get("source_run", "")).resolve() == run.resolve(): learned = rec["positions"]
        except Exception: pass
    try:
        rec = json.load(open(run / "receipt.json")).get("learned_shadow")
        if rec and (run.parent / "candidate_scores.csv").exists():
            cs = pd.read_csv(run.parent / "candidate_scores.csv").set_index("cand"); lscores = cs.loc[rec["source_cand_ids"]].reset_index()
    except Exception: lscores = None
    mk = json.load(open(a.market)) if a.market else None
    # auto-detect sibling vetting / composite outputs for this run (by source_run in their receipts)
    comp_pos, vet_tier = {}, {}
    for cj in pathlib.Path("/home/erich/week1-sunday").glob("composite-*/composite_receipt.json"):
        try:
            rec = json.load(open(cj))
            if pathlib.Path(rec.get("source_run", "")).resolve() == run.resolve():
                comp_pos = {int(i): pidx + 1 for pidx, i in enumerate(rec["order_source_ranks"])}
        except Exception: pass
    for vj in pathlib.Path("/home/erich/week1-sunday").glob("vetted-*/vetting.json"):
        try:
            rec = json.load(open(vj))
            if pathlib.Path(rec.get("source_run", "")).resolve() == run.resolve():
                for lu in rec["lineups"]: vet_tier[int(lu["rank"])] = "HARD" if lu.get("hard") else ("material" if lu.get("material") else ("soft" if lu.get("risk", 0) > 0 else ""))
        except Exception: pass
    for i, row in book.iterrows():
        ids = [str(v) for v in row.tolist()]; fids = [dk2id[d] for d in ids]
        Mi = inc[[idx[p] for p in fids]].sum(axis=0); Mh = hs[[idx[p] for p in fids]].sum(axis=0)
        gc = Counter(game[d] for d in ids)
        r = {"rank": i + 1, "lineup": " | ".join(name[d] for d in ids), "salary": int(sum(sal[d] for d in ids)), "games": len(gc), "max_game": max(gc.values()),
             "inc_mean": round(float(Mi.mean()), 1), "inc_q99": round(float(np.quantile(Mi, .99)), 1), "inc_p220": round(float((Mi >= 220).mean()), 4),
             "hsim_mean": round(float(Mh.mean()), 1), "hsim_q99": round(float(np.quantile(Mh, .99)), 1), "hsim_p220": round(float((Mh >= 220).mean()), 4)}
        for k, pos in full_pos.items(): r[f"pos_{k}"] = pos.get(i + 1, "")
        if comp_pos: r["pos_composite"] = comp_pos.get(i + 1, "")
        if learned:
            for key, col in (("learned-book", "pos_learned_book"), ("learned-pool", "pos_learned_pool"), ("blend-q99", "pos_blend_q99"), ("union", "pos_union")):
                v = learned[key].get(str(i + 1)); r[col] = v if v is not None else ""
            r["learned_pool_rank_in_pool"] = learned["learned_pool_rank_in_pool"].get(str(i + 1), "")
        if lscores is not None:
            ls = lscores.iloc[i]; r["tag"] = ls["tag"]; r["learned_pool_score"] = round(float(ls["learned_pool"]), 3); r["pool_rank_learned"] = int(ls["learned_pool_pos"]); r["pool_rank_blend"] = int(ls["blend_pos"]); r["paid_book_rank"] = "" if pd.isna(ls["book_rank"]) else int(ls["book_rank"])
        if vet_tier: r["vet_tier"] = vet_tier.get(i + 1, "")
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
