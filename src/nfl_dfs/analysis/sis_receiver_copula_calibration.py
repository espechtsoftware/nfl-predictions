"""Split-stage 2022 calibration for the frozen SIS receiver copula."""

from __future__ import annotations

import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from . import g2_qb_gumbel_factor as g2
from . import sis_receiver_copula as gate
from ..research import sis_receiver_copula as treatment


OUTPUT_META_PREFIX = "SIS_RECEIVER_COPULA_CALIBRATION_META="
OUTPUT_CHUNK_PREFIX = "SIS_RECEIVER_COPULA_CALIBRATION_CHUNK="
VERSION = "sis-receiver-copula-calibration-v1"
CALIBRATION_SEASON = 2022
TARGET_WEEKS = tuple(range(5, 19))
HISTORICAL_CACHE = "tabpfn_projections_pit_v2"
FP_SOURCE_RUN = "20260813T202926Z__same-season-alignment-last-four-v1"
SIS_SOURCE_RUN = "sis-receiver-copula-v1"
PARENT_PROTOCOL_SHA256 = (
    "045a5a8e90bdbc95b5fdfa4ff29574f71fe03fcc69701d3c39dfc159c1395274"
)
AMENDMENT_SHA256 = (
    "cb28791b593023ab6abc80becf94c901b80c095a268f154c77af15214dc6b500"
)
PARENT_PROTOCOL = "reports/2026-08-15-sis-receiver-copula-protocol.md"
AMENDMENT = (
    "reports/2026-08-15-sis-receiver-copula-calibration-book-amendment.md"
)


def _runtime_identity() -> dict[str, str]:
    run_id = os.environ.get("SIS_RECEIVER_COPULA_CALIBRATION_RUN_ID", "").strip()
    code_sha = os.environ.get("SIS_RECEIVER_COPULA_CALIBRATION_CODE_SHA", "").strip()
    if not run_id or not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise ValueError("receiver-copula calibration identity is missing")
    return {"run_id": run_id, "code_sha": code_sha}


def _verify_protocols() -> dict[str, str]:
    root = Path(os.environ.get("SIS_RECEIVER_COPULA_REPORT_ROOT", "/app"))
    paths = {
        "parent_protocol_sha256": (root / PARENT_PROTOCOL, PARENT_PROTOCOL_SHA256),
        "calibration_amendment_sha256": (root / AMENDMENT, AMENDMENT_SHA256),
    }
    output = {}
    for label, (path, expected) in paths.items():
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"receiver-copula {label} differs")
        output[label] = expected
    return output


def _frame_sha256(frame: pd.DataFrame, columns: list[str]) -> str:
    content = frame[columns].sort_values(columns, kind="stable").to_csv(
        index=False, lineterminator="\n", float_format="%.17g",
    ).encode()
    return sha256(content).hexdigest()


def load_calibration_book(panel_id: str) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """Rebuild only the accepted 2022 historical book and require parity."""
    from ..backtest.replay import (
        _market_blend_worlds, load_panel_and_dst, replay_projections,
    )
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    accepted = query_df(f"""
        SELECT season, week, gsis_id, pos, team, opp, game_id, actual,
               model_points_pre, mean_projection
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season = @season AND pos IN UNNEST(@positions)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={
            "panel_id": panel_id,
            "season": CALIBRATION_SEASON,
            "positions": list(g1.POSITIONS),
        })
    if accepted.empty or accepted.duplicated(
            ["season", "week", "gsis_id"]).any():
        raise ValueError("receiver-copula 2022 accepted snapshot differs")
    cache_keys = query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{HISTORICAL_CACHE}`
        WHERE season = @season
        ORDER BY season, week, gsis_id
        """, params={"season": CALIBRATION_SEASON})
    if cache_keys.empty or cache_keys.duplicated(
            ["season", "week", "gsis_id"]).any():
        raise ValueError("receiver-copula 2022 cache keys differ")

    with g2._historical_environment():
        if os.environ.get("GAME_SIM_USAGE", "") or os.environ.get("DIRICHLET_K", ""):
            raise ValueError("receiver-copula 2022 usage law is not multinomial")
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("receiver-copula 2022 blend weight differs")
        panel, _ = load_panel_and_dst(CALIBRATION_SEASON)
        market = market_points((CALIBRATION_SEASON,)).drop_duplicates(
            ["season", "week", "gsis_id"])
        projected, draws = replay_projections(
            panel, CALIBRATION_SEASON, n_sims=10_000, seed=0,
            return_draws=True,
        )
        projected, draws, _ = _market_blend_worlds(
            projected, draws, market, weight,
        )
        frame, aligned, parity = g2._align_historical_season(
            projected, draws, accepted, cache_keys, CALIBRATION_SEASON,
        )
    mask = frame.week.astype(int).isin(TARGET_WEEKS).to_numpy(bool)
    frame = frame.loc[mask].reset_index(drop=True)
    aligned = np.asarray(aligned)[mask]
    if frame.empty or frame.week.astype(int).min() != 5 or \
            frame.week.astype(int).max() != 18:
        raise ValueError("receiver-copula 2022 Week 5--18 population differs")
    return frame, aligned, {
        "panel": panel_id,
        "season": CALIBRATION_SEASON,
        "target_weeks": list(TARGET_WEEKS),
        "cache_table": HISTORICAL_CACHE,
        "usage_law": "production-multinomial",
        "served_position_adjustment": "none",
        "model_market_blend": "0.45/0.55",
        "worlds": 10_000,
        "seed": 0,
        "full_season_cache_rows": int(len(cache_keys)),
        "rows": int(len(frame)),
        "slates": int(frame[["season", "week"]].drop_duplicates().shape[0]),
        "parity": parity,
    }


