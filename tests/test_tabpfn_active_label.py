import copy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


SPEC = spec_from_file_location(
    "validate_tabpfn_active_label",
    Path(__file__).parents[1] / "scripts" / "validate_tabpfn_active_label.py",
)
assert SPEC and SPEC.loader
validation = module_from_spec(SPEC)
SPEC.loader.exec_module(validation)


def _reports():
    folds_control = {}
    folds_treatment = {}
    for season in validation.TARGET_SEASONS:
        folds_control[str(season)] = {
            "target_rows": 1,
            "eligible_context_rows": 100,
            "sampled_inactive_rows": 10,
        }
        folds_treatment[str(season)] = {
            "target_rows": 1,
            "eligible_context_rows": 90,
            "sampled_inactive_rows": 0,
        }
    shared = {
        "code_sha": "82619ed",
        "training_source": {"table": "training", "last_modified": "fixed"},
        "feature_columns": ["a"],
        "feature_contract_sha256": "feature-sha",
        "target_seasons": validation.TARGET_SEASONS,
        "quantiles": [0.01, 0.99],
        "context_max": 28_000,
        "random_seed": 7,
        "n_estimators": 4,
        "device": "cuda",
        "output_rows": validation.EXPECTED_ROWS,
        "unique_keys": validation.EXPECTED_ROWS,
    }
    control = {
        **shared, "arm": "control", "active_context_only": False,
        "folds": folds_control,
    }
    treatment = {
        **copy.deepcopy(shared), "arm": "active_only",
        "active_context_only": True, "folds": folds_treatment,
    }
    return control, treatment


def test_report_validation_requires_only_the_frozen_activity_difference():
    control, treatment = _reports()
    result = validation.validate_reports(control, treatment, "82619ed")
    assert result["passes"]
    treatment["folds"]["2024"]["sampled_inactive_rows"] = 1
    result = validation.validate_reports(control, treatment, "82619ed")
    assert not result["passes"]
    assert not result["checks"]["treatment_contexts_active_only"]


def test_table_validation_requires_same_keys_ordered_quantiles_and_change(monkeypatch):
    monkeypatch.setattr(validation, "EXPECTED_ROWS", 4)
    base = pd.DataFrame({
        "season": [2022, 2023, 2024, 2025],
        "week": [1, 1, 1, 1],
        "gsis_id": ["a", "b", "c", "d"],
        "mean": [10.0, 11.0, 12.0, 13.0],
        "arm": ["control"] * 4,
        "active_context_only": [False] * 4,
        "feature_contract_sha256": ["x"] * 4,
        "code_sha": ["82619ed"] * 4,
    })
    for index, column in enumerate(validation.QUANTILE_COLUMNS):
        base[column] = float(index)
    treatment = base.copy()
    treatment["arm"] = "active_only"
    treatment["active_context_only"] = True
    treatment["mean"] += 0.1
    result = validation.validate_tables(base, treatment)
    assert result["passes"]
    treatment.loc[0, "q95"] = -5
    result = validation.validate_tables(base, treatment)
    assert not result["passes"]
    assert not result["checks"]["ordered_quantiles"]
