import time, logging, numpy as np, pandas as pd
logging.disable(logging.WARNING)
from nfl2.pipeline import PRODUCTION_STACK, generate_candidates
D = "/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/results/live/2026-w02/20260919T151024628419Z-2dc116c"
fr = pd.read_parquet(f"{D}/frame.parquet").reset_index(drop=True); draws = np.load(f"{D}/incumbent_player_scores.npy").astype(np.float64)
for n in (80, 160):
    for cap in (None, 4):
        env = {} if cap is None else {"MAX_PER_GAME": str(cap)}
        t = time.perf_counter(); lev = generate_candidates(fr, draws, n_lev=n, n_boom=0, stack=PRODUCTION_STACK, env=env); dt = time.perf_counter() - t
        print(f"lev n={n:3d} cap={cap}: {len(lev)} lineups in {dt:6.1f}s", flush=True)
