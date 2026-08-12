from pathlib import Path

import pandas as pd

from nfl_dfs.research import usage_dirichlet_lineup_v2 as usage


POSITION_SPEC = "QB:0.97,RB:1.005,TE:0.94,WR:1.07"
FITTED_K = "28.246898139750336"


def test_pit_usage_runner_binds_repaired_table_and_waits_for_tier1():
    root = Path(__file__).parents[1]
    launch = (root / "scripts/cloud_usage_dirichlet_calibration_v2.sh").read_text(
        encoding="utf-8"
    )
    finish = (
        root / "scripts/cloud_finish_usage_dirichlet_calibration_v2.sh"
    ).read_text(encoding="utf-8")
    assert "selected_tier1.txt" in launch
    assert "pit-repair-warehouse-reconciled" in launch
    assert "BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t)))" in launch
    assert "1904430067081090565" in launch
    assert "MODEL_ENSEMBLE=1" in launch
    assert "USAGE_DIRICHLET_CALIBRATION_JSON=" in finish


def _provenance(*, treatment: bool = False) -> pd.DataFrame:
    values = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": usage.CACHE_TABLE,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": (
            "target_share_last,carry_share_last,snap_share_last,"
            "target_share_jump,carry_share_jump,snap_share_jump"
        ),
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
        "SERVED_POSITION_SCALES": POSITION_SPEC,
    }
    if treatment:
        values.update({"GAME_SIM_USAGE": "dirichlet", "DIRICHLET_K": FITTED_K})
    return pd.DataFrame([{
        "code_sha": "a12ab31",
        "seeds": "fixed",
        "lever_env": ",".join(
            f"{key}={value}" for key, value in values.items()),
    }])


def _features(*, ignored: bool = False) -> dict:
    report = {
        "left_rows": 10, "right_rows": 10,
        "left_only_rows": 0, "right_only_rows": 0,
        "mismatch_rows": 0, "max_numeric_abs_delta": 0.0,
    }
    if ignored:
        report["ignored_numeric_fields"] = list(
            usage.DISTRIBUTION_DERIVED_FEATURES)
    return report


def _candidates(*, changed: bool = False) -> dict:
    return {
        "paired_slates": 54, "common_rows": 10,
        "left_only_rows": 1 if changed else 0,
        "right_only_rows": 1 if changed else 0,
        "common_actual_mismatch": 0, "common_sim_mean_mismatch": 0,
    }


def test_usage_v2_mechanism_accepts_only_fitted_allocation_change():
    failures = usage.mechanism_failures(
        _provenance(), _provenance(), _provenance(treatment=True),
        _features(), _features(ignored=True),
        _candidates(), _candidates(changed=True),
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        expected_code_sha="a12ab31", fitted_k=FITTED_K,
        base="k1", role_selected=True, position_spec=POSITION_SPEC,
    )
    assert failures == []


def test_usage_v2_rejects_wrong_k_and_unchanged_candidate_pool():
    treatment = _provenance(treatment=True)
    treatment.loc[:, "lever_env"] = treatment.lever_env.str.replace(
        FITTED_K, "20.0", regex=False)
    failures = usage.mechanism_failures(
        _provenance(), _provenance(), treatment,
        _features(), _features(ignored=True),
        _candidates(), _candidates(),
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        expected_code_sha="a12ab31", fitted_k=FITTED_K,
        base="k1", role_selected=True, position_spec=POSITION_SPEC,
    )
    assert "treatment DIRICHLET_K differs from repaired fit" in failures
    assert "fitted usage K did not change candidate membership" in failures


def test_usage_v2_freezes_both_result_branches_and_packages_comparator():
    root = Path(__file__).parents[1]
    protocol = (root / "reports/2026-08-12-pit-clean-usage-exact80.md").read_text(
        encoding="utf-8")
    launch = (root / "scripts/prop_lock_usage_dirichlet_exact80_v2.sh").read_text(
        encoding="utf-8")
    finish = (root / "scripts/cloud_finish_usage_dirichlet_exact80_v2.sh").read_text(
        encoding="utf-8")
    fallback = (root / "scripts/resolve_usage_dirichlet_fallback_v2.sh").read_text(
        encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "no undefined shrinkage target" in protocol
    assert "selected_position.txt" in launch
    assert "selected_k" in launch
    assert "USAGE_DIRICHLET_STAGE_B_V2_JSON=" in finish
    assert "allocation=multinomial" in fallback
    assert "likelihood-gate-failed" in fallback
    assert "COPY scripts/compare_usage_dirichlet_lineup_v2.py " \
        "./scripts/compare_usage_dirichlet_lineup_v2.py" in dockerfile
