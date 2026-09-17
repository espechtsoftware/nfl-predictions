"""Ownership-consistent field sampler for PREREG-098 (frozen with the cohort).

Draws synthetic DraftKings Classic lineups whose per-player usage matches a target ownership vector (fraction of the field's
lineups containing each player) under the roster shape (QB, RB, RB, WR, WR, WR, TE, FLEX(RB/WR/TE), DST), the $50,000 cap and a
per-lineup salary floor drawn from a band, with a QB-stack propensity.  Sampling weights are fitted by iterative proportional
fitting so the sampled field reproduces the target ownership.  Fully vectorised; deterministic given (targets, seed).

Mechanics gate (PREREG-098 §Gate): on the one real field we hold (2026 Week-1 Millionaire) the sampled field's per-world
payout cutoffs must track the real field's, and its realized-points cutoffs the real ones.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FLEX_POS = ("RB", "WR", "TE")
CAP = 50_000


def _draw(rng, pool: np.ndarray, w: np.ndarray, m: int) -> np.ndarray:
    p = w[pool]; p = p / p.sum() if p.sum() > 0 else np.full(len(pool), 1.0 / len(pool))
    return pool[rng.choice(len(pool), size=m, p=p)]


def sample_field(frame: pd.DataFrame, target: dict[str, float], n: int, seed: int, *, ipf_rounds: int = 6,
                 stack_prob: float = 0.70, salary_floor_band: tuple[int, int] = (48_500, 50_000)) -> tuple[np.ndarray, dict]:
    """Return (lineups as an (n, 9) int array of frame row indices in slot order QB,RB,RB,WR,WR,WR,TE,FLEX,DST, receipt)."""
    rng = np.random.default_rng(seed)
    ids = frame.id.astype(str).to_numpy(); pos = frame.pos.astype(str).to_numpy(); team = frame.team.astype(str).to_numpy()
    sal = pd.to_numeric(frame.salary, errors="coerce").fillna(99_999).to_numpy(float)
    t = np.clip(np.array([float(target.get(i, 0.0)) for i in ids]), 0.0, 1.0)
    live = t > 0
    pools = {p: np.where((pos == p) & live)[0] for p in ("QB", "RB", "WR", "TE", "DST")}
    flex_pool = np.where(np.isin(pos, FLEX_POS) & live)[0]
    for p, arr in pools.items():
        if len(arr) < {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "DST": 1}[p]:
            raise ValueError(f"ownership targets leave too few {p}s to build lineups")
    mates_by_team = {tm: np.where((team == tm) & np.isin(pos, ("WR", "TE")) & live)[0] for tm in np.unique(team[pools["QB"]])}
    w = np.where(live, t, 0.0).astype(float)
    receipt = {"n": n, "seed": seed, "ipf_rounds": ipf_rounds, "stack_prob": stack_prob, "salary_floor_band": list(salary_floor_band), "rounds": []}

    def draw_batch(m: int) -> np.ndarray:
        L = np.empty((m, 9), dtype=np.int32)
        L[:, 0] = _draw(rng, pools["QB"], w, m)
        # stack: for a share of rows, the first WR/TE slot comes from the QB's team
        stacked = rng.random(m) < stack_prob; first = np.full(m, -1, dtype=np.int64)
        for tm, mates in mates_by_team.items():
            rows = np.where(stacked & (team[L[:, 0]] == tm))[0]
            if len(rows) and len(mates):
                first[rows] = _draw(rng, mates, w, len(rows))
        L[:, 1] = _draw(rng, pools["RB"], w, m); L[:, 2] = _draw(rng, pools["RB"], w, m)
        for j in (3, 4, 5): L[:, j] = _draw(rng, pools["WR"], w, m)
        L[:, 6] = _draw(rng, pools["TE"], w, m)
        is_wr = first >= 0; is_wr &= np.isin(pos[np.maximum(first, 0)], ["WR"]) & (first >= 0)
        is_te = (first >= 0) & ~is_wr
        L[is_wr, 3] = first[is_wr]; L[is_te, 6] = first[is_te]
        L[:, 7] = _draw(rng, flex_pool, w, m); L[:, 8] = _draw(rng, pools["DST"], w, m)
        return L

    def valid(L: np.ndarray, floors: np.ndarray) -> np.ndarray:
        s = np.sort(L[:, :8], axis=1); nodup = np.all(s[:, 1:] != s[:, :-1], axis=1)
        tot = sal[L].sum(axis=1)
        return nodup & (tot <= CAP) & (tot >= floors)

    def sample(m_target: int) -> np.ndarray:
        # Draw batches until m_target valid lineups exist.  The batch never shrinks below 20,000 rows: the acceptance
        # rate under a tight salary band can be a few percent, and a batch sized to the remaining shortfall would
        # otherwise starve on the last few hundred lineups (118m980r1: 199,748 of 200,000 after 60 tries).
        out = []; have = 0; tries = 0
        while have < m_target and tries < 400:
            tries += 1; m = max(int((m_target - have) * 1.6) + 500, 20_000)
            L = draw_batch(m); ok = valid(L, rng.uniform(salary_floor_band[0], salary_floor_band[1], size=m))
            keep = L[ok][: m_target - have]; out.append(keep); have += len(keep)
        if have < m_target:
            raise RuntimeError(f"field sampler could not fill {m_target} lineups (got {have}) — targets or salary band infeasible")
        return np.vstack(out)

    lineups = None
    for rnd in range(ipf_rounds):
        lineups = sample(n if rnd == ipf_rounds - 1 else max(20_000, n // 5))
        realized = np.bincount(lineups.ravel(), minlength=len(ids)) / len(lineups)
        err = float(np.abs(realized - t)[live].sum()); receipt["rounds"].append({"round": rnd, "n": int(len(lineups)), "abs_ownership_error_sum": round(err, 4)})
        if rnd < ipf_rounds - 1:
            ratio = np.ones_like(t); ratio[live] = (t[live] / np.maximum(realized[live], 1e-4)) ** 0.7
            w = np.clip(w * ratio, 1e-7, None)
    realized = np.bincount(lineups.ravel(), minlength=len(ids)) / len(lineups)
    sub = lineups[: min(50_000, len(lineups))]
    receipt.update({"final_abs_ownership_error_sum": round(float(np.abs(realized - t)[live].sum()), 4), "target_mass": round(float(t.sum()), 3), "realized_mass": round(float(realized.sum()), 3),
                    "mean_salary": float(sal[lineups].sum(axis=1).mean()),
                    "stack_rate": float(np.mean(np.any(team[sub[:, 3:7]] == team[sub[:, [0]]], axis=1)))})
    return lineups, receipt


def world_cutoffs(field: np.ndarray, M: np.ndarray, ranks: np.ndarray, chunk: int = 500) -> np.ndarray:
    """Per-world score at each of `ranks` (1-based from the top) over the field; M is players x worlds aligned with the frame."""
    W = M.shape[1]; out = np.zeros((W, len(ranks)), np.float32); kth = (len(field) - ranks).astype(int)
    for s in range(0, W, chunk):
        Mc = M[:, s:s + chunk]; S = np.zeros((len(field), Mc.shape[1]), np.float32)
        for j in range(field.shape[1]): S += Mc[field[:, j]]
        P = np.partition(S, kth, axis=0); out[s:s + chunk] = P[kth].T
    return out
