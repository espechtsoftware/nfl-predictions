from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


SPEC = spec_from_file_location(
    "compare_corrected_k1_direct_role",
    Path(__file__).parents[1] / "scripts" / "compare_corrected_k1_direct_role.py")
assert SPEC and SPEC.loader
compare = module_from_spec(SPEC)
SPEC.loader.exec_module(compare)


def _rows(lever: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "code_sha": "8677d21",
        "config_hash": "cfg",
        "seeds": "ROLE_BELIEF_SEED=7331;MODEL_ENSEMBLE_SIZE=1",
        "lever_env": lever,
    }])


def _features() -> dict:
    return {
        "source_rows": 100,
        "treatment_rows": 100,
        "source_only_rows": 0,
        "treatment_only_rows": 0,
        "mismatch_rows": 0,
    }


def _pairs() -> dict:
    return {
        "paired_slates": 107,
        "slates_with_role": 107,
        "min_role_per_slate": 12,
        "max_role_per_slate": 12,
        "novel_role_rows": 1000,
        "common_actual_mismatch": 0,
        "common_p_line_mismatch": 0,
        "common_sim_mean_mismatch": 0,
        "common_support_mismatch": 0,
        "source_only_rows": 0,
        "slates_with_larger_treatment": 107,
    }


def _source() -> pd.DataFrame:
    return _rows(
        "MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0,N_EPISTEMIC=0,N_GUMBEL=0")


def _treatment() -> pd.DataFrame:
    return _rows(
        "EPISTEMIC_FAMILY=role_draws,MODEL_ENSEMBLE=1,N_BOOM=40,N_CE=0,"
        "N_EPISTEMIC=12,N_GUMBEL=0,REPLACEMENT_SLOTS=12,"
        f"ROLE_BELIEF_FEATURES={compare.ROLE_FEATURES},ROLE_BELIEF_SEED=7331")


def test_direct_role_mechanism_accepts_only_frozen_union():
    assert compare._mechanism_failures(
        _source(), _treatment(), _features(), _pairs()) == []


def test_direct_role_mechanism_rejects_noncontainment_and_wrong_dose():
    pairs = _pairs()
    pairs["source_only_rows"] = 1
    treatment = _treatment().copy()
    treatment.loc[0, "lever_env"] = treatment.loc[0, "lever_env"].replace(
        "N_EPISTEMIC=12", "N_EPISTEMIC=8")
    failures = compare._mechanism_failures(
        _source(), treatment, _features(), pairs)
    assert "treatment N_EPISTEMIC is not 12" in failures
    assert "direct-role treatment is not a source-roster superset" in failures


def test_tail_first_decision_prefers_first_high_threshold_difference():
    source = {
        "clear_240": 1, "clear_230": 2, "clear_220": 4, "clear_210": 7,
    }
    treatment = {
        "clear_240": 1, "clear_230": 3, "clear_220": 3, "clear_210": 9,
    }
    decision = compare.tail_first_decision(source, treatment)
    assert decision["first_difference"] == 230
    assert decision["promotion_candidate"]

