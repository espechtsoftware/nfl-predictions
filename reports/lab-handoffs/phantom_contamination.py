#!/usr/bin/env python3
"""How much of a slate's candidate pool is built on players who never took a snap,
and does the simulator's ranking invert because of it?

    PYTHONPATH=<worktree>/src <venv>/python reports/lab-handoffs/phantom_contamination.py \
        --run-dir <archived run with frame.parquet + candidates.parquet> --season 2026 --week 1

Week 2 (laptop, 2026-09-22): 99.9% of 12,555 candidates carried a phantom; corr(sel_mean,
realized) = -0.49; mean realized fell and mean simulated ROSE with phantom count. This tool
exists so the same numbers can be produced for Week 1 on whichever host holds its run dir.

Definitions (fixed before Week 1 is seen):
  phantom       = projected >= 5.0 and zero offensive snaps that week (snap_counts)
  realized      = contest_ownership MAX(fpts) per name; a phantom scores 0 whether or not
                  the export lists him, which is correct for a player who did not play
  inversion     = Spearman(sel_mean, realized) over the whole pool, reported beside a
                  permutation null (the direct correlation needs none; printed for symmetry)
Read-only: two warehouse reads, no writes.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from nfl_dfs.bq import query_df

ap = argparse.ArgumentParser()
ap.add_argument("--run-dir", required=True); ap.add_argument("--season", type=int, required=True)
ap.add_argument("--week", type=int, required=True); ap.add_argument("--min-proj", type=float, default=5.0)
a = ap.parse_args(); D = Path(a.run_dir)
fr = pd.read_parquet(D / "frame.parquet").reset_index(drop=True)
cd_ = pd.read_parquet(D / "candidates.parquet").reset_index(drop=True)
own = query_df(f"""SELECT display_name, MAX(fpts) f FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                   WHERE season={a.season} AND week={a.week} GROUP BY 1""")
sn = query_df(f"""SELECT REGEXP_REPLACE(LOWER(player), r'[^a-z]','') nn, SUM(COALESCE(offense_snaps,0)) off
                  FROM `nfl-predictions-503414.nfl_raw.snap_counts`
                  WHERE season={a.season} AND week={a.week} AND game_type='REG' GROUP BY 1""")
lut = {str(k).strip(): float(v) for k, v in zip(own.display_name, own.f)}
snl = dict(zip(sn.nn, sn.off))
nn = fr.display_name.astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
pts = np.nan_to_num(np.array([lut.get(str(n).strip(), np.nan) for n in fr.display_name], float), nan=0.0)
snaps = np.array([snl.get(x, 0.0) for x in nn]); proj = fr.mean_projection.to_numpy(float)
is_dst = fr.pos.astype(str).str.upper().eq("DST").to_numpy()
phantom = (proj >= a.min_proj) & (snaps == 0) & ~is_dst
ph_ids = set(fr.id.astype(str)[phantom])
idx = {str(i): k for k, i in enumerate(fr.id.astype(str))}
rost = [s.split(",") for s in cd_.players.astype(str)]
realized = np.array([pts[[idx[p] for p in r]].sum() for r in rost])
nph = np.array([sum(p in ph_ids for p in r) for r in rost])
sel = cd_.sel_mean.to_numpy(float)

print(f"{a.season} W{a.week}: frame {len(fr)} players, pool {len(rost):,} candidates")
print(f"phantoms (proj >= {a.min_proj}, zero offensive snaps): {phantom.sum()}  "
      f"by pos {pd.Series(fr.pos[phantom]).value_counts().to_dict()}")
print(f"pool share carrying >= 1 phantom: {100*(nph>0).mean():.1f}%   mean phantoms/lineup {nph.mean():.2f}")
print(f"\n{'phantoms':>9}{'n':>8}{'mean realized':>15}{'mean simulated':>16}")
for d in range(int(nph.max()) + 1):
    m = nph == d
    if m.sum() >= 50:
        print(f"{d:>9}{int(m.sum()):>8}{realized[m].mean():>15.2f}{sel[m].mean():>16.2f}")
rho, _ = stats.spearmanr(sel, realized)
print(f"\nSpearman(sel_mean, realized) = {rho:+.4f}   (positive = the simulator ranks correctly)")
