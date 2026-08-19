"""Winner-world optima (N1c, 2026-08-19): solve each Milly winner's best
generating world to exact optimality.

The winner-law audit (N1b) established that every tracked winner outscores
the entire registered candidate pool in a median of 448 archived worlds,
but a generating world only proves the winner beats OUR pool there — not
that a per-world solver visiting that world would have produced the
winner. This module settles that: for each winner's best generating world
(maximum winner-minus-pool margin), solve the world to exact optimality
under (L) DraftKings-legal rules only and (P) the exact production
construction contract (QB stack >= 2, one bring-back, $49k floor — the
S1 mirror), then measure the winner's gap and player overlap against both
optima.

Reading, frozen before execution in the protocol document: winners at or
near the L optimum mean boom DEPTH suffices to build them and
regret-targeted generation is the priority lane; winners far below their
own worlds' optima mean the law prefers different rosters even where the
winner dominates our pool, shifting priority to law repair. Winners that
violate the production contract, or negative P gaps, measure how much the
construction rules themselves exclude winning rosters.

Diagnostic-only. No realized score is ever read here: inputs are winner
roster identities (already consumed and published by the frozen N1
report) and archived simulated worlds. It fits nothing, licenses nothing,
and runs exactly once per frozen protocol version. Artifact IO stays in
the runner script so this module remains offline-testable.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from nfl_dfs.research.final_forensic import (
    _solve_oracle,
    audit_roster,
    canonical_game_id,
    solve_draftkings_legal_oracle,
)

PROTOCOL_ID = "20260819-winner-world-optima-v1"
ROSTER_SIZE = 9
# Exact production construction contract (S1 exact-stack mirror).
QB_STACK_MIN = 2
BRING_BACK_MIN = 1
MIN_SALARY = 49_000
SALARY_CAP = 50_000
# Frozen classification band: a winner within this many simulated points
# of its world's DK-legal optimum counts as "near-optimal".
NEAR_OPTIMAL_POINTS = 2.0


class WinnerOptimaError(ValueError):
    """Fail-closed protocol violation."""


def best_generating_world(
    winner_totals: np.ndarray, candidate_totals: np.ndarray,
) -> dict | None:
    """The world with the maximum winner-over-pool margin, or None.

    Margin follows the N1b definition exactly: winner total minus the
    best registered candidate total in that world; a world generates the
    winner only when the margin is strictly positive. Ties break to the
    lowest world index (``np.argmax`` semantics) for determinism.
    """
    winner = np.asarray(winner_totals, dtype=np.float64)
    cands = np.asarray(candidate_totals, dtype=np.float64)
    if winner.ndim != 1 or cands.ndim != 2 or cands.shape[1] != len(winner):
        raise WinnerOptimaError("winner/candidate worlds are misaligned")
    if not np.isfinite(winner).all() or not np.isfinite(cands).all():
        raise WinnerOptimaError("world totals must be finite")
    pool_best = cands.max(axis=0)
    margin = winner - pool_best
    world = int(np.argmax(margin))
    if margin[world] <= 0:
        return None
    return {
        "world_index": world,
        "margin": float(margin[world]),
        "winner_total": float(winner[world]),
        "pool_best": float(pool_best[world]),
    }


def world_player_frame(
    slate_players: pd.DataFrame,
    opp_by_team: Mapping[str, str],
    player_ids: np.ndarray,
    world_scores: np.ndarray,
) -> pd.DataFrame:
    """Build the oracle player frame for one archived world.

    ``slate_players`` carries id/pos/team/salary for the slate (extra rows
    beyond the artifact universe are dropped; any ``actual`` column is
    ignored). ``opp_by_team`` maps team code to opponent code for this
    slate. The frame is restricted to exactly the artifact player
    universe, with ``actual`` set to the world's simulated scores. Any
    artifact player missing a snapshot row, salary, or opponent fails
    closed.
    """
    ids = np.asarray(player_ids, dtype=str)
    scores = np.asarray(world_scores, dtype=np.float64)
    if scores.ndim != 1 or len(scores) != len(ids):
        raise WinnerOptimaError("world scores do not align with player ids")
    if len(set(ids.tolist())) != len(ids):
        raise WinnerOptimaError("artifact player ids are not unique")
    frame = slate_players.copy()
    frame["id"] = frame.id.astype(str)
    frame = frame.drop_duplicates("id").set_index("id", drop=False)
    missing = [pid for pid in ids if pid not in frame.index]
    if missing:
        raise WinnerOptimaError(
            f"artifact players absent from slate snapshot: {missing[:5]}")
    frame = frame.loc[list(ids)].reset_index(drop=True)
    frame["actual"] = scores
    opp = [opp_by_team.get(str(team)) for team in frame.team]
    if any(value is None for value in opp):
        absent = sorted(
            {str(t) for t, o in zip(frame.team, opp) if o is None})
        raise WinnerOptimaError(f"teams lack an opponent mapping: {absent}")
    frame["opp"] = [str(value) for value in opp]
    frame["game_id"] = [
        canonical_game_id(team, opponent)
        for team, opponent in zip(frame.team, frame.opp)
    ]
    return frame[
        ["id", "pos", "team", "opp", "game_id", "salary", "actual"]
    ]


def solve_winner_world(
    frame: pd.DataFrame, winner_ids: Sequence[str],
) -> dict:
    """Solve one world under L and P and place the winner against both."""
    roster = [str(pid) for pid in winner_ids]
    if len(roster) != ROSTER_SIZE or len(set(roster)) != ROSTER_SIZE:
        raise WinnerOptimaError("winner roster must hold nine unique ids")
    by_id = frame.set_index("id")
    missing = [pid for pid in roster if pid not in by_id.index]
    if missing:
        raise WinnerOptimaError(
            f"winner players absent from the world frame: {missing}")
    winner_total = float(by_id.loc[roster].actual.sum())

    dk_audit = audit_roster(
        frame, roster, min_salary=0, salary_cap=SALARY_CAP,
        qb_stack_min=0, bring_back_min=0,
        forbid_two_rb_same_team=False, forbid_rb_vs_dst=False,
    )
    production_audit = audit_roster(
        frame, roster, min_salary=MIN_SALARY, salary_cap=SALARY_CAP,
        qb_stack_min=QB_STACK_MIN, bring_back_min=BRING_BACK_MIN,
    )

    legal = solve_draftkings_legal_oracle(frame, salary_cap=SALARY_CAP)
    production = _solve_oracle(
        frame, qb_stack_min=QB_STACK_MIN, bring_back_min=BRING_BACK_MIN,
        min_salary=MIN_SALARY, salary_cap=SALARY_CAP,
    )
    legal_score = float(legal["actual_score"])
    production_score = float(production["actual_score"])
    if dk_audit["valid"] and legal_score < winner_total - 1e-6:
        raise WinnerOptimaError(
            "DK-legal oracle scored below a DK-legal winner: "
            "frame or solver contract defect")

    legal_players = set(legal["players"])
    production_players = set(production["players"])
    l_gap = legal_score - winner_total
    return {
        "winner_total": winner_total,
        "winner_dk_legal_in_snapshot": bool(dk_audit["valid"]),
        "winner_dk_legal_failures": list(dk_audit["failures"]),
        "winner_production_valid": bool(production_audit["valid"]),
        "winner_production_failures": list(production_audit["failures"]),
        "winner_salary": int(dk_audit["salary"]),
        "legal_optimum": legal_score,
        "legal_gap": float(l_gap),
        "legal_overlap": int(len(legal_players & set(roster))),
        "legal_roster": sorted(legal_players),
        "is_legal_optimum_score": bool(l_gap <= 1e-6),
        "is_legal_optimum_identity": bool(legal_players == set(roster)),
        "is_near_legal_optimum": bool(l_gap <= NEAR_OPTIMAL_POINTS),
        "production_optimum": production_score,
        "production_gap": float(production_score - winner_total),
        "production_overlap": int(
            len(production_players & set(roster))),
        "production_roster": sorted(production_players),
    }


def winner_optima_report(entries: Sequence[dict]) -> dict:
    """Aggregate the frozen report over per-winner solve entries.

    Each entry carries ``season``, ``week``, ``roster_ids``, ``world``
    (from :func:`best_generating_world` plus block identity) and
    ``solve`` (from :func:`solve_winner_world`).
    """
    if not entries:
        raise WinnerOptimaError("no winner entries to aggregate")
    frame = pd.DataFrame([
        {
            "season": int(e["season"]),
            "week": int(e["week"]),
            "legal_gap": float(e["solve"]["legal_gap"]),
            "legal_overlap": int(e["solve"]["legal_overlap"]),
            "exact": bool(e["solve"]["is_legal_optimum_score"]),
            "near": bool(e["solve"]["is_near_legal_optimum"]),
            "production_gap": float(e["solve"]["production_gap"]),
            "production_overlap": int(e["solve"]["production_overlap"]),
            "production_valid": bool(
                e["solve"]["winner_production_valid"]),
            "dk_legal": bool(e["solve"]["winner_dk_legal_in_snapshot"]),
        }
        for e in entries
    ])
    if frame.duplicated(["season", "week"]).any():
        raise WinnerOptimaError("duplicate winner slates in the entries")
    by_season = {
        str(season): {
            "n": int(len(group)),
            "n_exact_legal_optimum": int(group.exact.sum()),
            "n_near_legal_optimum": int(group.near.sum()),
            "median_legal_gap": float(group.legal_gap.median()),
            "n_production_valid": int(group.production_valid.sum()),
        }
        for season, group in frame.groupby("season")
    }
    return {
        "protocol_id": PROTOCOL_ID,
        "n_winners": int(len(frame)),
        "n_exact_legal_optimum": int(frame.exact.sum()),
        "n_near_legal_optimum": int(frame.near.sum()),
        "near_optimal_points": float(NEAR_OPTIMAL_POINTS),
        "mean_legal_gap": float(frame.legal_gap.mean()),
        "median_legal_gap": float(frame.legal_gap.median()),
        "max_legal_gap": float(frame.legal_gap.max()),
        "median_legal_overlap": float(frame.legal_overlap.median()),
        "n_winner_production_valid": int(frame.production_valid.sum()),
        "n_winner_dk_legal_in_snapshot": int(frame.dk_legal.sum()),
        "n_negative_production_gap": int(
            (frame.production_gap < -1e-6).sum()),
        "median_production_gap": float(frame.production_gap.median()),
        "median_production_overlap": float(
            frame.production_overlap.median()),
        "by_season": by_season,
        "winners": list(entries),
        # Sim-side diagnostic: winner identities were consumed by the
        # frozen N1 report; no realized score is read here.
        "uses_realized_outcomes": False,
        "winner_identities_outcome_derived": True,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
