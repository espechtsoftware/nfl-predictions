import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_sched", ROOT / "scripts/validate_tabpfn_sched.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _report(arm: str, features: list[str], *, label_law: str = "active_only"):
    active_only = label_law == "active_only"
    folds = {
        str(season): {
            "target_rows": 100,
            "sampled_context_rows": 1000,
            "sampled_inactive_rows": 0 if active_only else 10,
        }
        for season in validator.TARGET_SEASONS
    }
    return {
        "arm": arm,
        "label_law": label_law,
        "active_context_only": active_only,
        "code_sha": "abcdef1",
        "output_table": (
            "p.nfl_features.tabpfn_sched_control_v1"
            if arm == "control"
            else "p.nfl_features.tabpfn_sched_treatment_v1"
        ),
        "training_source": {"content_checksum": 123},
        "feature_columns": features,
        "feature_contract_sha256": f"hash-{arm}",
        "target_seasons": validator.TARGET_SEASONS,
        "quantiles": [0.1],
        "context_max": 28000,
        "random_seed": 7,
        "n_estimators": 4,
        "device": "cuda",
        "output_rows": validator.EXPECTED_ROWS,
        "unique_keys": validator.EXPECTED_ROWS,
        "folds": folds,
    }


def test_sched_report_gate_accepts_only_appended_pair_and_common_label_law():
    control, treatment = validator.expected_features(
        ROOT / "scripts/tabpfn_sched/features_control.txt")
    result = validator.validate_reports(
        _report("control", control), _report("treatment", treatment),
        "abcdef1", "active_only", control, treatment)
    assert result["passes"]
    broken = _report("treatment", [*control, "body_clock_hour"])
    result = validator.validate_reports(
        _report("control", control), broken, "abcdef1", "active_only",
        control, treatment)
    assert not result["passes"]
    assert not result["checks"]["exact_feature_contracts"]


def test_sched_table_gate_requires_changed_predictions(monkeypatch):
    monkeypatch.setattr(validator, "EXPECTED_ROWS", 4)
    common = {
        "season": [2022, 2023, 2024, 2025], "week": [1, 1, 1, 1],
        "gsis_id": ["a", "b", "c", "d"],
        "label_law": ["current"] * 4,
        "active_context_only": [False] * 4,
        "code_sha": ["abcdef1"] * 4,
    }
    quantiles = {
        name: [float(index + offset) for offset in range(4)]
        for index, name in enumerate(validator.QUANTILE_COLUMNS)
    }
    left = pd.DataFrame({
        **common, **quantiles, "mean": [1.0, 2.0, 3.0, 4.0],
        "arm": ["control"] * 4,
        "feature_contract_sha256": ["left"] * 4,
    })
    right = left.copy()
    right["arm"] = "treatment"
    right["feature_contract_sha256"] = "right"
    assert not validator.validate_tables(left, right)["passes"]
    right.loc[0, "mean"] = 1.1
    result = validator.validate_tables(left, right)
    assert result["passes"]


def test_sched_launch_is_terminal_active_label_dependent_and_write_once():
    launch = (ROOT / "scripts/cloud_tabpfn_sched.sh").read_text(
        encoding="utf-8")
    finish = (ROOT / "scripts/cloud_finish_tabpfn_sched.sh").read_text(
        encoding="utf-8")
    generator = (ROOT / "scripts/tabpfn_sched/gen.py").read_text(
        encoding="utf-8")
    old = (ROOT / "scripts/tabpfn_gen/features.txt").read_text(
        encoding="utf-8").split()
    control = (ROOT / "scripts/tabpfn_sched/features_control.txt").read_text(
        encoding="utf-8").split()
    assert old == control
    assert "selected_active_label.txt" in launch
    assert "active-only) LABEL_LAW=active_only" in launch
    assert "WRITE_EMPTY" in generator
    assert 'SCHED_FEATURES = ("net_rest_diff", "body_clock_hour")' in generator
    assert "TABPFN_SCHED_JSON=" in finish
    assert "validate_tabpfn_sched.py" in finish
