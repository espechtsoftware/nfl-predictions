from copy import deepcopy

from nfl_dfs.analysis.g2_qb_gumbel_factor import (
    gate_decision,
    select_grid_cell,
)


def _arm(value: float) -> dict:
    relationship_errors = {
        relationship: {"absolute_log_error": value, "weight": 1.0}
        for relationship in ("QB_WR", "QB_TE")
    }
    return {
        "primary": {
            "joint_q90_brier": value,
            "variogram_p0_5": value,
            "g0_absolute_log_error_sum": value,
            "g1_weighted_absolute_log_error_sum": value,
            "g1_relationship_errors": relationship_errors,
        },
    }


def test_grid_tiebreak_uses_variogram_then_lower_theta():
    grid = [
        {"theta_wr": 1.4, "theta_te": 1.2,
         "joint_q90_brier": 0.1, "variogram_p0_5": 1.0},
        # Brier is within the frozen exact-tie tolerance; variogram wins.
        {"theta_wr": 1.2, "theta_te": 1.1,
         "joint_q90_brier": 0.1 + 5e-13, "variogram_p0_5": 0.9},
        # All score ties; lower theta sum wins.
        {"theta_wr": 1.1, "theta_te": 1.1,
         "joint_q90_brier": 0.1 + 5e-13,
         "variogram_p0_5": 0.9 + 5e-13},
    ]
    assert select_grid_cell(grid)["theta_wr"] == 1.1


def test_gate_passes_only_when_every_registered_condition_improves():
    result = gate_decision(
        _arm(2.0), _arm(1.0), invariants_pass=True,
        selected={"theta_wr": 1.2, "theta_te": 1.1},
        treatment_audit={"changed_rank_rows": 10},
    )
    assert result["disposition"] == "g2-dependence-gate-passes"
    assert result["exact80_licensed"]
    assert result["gate"]["passes"]

    failed_treatment = deepcopy(_arm(1.0))
    failed_treatment["primary"]["joint_q90_brier"] = 3.0
    failed = gate_decision(
        _arm(2.0), failed_treatment, invariants_pass=True,
        selected={"theta_wr": 1.2, "theta_te": 1.1},
        treatment_audit={"changed_rank_rows": 10},
    )
    assert failed["disposition"] == "g2-dependence-gate-fails"
    assert not failed["gate"]["passes"]


def test_failed_invariant_is_invalid_not_a_valid_gate_failure():
    result = gate_decision(
        _arm(2.0), _arm(1.0), invariants_pass=False,
        selected={"theta_wr": 1.2, "theta_te": 1.1},
        treatment_audit={"changed_rank_rows": 10},
    )
    assert result["disposition"] == "g2-invalid-or-inconclusive"
    assert not result["exact80_licensed"]
