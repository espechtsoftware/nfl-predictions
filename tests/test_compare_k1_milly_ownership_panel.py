from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


SPEC = spec_from_file_location(
    "compare_k1_milly_ownership_panel",
    Path(__file__).parents[1] / "scripts" /
    "compare_k1_milly_ownership_panel.py")
assert SPEC and SPEC.loader
compare = module_from_spec(SPEC)
SPEC.loader.exec_module(compare)


def _candidates(lever: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "config_hash": "cfg",
        "seeds": "CE_SEED=1701;MODEL_ENSEMBLE_SIZE=1",
        "lever_env": lever,
    }])


def _features() -> dict:
    return {
        "source_rows": 100,
        "treatment_rows": 100,
        "source_only_rows": 0,
        "treatment_only_rows": 0,
        "invariant_mismatch_rows": 0,
        "preownership_change_rows": 0,
        "ownership_changed_rows": 50,
        "ownership_changed_slates": 54,
        "fade_equation_max_error": 1e-12,
    }


def _candidate_audit() -> dict:
    return {
        "common_actual_mismatch": 0,
        "common_p_line_mismatch": 0,
        "common_sim_mean_mismatch": 0,
        "common_support_mismatch": 0,
        "source_only_rows": 10,
        "treatment_only_rows": 11,
        "selected_source_only": 4,
        "selected_treatment_only": 5,
    }


def test_milly_mechanism_allows_only_fade_mode():
    source = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0")
    treatment = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0,"
        "OWN_MODEL=milly_fade")
    assert compare._mechanism_failures(
        source, treatment, _features(), _candidate_audit()) == []


def test_milly_mechanism_rejects_upstream_drift():
    source = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0")
    treatment = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0,"
        "OWN_MODEL=milly_fade")
    features = _features()
    features["invariant_mismatch_rows"] = 1
    failures = compare._mechanism_failures(
        source, treatment, features, _candidate_audit())
    assert "upstream player snapshots differ" in failures


def test_milly_mechanism_rejects_field_or_other_lever_change():
    source = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0")
    treatment = _candidates(
        "GAME_SIM_MODE=possession,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0,"
        "OWN_MODEL=milly_fade,PEAK_SLICE=4")
    failures = compare._mechanism_failures(
        source, treatment, _features(), _candidate_audit())
    assert "ownership arm changes unrelated replay levers" in failures
