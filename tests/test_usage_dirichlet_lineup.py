from pathlib import Path

import pandas as pd

from nfl_dfs.research import usage_dirichlet_lineup as lineup


def _provenance(kind: str, code: str) -> pd.DataFrame:
    values = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": lineup.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
        "SERVED_POSITION_SCALES": lineup.POSITION_SPEC,
    }
    if kind == "treatment":
        values["GAME_SIM_USAGE"] = "dirichlet"
        values["DIRICHLET_K"] = lineup.FITTED_K
    return pd.DataFrame([{
        "code_sha": code,
        "config_hash": f"config-{code}-{kind}",
        "seeds": "same-seeds",
        "lever_env": ",".join(
            f"{key}={value}" for key, value in sorted(values.items())),
    }])


def _features() -> dict:
    return {
        "left_rows": 100,
        "right_rows": 100,
        "left_only_rows": 0,
        "right_only_rows": 0,
        "mismatch_rows": 0,
        "max_numeric_abs_delta": 0.0,
    }


def _candidates(*, changed: bool = False) -> dict:
    return {
        "paired_slates": 54,
        "common_rows": 100,
        "left_only_rows": 5 if changed else 0,
        "right_only_rows": 6 if changed else 0,
        "common_actual_mismatch": 0,
        "common_sim_mean_mismatch": 0,
    }


def test_mechanism_accepts_exact_fitted_k_as_only_change():
    source = _provenance("source", lineup.EVALUATION_SOURCE_CODE_SHA)
    control = _provenance("control", "new")
    treatment = _provenance("treatment", "new")
    assert lineup.mechanism_failures(
        source,
        control,
        treatment,
        _features(),
        _features(),
        _candidates(),
        _candidates(changed=True),
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        experiment_code_sha="new",
    ) == []


def test_mechanism_rejects_wrong_k_and_silent_noop():
    source = _provenance("source", lineup.EVALUATION_SOURCE_CODE_SHA)
    control = _provenance("control", "new")
    treatment = _provenance("treatment", "new")
    treatment.loc[0, "lever_env"] = treatment.loc[0, "lever_env"].replace(
        lineup.FITTED_K, "29")
    failures = lineup.mechanism_failures(
        source,
        control,
        treatment,
        _features(),
        _features(),
        _candidates(),
        _candidates(changed=False),
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        experiment_code_sha="new",
    )
    assert "treatment DIRICHLET_K differs from frozen fit" in failures
    assert "fitted usage K did not change candidate membership" in failures


def test_mechanism_rejects_unregistered_second_change():
    source = _provenance("source", lineup.EVALUATION_SOURCE_CODE_SHA)
    control = _provenance("control", "new")
    treatment = _provenance("treatment", "new")
    treatment.loc[0, "lever_env"] += ",Q99_WILD=1"
    failures = lineup.mechanism_failures(
        source,
        control,
        treatment,
        _features(),
        _features(),
        _candidates(),
        _candidates(changed=True),
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        experiment_code_sha="new",
    )
    assert "treatment changes replay levers beyond fitted usage K" in failures


def test_fitted_k_comparator_and_runners_are_packaged():
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text()
    assert "COPY scripts/compare_usage_dirichlet_lineup.py " \
        "./scripts/compare_usage_dirichlet_lineup.py" in dockerfile
    protocol = (root / "reports/2026-08-11-data-fitted-dirichlet-exact80.md")
    assert lineup.FITTED_K in protocol.read_text()
    for name in (
        "prop_lock_usage_dirichlet_exact80.sh",
        "cloud_accept_usage_dirichlet_exact80.sh",
        "cloud_compare_usage_dirichlet_exact80.sh",
    ):
        assert (root / "scripts" / name).is_file()
