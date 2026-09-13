"""Build the D*_NOV live arm from a live_week run dir: PREREG-060's frozen novelty-ladder selector over the run's
candidate pool on the run's own dual (incumbent + corrected-hsim) banks, written as a sibling run dir whose
book.csv (DK slot order, dk_player_ids) and frame.parquet the production upload emitter accepts.  Outcome-blind.
Usage: python nov_book.py RUN_DIR [--k 80] [--output-dir DIR]"""
import argparse, csv, hashlib, importlib.util, json, pathlib, shutil
from datetime import UTC, datetime
import numpy as np, pandas as pd

NOV_SRC = pathlib.Path("/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/scripts/prereg060_qd_frontier.py")
SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")

def slot_order(players, pos):
    by = {"QB": [], "RB": [], "WR": [], "TE": [], "DST": []}
    for p in players: by[pos[p]].append(p)
    row = [by["QB"][0], by["RB"][0], by["RB"][1], by["WR"][0], by["WR"][1], by["WR"][2], by["TE"][0]]
    flex = by["RB"][2:] + by["WR"][3:] + by["TE"][1:]
    assert len(flex) == 1 and len(by["QB"]) == 1 and len(by["DST"]) == 1, (by,)
    return row + [flex[0], by["DST"][0]]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--k", type=int, default=80); ap.add_argument("--output-dir"); a = ap.parse_args()
    run = pathlib.Path(a.run); out = pathlib.Path(a.output_dir or (str(run) + "-nov")); out.mkdir(parents=True, exist_ok=True)
    f = pd.read_parquet(run / "frame.parquet"); idx = {str(i): k for k, i in enumerate(f.id.astype(str))}
    dkid = dict(zip(f.id.astype(str), f.dk_player_id.astype(str))); pos = dict(zip(f.id.astype(str), f.pos.astype(str))); name = dict(zip(f.id.astype(str), f.display_name.astype(str)))
    c = pd.read_parquet(run / "candidates.parquet"); rosters = [pl.split(",") for pl in c.players]
    inc = np.load(run / "incumbent_player_scores.npy").astype(np.float32); hs = np.load(run / "corrected_hsim_player_scores.npy").astype(np.float32)
    def totals(bank): return np.stack([bank[[idx[p] for p in pl]].sum(axis=0) for pl in rosters])
    M = np.concatenate([totals(inc), totals(hs)], axis=1)
    spec = importlib.util.spec_from_file_location("p060", NOV_SRC); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    plan = [int(i) for i in mod._novelty_plan(M, a.k)]
    assert len(plan) == a.k and len(set(plan)) == a.k
    demax = set(c.index[c.book_rank.notna()].tolist())
    with (out / "book.csv").open("w", newline="") as h:
        w = csv.writer(h); w.writerow(SLOTS)
        for i in plan: w.writerow([dkid[p] for p in slot_order(rosters[i], pos)])
    with (out / "book_names.csv").open("w", newline="") as h:
        w = csv.writer(h); w.writerow(("nov_rank", "cand", "tag", "demax_book_rank") + SLOTS)
        for r, i in enumerate(plan, 1): w.writerow([r, int(c.cand.iloc[i]), c.tag.iloc[i], (int(c.book_rank.iloc[i]) if pd.notna(c.book_rank.iloc[i]) else "")] + [name[p] for p in slot_order(rosters[i], pos)])
    shutil.copy(run / "frame.parquet", out / "frame.parquet"); shutil.copy(run / "receipt.json", out / "source_receipt.json")
    Mi, Mh = M[:, :inc.shape[1]], M[:, inc.shape[1]:]
    rec = {"version": "nov-book-v1", "source_run": str(run), "k": a.k, "candidates": len(c), "novelty_source_sha256": hashlib.sha256(NOV_SRC.read_bytes()).hexdigest(),
           "ladder": [float(t) for t in mod.LADDER], "built_utc": datetime.now(UTC).isoformat(), "plan": plan, "overlap_with_demax_book": len(set(plan) & demax),
           "sim_receipts": {"nov_inc_emax": float(Mi[plan].max(axis=0).mean()), "nov_inc_p220": float((Mi[plan].max(axis=0) >= 220).mean()), "nov_hsim_emax": float(Mh[plan].max(axis=0).mean()),
                            "nov_hsim_p220": float((Mh[plan].max(axis=0) >= 220).mean()), "demax_inc_emax": float(Mi[sorted(demax)].max(axis=0).mean()) if demax else None,
                            "demax_hsim_emax": float(Mh[sorted(demax)].max(axis=0).mean()) if demax else None}}
    for kk in (10, 20, 30):
        rec["sim_receipts"][f"nov_top{kk}_inc_emax"] = float(Mi[plan[:kk]].max(axis=0).mean()); rec["sim_receipts"][f"nov_top{kk}_hsim_emax"] = float(Mh[plan[:kk]].max(axis=0).mean())
    (out / "nov_receipt.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "plan"}, indent=1)); print("book ->", out / "book.csv")

if __name__ == "__main__":
    main()
