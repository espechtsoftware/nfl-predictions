import hashlib
import json

import pandas as pd
import pytest

from nfl_dfs.analysis import fantasy_points_same_season_passing as diagnostic
from nfl_dfs.ingest import fantasy_points_same_season_passing as passing_import


def _passing(**overrides):
    row = {
        "season": 2025,
        "target_week": 9,
        "gsis_id": "qb-1",
        "resolution_status": "resolved",
        "fp_pass_l4_supported": True,
        "source_week_start": 5,
        "source_week_end": 8,
        "source_run_id": "20260811T000000Z__same-season-advanced-passing-last-four-v1",
        **{feature: 0.1 for feature in passing_import.PASSING_FEATURES},
    }
    row.update(overrides)
    return row


def test_same_season_passing_join_is_strictly_prior():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "gsis_id": "qb-1", "pos": "QB",
    }])
    row = diagnostic.attach_same_season_passing(
        targets, pd.DataFrame([_passing()])).iloc[0]
    assert row.fp_pass_l4_supported
    assert row.passing_source_week_start == 5
    assert row.passing_source_week_end == 8


def test_same_season_passing_rejects_target_week_in_source():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "gsis_id": "qb-1", "pos": "QB",
    }])
    with pytest.raises(ValueError, match="PIT/QB"):
        diagnostic.attach_same_season_passing(
            targets, pd.DataFrame([_passing(source_week_end=9)]))


def test_same_season_passing_gate_is_aggregate_tail_first():
    aggregate = {"control_brier_30": 0.03, "treatment_brier_30": 0.029}
    coverage = {2023: 0.50, 2024: 0.60, 2025: 0.55}
    assert diagnostic.passing_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.49
    assert not diagnostic.passing_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.60
    aggregate["treatment_brier_30"] = 0.031
    assert not diagnostic.passing_gate(aggregate, coverage)["passes"]


def test_passing_manifest_requires_complete_strict_prior_grid(tmp_path):
    payload = b"a,b\n1,2\n"
    digest = hashlib.sha256(payload).hexdigest()
    exports = []
    for season in passing_import.SEASONS:
        for target_week in passing_import.TARGET_WEEKS:
            name = f"advanced-passing-{season}-{target_week}.csv"
            (tmp_path / name).write_bytes(payload)
            exports.append({
                "status": "downloaded",
                "report": "advanced-passing",
                "season": season,
                "weeks": list(range(target_week - 4, target_week)),
                "include_group_headers": True,
                "context": "Player",
                "target_week": target_week,
                "path": name,
                "bytes": len(payload),
                "csv_rows_including_headers": 2,
                "max_csv_columns": 2,
                "sha256": digest,
            })
    manifest = {
        "schema_version": 1,
        "run_id": (
            "20260811T000000Z__"
            "same-season-advanced-passing-last-four-v1"
        ),
        "exports": exports,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    _, keyed = passing_import.validate_manifest(tmp_path)
    assert len(keyed) == 56
    exports[0]["weeks"][-1] = exports[0]["target_week"]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="source weeks"):
        passing_import.validate_manifest(tmp_path)
