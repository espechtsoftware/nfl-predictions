"""Slate-level posterior predictive check (PPC) of a live run against its own simulated worlds.

    python slate_ppc.py <run_dir> <week> <inputs_dir> [--condition-availability] [--dual]
                        [--override "Display Name=served_mean" ...]

Each of the run's 10,000 selection worlds (incumbent bank; the corrected-hsim bank separately) is
treated as a pseudo-realized slate.  For each pool statistic the realized value is ranked among the
world values ("world-rank"; 0.5 = typical, <0.025 or >0.975 = outside the simulator's own range).
With the dead-player and projection defects of a week removed, this separates "the simulator is
miscalibrated" from "one slate is one draw" -- the null that the two-slate sign-flip reading lacked.

--condition-availability  zero, in every world, each skill player projected >= 5 with no box-score
                          row (did not play); the simulator's worlds never contain that outcome.
--override NAME=VALUE     shift that player's draws so his served mean equals VALUE (used here to
                          remove the Week-2 DK-PPG market stand-in, since deleted from production).
Realized DK points: that week's Millionaire FPTS, else box-score DK points, else 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

run, week, inputs = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
cond = "--condition-availability" in sys.argv
overrides = {}
for i, tok in enumerate(sys.argv):
    if tok == "--override":
        name, val = sys.argv[i + 1].rsplit("=", 1)
        overrides[name] = float(val)

fr = pd.read_parquet(run / "frame.parquet")
cands = pd.read_parquet(run / "candidates.parquet")
banks = {"incumbent": np.load(run / "incumbent_player_scores.npy"),
         "corrected hsim": np.load(run / "corrected_hsim_player_scores.npy")}
pos_of = {i: k for k, i in enumerate(fr.id.astype(str))}

own = pd.read_csv(inputs / "milly_own_2026.csv")
own = own[own.week == week].set_index("display_name").fpts
box = pd.read_csv(inputs / "dk_points_2026.csv")
box = box[box.week == week].set_index("player_id").dk
real = np.array([own.get(r.display_name, np.nan) if pd.notna(own.get(r.display_name, np.nan))
                 else box.get(str(r.gsis_id), 0.0) for r in fr.itertuples()], dtype=float)
real = np.nan_to_num(real)
played = fr.gsis_id.astype(str).isin(set(box.index.astype(str))).to_numpy() | (fr.pos == "DST").to_numpy()
proj = fr.mean_projection.to_numpy(float)
dead = (~played) & (proj >= 5)

rows, cols = [], []
for i, s in enumerate(cands.players.astype(str)):
    for pid in s.split(","):
        rows.append(i); cols.append(pos_of[pid])
A = sparse.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(cands), len(fr)))
book = cands.book_rank.notna().to_numpy()
cand_real = A @ real
cand_dead = (A @ dead.astype(np.float32)) > 0
print(f"week {week}: {len(cands)} candidates, book {book.sum()}, players who did not play (proj>=5) {dead.sum()},"
      f" candidates holding one {cand_dead.mean():.3f}")

shift = np.zeros(len(fr))
for name, val in overrides.items():
    k = np.flatnonzero((fr.display_name == name).to_numpy())
    for j in k:
        print(f"override {name}: served {proj[j]:.2f} -> {val:.2f}")
        shift[j] = val - proj[j]


def ppc(D: np.ndarray, label: str) -> None:
    D = D + shift[:, None].astype(np.float32)
    if cond:
        D = D.copy(); D[dead] = 0.0
    sim_mean = A @ D.mean(axis=1)
    dec = pd.qcut(sim_mean, 10, labels=False)
    top, bot = dec == 9, dec == 0
    smc = sim_mean - sim_mean.mean()
    stats_w = {k: [] for k in ("pool mean", "share >= 194", "corr(sim mean, error)", "corr(sim mean, score)",
                               "top-minus-bottom decile error", "book mean", "book max")}
    for s in range(0, D.shape[1], 500):
        S = (A @ D[:, s:s + 500]).astype(np.float32)
        err = S - sim_mean[:, None]
        ec = err - err.mean(axis=0); Sc = S - S.mean(axis=0)
        stats_w["pool mean"].append(S.mean(axis=0))
        stats_w["share >= 194"].append((S >= 194).mean(axis=0))
        stats_w["corr(sim mean, error)"].append(smc @ ec / (np.linalg.norm(smc) * np.linalg.norm(ec, axis=0)))
        stats_w["corr(sim mean, score)"].append(smc @ Sc / (np.linalg.norm(smc) * np.linalg.norm(Sc, axis=0)))
        stats_w["top-minus-bottom decile error"].append(err[top].mean(axis=0) - err[bot].mean(axis=0))
        stats_w["book mean"].append(S[book].mean(axis=0))
        stats_w["book max"].append(S[book].max(axis=0))
    R = cand_real; err = R - sim_mean; ec = err - err.mean(); Rc = R - R.mean()
    realized = {"pool mean": R.mean(), "share >= 194": (R >= 194).mean(),
                "corr(sim mean, error)": smc @ ec / (np.linalg.norm(smc) * np.linalg.norm(ec)),
                "corr(sim mean, score)": smc @ Rc / (np.linalg.norm(smc) * np.linalg.norm(Rc)),
                "top-minus-bottom decile error": err[top].mean() - err[bot].mean(),
                "book mean": R[book].mean(), "book max": R[book].max()}
    print(f"\n=== {label}{' | availability-conditioned' if cond else ''}{' | overrides' if overrides else ''}"
          f" ({D.shape[1]} worlds; simulated pool mean {sim_mean.mean():.2f})")
    print(f"  {'statistic':<32}{'realized':>10}{'q05':>10}{'q50':>10}{'q95':>10}{'world-rank':>12}")
    for k, v in stats_w.items():
        w = np.concatenate(v)
        rank = (w < realized[k]).mean() + 0.5 * (w == realized[k]).mean()
        print(f"  {k:<32}{realized[k]:>10.3f}{np.quantile(w, .05):>10.3f}{np.quantile(w, .5):>10.3f}"
              f"{np.quantile(w, .95):>10.3f}{rank:>12.4f}")


for lab, D in banks.items():
    ppc(D, lab)
if "--dual" in sys.argv:          # the live selector's equal-mass concatenation of both banks
    ppc(np.concatenate([banks["incumbent"], banks["corrected hsim"]], axis=1), "dual (both banks)")
