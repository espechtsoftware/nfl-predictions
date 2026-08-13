from nfl_dfs.research import tabpfn_sis_rb_rdef_lineup_v1 as lineup


def test_frozen_sis_rb_exact80_identities():
    assert lineup.CONTROL_PANEL.endswith("sis-rb-rdef-control-v1")
    assert lineup.TREATMENT_PANEL.endswith("sis-rb-rdef-treatment-v1")
    assert lineup.CONTROL_TABLE == "tabpfn_sis_rb_rdef_control_v1"
    assert lineup.TREATMENT_TABLE == "tabpfn_sis_rb_rdef_treatment_v1"


def test_tail_first_order_is_terminal_order():
    thresholds = (240, 230, 220, 210, 200, 194, 187)
    control = {**{f"clear_{x}": 1 for x in thresholds}, "mean_best": 100.0}
    treatment = {**{f"clear_{x}": 1 for x in thresholds}, "mean_best": 101.0}
    assert lineup.tail_first_decision(control, treatment)["treatment_selected"]
