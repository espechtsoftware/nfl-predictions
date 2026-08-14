from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def _module():
    path = Path(__file__).parents[1] / "scripts" / "validate_tabpfn_route_channel_i1.py"
    spec = importlib.util.spec_from_file_location("route_i1_validation", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


validation = _module()


def _source():
    return {
        "table": "nfl-predictions-503414.nfl_features.player_week_training",
        "last_modified": "2026-08-12T04:06:47.502000+00:00",
        "schema_sha256": "schema",
        "content_checksum": validation.SOURCE_CHECKSUM,
        "rows": validation.SOURCE_ROWS,
        "active_rows": 78_404,
        "inactive_zero_labels_by_season": {
            str(season): 1 for season in validation.TARGET_SEASONS
        },
    }


def _folds():
    return {
        str(season): {
            "target_rows": 100,
            "sampled_context_rows": 28_000,
            "sampled_inactive_rows": 0,
            "route_context_rows": 0 if season == 2022 else 1_000,
            "route_target_rows": 1_000,
        }
        for season in validation.TARGET_SEASONS
    }


def _reports():
    base = ["a", "b"]
    common = {
        "disposition": "tabpfn-route-channel-cache-generated",
        "active_context_only": True,
        "code_sha": "abcdef1",
        "base_feature_contract_sha256": validation.BASE_FEATURE_SHA,
        "target_seasons": validation.TARGET_SEASONS,
        "quantiles": [0.01, 0.99],
        "context_max": 28_000,
        "random_seed": 7,
        "n_estimators": 4,
        "device": "cuda",
        "output_rows": validation.EXPECTED_ROWS,
        "unique_keys": validation.EXPECTED_ROWS,
        "training_source": _source(),
        "folds": _folds(),
    }
    control = {
        **common,
        "arm": "control",
        "route_marginal": False,
        "output_table": f"x.{validation.TABLES['control']}",
        "feature_columns": base,
        "feature_contract_sha256": validation.BASE_FEATURE_SHA,
    }
    marginal = {
        **common,
        "arm": "marginal",
        "route_marginal": True,
        "output_table": f"x.{validation.TABLES['marginal']}",
        "feature_columns": sorted([*base, *validation.ROUTE_FEATURES]),
        "feature_contract_sha256": "treatment-sha",
        "route_features": list(validation.ROUTE_FEATURES),
    }
    incumbent = {
        "version": "v2",
        "passes": True,
        "disposition": "tabpfn-active-label-caches-valid",
        "reports": {"treatment": {
            **common,
            "feature_columns": base,
            "feature_contract_sha256": validation.BASE_FEATURE_SHA,
        }},
    }
    return control, marginal, incumbent


def test_report_gate_accepts_only_exact_route_feature_addition():
    control, marginal, incumbent = _reports()
    result = validation.validate_reports(
        control, marginal, incumbent, "abcdef1")
    assert result["passes"]

    changed = copy.deepcopy(marginal)
    changed["feature_columns"].append("unregistered")
    assert not validation.validate_reports(
        control, changed, incumbent, "abcdef1")["passes"]


def _table(arm: str, delta: float = 0.0):
    n = validation.EXPECTED_ROWS
    data = {
        "season": np.repeat(validation.TARGET_SEASONS, n // 4 + 1)[:n],
        "week": np.arange(n) % 18 + 1,
        "gsis_id": [f"p{index}" for index in range(n)],
        "arm": arm,
        "active_context_only": True,
        "route_marginal": arm == "marginal",
        "base_feature_contract_sha256": validation.BASE_FEATURE_SHA,
        "feature_contract_sha256": (
            validation.BASE_FEATURE_SHA if arm == "control" else "marginal-sha"),
        "code_sha": "abcdef1",
    }
    for index, column in enumerate(validation.VALUE_COLUMNS):
        data[column] = np.full(n, float(index) + delta)
    return pd.DataFrame(data)


def test_table_gate_requires_incumbent_reproduction_and_changed_treatment():
    control = _table("control")
    marginal = _table("marginal", delta=0.1)
    incumbent = control[[
        "season", "week", "gsis_id", *validation.VALUE_COLUMNS]].copy()
    result = validation.validate_tables(control, marginal, incumbent)
    assert result["passes"]
    assert result["control_incumbent_max_abs_delta"] == 0.0

    incumbent.loc[0, "q99"] += 1e-5
    assert not validation.validate_tables(
        control, marginal, incumbent)["passes"]
