from pathlib import Path

import pandas as pd

from nfl_dfs.research import served_position_lineup_v2 as lineup


def test_position_v2_runner_derives_selected_base_panel_and_pit_cache():
    root = Path(__file__).parents[1]
    launch = (root / "scripts/cloud_served_position_calibration_v2.sh").read_text(
        encoding="utf-8"
    )
    finish = (
        root / "scripts/cloud_finish_served_position_calibration_v2.sh"
    ).read_text(encoding="utf-8")
    assert "selected_tier1.txt" in launch
    assert 'k3) ENSEMBLE=3' in launch
    assert 'k1) ENSEMBLE=1' in launch
    assert "TABPFN_MARGINAL_TABLE=tabpfn_projections_pit_v2" in launch
    assert "SERVED_POSITION_CALIBRATION_PIT_V2=1" in launch
    assert "107" in launch
    assert '"version": "v2"' in finish
    assert '"tabpfn_table": "tabpfn_projections_pit_v2"' in finish


def _provenance(scale: str | None) -> pd.DataFrame:
    values = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": lineup.CACHE_TABLE,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": lineup.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
    }
    if scale is not None:
        values["SERVED_POSITION_SCALES"] = scale
    return pd.DataFrame([{
        "code_sha": "a12ab31",
        "seeds": "fixed",
        "lever_env": ",".join(
            f"{key}={value}" for key, value in values.items()),
    }])


def _features() -> dict:
    return {
        "left_rows": 10, "right_rows": 10,
        "left_only_rows": 0, "right_only_rows": 0,
        "mismatch_rows": 0, "max_numeric_abs_delta": 0.0,
    }


def _candidates() -> dict:
    return {
        "paired_slates": 54, "common_rows": 10,
        "left_only_rows": 0, "right_only_rows": 0,
        "common_actual_mismatch": 0, "common_sim_mean_mismatch": 0,
    }


def test_position_v2_mechanism_accepts_dynamic_fit_on_selected_role_law():
    factors = "QB:0.97,RB:1.005,TE:0.94,WR:1.07"
    failures = lineup.mechanism_failures(
        _provenance(None),
        _provenance("identity"),
        _provenance(factors),
        _features(), _features(), _candidates(), _candidates(),
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        expected_code_sha="a12ab31", position_spec=factors,
        base="k1", role_selected=True,
    )
    assert failures == []


def test_position_v2_uses_full_frozen_tail_order_then_mean():
    control = {f"clear_{threshold}": 1 for threshold in lineup.TAIL_ORDER}
    control["mean_best"] = 180.0
    treatment = dict(control)
    treatment["clear_194"] = 2
    treatment["clear_187"] = 0
    decision = lineup.tail_first_decision(control, treatment)
    assert decision["treatment_selected"]
    assert decision["first_difference"] == 194
    tied = dict(control, mean_best=180.1)
    decision = lineup.tail_first_decision(control, tied)
    assert decision["treatment_selected"]
    assert decision["first_difference"] is None
    assert decision["tiebreaker"] == "mean_best"


def test_position_v2_stage_b_is_dynamic_and_comparator_is_packaged():
    root = Path(__file__).parents[1]
    launch = (root / "scripts/prop_lock_served_position_stage_b_v2.sh").read_text(
        encoding="utf-8")
    finish = (
        root / "scripts/cloud_finish_served_position_stage_b_v2.sh"
    ).read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    for value in (
        "selected_tier1.txt", "r2_final_served_fit", "POSITION_SPEC",
        "MODEL_ENSEMBLE=1", "role_selected",
    ):
        assert value in launch
    assert "20260812-pitclean-e80-selected-position-control-v2" in launch
    assert "20260812-pitclean-e80-selected-position-scales-v2" in launch
    assert "SERVED_POSITION_STAGE_B_V2_JSON=" in finish
    assert "selected_position.txt" in finish
    assert "COPY scripts/compare_served_position_lineup_v2.py " \
        "./scripts/compare_served_position_lineup_v2.py" in dockerfile
