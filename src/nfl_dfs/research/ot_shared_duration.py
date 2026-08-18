"""Overtime as a dependence-only shared-duration mixture (S2 v2).

Measured basis (frozen 2026-08-15 study): current-rule overtime directly
added 23.77 skill DK points per OT game across 2025's 14 regular-season OT
games (~5.1% of games), concentrated in that game's players — a *shared*
mechanism. The simulator has no overtime branch anywhere (a tied simulated
game simply ends), while player marginals are fit on real outcomes that
include OT weeks. The joint law therefore carries OT mass marginally but
never lets one game's players spike *together* for that reason — exactly
the missing co-boom signature the 210+ book-tail under-prediction points
at.

The failed piece of OT v1 was *predicting* which games reach overtime
(2022-24 spread/total model, AUC 0.507 held out); its protocol licensed
only a market-priced duration arm, which therefore stayed unlicensed. This
v2 mechanism needs no prediction skill: each game is flagged OT in a world
at the frozen league base rate, and flagged worlds are rank-remapped so
that game's players co-move upward while every player's sorted marginal is
preserved EXACTLY (the established dependence-only transform pattern).

Research-only: no production call site, no sim-path wiring. The eventual
arm runs from its own frozen image under protocol
reports/2026-08-18-ot-shared-duration-v2-protocol.md and remains gated on
the production-law dependence scorecard per the operator's recorded
decision (2026-08-18, decision b).
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

PROTOCOL_ID = "20260818-ot-shared-duration-v2"
# 14 current-rule regular-season OT games / 272 games, 2025 (frozen study).
DEFAULT_P_OT = 14.0 / 272.0
# Uplift applied before rank remapping, in units of each player's own draw
# standard deviation. Only ranks matter downstream (the remap restores the
# exact marginal), so kappa controls how decisively flagged worlds move to
# the marginal upper tail; 1.5 places a median flagged world deep in its
# player's upper tail without making flags deterministic.
DEFAULT_KAPPA = 1.5
DEFAULT_SEED = 20_260_818


class OtMixtureError(ValueError):
    """Fail-closed contract violation."""


def _ranks_stable(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=int)
    ranks[order] = np.arange(len(values))
    return ranks


def apply_ot_duration_mixture(
    draws: np.ndarray,
    game_ids: Sequence[object],
    *,
    p_ot: float = DEFAULT_P_OT,
    kappa: float = DEFAULT_KAPPA,
    seed: int = DEFAULT_SEED,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Rank-remap ``draws`` so each game's players co-boom in its flagged
    OT worlds, preserving every player's sorted marginal exactly.

    ``draws``: (players, worlds); ``game_ids``: per-row game key (rows with
    a null/empty key are never touched). Flags are drawn per game from a
    deterministic seed in sorted-game order, so the same inputs always
    produce the same worlds. Returns ``(new_draws, flags_by_game)``.

    Constant rows (zero draw standard deviation — DST under the current
    law) are left byte-identical: a constant marginal has only one
    rank-preserving image, and this transform never invents variance.
    """
    draws = np.asarray(draws, dtype=np.float64)
    if draws.ndim != 2:
        raise OtMixtureError("draws must be (players, worlds)")
    if len(game_ids) != draws.shape[0]:
        raise OtMixtureError("game ids do not align with draw rows")
    if not np.isfinite(draws).all():
        raise OtMixtureError("draws must be finite")
    if not 0.0 <= float(p_ot) < 1.0:
        raise OtMixtureError("p_ot must be in [0, 1)")
    if float(kappa) <= 0.0:
        raise OtMixtureError("kappa must be positive")

    keys = ["" if g is None else str(g) for g in game_ids]
    games = sorted({k for k in keys if k})
    rng = np.random.default_rng(int(seed))
    out = draws.copy()
    flags_by_game: dict[str, np.ndarray] = {}
    n_worlds = draws.shape[1]
    for game in games:
        flags = rng.random(n_worlds) < float(p_ot)
        flags_by_game[game] = flags
        if not flags.any():
            continue
        rows = [i for i, k in enumerate(keys) if k == game]
        for i in rows:
            row = draws[i]
            sd = float(row.std())
            if sd == 0.0:
                continue
            shifted = row + flags * (float(kappa) * sd)
            out[i] = np.sort(row, kind="mergesort")[_ranks_stable(shifted)]
    return out, flags_by_game


def assert_marginals_preserved(
    before: np.ndarray, after: np.ndarray,
) -> float:
    """Maximum absolute sorted-marginal delta; must be exactly 0.0."""
    before = np.asarray(before, dtype=np.float64)
    after = np.asarray(after, dtype=np.float64)
    if before.shape != after.shape:
        raise OtMixtureError("shapes differ")
    delta = float(np.abs(
        np.sort(before, axis=1) - np.sort(after, axis=1)).max())
    if delta != 0.0:
        raise OtMixtureError(
            f"marginal preservation violated: max sorted delta {delta}")
    return delta


def same_game_comovement(
    draws: np.ndarray, game_ids: Sequence[object],
) -> float:
    """Mean Pearson correlation across same-game player pairs (variance
    rows only) — the diagnostic the mixture is supposed to move."""
    draws = np.asarray(draws, dtype=np.float64)
    keys = ["" if g is None else str(g) for g in game_ids]
    correlations: list[float] = []
    for game in sorted({k for k in keys if k}):
        rows = [i for i, k in enumerate(keys)
                if k == game and draws[i].std() > 0]
        for a_ix in range(len(rows)):
            for b_ix in range(a_ix + 1, len(rows)):
                correlations.append(float(np.corrcoef(
                    draws[rows[a_ix]], draws[rows[b_ix]])[0, 1]))
    if not correlations:
        raise OtMixtureError("no same-game variance pairs to correlate")
    return float(np.mean(correlations))
