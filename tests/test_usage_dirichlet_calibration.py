from pathlib import Path

import numpy as np
import pandas as pd

from nfl_dfs.analysis import usage_dirichlet_calibration as diagnostic


def _usage_group(
    observed=(15, 9, 4, 2),
    probabilities=(0.50, 0.30, 0.15, 0.05),
    index=1,
):
    return diagnostic.UsageGroup(
        season=2022,
        week=index,
        team=f"T{index}",
        kind="targets",
        players=("a", "b", "c", "d"),
        probabilities=np.asarray(probabilities, dtype=float),
        observed=np.asarray(observed, dtype=np.int64),
    )


def test_dirichlet_multinomial_converges_to_production_multinomial():
    group = _usage_group()
    production = diagnostic.multinomial_nll(group)
    finite = diagnostic.dirichlet_multinomial_nll(group, 1e9)
    assert abs(production - finite) < 1e-5


def test_frozen_estimator_recovers_synthetic_finite_concentration():
    rng = np.random.default_rng(20260811)
    p = np.asarray([0.50, 0.30, 0.15, 0.05])
    groups = []
    for index in range(600):
        share = rng.dirichlet(35.0 * p)
        observed = rng.multinomial(30, share)
        groups.append(_usage_group(observed, p, index + 1))
    fit = diagnostic.fit_concentration(groups)
    assert fit["optimizer_success"]
    assert fit["strictly_interior"]
    assert 25.0 < fit["selected_k"] < 50.0


def test_group_builder_excludes_positive_usage_on_zero_model_mean():
    rows = pd.DataFrame({
        "season": [2022] * 6,
        "week": [1] * 6,
        "team": ["A"] * 3 + ["B"] * 3,
        "gsis_id": ["a1", "a2", "a3", "b1", "b2", "b3"],
        "position": ["RB", "WR", "TE", "RB", "WR", "TE"],
        "was_active": [True] * 6,
        "y_targets": [10, 9, 1, 9, 7, 4],
        "y_carries": [10, 5, 0, 9, 6, 0],
    })
    predicted = pd.DataFrame({
        "targets": [10.0, 5.0, 0.0, 10.0, 5.0, 2.0],
        "carries": [9.0, 3.0, 1.0, 8.0, 4.0, 1.0],
    })
    groups, audit = diagnostic.build_usage_groups(rows, predicted, 2022)
    target_groups = [group for group in groups if group.kind == "targets"]
    assert len(target_groups) == 1
    assert target_groups[0].team == "B"
    assert audit["targets"]["excluded_zero_mean_groups"] == 1
    assert audit["targets"]["opportunity_coverage"] == 0.5
    assert audit["carries"]["retained_groups"] == 2


def test_usage_gate_follows_only_frozen_likelihood_rules():
    records = []
    for season, fitted in ((2023, 9.0), (2024, 9.0), (2025, 11.0)):
        for kind in diagnostic.KINDS:
            records.append({
                "season": season,
                "week": 1,
                "team": f"{season}-{kind}",
                "kind": kind,
                "players": 3,
                "opportunities": 30,
                "production_nll": 10.0,
                "fitted_nll": fitted,
                "fitted_minus_production": fitted - 10.0,
            })
    scores = pd.DataFrame(records)
    population = {
        season: {
            kind: {"opportunity_coverage": 1.0}
            for kind in diagnostic.KINDS
        }
        for season in diagnostic.ALL_SEASONS
    }
    fit = {"optimizer_success": True, "strictly_interior": True}
    gate = diagnostic.usage_gate(fit, population, scores)
    assert gate["passes"]
    assert gate["improving_seasons"] == 2

    population[2025]["carries"]["opportunity_coverage"] = 0.94
    assert not diagnostic.usage_gate(fit, population, scores)["passes"]


def test_usage_cli_and_cloud_runner_are_packaged():
    root = Path(__file__).resolve().parents[1]
    cli = (root / "src/nfl_dfs/cli.py").read_text()
    runner = root / "scripts/cloud_usage_dirichlet_calibration.sh"
    assert "usage-dirichlet-calibration-diagnostic" in cli
    assert runner.is_file()
    text = runner.read_text()
    assert "20260811-data-fitted-usage-k-v1" in text
    assert "USAGE_DIRICHLET_CALIBRATION_JSON=" in text
