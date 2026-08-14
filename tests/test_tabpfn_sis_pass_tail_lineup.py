import pandas as pd

from nfl_dfs.research import tabpfn_sis_pass_tail_lineup_v1 as lineup


def test_frozen_ids_schedules_and_tail_order():
    assert lineup.panel_id("control", 4) == \
        "20260814-sis-pass-tail-control-r4-v1"
    assert lineup.CONTROL_TABLE == "tabpfn_sis_pass_tail_control_v1"
    assert lineup.TREATMENT_TABLE == "tabpfn_sis_pass_tail_treatment_v1"
    assert lineup.TAILS == (240, 230, 220, 210, 200, 194, 187)
    assert lineup.CONTROL_SCHEDULES[2023].startswith("QB:0.76,")
    assert lineup.TREATMENT_SCHEDULES[2025].startswith("QB:0.92,")


def test_tail_first_uses_all_seed_counts_before_mean():
    metrics = {}
    for arm in ("control", "treatment"):
        for replicate in lineup.SEEDS:
            metrics[f"{arm}-R{replicate}"] = {
                "selected_tail": {str(t): 0 for t in lineup.TAILS},
                "selected_mean": 200.0 if arm == "control" else 100.0,
            }
    metrics["treatment-R4"]["selected_tail"]["230"] = 1
    decision = lineup.tail_first_decision(metrics)
    assert decision["selected_arm"] == "treatment"
    assert decision["deciding_threshold"] == 230


def test_feature_audit_allows_only_registered_distribution_changes():
    common = {
        "season": [2025], "week": [5], "id": ["p"], "name": ["Player"],
        "actual": [20.0], "panel_run_id": ["left"],
        "slate_run_id": ["l"], "generated_at": ["then"],
        "config_hash": ["a"], "proj": [10.0],
    }
    control = pd.DataFrame(common)
    treatment = control.copy()
    treatment["panel_run_id"] = "right"
    treatment["slate_run_id"] = "r"
    treatment["generated_at"] = "now"
    treatment["config_hash"] = "b"
    treatment["proj"] = 11.0
    audit = lineup.feature_invariance_audit(control, treatment)
    assert audit["invariant_mismatch_rows"] == 0
    assert audit["distribution_changed_rows"] == 1
    treatment["actual"] = 21.0
    assert lineup.feature_invariance_audit(
        control, treatment)["invariant_mismatch_rows"] == 1


def test_candidate_audit_detects_material_scoring_change_not_actual_change():
    control = pd.DataFrame({
        "season": [2025], "week": [5], "players": ["a,b"],
        "actual_score": [200.0], "sim_mean": [150.0],
    })
    treatment = control.copy()
    treatment["sim_mean"] = 151.0
    audit = lineup.candidate_audit(control, treatment)
    assert audit["common_actual_mismatch"] == 0
    assert audit["common_sim_mean_mismatch"] == 1
