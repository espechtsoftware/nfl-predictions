#!/usr/bin/env bash
# Single-core CBC benchmark: can this machine run the Saturday build?
#
# Week-2's D12800 build took 36,788 s (10.22 h) on the workstation (i9-9900K).
# That time is SINGLE-CORE bound: nfl2's optimize_many is a serial `for` loop of
# single-threaded PULP_CBC_CMD solves with no multiprocessing anywhere, so core
# count barely matters and sustained single-thread clock is everything.
#
# This solves a DK-classic-shaped MILP repeatedly and reports solves/sec. Run the
# IDENTICAL script on both machines; the ratio is what transfers.
#
#   bash scripts/solver_benchmark.sh [n_solves]
#
# Read-only. Starts nothing, writes nothing outside stdout.
set -uo pipefail
N="${1:-40}"
PY="${PY:-$(dirname "$0")/../.venv/bin/python}"
[ -x "$PY" ] || PY=python3
"$PY" - "$N" <<'PYEOF'
import sys, time, random
import pulp

n_solves = int(sys.argv[1])
rng = random.Random(20260922)          # fixed: both machines solve the identical problems
NP = 600
pos = (["QB"] * 60 + ["RB"] * 140 + ["WR"] * 240 + ["TE"] * 100 + ["DST"] * 60)
sal = [rng.randrange(3000, 9000, 100) for _ in range(NP)]
pts = [round(rng.uniform(2, 25), 2) for _ in range(NP)]

need = {"QB": (1, 1), "RB": (2, 3), "WR": (3, 4), "TE": (1, 2), "DST": (1, 1)}
banned, times = [], []
for k in range(n_solves):
    t0 = time.perf_counter()
    prob = pulp.LpProblem("dk", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(NP)]
    prob += pulp.lpSum(pts[i] * x[i] for i in range(NP))
    prob += pulp.lpSum(x) == 9
    prob += pulp.lpSum(sal[i] * x[i] for i in range(NP)) <= 50000
    prob += pulp.lpSum(sal[i] * x[i] for i in range(NP)) >= 49000
    for p, (lo, hi) in need.items():
        idx = [i for i in range(NP) if pos[i] == p]
        prob += pulp.lpSum(x[i] for i in idx) >= lo
        prob += pulp.lpSum(x[i] for i in idx) <= hi
    # the overlap cuts that make the real loop superlinear
    for prev in banned:
        prob += pulp.lpSum(x[i] for i in prev) <= 7
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    chosen = [i for i in range(NP) if x[i].value() and x[i].value() > 0.5]
    banned.append(chosen)
    times.append(time.perf_counter() - t0)

tot = sum(times)
print(f"solves={n_solves}  total={tot:.2f}s  mean={tot/n_solves*1000:.1f}ms  "
      f"first={times[0]*1000:.1f}ms  last={times[-1]*1000:.1f}ms  rate={n_solves/tot:.2f}/s")
print(f"WORKSTATION BASELINE (i9-9900K, 2026-09-22): see scripts/solver_benchmark.baseline")
print("Interpretation: a machine at HALF this rate turns a 10.2 h build into ~20 h,")
print("which does not fit between Saturday morning and Sunday's 11:15 CT upload.")
PYEOF
