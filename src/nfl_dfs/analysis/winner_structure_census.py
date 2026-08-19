"""Winner structure census (A11+A12, 2026-08-19): stack anatomy of the
tracked Milly winners versus our registered pools and selected books.

The dependence remeasurement found the law over-couples generic teammate
booms and under-couples QB->WR — but nobody has measured what stack
SHAPES the winners actually carry versus what we build. This census is
pure roster structure: QB stack size (same-team WR/TE), bring-back
count, double-stack rate, game concentration. No realized score, no
ownership, no simulated total is read anywhere — the census is
outcome-blind by construction and safe to run while an outcome-reading
arm is in flight.

The A12 half zooms into the eight production-legal winners: rule-legal,
yet the pool never exceeded 5/9 overlap with any of them. Their case
records join the census structure with the already-published census
facts (pool coverage of their players, generating-world ranks) to name
the residual, non-rule blocker.

Descriptive only; licenses nothing. Pure computation lives here;
BQ/file IO stays in the runner so this module remains offline-testable.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

PROTOCOL_ID = "20260819-winner-structure-census-v1"
ROSTER_SIZE = 9
SKILL = ("RB", "WR", "TE")


class StructureCensusError(ValueError):
    """Fail-closed contract violation."""


def roster_structure(
    roster: Sequence[str],
    pos_of: Mapping[str, str],
    team_of: Mapping[str, str],
    opp_of: Mapping[str, str],
) -> dict:
    """Structural anatomy of one nine-player roster."""
    ids = [str(p) for p in roster]
    if len(ids) != ROSTER_SIZE or len(set(ids)) != ROSTER_SIZE:
        raise StructureCensusError("roster must hold nine unique ids")
    missing = [p for p in ids if p not in pos_of or p not in team_of]
    if missing:
        raise StructureCensusError(
            f"roster players lack position/team: {missing[:3]}")
    qbs = [p for p in ids if pos_of[p] == "QB"]
    if len(qbs) != 1:
        raise StructureCensusError(f"roster holds {len(qbs)} QBs")
    qb = qbs[0]
    qb_team = str(team_of[qb])
    qb_opp = str(opp_of.get(qb, ""))
    if not qb_opp:
        raise StructureCensusError(f"QB {qb} lacks an opponent mapping")

    stack = sum(
        1 for p in ids
        if p != qb and team_of[p] == qb_team and pos_of[p] in ("WR", "TE"))
    bring_back = sum(
        1 for p in ids if team_of[p] == qb_opp and pos_of[p] in SKILL)
    games: dict[str, int] = {}
    for p in ids:
        team = str(team_of[p])
        opp = str(opp_of.get(p, ""))
        key = "|".join(sorted((team, opp))) if opp else team
        games[key] = games.get(key, 0) + 1
    secondary = {}
    for p in ids:
        if pos_of[p] in ("WR", "TE") and team_of[p] not in (qb_team,):
            secondary[team_of[p]] = secondary.get(team_of[p], 0) + 1
    return {
        "qb_stack": int(stack),
        "bring_back": int(bring_back),
        "double_stack": bool(stack >= 2),
        "full_production_shape": bool(stack >= 2 and bring_back >= 1),
        "naked_qb": bool(stack == 0),
        "max_game_concentration": int(max(games.values())),
        "n_games": int(len(games)),
        "max_secondary_stack": int(max(secondary.values(), default=0)),
    }


def structure_census(structures: Sequence[dict]) -> dict:
    """Distributional summary over roster structures."""
    if not structures:
        raise StructureCensusError("no structures to summarize")
    frame = pd.DataFrame(list(structures))
    def dist(series: pd.Series, top: int) -> dict:
        counts = series.value_counts()
        out = {str(v): int(counts.get(v, 0)) for v in range(top)}
        out[f"{top}+"] = int(counts[counts.index >= top].sum())
        return out
    return {
        "n": int(len(frame)),
        "qb_stack_mean": float(frame.qb_stack.mean()),
        "qb_stack_dist": dist(frame.qb_stack, 3),
        "bring_back_mean": float(frame.bring_back.mean()),
        "bring_back_dist": dist(frame.bring_back, 2),
        "double_stack_rate": float(frame.double_stack.mean()),
        "full_production_shape_rate": float(
            frame.full_production_shape.mean()),
        "naked_qb_rate": float(frame.naked_qb.mean()),
        "max_game_concentration_mean": float(
            frame.max_game_concentration.mean()),
        "max_game_concentration_dist": dist(
            frame.max_game_concentration, 5),
        "n_games_mean": float(frame.n_games.mean()),
        "max_secondary_stack_mean": float(frame.max_secondary_stack.mean()),
    }


def structure_report(
    winner_census: dict,
    pool_census: dict,
    selected_census: dict,
    constructible_cases: Sequence[dict],
) -> dict:
    """Aggregate the frozen census report."""
    if len(constructible_cases) == 0:
        raise StructureCensusError("constructible case list is empty")
    return {
        "protocol_id": PROTOCOL_ID,
        "winners": winner_census,
        "pool": pool_census,
        "selected_books": selected_census,
        "constructible_forensic": list(constructible_cases),
        # Pure roster structure: no realized score, ownership, or
        # simulated total is consumed anywhere in this census.
        "uses_realized_outcomes": False,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
