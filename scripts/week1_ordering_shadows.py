"""Frozen within-book ORDERING shadows for a live_week run dir (outcome-blind; graded prospectively).

Usage: python ordering_shadows.py RUN_DIR [--k 30] [--banks-from RUN_DIR_WITH_NPY] [--output PATH]
For the run's selected book (ranks 1..K80/K90), computes several orderings and writes each ordering's top-k set:
  greedy            the selector's own order (ranks 1..k)  -- the entered layout
  inc_mean / hsim_mean      per-lineup simulated mean under the incumbent / corrected-hsim selection bank
  inc_q99 / hsim_q99        per-lineup simulated 99th percentile
  inc_p200 / hsim_p220      per-lineup P(>=200) / P(>=220)
  nov_ladder        PREREG-060's novelty-ladder plan run over the BOOK's dual matrix (first k picks)
  broad             most distinct games, then fewest from any one game, then greedy rank (the Neo4j census phenotype)
  concentrated      the opposite of broad (most from one game first)  -- expected-negative control
  salary_desc       total salary descending (spend the cap first); teams_desc: most distinct teams; max_team_asc: fewest from one team
  rb3_first         3-RB rosters first, then greedy rank
  dkppg_sum         sum of the frame's prior-season DK points per game (the "proven performers" heuristic)
  ptail_inc / ptail_hsim   sum over the 9 players of P(player >= 25) from each selection bank (marginal tails, not the joint)
  law_agreement     lineups both laws rank highly (max of the two q99 ranks, ascending)
  player_novelty    greedy re-ordering that minimises player overlap with the lineups already placed (roster diversity first)
  reverse_greedy    ranks 80..1 (control)
  random            a seeded random k-subset (grading reference)
No realized score is read.  Grade after the slate: max realized score of each set vs the entered set.
"""
import argparse, hashlib, importlib.util, json, pathlib, sys
from collections import Counter
from datetime import UTC, datetime
import numpy as np, pandas as pd

NOV_SRC = pathlib.Path("/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/scripts/prereg060_qd_frontier.py")

def load(run, banks_from):
    run = pathlib.Path(run); bsrc = pathlib.Path(banks_from or run)
    f = pd.read_parquet(bsrc / "frame.parquet"); idx = {str(i): k for k, i in enumerate(f.id.astype(str))}
    c = pd.read_parquet(run / "candidates.parquet"); book = c[c.book_rank.notna()].sort_values("book_rank").reset_index(drop=True)
    inc = np.load(bsrc / "incumbent_player_scores.npy"); hs = np.load(bsrc / "corrected_hsim_player_scores.npy")
    rosters = [pl.split(",") for pl in book.players]
    missing = [p for pl in rosters for p in pl if p not in idx]
    if missing: raise SystemExit(f"{len(missing)} book players absent from the bank frame (banks-from mismatch): {missing[:5]}")
    def totals(bank): return np.stack([bank[[idx[p] for p in pl]].sum(axis=0) for pl in rosters]).astype(np.float32)
    game = dict(zip(f.id.astype(str), f.game_id.astype(str)))
    return run, book, rosters, totals(inc), totals(hs), game

