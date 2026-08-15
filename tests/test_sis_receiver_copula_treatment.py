from __future__ import annotations

import numpy as np
import pandas as pd

from nfl_dfs.research.sis_receiver_copula import (
    apply_receiver_copula,
    build_receiver_context,
)


def _fixture():
    frame = pd.DataFrame([
        (2025, 5, "G", "A", "B", "qb", "QB", 20.0),
        (2025, 5, "G", "A", "B", "wr_wide", "WR", 15.0),
        (2025, 5, "G", "A", "B", "wr_slot", "WR", 10.0),
        (2025, 5, "G", "A", "B", "rb", "RB", 12.0),
        (2025, 5, "G", "A", "B", "te", "TE", 8.0),
    ], columns=[
        "season", "week", "game_id", "team", "opp", "gsis_id",
        "position", "mean_projection",
    ])
    profiles = pd.DataFrame([
        (2025, 5, "A", "wr_wide", "WR", 80.0, 80.0, 0.9, True),
        (2025, 5, "A", "wr_slot", "WR", 40.0, 40.0, 0.1, True),
    ], columns=[
        "season", "target_week", "team", "gsis_id", "position",
        "overall_routes", "wide_slot_routes", "player_wide_share",
        "alignment_supported",
    ])
    defense = pd.DataFrame([
        (2025, 5, "B", "wide", 0.4, True),
        (2025, 5, "B", "slot", 0.1, True),
    ], columns=[
        "season", "target_week", "defense", "alignment",
        "vulnerability", "context_supported",
    ])
    return frame, profiles, defense


def test_context_is_receiver_specific_centered_and_bounded():
    frame, profiles, defense = _fixture()
    scores, eligible, audit = build_receiver_context(
        frame, profiles, defense
    )
    assert audit["eligible_groups"] == 1
    assert eligible.tolist() == [False, True, True, False, False]
    assert scores[1] == 1.0
    assert scores[2] == -1.0


def test_treatment_preserves_exact_marginals_and_non_receivers():
    frame, profiles, defense = _fixture()
    scores, eligible, _ = build_receiver_context(frame, profiles, defense)
    rng = np.random.default_rng(17)
    control = rng.normal(size=(len(frame), 200))
    treatment, audit = apply_receiver_copula(
        control, frame, scores, eligible, strength=1.0
    )
    assert audit["changed_rows"] == 2
    assert audit["maximum_mean_delta"] <= 1e-12
    assert np.array_equal(treatment[~eligible], control[~eligible])
    for left, right in zip(control, treatment, strict=True):
        assert np.array_equal(np.sort(left), np.sort(right))
    repeated, repeated_audit = apply_receiver_copula(
        control, frame, scores, eligible, strength=1.0
    )
    assert np.array_equal(treatment, repeated)
    assert audit == repeated_audit


def test_zero_strength_is_inert():
    frame, profiles, defense = _fixture()
    scores, eligible, _ = build_receiver_context(frame, profiles, defense)
    control = np.arange(len(frame) * 20, dtype=float).reshape(len(frame), 20)
    treatment, audit = apply_receiver_copula(
        control, frame, scores, eligible, strength=0.0
    )
    assert np.array_equal(treatment, control)
    assert audit["changed_rows"] == 0


def test_unresolved_profiles_count_against_route_mass_without_ambiguous_key():
    frame, profiles, defense = _fixture()
    unresolved = pd.DataFrame([
        (2025, 5, "A", None, "WR", 120.0, 120.0, 0.5, False),
        (2025, 5, "A", None, "WR", 120.0, 120.0, 0.5, False),
    ], columns=profiles.columns)
    profiles = pd.concat([profiles, unresolved], ignore_index=True)

    _scores, eligible, audit = build_receiver_context(
        frame, profiles, defense,
    )

    assert not eligible.any()
    assert audit["support_failures"] == {"route-mass": 1}


def test_subfloor_backup_qb_does_not_change_eligible_group_geometry():
    frame, profiles, defense = _fixture()
    backup = pd.DataFrame([{
        "season": 2025,
        "week": 5,
        "game_id": "G",
        "team": "A",
        "opp": "B",
        "gsis_id": "qb_backup",
        "position": "QB",
        "mean_projection": 3.99,
    }])
    frame = pd.concat([frame, backup], ignore_index=True)
    scores, eligible, context = build_receiver_context(frame, profiles, defense)
    assert context["eligible_groups"] == 1
    assert eligible.tolist() == [False, True, True, False, False, False]

    rng = np.random.default_rng(260_815)
    control = rng.normal(size=(len(frame), 200))
    treatment, audit = apply_receiver_copula(
        control, frame, scores, eligible, strength=1.0
    )
    assert audit["eligible_groups"] == 1
    assert audit["changed_rows"] == 2
    assert np.array_equal(treatment[~eligible], control[~eligible])
    for left, right in zip(control, treatment, strict=True):
        assert np.array_equal(np.sort(left), np.sort(right))
