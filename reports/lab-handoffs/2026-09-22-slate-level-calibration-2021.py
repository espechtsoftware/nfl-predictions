"""Diagnostic: is the simulator's slate LEVEL under-dispersed? 2021 slates (outside L01). Per slate: a 120-lineup boom pool on
one bank; on an independent bank, the per-world mean score of that pool; the realized pool mean's rank among the 10,000
world means. Calibrated levels give ranks ~Uniform(0,1); an under-dispersed level piles ranks near 0 and 1."""
import warnings, numpy as np, pandas as pd
from scipy.stats import kstest
warnings.filterwarnings("ignore")
from nfl2.data import slates
from nfl2.pipeline import candidate_actual, candidate_matrix, generate_candidates, simulate_slate, slate_frame, slate_seed
ENV = {"NFL2_ENSEMBLE": "1", "NFL2_CENTER": "mean"}
out = []
for s, w in [sw for sw in slates("k1") if sw[0] == 2021]:
    fr = slate_frame(s, w)
    gen = simulate_slate(fr, n_sims=10_000, seed=slate_seed(2221, s, w), law_env=ENV)
    judge = simulate_slate(fr, n_sims=10_000, seed=slate_seed(2271, s, w), law_env=ENV)
    cands = generate_candidates(fr, gen, n_lev=0, n_boom=120, env=ENV)
    wm = candidate_matrix(fr, cands, judge).mean(axis=0); real = float(np.mean(candidate_actual(fr, cands)))
    out.append({"week": w, "sim_level_mean": wm.mean(), "sim_level_sd": wm.std(), "realized": real, "rank": float((wm <= real).mean())})
    print(f"2021-W{w:02d}: realized {real:6.1f}  sim {wm.mean():6.1f} ± {wm.std():4.1f}  rank {out[-1]['rank']:.3f}", flush=True)
r = pd.DataFrame(out)
print(f"\nranks: {sorted(r['rank'].round(3).tolist())}")
print(f"share of slates in the outer 10% (rank < .05 or > .95): {((r['rank'] < .05) | (r['rank'] > .95)).mean():.2f} (calibrated 0.10)")
print(f"KS vs Uniform(0,1): p = {kstest(r['rank'], 'uniform').pvalue:.3f}; realized-level sd across slates {r.realized.std():.1f} vs mean sim within-slate sd {r.sim_level_sd.mean():.1f}")
