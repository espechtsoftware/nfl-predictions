"""Re-run of the laptop's player lower-tail PIT with realized zeros kept.
Same bank, seed and filter (skill, proj >= 5) as reports/lab-handoffs/2026-09-22-tail_calibration-by-season.py.
Randomized PIT: P(d < a) + U * P(d == a), so point masses at 0 are handled fairly. Saves rows for a follow-up."""
import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from nfl2.data import slates
from nfl2.pipeline import simulate_slate, slate_frame, slate_seed
SEASON = int(sys.argv[1]); OUT = sys.argv[2]
ENV = {"NFL2_ENSEMBLE": "1", "NFL2_CENTER": "mean"}
rng = np.random.default_rng(7)
rows = []
for s, w in [sw for sw in slates("k1") if sw[0] == SEASON]:
    fr = slate_frame(s, w)
    draws = simulate_slate(fr, n_sims=10_000, seed=slate_seed(SEASON, s, w), law_env=ENV)
    act = pd.to_numeric(fr.actual, errors="coerce").to_numpy(float)
    proj = pd.to_numeric(fr.mean_projection, errors="coerce").to_numpy(float)
    pos = fr.pos.astype(str).to_numpy(); active = fr.was_active.to_numpy()
    for i in range(len(fr)):
        if pos[i] in ("QB", "RB", "WR", "TE") and proj[i] >= 5 and np.isfinite(act[i]):
            d = draws[i]
            lo, eq = float((d < act[i]).mean()), float((d == act[i]).mean())
            rows.append({"season": SEASON, "week": w, "id": fr.id.iloc[i], "name": fr.name.iloc[i], "team": fr.team.iloc[i],
                         "pos": pos[i], "salary": fr.salary.iloc[i], "proj": proj[i], "act": act[i],
                         "active": active[i], "pit_old": float((d <= act[i]).mean()), "pit": lo + rng.uniform() * eq,
                         "p_zero_sim": float((d <= 0).mean()), "p10": float(np.quantile(d, .1)),
                         "p50": float(np.quantile(d, .5)), "mean_sim": float(d.mean()), "sd_sim": float(d.std())})
    print(f"{SEASON}-W{w:02d} done ({len(rows)})", flush=True)
pd.DataFrame(rows).to_parquet(OUT)
print("DONE")
