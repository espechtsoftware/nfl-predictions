"""GFlowNet gate experiment (emerging-technologies-plan.md §5.8-5.10).

Synthetic-slate comparison of the conditional GFlowNet candidate
generator against the repeated-MILP baseline at EQUAL candidate count:

- legal rate (GFN must be 100%),
- unique player-set rate,
- QB / stack-shape entropy,
- candidate frontier: best realized total per held-out draw column
  (the draws used for frontier evaluation are never seen by training
  or by reward-center fitting).

Both generators face identical legality: cap 50k, floor 49k
(``optimize(min_salary=...)``), DK slots, team/game limits. The MILP
maximizes mean projection with banned-lineup accumulation; the GFlowNet
samples in proportion to exp(P(total >= line)/T) on training draws.

Run:  python scripts/gfn_gate.py            (small settings, ~2-4 min CPU)
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.optimizer.lineup import optimize  # noqa: E402
from nfl_dfs.research.gfn_env import (  # noqa: E402
    DEFAULT_SALARY_FLOOR,
    LineupEnv,
    canonical_hash,
    check_lineup,
)
from nfl_dfs.research.gfn_train import (  # noqa: E402
    RewardConfig,
    lineup_utility,
    train_gfn,
)


def build_slate(seed: int = 17, n_teams: int = 8):
    """~64-player slate over n_teams/2 games with plausible DK economics."""
    rng = np.random.default_rng(seed)
    players, pid = [], 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        game = f"G{t // 2}"
        for pos, n in [("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("DST", 1)]:
            base = {"QB": 20, "RB": 15, "WR": 13, "TE": 9, "DST": 6}[pos]
            for i in range(n):
                proj = max(2.0, base - 3.5 * i + rng.normal(0, 2.0))
                players.append({
                    "id": pid, "name": f"{pos}{i}_{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": game,
                    "salary": int(np.clip(2600 + proj * 330 + rng.normal(0, 350),
                                          2500, 9600) // 100 * 100),
                    "proj": round(proj, 2),
                })
                pid += 1
    return players


def build_draws(players, n_sims: int, seed: int = 29) -> np.ndarray:
    """Correlated outcome draws: game environment + team factor +
    shared passing-game factor for QB and his pass catchers."""
    rng = np.random.default_rng(seed)
    games = sorted({p["game_id"] for p in players})
    teams = sorted({p["team"] for p in players})
    g_f = {g: rng.normal(0, 1, n_sims) for g in games}
    t_f = {t: rng.normal(0, 1, n_sims) for t in teams}
    pass_f = {t: rng.normal(0, 1, n_sims) for t in teams}
    rows = []
    for p in players:
        mu = p["proj"]
        z = 0.10 * g_f[p["game_id"]] + 0.08 * t_f[p["team"]]
        if p["pos"] in ("QB", "WR", "TE"):
            z = z + 0.14 * pass_f[p["team"]]
        noise = rng.normal(0, 0.40 * mu, n_sims)
        rows.append(np.maximum(0.0, mu * (1.0 + z) + noise))
    return np.stack(rows)


def entropy_bits(labels) -> float:
    counts = np.array(list(Counter(labels).values()), dtype=float)
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum())


def stack_shape(players_in_lineup) -> str:
    qb = next(p for p in players_in_lineup if p["pos"] == "QB")
    mates = sum(1 for p in players_in_lineup
                if p["team"] == qb["team"] and p["pos"] in ("WR", "TE"))
    bring = sum(1 for p in players_in_lineup
                if p["team"] == qb["opp"] and p["pos"] in ("RB", "WR", "TE"))
    return f"QB+{mates}/bb{bring}"


def milp_candidates(players, n: int, floor: int):
    """Repeated-MILP baseline: banned-lineup accumulation on mean proj."""
    out, banned = [], []
    for _ in range(n):
        lu = optimize(players, banned_lineups=banned, max_overlap=8,
                      min_salary=floor)
        if lu is None:
            break
        out.append([p["id"] for p in lu.players])
        banned.append(lu.ids)
    return out


def gfn_candidates(policy, env, n: int, rng, max_tries: int = 8):
    """Sample until n unique player sets (or budget exhausted)."""
    seen, out, sampled = set(), [], 0
    for _ in range(max_tries):
        batch = policy.sample(n, rng=rng)
        sampled += len(batch)
        for s in batch:
            h = env.lineup_hash(s)
            if h not in seen:
                seen.add(h)
                out.append([p["id"] for p in env.lineup_players(s)])
            if len(out) >= n:
                return out, sampled
    return out, sampled


def describe(name, id_lists, by_id, env, draws_eval):
    players_of = [[by_id[i] for i in ids] for ids in id_lists]
    legal = [
        check_lineup(ps, salary_cap=env.salary_cap, salary_floor=env.salary_floor,
                     max_from_team=env.max_from_team, min_games=env.min_games) == []
        for ps in players_of
    ]
    hashes = [canonical_hash(ids) for ids in id_lists]
    idx_of = {p["id"]: k for k, p in enumerate(env.players)}
    totals = np.stack([
        draws_eval[[idx_of[i] for i in ids]].sum(axis=0) for ids in id_lists
    ])  # [n_candidates, n_eval_sims]
    return {
        "name": name,
        "n": len(id_lists),
        "legal_rate": float(np.mean(legal)),
        "unique_rate": len(set(hashes)) / max(1, len(hashes)),
        "qb_entropy": entropy_bits(
            [next(p["id"] for p in ps if p["pos"] == "QB") for ps in players_of]
        ),
        "stack_entropy": entropy_bits([stack_shape(ps) for ps in players_of]),
        "mean_salary": float(np.mean([sum(p["salary"] for p in ps) for ps in players_of])),
        "frontier_mean": float(totals.max(axis=0).mean()),
        "frontier_p90": float(np.quantile(totals.max(axis=0), 0.9)),
        "per_col_max": totals.max(axis=0),
        "hashes": set(hashes),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-candidates", type=int, default=24)
    ap.add_argument("--steps", type=int, default=250)
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--eval-sims", type=int, default=500)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    players = build_slate()
    by_id = {p["id"]: p for p in players}
    draws = build_draws(players, args.sims)
    train_cols = np.arange(args.sims - args.eval_sims)
    eval_cols = np.arange(args.sims - args.eval_sims, args.sims)
    floor = DEFAULT_SALARY_FLOOR
    env = LineupEnv(players, salary_floor=floor)

    t0 = time.time()
    milp = milp_candidates(players, args.n_candidates, floor)
    t_milp = time.time() - t0
    print(f"MILP baseline: {len(milp)} candidates in {t_milp:.1f}s")

    # tail line fitted on TRAINING draws of the best-proj MILP lineup
    idx_of = {p["id"]: k for k, p in enumerate(players)}
    best_idx = [idx_of[i] for i in milp[0]]
    line = float(np.quantile(draws[best_idx][:, train_cols].sum(axis=0), 0.80))
    print(f"tail line (q80 of best MILP lineup, train draws): {line:.1f}")

    # per-player quantile features from training draws only
    for p in players:
        row = draws[idx_of[p["id"]]][train_cols]
        p["q10"], p["q50"], p["q90"] = (
            round(float(np.quantile(row, q)), 2) for q in (0.1, 0.5, 0.9)
        )

    t0 = time.time()
    result = train_gfn(
        env, draws, line, steps=args.steps, batch_size=8, replay_batch=8,
        explore_eps=0.1, hidden=64, quantile_cols=("q10", "q50", "q90"),
        warm_start_lineups=milp, sim_cols=train_cols, seed=args.seed,
        reward_cfg=RewardConfig(temperature=0.05),
    )
    t_train = time.time() - t0
    hist = result.history
    print(f"GFN trained {args.steps} steps in {t_train:.1f}s "
          f"(warm-start {result.warm_started} MILP lineups, "
          f"{result.warm_skipped} skipped); "
          f"loss {hist[0]['loss']:.1f} -> {hist[-1]['loss']:.1f}, "
          f"mean utility {hist[0]['mean_utility']:.3f} -> {hist[-1]['mean_utility']:.3f}")

    rng = np.random.default_rng(args.seed + 100)
    t0 = time.time()
    gfn, sampled = gfn_candidates(result.policy, env, args.n_candidates, rng)
    t_sample = time.time() - t0
    print(f"GFN candidates: {len(gfn)} unique from {sampled} samples in {t_sample:.1f}s\n")

    draws_eval = draws[:, eval_cols]
    rows = [
        describe("GFlowNet", gfn, by_id, env, draws_eval),
        describe("MILP", milp, by_id, env, draws_eval),
        describe("Union", gfn + milp, by_id, env, draws_eval),
    ]
    g, m, u = rows

    overlap = len(g["hashes"] & m["hashes"])
    win = float((g["per_col_max"] > m["per_col_max"]).mean())
    tie = float((g["per_col_max"] == m["per_col_max"]).mean())
    union_gain = float((u["per_col_max"] - m["per_col_max"]).mean())

    print("=" * 74)
    print(f"{'metric':<34}{'GFlowNet':>12}{'MILP':>12}{'verdict':>14}")
    print("-" * 74)

    def row(label, gv, mv, verdict, fmt="{:.3f}"):
        print(f"{label:<34}{fmt.format(gv):>12}{fmt.format(mv):>12}{verdict:>14}")

    row("candidates", g["n"], m["n"],
        "PASS" if g["n"] == m["n"] else "FAIL", "{:d}")
    row("legal rate", g["legal_rate"], m["legal_rate"],
        "PASS" if g["legal_rate"] == 1.0 else "FAIL")
    row("unique player-set rate", g["unique_rate"], m["unique_rate"],
        "PASS" if g["unique_rate"] == 1.0 else "FAIL")
    row("QB entropy (bits)", g["qb_entropy"], m["qb_entropy"],
        "PASS" if g["qb_entropy"] > m["qb_entropy"] else "FAIL")
    row("stack-shape entropy (bits)", g["stack_entropy"], m["stack_entropy"],
        "PASS" if g["stack_entropy"] > m["stack_entropy"] else "INFO")
    row("mean salary", g["mean_salary"], m["mean_salary"], "INFO", "{:.0f}")
    row("frontier: mean best total", g["frontier_mean"], m["frontier_mean"],
        "PASS" if g["frontier_mean"] >= m["frontier_mean"] else "FAIL")
    row("frontier: p90 best total", g["frontier_p90"], m["frontier_p90"], "INFO")
    print(f"{'GFN beats MILP per held-out col':<34}{win:>12.3f}{'-':>12}{'INFO':>14}")
    print(f"{'overlap with MILP sets':<34}{overlap:>12d}{'-':>12}"
          f"{('INFO' if overlap < g['n'] else 'FAIL'):>14}")
    print(f"{'union frontier gain vs MILP':<34}{union_gain:>+12.3f}{'-':>12}"
          f"{('PASS' if union_gain > 0 else 'FAIL'):>14}")
    print("=" * 74)

    hard_fail = (
        g["legal_rate"] < 1.0
        or g["n"] < m["n"]
        or overlap == g["n"]  # §5.11: merely reproduces MILP
    )
    frontier_ok = g["frontier_mean"] >= m["frontier_mean"] or union_gain > 0
    print("\nVERDICT:", "FAIL (hard gate)" if hard_fail else
          ("PASS — GFN adds legal, diverse, frontier-positive candidates"
           if frontier_ok else
           "MIXED — legal+diverse but no frontier value at equal count"))
    print("(synthetic slate; a real adoption gate requires plan §5.10 "
          "decision metrics on historical slates)")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
