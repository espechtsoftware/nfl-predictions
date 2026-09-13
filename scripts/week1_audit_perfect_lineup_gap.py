"""Perfect-lineup gap: the realized optimal DK lineup per historical slate (MILP on actual points) vs the simulator's own
per-world optimal lineups (MILP on simulated draws, sampled worlds). Same objective (max over ALL legal lineups), so the
two are directly comparable. Writes JSON + a markdown summary."""
import json, sys, time, pathlib, numpy as np, pandas as pd, pulp
from nfl2.data import DEV_SEASONS, slates
from nfl2.pipeline import simulate_slate, slate_frame, slate_seed
ENV = {"NFL2_ENSEMBLE": "1", "NFL2_CENTER": "mean"}
OUT = pathlib.Path("/home/erich/week1-sunday/audit"); SKILL = ("QB", "RB", "WR", "TE")

def best_lineup(fr, pts):
    ids = list(range(len(fr))); pos = fr.pos.astype(str).to_numpy(); sal = pd.to_numeric(fr.salary, errors="coerce").fillna(99999).to_numpy(); pts = np.nan_to_num(np.asarray(pts, float), nan=0.0)
    prob = pulp.LpProblem("perfect", pulp.LpMaximize); x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in ids]
    prob += pulp.lpSum(x[i] * pts[i] for i in ids)
    prob += pulp.lpSum(x) == 9; prob += pulp.lpSum(x[i] * sal[i] for i in ids) <= 50000
    for p, lo, hi in (("QB", 1, 1), ("RB", 2, 3), ("WR", 3, 4), ("TE", 1, 2), ("DST", 1, 1)):
        prob += pulp.lpSum(x[i] for i in ids if pos[i] == p) >= lo; prob += pulp.lpSum(x[i] for i in ids if pos[i] == p) <= hi
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=20)); return float(pulp.value(prob.objective))

todo = [sw for sw in slates("k1") if sw[0] in DEV_SEASONS and sw[0] > min(DEV_SEASONS)]
res = {"realized_perfect": {}, "sim_perfect": {}}
t0 = time.time()
for s, w in todo:   # realized perfect lineup for every dev slate
    fr = slate_frame(s, w); fr = fr[fr.pos.isin(SKILL + ("DST",))].reset_index(drop=True)
    res["realized_perfect"][f"{s}-w{w}"] = best_lineup(fr, pd.to_numeric(fr.actual, errors="coerce").fillna(0.0).to_numpy())
    print(f"realized {s}-w{w}: {res['realized_perfect'][f'{s}-w{w}']:.1f}", flush=True)
print(f"realized perfect: mean {np.mean(list(res['realized_perfect'].values())):.1f} ({time.time()-t0:.0f}s)", flush=True)
sample = [(2021, 5), (2022, 9), (2023, 1), (2023, 12), (2024, 7), (2024, 15)]
for s, w in sample:   # the simulator's per-world perfect lineup, 120 sampled worlds per slate
    fr = slate_frame(s, w); t1 = time.time(); draws = simulate_slate(fr, n_sims=2000, seed=slate_seed(777, s, w), law_env=ENV); keep = fr.pos.isin(SKILL + ("DST",)).to_numpy()
    frk = fr[keep].reset_index(drop=True); dk = draws[keep]; rng = np.random.default_rng(s * 100 + w); worlds = rng.choice(dk.shape[1], size=120, replace=False)
    vals = [best_lineup(frk, dk[:, j]) for j in worlds]; q = np.quantile(vals, [0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    res["sim_perfect"][f"{s}-w{w}"] = {"mean": float(np.mean(vals)), "q05": q[0], "q25": q[1], "median": q[2], "q75": q[3], "q95": q[4], "q99": q[5], "max": float(np.max(vals)), "realized": res["realized_perfect"][f"{s}-w{w}"], "n_players": int(len(frk)), "secs": round(time.time() - t1, 1)}
    print(f"sim {s}-w{w}: per-world perfect mean {np.mean(vals):.1f} median {q[2]:.1f} q95 {q[4]:.1f} q99 {q[5]:.1f} max {np.max(vals):.1f} | realized perfect {res['realized_perfect'][f'{s}-w{w}']:.1f}", flush=True)
(OUT / "perfect_lineup_gap.json").write_text(json.dumps(res, indent=1))
rp = np.array(list(res["realized_perfect"].values())); sp = res["sim_perfect"]
lines = ["# Perfect-lineup gap (2026-09-13)", "", f"Realized perfect lineup over the 72 dev slates: mean {rp.mean():.1f}, median {np.median(rp):.1f}, min {rp.min():.1f}, max {rp.max():.1f}; slates with perfect >= 300: {(rp >= 300).sum()}", "",
         "| slate | sim per-world perfect: mean | median | q95 | q99 | max of 120 worlds | realized perfect |", "|---|---:|---:|---:|---:|---:|---:|"]
lines += [f"| {k} | {v['mean']:.1f} | {v['median']:.1f} | {v['q95']:.1f} | {v['q99']:.1f} | {v['max']:.1f} | {v['realized']:.1f} |" for k, v in sp.items()]
(OUT / "perfect_lineup_gap.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines)); print("DONE")
