#!/usr/bin/env python3
"""Supply vs retrieval for one archived slate: did the lineup exist, or did we miss it?

    PYTHONPATH=<worktree>/src <venv>/python reports/lab-handoffs/supply_vs_retrieval.py \
        --run-dir <archived run with frame.parquet + candidates.parquet> --season 2026 --week 2

Reports the pool oracle, the entered book's best, the retrieval gap, threshold
counts in-pool vs entered, the minimum roster edit distance from the book to the
pool's best candidate, and which of its players were never rostered at all.

Retrospective: it uses realized points, so it is a diagnostic and not a gate.
Read-only -- one warehouse read, no writes.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from nfl_dfs.bq import query_df

ap = argparse.ArgumentParser()
ap.add_argument("--run-dir", required=True)
ap.add_argument("--season", type=int, required=True)
ap.add_argument("--week", type=int, required=True)
a = ap.parse_args()
D = Path(a.run_dir)

fr = pd.read_parquet(D / "frame.parquet").reset_index(drop=True)
cd_ = pd.read_parquet(D / "candidates.parquet").reset_index(drop=True)
own = query_df(f"""SELECT display_name, MAX(fpts) fpts
                   FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                   WHERE season={a.season} AND week={a.week} GROUP BY 1""")
lut = dict(zip(own.display_name.astype(str), own.fpts.astype(float)))
idx = {str(i): k for k, i in enumerate(fr.id.astype(str))}
pts = np.nan_to_num(np.array([lut.get(str(n), np.nan) for n in fr.display_name], float), nan=0.0)
missing_players = int(np.isnan([lut.get(str(n), np.nan) for n in fr.display_name]).sum())

rosters = [frozenset(s.split(",")) for s in cd_.players.astype(str)]
realized = np.array([pts[[idx[p] for p in r]].sum() for r in rosters])
book_mask = cd_.book_rank.notna().to_numpy()
book_idx = np.where(book_mask)[0]
if not len(book_idx):
    raise SystemExit("no delivered book rows (book_rank all null) in this run")
book_best = book_idx[int(np.argmax(realized[book_idx]))]
oracle = int(np.argmax(realized))

print(f"candidates {len(cd_)}   entered {book_mask.sum()}   "
      f"players with no standings row {missing_players}/{len(fr)}")
print(f"pool oracle   {realized[oracle]:.2f}")
print(f"book best     {realized[book_best]:.2f}")
print(f"RETRIEVAL GAP {realized[oracle] - realized[book_best]:.2f}")
K, N = int(book_mask.sum()), len(rosters)
print("  threshold   in pool   entered   expected-if-random   lift   P(random enters 0)")
for t in (150, 170, 194, 200, 220):
    a_ = int((realized >= t).sum()); b_ = int((realized[book_mask] >= t).sum())
    if not a_:
        continue
    exp_ = K * a_ / N
    p0 = 1.0
    for i in range(K):
        p0 *= (N - a_ - i) / (N - i)
    lift = (b_ / exp_) if exp_ else float("nan")
    print(f"  >= {t:4d}    {a_:6d}   {b_:5d}        {exp_:8.2f}       {lift:5.2f}x      {p0:6.1%}")
print("  (a zero entered count is only meaningful when P(random enters 0) is SMALL)")

best = rosters[oracle]
dists = [9 - len(best & rosters[i]) for i in book_idx]
obs = min(dists)
# NULL, added 2026-09-22 after this tool's first output was over-read. A K-row
# sample from a pool thousands of times larger misses almost everything by
# construction, so every count below needs dividing by what chance would give.
rng = np.random.default_rng(20260922)
dall = np.array([9 - len(best & r) for r in rosters])
sims = np.array([dall[rng.choice(len(rosters), size=len(book_idx), replace=False)].min()
                 for _ in range(2000)])
print(f"\nmin edit distance book -> pool best: {obs} of 9 (median {int(np.median(dists))})")
print(f"  NULL over 2000 random books of the same size: median {int(np.median(sims))}, "
      f"mean {sims.mean():.2f}, P(random <= observed) = {(sims <= obs).mean():.1%}")
entered = set().union(*[rosters[i] for i in book_idx])
never = [p for p in best if p not in entered]
print(f"players in the pool best never rostered anywhere in the book: {len(never)}")
for p in never:
    k = idx[p]
    print(f"   {fr.pos[k]:4s} {str(fr.display_name[k]):24s} ${fr.salary[k]:<6} "
          f"proj={fr.mean_projection[k]:6.2f} realized={pts[k]:6.2f}")
