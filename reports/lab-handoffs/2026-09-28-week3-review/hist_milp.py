import pandas as pd, numpy as np, pulp, time, sys
S = pd.read_parquet("spf_full.parquet"); C = pd.read_parquet("cands.parquet")
K = 40; out = []; t0 = time.time()
for (sn, wk), fr in S.groupby(["season", "week"]):
    fr = fr[fr.mean_projection.notna() & (fr.salary > 0)].reset_index(drop=True)
    fr["game"] = [":".join(sorted([a, b])) for a, b in zip(fr.team.astype(str), fr.opp.astype(str))]
    n = len(fr); pos = fr.pos.to_numpy(); sal = fr.salary.to_numpy(); team = fr.team.to_numpy(); opp = fr.opp.to_numpy(); game = fr.game.to_numpy()
    mean = fr.mean_projection.to_numpy(); actual = fr.actual.fillna(0).to_numpy()
    P = {p: [i for i in range(n) if pos[i] == p] for p in ("QB", "RB", "WR", "TE", "DST")}
    if any(len(P[p]) == 0 for p in P): continue
    prev, A, PR = [], [], []
    for k in range(K):
        m = pulp.LpProblem("lu", pulp.LpMaximize); x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(n)]
        m += pulp.lpSum(mean[i] * x[i] for i in range(n)); m += pulp.lpSum(x) == 9
        m += pulp.lpSum(sal[i] * x[i] for i in range(n)) <= 50000; m += pulp.lpSum(sal[i] * x[i] for i in range(n)) >= 49000
        m += pulp.lpSum(x[i] for i in P["QB"]) == 1; m += pulp.lpSum(x[i] for i in P["DST"]) == 1
        m += pulp.lpSum(x[i] for i in P["RB"]) >= 2; m += pulp.lpSum(x[i] for i in P["RB"]) <= 3
        m += pulp.lpSum(x[i] for i in P["WR"]) >= 3; m += pulp.lpSum(x[i] for i in P["WR"]) <= 4
        m += pulp.lpSum(x[i] for i in P["TE"]) >= 1; m += pulp.lpSum(x[i] for i in P["TE"]) <= 2
        for g in set(game): m += pulp.lpSum(x[i] for i in range(n) if game[i] == g) <= 4
        for q in P["QB"]:
            m += pulp.lpSum(x[i] for i in range(n) if team[i] == team[q] and pos[i] in ("WR", "TE")) >= 2 * x[q]
            m += pulp.lpSum(x[i] for i in range(n) if team[i] == opp[q] and pos[i] in ("RB", "WR", "TE")) >= x[q]
        for r in prev: m += pulp.lpSum(x[i] for i in r) <= 7
        m.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
        r = [i for i in range(n) if x[i].value() is not None and x[i].value() > 0.5]
        if len(r) != 9: break
        prev.append(r); A.append(actual[r].sum()); PR.append(mean[r].sum())
    if len(A) < K: print("short", sn, wk, len(A)); continue
    c = C[(C.season == sn) & (C.week == wk)]
    out.append({"season": sn, "week": wk, "milp_realized": float(np.mean(A)), "milp_best": float(np.max(A)), "milp_proj": float(np.mean(PR)),
                "pool_topmean_proj": float(c.sort_values("sim_mean", ascending=False).head(K).sim_mean.mean()),
                "pool_topmean_realized": float(c.sort_values("sim_mean", ascending=False).head(K).actual_score.mean())})
    print(f"{sn} w{wk}: milp proj {np.mean(PR):.1f} realized {np.mean(A):.1f} | pool top-{K} proj {out[-1]['pool_topmean_proj']:.1f} realized {out[-1]['pool_topmean_realized']:.1f} | {time.time()-t0:.0f}s", flush=True)
D = pd.DataFrame(out); D.to_csv("hist_milp.csv", index=False)
d = D.milp_realized - D.pool_topmean_realized
print(f"\n{len(D)} slates: MILP top-{K} by mean realized {D.milp_realized.mean():.2f} vs pool top-{K} by mean {D.pool_topmean_realized.mean():.2f}: {d.mean():+.2f} (t {d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):+.1f}, seasons+ {int((d.groupby(D.season).mean()>0).sum())}/{D.season.nunique()})")
print(f"projected: MILP {D.milp_proj.mean():.2f} vs pool {D.pool_topmean_proj.mean():.2f}; best: {D.milp_best.mean():.2f}")
