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
for t in (150, 170, 194, 200, 220):
    a_, b_ = int((realized >= t).sum()), int((realized[book_mask] >= t).sum())
    flag = "  <- generated, none entered" if a_ and not b_ else ""
    print(f"  >= {t}: {a_:6d} in pool {b_:4d} entered{flag}")

best = rosters[oracle]
dists = [9 - len(best & rosters[i]) for i in book_idx]
print(f"\nmin edit distance book -> pool best: {min(dists)} of 9 (median {int(np.median(dists))})")
entered = set().union(*[rosters[i] for i in book_idx])
never = [p for p in best if p not in entered]
print(f"players in the pool best never rostered anywhere in the book: {len(never)}")
for p in never:
    k = idx[p]
    print(f"   {fr.pos[k]:4s} {str(fr.display_name[k]):24s} ${fr.salary[k]:<6} "
          f"proj={fr.mean_projection[k]:6.2f} realized={pts[k]:6.2f}")
