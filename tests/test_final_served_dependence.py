import itertools
import base64
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import final_served_dependence as g0


ROOT = Path(__file__).parents[1]


def test_poisson_binomial_tail_is_exact():
    probabilities = np.array([0.2, 0.3])
    assert g0.poisson_binomial_tail(probabilities, 0) == 1.0
    assert g0.poisson_binomial_tail(probabilities, 1) == pytest.approx(0.44)
    assert g0.poisson_binomial_tail(probabilities, 2) == pytest.approx(0.06)
    assert g0.poisson_binomial_tail(probabilities, 3) == 0.0


def test_materiality_and_equivalence_are_distinct():
    band = np.log(1.15)
    assert g0._classify(0.01, -0.03, 0.04, band, True) == "equivalent"
    assert g0._classify(0.20, 0.10, 0.30, band, True) == "material-miss"
    assert g0._classify(0.20, -0.01, 0.30, band, True) == "inconclusive"
    assert g0._classify(0.20, 0.10, 0.30, band, False) == "unsupported"


def _independent_book(seed=22):
    rng = np.random.default_rng(seed)
    positions = ["QB", "RB", "RB", "WR", "WR", "TE", "TE"]
    rows = []
    for season, week, team in itertools.product(
        (2023, 2024, 2025), range(1, 19), range(12)
    ):
        for slot, position in enumerate(positions):
            rows.append({
                "season": season,
                "week": week,
                "team": f"T{team:02d}",
                "position": position,
                "gsis_id": f"{season}-{week}-{team}-{slot}",
                "mean_projection": 10.0,
            })
    frame = pd.DataFrame(rows)
    draws = rng.normal(10.0, 4.0, size=(len(frame), 200))
    frame["actual"] = draws[:, 0]
    return frame, draws


def test_evaluate_dependence_emits_frozen_cells_and_is_reproducible():
    frame, draws = _independent_book()
    first = g0.evaluate_dependence(frame, draws, n_bootstraps=60)
    second = g0.evaluate_dependence(frame, draws, n_bootstraps=60)
    assert first == second
    assert set(first["cells"]) == set(g0.CELL_BANDS)
    assert first["population"] == {
        "rows": len(frame),
        "slates": 54,
        "mean_projection_minimum": 4.0,
        "n_sims": 200,
        "pooled_simulated_exceedance_probability": pytest.approx(0.1),
    }
    assert first["bootstrap"] == {"clusters": 54, "replicates": 60, "seed": 1701}
    assert first["cells"]["multiplicity_ge2"]["supported"]
    assert not first["cells"]["multiplicity_ge4"]["supported"]
    assert all(
        first["cells"][cell]["support"]["directed_pair_team_weeks"] >= 500
        for cell in (*g0.QB_CELLS.values(), *g0.SAME_POSITION_CELLS.values())
    )


def test_evaluate_dependence_rejects_bad_alignment():
    frame, draws = _independent_book()
    with pytest.raises(ValueError, match="rows x"):
        g0.evaluate_dependence(frame, draws[:-1], n_bootstraps=10)
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    duplicated_draws = np.vstack([draws, draws[[0]]])
    with pytest.raises(ValueError, match="duplicate"):
        g0.evaluate_dependence(duplicated, duplicated_draws, n_bootstraps=10)


def test_terminal_schedule_and_cache_contracts_restore_environment(monkeypatch):
    schedule = {
        str(season): {"factors": {"QB": 0.95, "RB": 1.0, "WR": 1.05, "TE": 0.9}}
        for season in (2023, 2024, 2025)
    }
    encoded = base64.b64encode(json.dumps(schedule).encode()).decode()
    assert set(g0._selected_schedule({"G0_POSITION_SCHEDULE_B64": encoded})) == {
        2023, 2024, 2025}
    # Cloud Run's --set-env-vars transport strips trailing base64 padding.
    assert set(g0._selected_schedule({
        "G0_POSITION_SCHEDULE_B64": encoded.rstrip("=")
    })) == {2023, 2024, 2025}
    with pytest.raises(ValueError, match="wrong seasons"):
        g0._selected_schedule({
            "G0_POSITION_SCHEDULE_B64": base64.b64encode(
                json.dumps({"2023": schedule["2023"]}).encode()).decode()
        })

    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "prior")
    with g0._selected_cache("tabpfn_active_label_treatment_v2"):
        assert os.environ["TABPFN_MARGINAL_TABLE"] == "tabpfn_active_label_treatment_v2"
    assert os.environ["TABPFN_MARGINAL_TABLE"] == "prior"
    with pytest.raises(ValueError, match="unlicensed"):
        with g0._selected_cache("arbitrary_table"):
            pass


def test_g0_cloud_path_is_terminal_bound_and_read_only():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    launch = (
        ROOT / "scripts/cloud_g0_final_served_dependence.sh"
    ).read_text(encoding="utf-8")
    finish = (
        ROOT / "scripts/cloud_finish_g0_final_served_dependence.sh"
    ).read_text(encoding="utf-8")
    assert "g0-final-served-dependence" in cli
    assert "selected_team_qb.txt" in launch
    assert "selected_active_label.txt" in launch
    assert "selected_sched.txt" in launch
    assert "selected_usage.txt" in launch
    assert "team_qb_final_served_sha256" in launch
    assert "active_label_selection_sha256" in launch
    assert "sched_selection_sha256" in launch
    assert "cache_preflight_sha256" in launch
    assert "WRITE_" not in launch
    assert "G0_FINAL_SERVED_DEPENDENCE_JSON=" in finish
    assert "immutable G0 report already exists" in finish
