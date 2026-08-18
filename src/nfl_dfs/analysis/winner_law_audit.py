"""Winner-lineup law audit (N1, 2026-08-18): score known Milly-winner
rosters under the archived production world book.

The book-tail calibration audit measured the law against our own selected
book. This audit asks the complementary, dollars-weighted question: for
each known Millionaire Maker winning roster, where does its realized
winning score sit within its OWN simulated total distribution under the
archived production worlds? A correct joint law should place realized
winning scores in the upper tail of their roster's distribution but not
beyond it; systematic mass at and beyond the 99.9th percentile is a direct
measurement of missing co-boom mass, on exactly the lineups the program is
trying to learn to build, independent of our generator and selector.

Deliberately diagnostic-only and outcome-aware (winner scores were already
consumed by the Addendum 114/116 diagnostic class). It fits nothing, tunes
nothing, licenses nothing, and must run only under the frozen protocol
reports/2026-08-18-winner-law-audit-protocol.md, exactly once per protocol
version. Pure computation lives here; artifact/warehouse IO stays in the
runner script so this module remains offline-testable.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

PROTOCOL_ID = "20260818-winner-law-audit-v1"
ROSTER_SIZE = 9
# Quantiles of the roster's simulated distribution reported per winner.
REPORT_QUANTILES = (0.50, 0.90, 0.95, 0.99, 0.999)
# Aggregate exceedance levels: how many winners' realized scores land at or
# beyond these percentiles of their own simulated distribution.
EXCEEDANCE_LEVELS = (0.95, 0.99, 0.999)


class WinnerLawAuditError(ValueError):
    """Fail-closed protocol violation."""


def align_world_blocks(
    blocks: Sequence[tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate per-block player worlds on one canonical player order.

    Each block is ``(player_ids, player_draws)`` with draws shaped
    ``(players, worlds)``. The first block's id order is canonical; every
    other block must contain exactly the same id set and is reindexed to
    it. Mismatched universes fail closed rather than silently dropping a
    player from the summed roster totals.
    """
    if not blocks:
        raise WinnerLawAuditError("at least one world block is required")
    canonical_ids = np.asarray(blocks[0][0], dtype=str)
    if len(set(canonical_ids.tolist())) != len(canonical_ids):
        raise WinnerLawAuditError("world-block player ids are not unique")
    index = {pid: i for i, pid in enumerate(canonical_ids)}
    aligned = []
    for block_ix, (ids, draws) in enumerate(blocks):
        ids = np.asarray(ids, dtype=str)
        draws = np.asarray(draws, dtype=np.float64)
        if draws.ndim != 2 or draws.shape[0] != len(ids):
            raise WinnerLawAuditError(
                f"block {block_ix} draws do not align with its ids")
        if set(ids.tolist()) != set(canonical_ids.tolist()):
            raise WinnerLawAuditError(
                f"block {block_ix} player universe differs from block 0")
        order = np.fromiter(
            (index[pid] for pid in ids), count=len(ids), dtype=int)
        reindexed = np.empty_like(draws)
        reindexed[order] = draws
        aligned.append(reindexed)
    return canonical_ids, np.concatenate(aligned, axis=1)


def winner_roster_world_totals(
    roster_ids: Sequence[str],
    player_ids: np.ndarray,
    player_draws: np.ndarray,
) -> np.ndarray:
    """Simulated roster totals across worlds; all nine slots must resolve."""
    roster = [str(pid) for pid in roster_ids]
    if len(roster) != ROSTER_SIZE:
        raise WinnerLawAuditError(
            f"winner roster has {len(roster)} slots, expected {ROSTER_SIZE}")
    if len(set(roster)) != ROSTER_SIZE:
        raise WinnerLawAuditError("winner roster ids are not unique")
    index = {pid: i for i, pid in enumerate(np.asarray(player_ids, dtype=str))}
    missing = [pid for pid in roster if pid not in index]
    if missing:
        raise WinnerLawAuditError(
            f"winner players absent from the world artifact: {missing}")
    rows = np.fromiter(
        (index[pid] for pid in roster), count=ROSTER_SIZE, dtype=int)
    return np.asarray(player_draws, dtype=np.float64)[rows].sum(axis=0)


def audit_roster_under_law(
    realized_total: float, totals: np.ndarray,
) -> dict:
    """Placement of one realized score within its simulated distribution."""
    totals = np.asarray(totals, dtype=np.float64)
    if totals.ndim != 1 or len(totals) < 100:
        raise WinnerLawAuditError(
            "roster totals must be one-dimensional with at least 100 worlds")
    if not np.isfinite(totals).all() or not np.isfinite(realized_total):
        raise WinnerLawAuditError("totals and realized score must be finite")
    realized = float(realized_total)
    n = len(totals)
    less = int((totals < realized).sum())
    equal = int((totals == realized).sum())
    percentile = (less + 0.5 * equal) / n
    return {
        "n_worlds": n,
        "realized_total": realized,
        "sim_mean": float(totals.mean()),
        "sim_sd": float(totals.std()),
        "sim_quantiles": {
            f"q{str(q).replace('0.', '')}": float(np.quantile(totals, q))
            for q in REPORT_QUANTILES
        },
        "percentile_mid_rank": float(percentile),
        "pr_sim_ge_realized": float((totals >= realized).mean()),
    }


def winner_law_report(entries: Sequence[dict]) -> dict:
    """Aggregate the frozen report over per-winner audit entries.

    Each entry carries ``season``, ``week``, ``roster_ids``,
    ``realized_snapshot_total`` (authoritative-scorer parity, the primary
    realized score), optional ``realized_tracked_total`` (descriptive), and
    ``audit`` from :func:`audit_roster_under_law` on the snapshot total.
    """
    if not entries:
        raise WinnerLawAuditError("no winner entries to aggregate")
    frame = pd.DataFrame([
        {
            "season": int(e["season"]),
            "week": int(e["week"]),
            "percentile": float(e["audit"]["percentile_mid_rank"]),
            "pr_ge": float(e["audit"]["pr_sim_ge_realized"]),
        }
        for e in entries
    ])
    if frame.duplicated(["season", "week"]).any():
        raise WinnerLawAuditError("duplicate winner slates in the entries")
    exceedance = {}
    for level in EXCEEDANCE_LEVELS:
        key = f"at_or_beyond_p{str(level).replace('0.', '')}"
        exceedance[key] = {
            "observed": int((frame.percentile >= level).sum()),
            # Not a null hypothesis: winners are field maxima, so a correct
            # law concentrates them high. The expected count under an
            # exchangeable-single-roster reading is reported only as a
            # scale anchor for the interpretation section.
            "single_roster_scale_anchor": float(
                len(frame) * (1.0 - level)),
        }
    by_season = {
        str(season): {
            "n": int(len(group)),
            "mean_percentile": float(group.percentile.mean()),
            "at_or_beyond_p99": int((group.percentile >= 0.99).sum()),
        }
        for season, group in frame.groupby("season")
    }
    return {
        "protocol_id": PROTOCOL_ID,
        "n_winners": int(len(frame)),
        "mean_percentile": float(frame.percentile.mean()),
        "median_percentile": float(frame.percentile.median()),
        "min_pr_sim_ge_realized": float(frame.pr_ge.min()),
        "exceedance": exceedance,
        "by_season": by_season,
        "winners": list(entries),
        # Outcome-aware diagnostic: flags are literal and non-negotiable.
        "uses_realized_outcomes": True,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
