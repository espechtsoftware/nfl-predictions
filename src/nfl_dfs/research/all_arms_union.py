"""All-arms union candidate census (B1, 2026-08-18).

`replay_candidates_staging` retains rosters with actual scores for 104
panel_run_ids — essentially every same-image arm/control ever run. The
mechanically-complete cross-arm union candidate ceiling per slate is
therefore a single aggregation over already-registered data, and it is
the exact ceiling of "better selection from the corpus" in its widest
defensible sense: if the union C approaches the 194-mean target, a
union-admission policy (CBWU-OI's mechanism generalized across arms) is
the fastest existing-data path; if it stays well short, the target is
construction-bound and the answer lives in residual columns and law work.

Mechanics frozen here: MECHANICAL inclusion of every supplied panel (no
per-arm cherry-picking — that bound on the selection effect is what makes
the ceiling readable), legality revalidation of every distinct roster
under the CORRECTED slate snapshot and the production strategy contract
(QB+2, one bring-back, $49k floor), and revaluation of every roster from
corrected snapshot actuals (cross-era stored scores are treated as labels
to reconcile, never as truth). Cross-era roster identities transfer;
their generating beliefs do not, and nothing here claims otherwise.

Outcome-facing (snapshot actuals are read): execution only under the
frozen protocol reports/2026-08-18-all-arms-union-census-protocol.md,
diagnostic-only, no adoption or promotion. Pure computation lives here;
warehouse IO stays in scripts/union_candidate_census.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .final_forensic import audit_roster

PROTOCOL_ID = "20260818-all-arms-union-census-v1"
THRESHOLDS = (240, 230, 220, 210, 200, 194, 187)
QB_STACK_MIN = 2
BRING_BACK_MIN = 1
MIN_SALARY = 49_000
SALARY_CAP = 50_000


class UnionCensusError(ValueError):
    """Fail-closed contract violation."""


def _roster_key(players: object) -> str:
    ids = sorted(p for p in str(players).split(",") if p)
    if len(ids) != 9 or len(set(ids)) != 9:
        raise UnionCensusError(f"roster is not nine unique ids: {players!r}")
    return ",".join(ids)


def slate_union_census(
    candidates: pd.DataFrame,
    players: pd.DataFrame,
) -> dict:
    """Union ceiling for one slate.

    ``candidates``: rows from every panel for this slate with
    ``panel_run_id``, ``players`` (comma ids) and ``actual_score`` (the
    stored label, reconciled but not trusted). ``players``: the corrected
    slate snapshot (id/pos/team/opp/game_id/salary/actual).
    """
    required = {"panel_run_id", "players", "actual_score"}
    if missing := required - set(candidates.columns):
        raise UnionCensusError(f"candidates lack {sorted(missing)}")
    if candidates.empty:
        raise UnionCensusError("no candidates supplied for the slate")

    frame = candidates.copy()
    frame["roster_key"] = frame.players.map(_roster_key)
    actual_by_id = dict(zip(
        players.id.astype(str), players.actual.astype(float)))

    rows = []
    dropped_illegal = 0
    dropped_unmatched = 0
    label_mismatches = 0
    for key, group in frame.groupby("roster_key", observed=True):
        ids = key.split(",")
        if any(pid not in actual_by_id for pid in ids):
            dropped_unmatched += 1
            continue
        audit = audit_roster(
            players, ids,
            min_salary=MIN_SALARY, salary_cap=SALARY_CAP,
            qb_stack_min=QB_STACK_MIN, bring_back_min=BRING_BACK_MIN,
        )
        if not audit["valid"]:
            dropped_illegal += 1
            continue
        revalued = float(sum(actual_by_id[pid] for pid in ids))
        stored = pd.to_numeric(group.actual_score, errors="coerce")
        if not np.allclose(stored.dropna(), revalued, atol=1e-3):
            label_mismatches += 1
        rows.append({
            "roster_key": key,
            "revalued_score": revalued,
            "panels": sorted(set(group.panel_run_id.astype(str))),
        })
    if not rows:
        raise UnionCensusError(
            "no legal, matched roster survived revalidation")
    union = pd.DataFrame(rows)
    best = union.loc[union.revalued_score.idxmax()]
    return {
        "n_panels": int(frame.panel_run_id.nunique()),
        "n_distinct_rosters": int(len(frame.roster_key.unique())),
        "n_legal_rosters": int(len(union)),
        "dropped_illegal": dropped_illegal,
        "dropped_unmatched_players": dropped_unmatched,
        "stored_label_mismatch_rosters": label_mismatches,
        "union_c": float(best.revalued_score),
        "union_c_panels": list(best.panels),
        "thresholds": {
            str(t): bool((union.revalued_score >= t).any())
            for t in THRESHOLDS
        },
    }


def union_census_report(
    slate_results: pd.DataFrame,
    comparison: dict[str, float] | None = None,
) -> dict:
    """Aggregate per-slate census rows into the frozen report.

    ``slate_results``: one row per slate with ``season``, ``week`` and the
    fields of :func:`slate_union_census` (thresholds expanded to columns
    ``clears_<t>``). ``comparison``: named mean-C anchors, e.g.
    {"canonical_pool_c": 181.07, "cbwu_oi_pool_c": 186.73}.
    """
    required = {"season", "week", "union_c"}
    if missing := required - set(slate_results.columns):
        raise UnionCensusError(f"slate results lack {sorted(missing)}")
    if slate_results.duplicated(["season", "week"]).any():
        raise UnionCensusError("duplicate slates in the census")
    grid = {}
    for t in THRESHOLDS:
        column = f"clears_{t}"
        if column in slate_results:
            grid[str(t)] = int(slate_results[column].astype(bool).sum())
    report = {
        "protocol_id": PROTOCOL_ID,
        "n_slates": int(len(slate_results)),
        "union_c_mean": float(slate_results.union_c.mean()),
        "union_c_median": float(slate_results.union_c.median()),
        "union_grid": grid,
        "by_season": {
            str(season): float(group.union_c.mean())
            for season, group in slate_results.groupby("season")
        },
        "uses_realized_outcomes": True,
        "fit_performed": False,
        "gate_decision": None,
    }
    if comparison:
        report["comparison_anchors"] = {
            name: {
                "mean_c": float(value),
                "union_minus_anchor": float(
                    slate_results.union_c.mean() - float(value)),
            }
            for name, value in comparison.items()
        }
    return report
