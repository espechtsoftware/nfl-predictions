"""Rebuild the delivered dual-Emax candidate x world matrices from the archived sidecars.

Reads only from the CLEAN release worktree; writes only to the scratchpad.
"""
import numpy as np, pandas as pd, hashlib, json, sys
from pathlib import Path

R = Path("/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c/results/live/2026-w02/20260919T153008787414Z-2dc116c")
OUT = Path(__file__).resolve().parent

rec = json.loads((R / "receipt.json").read_text())

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

# fail closed on the pinned sidecar identities
for name, key in (("incumbent_player_scores.npy", "incumbent_player_scores"),
                  ("corrected_hsim_player_scores.npy", "corrected_hsim_player_scores")):
    got = sha(R / name)
    want = rec["a5_sidecars"][key]["sha256"]
    if got != want:
        sys.exit(f"{name} sha256 {got} != receipted {want}")
    print(f"{name} sha256 OK")

fr = pd.read_parquet(R / "frame.parquet")
cd = pd.read_parquet(R / "candidates.parquet")
inc = np.load(R / "incumbent_player_scores.npy")
hs = np.load(R / "corrected_hsim_player_scores.npy")
assert inc.shape[0] == len(fr) == hs.shape[0], (inc.shape, len(fr), hs.shape)

idx = {pid: i for i, pid in enumerate(fr.id.astype(str))}
rosters = [[idx[p] for p in s.split(",")] for s in cd.players.astype(str)]
assert all(len(r) == 9 for r in rosters)
rix = np.array(rosters, dtype=np.int32)                     # (12555, 9)

# candidate_matrix: sum the roster's player rows, per world bank
T  = inc[rix].sum(axis=1).astype(np.float32)
Tv = hs[rix].sum(axis=1).astype(np.float32)
print("T", T.shape, "Tv", Tv.shape)

# sel_mean is the incumbent-bank mean of the lineup: an independent check that
# the roster->row mapping is right.
d = np.abs(T.mean(axis=1) - cd.sel_mean.to_numpy(np.float32))
print(f"sel_mean reproduction: max abs diff {d.max():.6f}, mean {d.mean():.8f}")

np.save(OUT / "T_inc.npy", T)
np.save(OUT / "T_hs.npy", Tv)
np.save(OUT / "roster_idx.npy", rix)
fr.to_parquet(OUT / "frame.parquet")
cd.to_parquet(OUT / "cands.parquet")
print("written")
