"""Field simulation (guide §10 step 5): approximate the opposing field with
ownership-weighted random lineups from the player pool.

Without real ownership, use the naive model — ownership correlates strongly
with value (proj/salary) and salary rank; a regression trained on scraped
post-hoc ownership slots in behind the same interface later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ROSTER = (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("FLEX", 1), ("DST", 1))
SALARY_CAP = 50_000


def naive_ownership(players: pd.DataFrame) -> np.ndarray:
    """Ownership proxy from value and salary within position. Returns
    weights normalized to sum to 1 within each position group."""
    df = players.copy()
    value = df["proj"] / (df["salary"] / 1000.0)
    # Softmax on standardized value; salary as mild popularity boost
    weights = np.zeros(len(df))
    for _pos, idx in df.groupby("pos").groups.items():
        loc = df.index.get_indexer(idx)
        v = value.iloc[loc]
        z = (v - v.mean()) / (v.std() + 1e-9)
        s = df["salary"].iloc[loc]
        zs = (s - s.mean()) / (s.std() + 1e-9)
        w = np.exp(1.2 * z + 0.3 * zs)
        weights[loc] = w / w.sum()
    return weights


def sharp_field(
    players: pd.DataFrame,
    n_lineups: int,
    n_distinct: int = 20,
    noise: float = 0.08,
    seed: int | None = 42,
) -> list[np.ndarray]:
    """Optimizer-built entrants: the slice of a real field that runs an
    optimizer over its own (imperfect) projections. Each batch jitters the
    projection column and takes a handful of optimal lineups; distinct
    lineups are then duplicated up to `n_lineups`, mirroring how heavily
    sharp lineups duplicate in large contests."""
    from ..optimizer.lineup import optimize_many

    rng = np.random.default_rng(seed)
    players = players.reset_index(drop=True)
    row_of = {r["id"]: i for i, r in players.iterrows()}
    distinct: list[np.ndarray] = []
    per_batch = 5
    for _ in range(2 * (n_distinct // per_batch + 1)):
        if len(distinct) >= n_distinct:
            break
        pool = players.to_dict("records")
        for p in pool:
            p["proj"] = float(p["proj"]) * float(rng.normal(1.0, noise))
        try:
            batch = optimize_many(pool, n_lineups=per_batch)
        except Exception as exc:  # noqa: BLE001 - a flaky CBC subprocess
            # shouldn't kill a whole replay; the field falls back to fewer
            # (or zero) sharp entrants.
            import logging

            logging.getLogger(__name__).warning("sharp_field batch failed: %s", exc)
            continue
        for lu in batch:
            distinct.append(np.array([row_of[p["id"]] for p in lu.players]))
    if not distinct:  # infeasible slate; let the caller fall back
        return []
    picks = rng.integers(0, len(distinct), n_lineups)
    return [distinct[i] for i in picks]


def sample_field(
    players: pd.DataFrame,
    n_lineups: int = 10_000,
    seed: int | None = 42,
    ownership: np.ndarray | None = None,
    sharp_fraction: float = 0.0,
) -> list[np.ndarray]:
    """Generate opposing lineups by ownership-weighted sampling per slot.
    Salary is enforced loosely (retry a few times, keep the best attempt) —
    the field is approximated, not optimized; most real entrants aren't
    optimal either. `sharp_fraction` of the field is instead built by
    `sharp_field` (optimizer entrants), which is what keeps GPP payout
    tails honest. Returns arrays of positional indices into `players`."""
    rng = np.random.default_rng(seed)
    n_sharp = int(n_lineups * sharp_fraction)
    sharp = sharp_field(players, n_sharp, seed=seed) if n_sharp else []
    n_lineups = n_lineups - len(sharp)
    own = ownership if ownership is not None else naive_ownership(players)
    players = players.reset_index(drop=True)
    pos_idx = {
        pos: players.index[players["pos"] == pos].to_numpy()
        for pos in ("QB", "RB", "WR", "TE", "DST")
    }
    flex_idx = players.index[players["pos"].isin(["RB", "WR", "TE"])].to_numpy()
    pos_weights = {
        pos: own[idx] / own[idx].sum() for pos, idx in pos_idx.items() if len(idx)
    }
    flex_w = own[flex_idx] / own[flex_idx].sum()
    salaries = players["salary"].to_numpy()

    field: list[np.ndarray] = []
    for _ in range(n_lineups):
        best: np.ndarray | None = None
        for _attempt in range(6):
            picks: list[int] = []
            ok = True
            for pos, n in ROSTER:
                if pos == "FLEX":
                    cand, w = flex_idx, flex_w
                else:
                    cand, w = pos_idx.get(pos, np.array([])), pos_weights.get(pos)
                    if cand is None or len(cand) < n:
                        ok = False
                        break
                avail = ~np.isin(cand, picks)
                if avail.sum() < n:
                    ok = False
                    break
                w_avail = w[avail] / w[avail].sum()
                chosen = rng.choice(cand[avail], size=n, replace=False, p=w_avail)
                picks.extend(chosen.tolist())
            if not ok:
                continue
            arr = np.array(picks)
            if salaries[arr].sum() <= SALARY_CAP:
                best = arr
                break
            if best is None:
                best = arr
        if best is not None:
            field.append(best)
    return sharp + field


def field_scores(field: list[np.ndarray], actual_points: np.ndarray) -> np.ndarray:
    """Actual DK points for each field lineup."""
    return np.array([actual_points[lu].sum() for lu in field])
