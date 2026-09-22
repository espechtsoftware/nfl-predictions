"""Out-of-sample cap test: rebuild Week-1 matrices from the archived banks."""
import numpy as np, pandas as pd, json, hashlib
from pathlib import Path
R = Path("/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01/20260912T204921889774Z-e7255e9")
rec = json.loads((R/"receipt.json").read_text())
for name, key in (("incumbent_player_scores.npy","incumbent_player_scores"),
                  ("corrected_hsim_player_scores.npy","corrected_hsim_player_scores")):
    h = hashlib.sha256((R/name).read_bytes()).hexdigest()
    want = (rec.get("a5_sidecars") or {}).get(key, {}).get("sha256")
    print(f"{name}: {'OK' if h==want else 'MISMATCH'}")
fr = pd.read_parquet(R/"frame.parquet").reset_index(drop=True)
cd = pd.read_parquet(R/"candidates.parquet").reset_index(drop=True)
inc = np.load(R/"incumbent_player_scores.npy"); hs = np.load(R/"corrected_hsim_player_scores.npy")
idx = {p:i for i,p in enumerate(fr.id.astype(str))}
rix = np.array([[idx[p] for p in s.split(",")] for s in cd.players.astype(str)], dtype=np.int32)
T = inc[rix].sum(axis=1).astype(np.float32); Tv = hs[rix].sum(axis=1).astype(np.float32)
d = np.abs(T.mean(axis=1) - cd.sel_mean.to_numpy(np.float32)).max()
print(f"sel_mean reproduction: max abs diff {d:.6f}")
print(f"candidates {len(cd)}  players {len(fr)}  worlds {T.shape[1]}x2  book {int(cd.book_rank.notna().sum())}")
np.save("T_inc.npy", T); np.save("T_hs.npy", Tv); np.save("rix.npy", rix)
fr.to_parquet("frame.parquet"); cd.to_parquet("cands.parquet")
