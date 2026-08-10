from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


SPEC = spec_from_file_location(
    "compare_k1_role_belief_panel",
    Path(__file__).parents[1] / "scripts" / "compare_k1_role_belief_panel.py")
assert SPEC and SPEC.loader
compare = module_from_spec(SPEC)
SPEC.loader.exec_module(compare)


def _rows(lever: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "code_sha": "c616390",
        "config_hash": "cfg",
        "seeds": "CE_SEED=1701;ROLE_BELIEF_SEED=7331;MODEL_ENSEMBLE_SIZE=1",
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


def _pairs(mode: str) -> dict:
    return {
        "paired_slates": 107,
        "slates_with_role": 107,
        "min_role_per_slate": 12,
        "max_role_per_slate": 12,
        "novel_role_rows": 1000,
        "missing_source_ce_rows": 0,
        "common_actual_mismatch": 0,
        "common_p_line_mismatch": 0,
        "common_sim_mean_mismatch": 0,
        "common_support_mismatch": 0,
        "source_only_rows": 0 if mode == "union" else 100,
        "slates_with_larger_treatment": 107 if mode == "union" else 0,
        "slates_with_equal_pools": 0 if mode == "union" else 107,
        "selected_role_rows": 0 if mode == "union" else 25,
        "selected_source_only": 0 if mode == "union" else 25,
        "selected_treatment_only": 25,
    }


def _source() -> pd.DataFrame:
    return _rows(
        'CE_SEED=1701,GEN_POOL_CAP_MAP={"2019-1":240,"2019-2":241},'
        "MODEL_ENSEMBLE=1,N_BOOM=28,N_CE=12,N_EPISTEMIC=0,"
        "N_GUMBEL=0,REPLACEMENT_SLOTS=12")


def _treatment(mode: str) -> pd.DataFrame:
    cap = ('GEN_POOL_CAP_MAP={"2019-1":240,"2019-2":241},'
           if mode == "fixed" else "")
    boom = 16 if mode == "fixed" else 28
    return _rows(
        "CE_SEED=1701,EPISTEMIC_FAMILY=role_draws,"
        f"{cap}MODEL_ENSEMBLE=1,N_BOOM={boom},N_CE=12,N_EPISTEMIC=12,"
        "N_GUMBEL=0,REPLACEMENT_SLOTS=12,"
        f"ROLE_BELIEF_FEATURES={compare.ROLE_FEATURES},"
        "ROLE_BELIEF_SEED=7331")


def test_parse_levers_keeps_cap_map_intact():
    values = compare._lever_values(_source().lever_env.iloc[0])
    assert values["GEN_POOL_CAP_MAP"] == '{"2019-1":240,"2019-2":241}'
    assert values["N_BOOM"] == "28"


def test_union_mechanism_accepts_only_frozen_role_addition():
    failures = compare._mechanism_failures(
        _source(), _treatment("union"), _features(), _pairs("union"), "union")
    assert failures == []


def test_fixed_mechanism_requires_same_cap_and_preserved_ce():
    failures = compare._mechanism_failures(
        _source(), _treatment("fixed"), _features(), _pairs("fixed"), "fixed")
    assert failures == []
    broken = _pairs("fixed")
    broken["missing_source_ce_rows"] = 1
    failures = compare._mechanism_failures(
        _source(), _treatment("fixed"), _features(), broken, "fixed")
    assert "role treatment failed to preserve source CE candidates" in failures


def test_score_gates_are_tail_first_without_season_or_mean_veto():
    source = {"clear_200": 18, "clear_210": 11, "clear_220": 5,
              "clear_230": 2, "clear_240": 1,
              "oracle_200": 22, "oracle_210": 13, "oracle_220": 5,
              "oracle_230": 2, "oracle_240": 1}
    treatment = {**source, "clear_200": 20}
    role = {"role_new_200_weeks": 2, "role_frontier_weeks": 2}
    union, fixed = compare._score_gates(source, treatment, role, True)
    assert union["passes"]
    assert fixed["passes"]
    treatment["clear_230"] = 1
    _, fixed = compare._score_gates(source, treatment, role, True)
    assert not fixed["passes"]
