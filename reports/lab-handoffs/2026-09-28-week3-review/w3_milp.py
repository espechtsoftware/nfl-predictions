import pandas as pd, numpy as np, pulp, time
f = pd.read_parquet("frame.parquet"); pts = pd.read_csv("../pts_w3.csv").set_index("display_name").fpts
f["actual_dk"] = f.display_name.map(pts).fillna(0.0)
f = f[(f.status.astype(str).isin(["None", "nan", "Q", "P"])) | f.status.isna()].reset_index(drop=True)   # DK-eligible at build
n = len(f); pos = f.pos.to_numpy(); sal = f.salary.to_numpy(); team = f.team.to_numpy(); game = f.game_id.to_numpy(); opp = f.opp.to_numpy()
def solve(score, bans, house=True, min_sal=49000, max_shared=7, prev=()):
    m = pulp.LpProblem("lu", pulp.LpMaximize); x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(n)]
    m += pulp.lpSum(score[i] * x[i] for i in range(n))
    m += pulp.lpSum(x) == 9; m += pulp.lpSum(sal[i] * x[i] for i in range(n)) <= 50000; m += pulp.lpSum(sal[i] * x[i] for i in range(n)) >= min_sal
    P = lambda p: [i for i in range(n) if pos[i] == p]
    m += pulp.lpSum(x[i] for i in P("QB")) == 1; m += pulp.lpSum(x[i] for i in P("DST")) == 1
    m += pulp.lpSum(x[i] for i in P("RB")) >= 2; m += pulp.lpSum(x[i] for i in P("RB")) <= 3
    m += pulp.lpSum(x[i] for i in P("WR")) >= 3; m += pulp.lpSum(x[i] for i in P("WR")) <= 4
    m += pulp.lpSum(x[i] for i in P("TE")) >= 1; m += pulp.lpSum(x[i] for i in P("TE")) <= 2
    for g in set(game): m += pulp.lpSum(x[i] for i in range(n) if game[i] == g) <= 4
    if house:
        for q in P("QB"):   # QB + >=2 same-team WR/TE, >=1 opposing skill player
            m += pulp.lpSum(x[i] for i in range(n) if team[i] == team[q] and pos[i] in ("WR", "TE")) >= 2 * x[q]
            m += pulp.lpSum(x[i] for i in range(n) if team[i] == opp[q] and pos[i] in ("RB", "WR", "TE")) >= x[q]
    for r in prev: m += pulp.lpSum(x[i] for i in r) <= max_shared
    for i in bans: m += x[i] == 0
    m.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=60))
    return [i for i in range(n) if x[i].value() > 0.5]
mean = f.mean_projection.to_numpy(); t0 = time.time()
opt = solve(mean, []); print("frame optimum by MEAN (house rules, cap 4, >=49k): projected", round(mean[opt].sum(), 1), "| realized", round(f.actual_dk.to_numpy()[opt].sum(), 1), "| punts", int((sal[opt] <= 4000).sum()), "| salary", int(sal[opt].sum()), f"| {time.time()-t0:.0f}s")
print("   ", ", ".join(f"{f.display_name[i]} ${sal[i]}" for i in opt))
prev, tot_p, tot_a, punts = [opt], [mean[opt].sum()], [f.actual_dk.to_numpy()[opt].sum()], [int((sal[opt] <= 4000).sum())]
for k in range(29):
    r = solve(mean, [], prev=prev); prev.append(r); tot_p.append(mean[r].sum()); tot_a.append(f.actual_dk.to_numpy()[r].sum()); punts.append(int((sal[r] <= 4000).sum()))
print(f"top-30 diverse lineups by MEAN (overlap <= 7): projected mean {np.mean(tot_p):.1f} (row 1 {tot_p[0]:.1f}, row 30 {tot_p[-1]:.1f}) | realized mean {np.mean(tot_a):.1f}, best {max(tot_a):.1f} | punts/row {np.mean(punts):.2f} | {time.time()-t0:.0f}s")
c = pd.read_parquet("cands_scored.parquet"); top = c.sort_values("simmean", ascending=False).head(30)
print(f"the POOL's top-30 by simulated mean: projected mean {top.mean_proj.mean():.1f} (row 1 {top.mean_proj.max():.1f}) | realized {top.act.mean():.1f} | punts/row {top.npunt.mean():.2f}")
tour = f.proj_tourney.to_numpy(); o2 = solve(tour, []); print(f"frame optimum by the TOURNEY valuation (what lev maximizes): tourney {tour[o2].sum():.1f}, its true mean {mean[o2].sum():.1f}, realized {f.actual_dk.to_numpy()[o2].sum():.1f}, punts {int((sal[o2] <= 4000).sum())}")
