from __future__ import annotations

from hashlib import sha256

import numpy as np
import pandas as pd

from nfl_dfs.analysis import sis_receiver_copula_calibration as calibration


def test_protocol_verification_binds_both_frozen_documents(tmp_path, monkeypatch):
    parent = tmp_path / "parent.md"
    amendment = tmp_path / "amendment.md"
    parent.write_text("parent", encoding="utf-8")
    amendment.write_text("amendment", encoding="utf-8")
    monkeypatch.setattr(calibration, "PARENT_PROTOCOL", "parent.md")
    monkeypatch.setattr(calibration, "AMENDMENT", "amendment.md")
    monkeypatch.setattr(
        calibration, "PARENT_PROTOCOL_SHA256",
        sha256(parent.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        calibration, "AMENDMENT_SHA256",
        sha256(amendment.read_bytes()).hexdigest(),
    )
    monkeypatch.setenv("SIS_RECEIVER_COPULA_REPORT_ROOT", str(tmp_path))

    assert calibration._verify_protocols() == {
        "parent_protocol_sha256": sha256(parent.read_bytes()).hexdigest(),
        "calibration_amendment_sha256": sha256(amendment.read_bytes()).hexdigest(),
    }


def test_marginal_check_is_exact_and_order_independent():
    control = np.asarray([[1.0, 2.0, 3.0], [7.0, 8.0, 9.0]])
    permuted = np.asarray([[3.0, 1.0, 2.0], [8.0, 9.0, 7.0]])
    changed = permuted.copy()
    changed[1, 2] = 7.5

    assert calibration._marginals_equal(control, permuted)
    assert not calibration._marginals_equal(control, changed)


def test_calibration_score_uses_complete_pair_scorebook(monkeypatch):
    frame = pd.DataFrame({
        "season": [2022, 2022],
        "week": [5, 5],
        "gsis_id": ["qb", "wr"],
        "position": ["QB", "WR"],
        "team": ["A", "A"],
        "opp": ["B", "B"],
        "game_id": ["g", "g"],
        "actual": [20.0, 10.0],
        "mean_projection": [18.0, 12.0],
    })
    draws = np.asarray([[10.0, 20.0], [5.0, 15.0]])
    pairs = pd.DataFrame({"relationship": ["QB_WR"]})
    monkeypatch.setattr(
        calibration.g0, "evaluate_dependence",
        lambda _frame, _draws: {"cells": {"qb_wr": {"supported": True}}},
    )
    monkeypatch.setattr(calibration.g1, "build_pair_book", lambda _frame: pairs)
    monkeypatch.setattr(
        calibration.g1, "pair_contributions",
        lambda *_args: pd.DataFrame({"relationship": ["QB_WR"]}),
    )
    broad = {
        "QB_WR": {"supported": True, "log_simulated_to_realized": -0.2},
    }
    monkeypatch.setattr(
        calibration.g1, "summarize_cells", lambda _values: ({}, broad),
    )
    scorecard = {
        relationship: {"joint_q90_brier": 0.02, "variogram_p0_5": 1.5}
        for relationship in calibration.g2.PRIMARY_WEIGHTS
    }
    monkeypatch.setattr(
        calibration.g1, "pair_scorecard", lambda *_args: scorecard,
    )
    monkeypatch.setattr(
        calibration.g2, "_g0_abs_log_error",
        lambda _report: (0.3, {"qb_wr": 0.3}),
    )

    result = calibration.score_calibration(frame, draws)

    assert np.isclose(result["primary"]["joint_q90_brier"], 0.02)
    assert np.isclose(result["primary"]["variogram_p0_5"], 1.5)
    assert np.isclose(result["primary"]["g0_absolute_log_error_sum"], 0.3)
    assert np.isclose(
        result["primary"]["g1_relationship_errors"]["QB_WR"][
            "absolute_log_error"
        ],
        0.2,
    )