def nov_plan(M, k):
    spec = importlib.util.spec_from_file_location("p060", NOV_SRC); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return [int(i) for i in m._novelty_plan(M, k)], hashlib.sha256(NOV_SRC.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--k", type=int, default=30); ap.add_argument("--banks-from"); ap.add_argument("--output"); a = ap.parse_args()
    run, book, rosters, Minc, Mhs, game = load(a.run, a.banks_from)
    n, k = len(book), a.k
    stats = {"inc_mean": Minc.mean(axis=1), "hsim_mean": Mhs.mean(axis=1), "inc_q99": np.quantile(Minc, .99, axis=1), "hsim_q99": np.quantile(Mhs, .99, axis=1),
             "inc_p200": (Minc >= 200).mean(axis=1), "hsim_p220": (Mhs >= 220).mean(axis=1)}
    orders = {"greedy": list(range(n))}
    for name, v in stats.items(): orders[name] = list(np.lexsort((np.arange(n), -v)))
    dual = np.concatenate([Minc, Mhs], axis=1); plan, nov_sha = nov_plan(dual, k); orders["nov_ladder"] = plan + [i for i in range(n) if i not in plan]
    counts = [Counter(game[p] for p in pl) for pl in rosters]
    orders["broad"] = sorted(range(n), key=lambda i: (-len(counts[i]), max(counts[i].values()), i))
    orders["concentrated"] = sorted(range(n), key=lambda i: (-max(counts[i].values()), len(counts[i]), i))
    f = pd.read_parquet(pathlib.Path(a.banks_from or a.run) / "frame.parquet"); fid = f.id.astype(str)
    team = dict(zip(fid, f.team.astype(str))); pos = dict(zip(fid, f.pos.astype(str))); sal = dict(zip(fid, pd.to_numeric(f.salary, errors="coerce").fillna(0)))
    ppg = dict(zip(fid, pd.to_numeric(f.get("dk_ppg"), errors="coerce").fillna(0))) if "dk_ppg" in f.columns else {}
    tcounts = [Counter(team[p] for p in pl) for pl in rosters]
    orders["salary_desc"] = sorted(range(n), key=lambda i: (-sum(sal[p] for p in rosters[i]), i))
    orders["teams_desc"] = sorted(range(n), key=lambda i: (-len(tcounts[i]), i))
    orders["max_team_asc"] = sorted(range(n), key=lambda i: (max(tcounts[i].values()), i))
    orders["rb3_first"] = sorted(range(n), key=lambda i: (-sum(1 for p in rosters[i] if pos[p] == "RB"), i))
    if ppg: orders["dkppg_sum"] = sorted(range(n), key=lambda i: (-sum(ppg[p] for p in rosters[i]), i))
    bsrc = pathlib.Path(a.banks_from or a.run); pinc = np.load(bsrc / "incumbent_player_scores.npy"); phs = np.load(bsrc / "corrected_hsim_player_scores.npy")
    idx = {str(i): k for k, i in enumerate(fid)}
    tail_inc = {p: float((pinc[idx[p]] >= 25).mean()) for pl in rosters for p in pl}; tail_hs = {p: float((phs[idx[p]] >= 25).mean()) for pl in rosters for p in pl}
    orders["ptail_inc"] = sorted(range(n), key=lambda i: (-sum(tail_inc[p] for p in rosters[i]), i))
    orders["ptail_hsim"] = sorted(range(n), key=lambda i: (-sum(tail_hs[p] for p in rosters[i]), i))
    r_inc = np.argsort(np.argsort(-stats["inc_q99"])); r_hs = np.argsort(np.argsort(-stats["hsim_q99"]))
    orders["law_agreement"] = sorted(range(n), key=lambda i: (max(r_inc[i], r_hs[i]), i))
    placed, remaining, used = [], list(range(n)), Counter()
    while remaining:   # player-novelty greedy: fewest already-used players, ties by greedy rank
        j = min(remaining, key=lambda i: (sum(used[p] for p in rosters[i]), i)); placed.append(j); remaining.remove(j); used.update(rosters[j])
    orders["player_novelty"] = placed
    orders["reverse_greedy"] = list(range(n - 1, -1, -1))
    orders["random"] = list(np.random.default_rng(2026).permutation(n))
    out = {"version": "ordering-shadows-v2", "run_dir": str(run), "book_size": n, "k": k, "frozen_at_utc": datetime.now(UTC).isoformat(), "banks_from": str(a.banks_from or run),
           "novelty_source_sha256": nov_sha, "orderings": {}}
    for name, order in orders.items():
        top = [int(i) for i in order[:k]]; sub_inc = Minc[top].max(axis=0); sub_hs = Mhs[top].max(axis=0)
        out["orderings"][name] = {"book_ranks": [int(book.book_rank.iloc[i]) for i in top], "rosters": [rosters[i] for i in top], "names": [book.names.iloc[i] for i in top],
            "sim_receipts": {"inc_emax": float(sub_inc.mean()), "inc_p200": float((sub_inc >= 200).mean()), "inc_p220": float((sub_inc >= 220).mean()),
                             "hsim_emax": float(sub_hs.mean()), "hsim_p200": float((sub_hs >= 200).mean()), "hsim_p220": float((sub_hs >= 220).mean()),
                             "overlap_with_greedy": len(set(top) & set(range(k))), "mean_games": float(np.mean([len(counts[i]) for i in top])), "mean_max_game": float(np.mean([max(counts[i].values()) for i in top]))}}
    out["book_sim_receipts"] = {"inc_emax": float(Minc.max(axis=0).mean()), "hsim_emax": float(Mhs.max(axis=0).mean())}
    path = pathlib.Path(a.output or run / f"ordering_shadows_k{k}.json"); path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"{path}  book {n}  k {k}  bank {out['banks_from']}")
    print(f"{'ordering':11s} {'inc E[max]':>10s} {'inc P220':>8s} {'hsim E[max]':>11s} {'hsim P220':>9s} {'ovl':>4s} {'games':>6s} {'maxg':>5s}")
    for name, o in out["orderings"].items():
        r = o["sim_receipts"]; print(f"{name:11s} {r['inc_emax']:10.1f} {r['inc_p220']:8.3f} {r['hsim_emax']:11.1f} {r['hsim_p220']:9.3f} {r['overlap_with_greedy']:4d} {r['mean_games']:6.2f} {r['mean_max_game']:5.2f}")
    print(f"{'whole book':11s} {out['book_sim_receipts']['inc_emax']:10.1f} {'':8s} {out['book_sim_receipts']['hsim_emax']:11.1f}")

if __name__ == "__main__":
    main()