def load_context() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load only frozen context columns and assert point-in-time identities."""
    from ..bq import query_df
    from ..config import settings

    profiles = query_df(f"""
        SELECT season, target_week, source_week_start, source_week_end,
               team, gsis_id, position, overall_routes, wide_slot_routes,
               player_wide_share, alignment_supported, source_run_id,
               source_sha256
        FROM `{settings.raw}.fantasy_points_alignment_player_l4`
        WHERE season = @season AND target_week IN UNNEST(@weeks)
        ORDER BY season, target_week, team, gsis_id
        """, params={"season": CALIBRATION_SEASON, "weeks": list(TARGET_WEEKS)})
    defense = query_df(f"""
        SELECT season, target_week, defense, offense, alignment,
               vulnerability, context_supported, prior_games,
               source_first_season, source_first_week,
               source_last_season, source_last_week, source_run_id,
               source_sha256
        FROM `{settings.raw}.sis_receiver_copula_defense_prior`
        WHERE season = @season AND target_week IN UNNEST(@weeks)
        ORDER BY season, target_week, defense, alignment
        """, params={"season": CALIBRATION_SEASON, "weeks": list(TARGET_WEEKS)})
    if profiles.empty or defense.empty:
        raise ValueError("receiver-copula calibration context is empty")
    if set(profiles.source_run_id.astype(str)) != {FP_SOURCE_RUN} or \
            set(defense.source_run_id.astype(str)) != {SIS_SOURCE_RUN}:
        raise ValueError("receiver-copula calibration context run differs")
    if not profiles.source_week_end.astype(int).lt(
            profiles.target_week.astype(int)).all():
        raise ValueError("receiver-copula Fantasy Points context is not prior")
    target_order = (
        defense.season.astype(int) * 100 + defense.target_week.astype(int)
    )
    source_order = (
        defense.source_last_season.fillna(-1).astype(int) * 100
        + defense.source_last_week.fillna(-1).astype(int)
    )
    if not source_order.lt(target_order).all():
        raise ValueError("receiver-copula SIS context is not prior")
    profile_columns = [
        "season", "target_week", "team", "gsis_id", "position",
        "overall_routes", "wide_slot_routes", "player_wide_share",
        "alignment_supported", "source_run_id", "source_sha256",
    ]
    defense_columns = [
        "season", "target_week", "defense", "alignment", "vulnerability",
        "context_supported", "prior_games", "source_last_season",
        "source_last_week", "source_run_id", "source_sha256",
    ]
    return profiles, defense, {
        "player_rows": int(len(profiles)),
        "defense_rows": int(len(defense)),
        "player_source_run": FP_SOURCE_RUN,
        "defense_source_run": SIS_SOURCE_RUN,
        "player_context_sha256": _frame_sha256(profiles, profile_columns),
        "defense_context_sha256": _frame_sha256(defense, defense_columns),
        "strictly_prior": True,
    }


def score_calibration(frame: pd.DataFrame, draws: np.ndarray) -> dict[str, Any]:
    """Compute the frozen 2022 G0/G1 calibration scorebook."""
    full_g0 = g0.evaluate_dependence(frame, draws)
    mask = (
        frame.position.isin(g1.POSITIONS)
        & frame.mean_projection.ge(g0.MIN_MEAN)
    ).to_numpy(bool)
    supported = frame.loc[mask].reset_index(drop=True)
    supported_draws = np.asarray(draws)[mask]
    supported["archetype"] = supported.position.astype(str) + "-calibration"
    pairs = g1.build_pair_book(supported)
    thresholds = np.quantile(supported_draws, 0.90, axis=1)
    actual_flags = supported.actual.to_numpy(float) > thresholds
    simulated_flags = supported_draws > thresholds[:, None]
    contributions = g1.pair_contributions(pairs, actual_flags, simulated_flags)
    cells, broad = g1.summarize_cells(contributions)
    scorecard = g1.pair_scorecard(pairs, supported, supported_draws)
    g0_abs, g0_cells = g2._g0_abs_log_error(full_g0)
    g1_cells = {}
    for relationship, weight in g2.PRIMARY_WEIGHTS.items():
        row = broad.get(relationship, {})
        value = row.get("log_simulated_to_realized")
        if row.get("supported") and value is not None and np.isfinite(value):
            g1_cells[relationship] = {
                "absolute_log_error": abs(float(value)),
                "weight": float(weight),
            }
    g1_abs = float(sum(
        row["weight"] * row["absolute_log_error"] for row in g1_cells.values()
    ))
    return {
        "population": {
            "rows": int(len(supported)),
            "slates": int(supported[["season", "week"]].drop_duplicates().shape[0]),
            "pairs": int(len(pairs)),
            "relationship_counts": {
                str(key): int(value) for key, value in
                pairs.relationship.value_counts().sort_index().items()
            },
        },
        "archetype_law": "position-calibration",
        "g0": full_g0,
        "cells": cells,
        "broad_relationships": broad,
        "scorecard": scorecard,
        "primary": {
            "joint_q90_brier": g2._weighted_score(
                scorecard, "joint_q90_brier",
            ),
            "variogram_p0_5": g2._weighted_score(
                scorecard, "variogram_p0_5",
            ),
            "g0_absolute_log_error_sum": g0_abs,
            "g0_cell_errors": g0_cells,
            "g1_weighted_absolute_log_error_sum": g1_abs,
            "g1_relationship_errors": g1_cells,
        },
    }


def _marginals_equal(control: np.ndarray, candidate: np.ndarray) -> bool:
    return bool(all(
        np.array_equal(
            np.sort(control[row], kind="stable"),
            np.sort(candidate[row], kind="stable"),
        )
        for row in range(len(control))
    ))


def _emit(report: dict[str, Any]) -> None:
    meta, chunks = g1.encode_report_transport(report)
    print(OUTPUT_META_PREFIX + json.dumps(meta, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print(f"{OUTPUT_CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}", flush=True)


def run(panel_id: str) -> dict[str, Any]:
    expected_panel = os.environ.get("SIS_RECEIVER_COPULA_CALIBRATION_PANEL", "").strip()
    if panel_id != expected_panel or panel_id != gate.REFERENCE_HISTORICAL_PANEL:
        raise ValueError("receiver-copula calibration panel differs")
    runtime = _runtime_identity()
    protocols = _verify_protocols()
    frame, control, book_audit = load_calibration_book(panel_id)
    profiles, defense, source_audit = load_context()
    receiver_scores, eligible, context_audit = treatment.build_receiver_context(
        frame, profiles, defense,
    )
    rows = []
    full_scores: dict[str, dict] = {}
    grid_invariants: dict[str, dict] = {}
    for strength in gate.STRENGTH_GRID:
        candidate, candidate_audit = treatment.apply_receiver_copula(
            control, frame, receiver_scores, eligible, strength=strength,
        )
        invariants = {
            "finite": bool(np.isfinite(candidate).all()),
            "exact_marginals": _marginals_equal(control, candidate),
            "ineligible_rows_unchanged": bool(np.array_equal(
                control[~eligible], candidate[~eligible],
            )),
            "maximum_mean_delta_at_most_1e_10": bool(
                candidate_audit["maximum_mean_delta"] <= 1e-10
            ),
        }
        invariants["passes"] = bool(all(invariants.values()))
        score = score_calibration(frame, candidate)
        selector = gate.calibration_grid_row(score, strength)
        selector["invariants_pass"] = invariants["passes"]
        if not invariants["passes"]:
            selector["required_support"] = False
            selector["support_failure"] = "calibration treatment invariant"
        key = format(strength, ".2f")
        rows.append(selector)
        full_scores[key] = score
        grid_invariants[key] = {**invariants, "treatment_audit": candidate_audit}
        del candidate, score
        gc.collect()

    try:
        selected = gate.select_calibration_grid(rows)
    except ValueError as exc:
        selected = None
        selection_failure = str(exc)
    else:
        selection_failure = None
    selected_repeat_exact = False
    if selected is not None:
        first, first_audit = treatment.apply_receiver_copula(
            control, frame, receiver_scores, eligible,
            strength=float(selected["strength"]),
        )
        second, second_audit = treatment.apply_receiver_copula(
            control, frame, receiver_scores, eligible,
            strength=float(selected["strength"]),
        )
        selected_repeat_exact = bool(
            np.array_equal(first, second) and first_audit == second_audit
        )
        del first, second
        gc.collect()
    passes = bool(
        selected is not None
        and selected_repeat_exact
        and all(value["passes"] for value in grid_invariants.values())
    )
    report = {
        "version": VERSION,
        "run_identity": runtime,
        "panel": panel_id,
        "protocols": protocols,
        "book": book_audit,
        "sources": source_audit,
        "context": context_audit,
        "strength_grid": list(gate.STRENGTH_GRID),
        "selector_grid": rows,
        "scorebooks": full_scores,
        "grid_invariants": grid_invariants,
        "selected": selected,
        "selection_failure": selection_failure,
        "selected_repeat_exact": selected_repeat_exact,
        "passes": passes,
        "disposition": (
            "sis-receiver-copula-calibration-passes"
            if passes else "sis-receiver-copula-calibration-invalid-or-inconclusive"
        ),
        "heldout_evaluation_licensed": passes,
        "retrospective_exact80_licensed": False,
        "heldout_outcomes_queried": False,
    }
    _emit(report)
    return report


__all__ = [
    "load_calibration_book", "load_context", "run", "score_calibration",
]
