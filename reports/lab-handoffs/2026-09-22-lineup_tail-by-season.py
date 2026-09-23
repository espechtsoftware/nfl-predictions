"""Diagnostic: is the missing ceiling the JOINT tail? 2021 slates (outside L01). Per slate: incumbent bank (10,000 worlds),
a 240-lineup boom pool (production stack), each lineup's realized score's PIT in its own simulated distribution. Split by
the max number of rostered players from one game (4 = the stack minimum; 5+ = game-heavy). Calibrated: 1% above p99."""
import warnings, numpy as np, pandas as pd
from collections import Counter
warnings.filterwarnings("ignore")
from nfl2.data import slates
from nfl2.pipeline import candidate_actual, candidate_matrix, generate_candidates, simulate_slate, slate_frame, slate_seed
import sys
SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2021
ENV = {"NFL2_ENSEMBLE": "1", "NFL2_CENTER": "mean"}
rows = []
for s, w in [sw for sw in slates("k1") if sw[0] == SEASON]:
    fr = slate_frame(s, w)
    gen = simulate_slate(fr, n_sims=10_000, seed=slate_seed(2121, s, w), law_env=ENV)
    judge = simulate_slate(fr, n_sims=10_000, seed=slate_seed(2171, s, w), law_env=ENV)   # independent worlds for the PIT
    cands = generate_candidates(fr, gen, n_lev=0, n_boom=240, env=ENV)
    mat = candidate_matrix(fr, cands, judge); act = np.asarray(candidate_actual(fr, cands), float)
    game = dict(zip(fr.id.astype(str), fr.game_id.astype(str)))
    for j, lu in enumerate(cands):
        mx = max(Counter(game[str(p["id"])] for p in lu.players).values())
        rows.append({"week": w, "maxgame": mx, "act": act[j], "pit": float((mat[j] <= act[j]).mean()),
                     "p99": float(np.quantile(mat[j], 0.99)), "mean": float(mat[j].mean())})
    print(f"{SEASON}-W{w:02d} done", flush=True)
r = pd.DataFrame(rows); r["grp"] = np.where(r.maxgame >= 5, "5+ from one game", "4 from one game")
print(f"\nlineups {len(r)} over {r.week.nunique()} slates; sim mean {r['mean'].mean():.1f} vs realized {r.act.mean():.1f}")
for label, g in [("ALL", r)] + list(r.groupby("grp")):
    n = len(g)
    print(f"  {label:18s} n={n:5d}  >p99 {100*(g.pit>0.99).mean():5.2f}% (1)  >p95 {100*(g.pit>0.95).mean():5.2f}% (5)  "
          f">p90 {100*(g.pit>0.90).mean():5.2f}% (10)  mean PIT {g.pit.mean():.3f}")
print("\nby slate, share of lineups above their sim p99 (lineups within a slate are strongly correlated; slates are the unit):")
print(r.groupby("week").apply(lambda g: round(100 * (g.pit > 0.99).mean(), 1)).to_string())
