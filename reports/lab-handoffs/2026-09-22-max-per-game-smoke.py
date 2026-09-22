"""Outcome-blind mechanics smoke of MAX_PER_GAME on the archived Week-2 frame (nfl2 69f98a7). No outcomes read."""
import time, collections, logging, numpy as np, pandas as pd
logging.disable(logging.WARNING)
from nfl2.pipeline import PRODUCTION_STACK, generate_candidates, candidate_matrix
from nfl2.selectors import select_expected_max
D = "/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/results/live/2026-w02/20260919T151024628419Z-2dc116c"
fr = pd.read_parquet(f"{D}/frame.parquet").reset_index(drop=True)
draws = np.load(f"{D}/incumbent_player_scores.npy").astype(np.float64)
assert draws.shape[0] == len(fr)
game = dict(zip(fr.id.astype(str), fr.game_id.astype(str)))
NL, NB = 20, 150
res = {}
for cap in (None, 5, 4, 3):
    env = {} if cap is None else {"MAX_PER_GAME": str(cap)}
    led = []
    t = time.perf_counter(); lev = generate_candidates(fr, draws, n_lev=NL, n_boom=0, stack=PRODUCTION_STACK, env=env, ledger=led); tl = time.perf_counter() - t
    t = time.perf_counter(); boom = generate_candidates(fr, draws, n_lev=0, n_boom=NB, stack=PRODUCTION_STACK, env=env, ledger=led, existing=lev); tb = time.perf_counter() - t
    cands = lev + boom
    mx = [max(collections.Counter(game[str(i)] for i in lu.ids).values()) for lu in cands]
    st = collections.Counter((r.get("family"), r.get("status")) for r in led)
    res[cap] = cands
    print(f"cap={cap}: lev {len(lev)}/{NL} in {tl:5.1f}s ({tl/NL:.2f}s/solve) | boom {len(boom)}/{NB} in {tb:5.1f}s ({tb/NB:.3f}s/solve) | "
          f"max per game in pool: {collections.Counter(mx)} | ledger {dict(st)}")
    if cap: assert all(m <= cap for m in mx), "cap violated"
for cap in (None, 4):
    c = res[cap]
    if len(c) < 10: print(f"cap={cap}: too few candidates to select"); continue
    T = candidate_matrix(fr, c, draws); book = list(select_expected_max(T, 10))
    print(f"cap={cap}: dual-matrix-free expected-max K10 ok, {len(set(book))} distinct, tags {collections.Counter(c[i].tag for i in book)}")
