from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


SPEC = spec_from_file_location(
    "compare_k1_ce_panel",
    Path(__file__).parents[1] / "scripts" / "compare_k1_ce_panel.py")
assert SPEC and SPEC.loader
compare = module_from_spec(SPEC)
SPEC.loader.exec_module(compare)


def _candidates(lever: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "code_sha": "c616390",
        "config_hash": "cfg",
        "seeds": "CE_SEED=1701;MODEL_ENSEMBLE_SIZE=1",
        "lever_env": lever,
    }])


def _feature_audit() -> dict:
    return {
        "source_rows": 100,
        "treatment_rows": 100,
        "source_only_rows": 0,
        "treatment_only_rows": 0,
        "bit_exact_mismatch_rows": 12,
        "mismatch_rows": 0,
        "max_numeric_abs_delta": 3.6e-15,
    }


def _pair_audit(mode: str) -> dict:
    union = mode == "union"
    return {
        "paired_slates": 107,
        "slates_with_ce": 107,
        "novel_ce_rows": 500,
        "common_actual_mismatch": 0,
        "common_p_line_mismatch": 0,
        "common_sim_mean_mismatch": 0,
        "common_support_mismatch": 0,
        "source_only_rows": 0 if union else 300,
        "slates_with_larger_treatment": 107 if union else 0,
        "slates_with_equal_pools": 0 if union else 107,
        "selected_source_only": 0 if union else 20,
        "selected_treatment_only": 20,
    }


def test_union_mechanism_accepts_only_frozen_ce_addition():
    source = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0")
    treatment = _candidates(
        "CE_SEED=1701,GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,"
        "N_BOOM=40,N_CE=12")
    failures = compare._mechanism_failures(
        source, treatment, _feature_audit(), _pair_audit("union"), "union")
    assert failures == []


def test_fixed_mechanism_tolerates_commas_inside_cap_map():
    source = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0")
    treatment = _candidates(
        'CE_SEED=1701,GAME_SIM_MODE=possession,'
        'GEN_POOL_CAP_MAP={"2019-1":240,"2019-2":241},'
        "MODEL_ENSEMBLE=1,N_BOOM=28,N_CE=12,REPLACEMENT_SLOTS=12")
    failures = compare._mechanism_failures(
        source, treatment, _feature_audit(), _pair_audit("fixed"), "fixed")
    assert failures == []


def test_ce_mechanism_rejects_unrelated_lever_drift():
    source = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0")
    treatment = _candidates(
        "CE_SEED=1701,GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,"
        "N_BOOM=40,N_CE=12,PEAK_SLICE=4")
    failures = compare._mechanism_failures(
        source, treatment, _feature_audit(), _pair_audit("union"), "union")
    assert "CE treatment changes unrelated replay levers" in failures
