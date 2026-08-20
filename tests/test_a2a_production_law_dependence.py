from __future__ import annotations

import copy
import math

import pandas as pd
import pytest

from nfl_dfs.analysis.a2a_production_law_dependence import (
    CONTROL_POINT_GAPS,
    EQUIVALENCE_BANDS,
    MECHANISM_ROLES,
    REALIZED_TARGETS,
    REGISTERED_BLOCKS,
    REGISTERED_CELLS,
    evaluate_remeasurement,
    support_accounting,
)


def _report(worlds: int) -> dict:
    return {
        "population": {"rows": 9_469, "slates": 54, "n_sims": worlds},
        "cells": {
            cell: {
                "realized_estimate": REALIZED_TARGETS[cell],
                "simulated_estimate": REALIZED_TARGETS[cell],
                "log_simulated_to_realized": 0.0,
                "cluster_ci95_low": -0.01,
                "cluster_ci95_high": 0.01,
                "equivalence_band_abs_log": EQUIVALENCE_BANDS[cell],
                "supported": True,
                "classification": "equivalent",
            }
            for cell in REGISTERED_CELLS
        },
    }


def _passing_inputs() -> tuple[dict[str, dict], dict]:
    return (
        {block: _report(10_000) for block in REGISTERED_BLOCKS},
        _report(50_000),
    )


def test_passing_gate_licenses_only_next_protocol() -> None:
    blocks, aggregate = _passing_inputs()
    result = evaluate_remeasurement(blocks, aggregate)

    assert result["passes"] is True
    assert result["disposition"] == (
        "a2a-law-shape-passes-single-stack-protocol-licensed"
    )
    assert result["qb_wr_location"] == "equivalent"
    assert result["licenses"] == {
        "uses_realized_outcomes": True,
        "actual_outcomes_queried": True,
        "candidate_or_lineup_scores_read": False,
        "single_stack_protocol_licensed": True,
        "single_stack_arm_licensed": False,
        "exact80_scoring_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }


def test_qb_wr_overshoot_is_a_miss_even_when_direction_changed() -> None:
    blocks, aggregate = _passing_inputs()
    gap = EQUIVALENCE_BANDS["qb_wr"] + 0.001
    aggregate["cells"]["qb_wr"].update({
        "simulated_estimate": REALIZED_TARGETS["qb_wr"] * math.exp(gap),
        "log_simulated_to_realized": gap,
        "cluster_ci95_low": 0.001,
        "cluster_ci95_high": 0.2,
        "classification": "material-miss",
    })
    result = evaluate_remeasurement(blocks, aggregate)

    assert result["passes"] is False
    assert result["qb_wr_location"] == "overshoot-above-realized-equivalence"
    assert result["disposition"] == "a2a-law-shape-miss-qb-wr-overshoot"
    assert result["licenses"]["single_stack_protocol_licensed"] is False


def test_attenuation_only_cell_cannot_cross_and_be_called_repaired() -> None:
    blocks, aggregate = _passing_inputs()
    aggregate["cells"]["qb_te"].update({
        "simulated_estimate": REALIZED_TARGETS["qb_te"] * math.exp(-0.5),
        "log_simulated_to_realized": -0.5,
        "cluster_ci95_low": -0.7,
        "cluster_ci95_high": -0.2,
        "classification": "material-miss",
    })
    result = evaluate_remeasurement(blocks, aggregate)

    assert result["passes"] is False
    assert result["conditions"]["qb_te_attenuation_only_guard"] is False
    assert result["disposition"] == (
        "a2a-law-shape-miss-attenuation-or-protected-cell"
    )
    assert MECHANISM_ROLES["qb_te"] == "attenuation-only-no-qb-te-recoupling"


def test_same_side_strict_improvement_may_remain_outside_band() -> None:
    blocks, aggregate = _passing_inputs()
    for block in blocks.values():
        gap = CONTROL_POINT_GAPS["multiplicity_ge2"] / 2
        block["cells"]["multiplicity_ge2"].update({
            "simulated_estimate": REALIZED_TARGETS[
                "multiplicity_ge2"
            ] * math.exp(gap),
            "log_simulated_to_realized": gap,
            "cluster_ci95_low": -0.2,
            "cluster_ci95_high": 0.2,
            "classification": "inconclusive",
        })
    gap = CONTROL_POINT_GAPS["multiplicity_ge2"] / 2
    aggregate["cells"]["multiplicity_ge2"].update({
        "simulated_estimate": REALIZED_TARGETS[
            "multiplicity_ge2"
        ] * math.exp(gap),
        "log_simulated_to_realized": gap,
        "cluster_ci95_low": -0.2,
        "cluster_ci95_high": 0.2,
        "classification": "inconclusive",
    })
    result = evaluate_remeasurement(blocks, aggregate)

    assert result["aggregate_cell_guards"]["multiplicity_ge2"] is True
    assert result["passes"] is True


def test_unsupported_registered_cell_is_inconclusive() -> None:
    blocks, aggregate = _passing_inputs()
    aggregate["cells"]["te_te"].update({
        "simulated_estimate": None,
        "log_simulated_to_realized": None,
        "cluster_ci95_low": None,
        "cluster_ci95_high": None,
        "supported": False,
        "classification": "unsupported",
    })
    result = evaluate_remeasurement(blocks, aggregate)

    assert result["passes"] is False
    assert result["disposition"] == "a2a-law-shape-inconclusive"


def test_classification_is_recomputed_from_ci_and_cannot_be_forged() -> None:
    blocks, aggregate = _passing_inputs()
    aggregate["cells"]["qb_wr"].update({
        "cluster_ci95_low": -99.0,
        "cluster_ci95_high": 99.0,
        "classification": "equivalent",
    })
    with pytest.raises(ValueError, match="classification differs"):
        evaluate_remeasurement(blocks, aggregate)


def test_realized_target_or_grid_drift_fails_closed() -> None:
    blocks, aggregate = _passing_inputs()
    bad = copy.deepcopy(aggregate)
    bad["cells"]["qb_wr"]["realized_estimate"] += 1e-12
    with pytest.raises(ValueError, match="realized target differs"):
        evaluate_remeasurement(blocks, bad)

    with pytest.raises(ValueError, match="exact R0--R4"):
        evaluate_remeasurement({"R0": blocks["R0"]}, aggregate)


def test_coverage_accounting_is_mutually_exclusive_and_reporting_only() -> None:
    rows = []

    def add(team: str, players: list[tuple[str, str]]) -> None:
        rows.extend({
            "season": 2023,
            "week": 1,
            "player_id": player_id,
            "position": position,
            "team": team,
            "mean_projection": 8.0,
        } for player_id, position in players)

    add("A", [("a-q", "QB"), ("a-w1", "WR"), ("a-w2", "WR"), ("a-r", "RB")])
    add("B", [("b-w1", "WR"), ("b-w2", "WR"), ("b-r", "RB")])
    add("C", [("c-q1", "QB"), ("c-q2", "QB"), ("c-w1", "WR"), ("c-w2", "WR")])
    add("D", [("d-q", "QB"), ("d-w", "WR"), ("d-r", "RB")])
    report = support_accounting(pd.DataFrame(rows))

    assert report["reporting_only_not_a_mechanism_or_gate"] is True
    assert report["eligible_team_slate_groups"] == 4
    assert report["covered_groups"] == 1
    assert report["skipped_groups"] == 3
    assert report["skipped_group_reasons"] == {
        "zero_eligible_qb": 1,
        "multiple_eligible_qbs": 1,
        "fewer_than_two_eligible_wrs": 1,
    }
    assert report["covered_group_fraction"] == 0.25
    assert report["covered_qb_anchor_rows_unchanged"] == 1
    assert report["directly_transformed_non_qb_rows"] == 3
    assert report["skipped_group_eligible_rows_unchanged"] == 10
    assert report["eligible_rows"] == 14
