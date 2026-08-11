import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import numpy as np

from nfl_dfs.analysis import fantasy_points_same_season_coverage as diagnostic
from nfl_dfs.ingest import fantasy_points_same_season_coverage as coverage_import


def _receiver(**overrides):
    row = {
        "season": 2025,
        "target_week": 9,
        "gsis_id": "wr-1",
        "resolution_status": "resolved",
        "fp_cov_l4_supported": True,
        "source_week_start": 5,
        "source_week_end": 8,
        "overall_tprr": 0.20,
        "overall_yprr": 1.50,
        "overall_fprr": 0.30,
        "overall_sep": 0.10,
        "man_tprr": 0.30,
        "man_yprr": 2.00,
        "man_fprr": 0.40,
        "man_sep": 0.20,
        "zone_tprr": 0.10,
        "zone_yprr": 1.00,
        "zone_fprr": 0.20,
        "zone_sep": 0.00,
        "source_run_id": "run-1",
    }
    row.update(overrides)
    return row


def _defense(**overrides):
    row = {
        "season": 2025,
        "target_week": 9,
        "team": "BAL",
        "source_week_start": 5,
        "source_week_end": 8,
        "def_man_rate": 0.25,
        "def_zone_rate": 0.75,
        "source_run_id": "run-1",
    }
    row.update(overrides)
    return row


def test_same_season_coverage_is_opponent_specific_and_strictly_prior():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "gsis_id": "wr-1", "pos": "WR",
        "opp": "BAL",
    }])
    row = diagnostic.attach_same_season_coverage(
        targets,
        pd.DataFrame([_receiver()]),
        pd.DataFrame([_defense()]),
    ).iloc[0]
    assert row.fp_cov_l4_supported
    assert row.receiver_source_week_start == 5
    assert row.receiver_source_week_end == 8
    assert row.fp_cov_l4_matchup_tprr_edge == pytest.approx(-0.05)
    assert row.fp_cov_l4_matchup_yprr_edge == pytest.approx(-0.25)
    assert row.fp_cov_l4_matchup_fprr_edge == pytest.approx(-0.05)
    assert row.fp_cov_l4_matchup_sep_edge == pytest.approx(-0.05)


def test_same_season_coverage_rejects_target_week_in_source():
    with pytest.raises(ValueError, match="PIT/opponent"):
        diagnostic.attach_same_season_coverage(
            pd.DataFrame([{
                "season": 2025, "week": 9, "gsis_id": "wr-1",
                "pos": "WR", "opp": "BAL",
            }]),
            pd.DataFrame([_receiver(source_week_end=9)]),
            pd.DataFrame([_defense()]),
        )


def test_same_season_coverage_gate_is_aggregate_tail_first():
    aggregate = {
        "control_brier_30": 0.020,
        "treatment_brier_30": 0.0199,
    }
    coverage = {2023: 0.31, 2024: 0.35, 2025: 0.30}
    assert diagnostic.coverage_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.29
    assert not diagnostic.coverage_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.35
    aggregate["treatment_brier_30"] = 0.0201
    assert not diagnostic.coverage_gate(aggregate, coverage)["passes"]


def test_manifest_validator_requires_complete_strict_prior_grid(tmp_path):
    exports = []
    payload = b"a,b\n1,2\n"
    digest = hashlib.sha256(payload).hexdigest()
    for report, context in coverage_import.REPORT_CONTEXTS.items():
        for season in coverage_import.SEASONS:
            for target_week in coverage_import.TARGET_WEEKS:
                name = f"{report}-{season}-{target_week}.csv"
                (tmp_path / name).write_bytes(payload)
                exports.append({
                    "status": "downloaded",
                    "report": report,
                    "season": season,
                    "weeks": list(range(target_week - 4, target_week)),
                    "include_group_headers": True,
                    "context": context,
                    "target_week": target_week,
                    "path": name,
                    "bytes": len(payload),
                    "csv_rows_including_headers": 2,
                    "max_csv_columns": 2,
                    "sha256": digest,
                })
    manifest = {
        "schema_version": 1,
        "run_id": "20260811T000000Z__same-season-coverage-last-four-v1",
        "exports": exports,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    _, keyed = coverage_import.validate_manifest(tmp_path)
    assert len(keyed) == 168

    exports[0]["weeks"][-1] = exports[0]["target_week"]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="source weeks"):
        coverage_import.validate_manifest(tmp_path)


def test_bigquery_array_results_have_explicit_list_semantics():
    values = np.array(["run-1", "run-2"], dtype=object)
    assert coverage_import._repeated_values(values) == ["run-1", "run-2"]
    assert coverage_import._repeated_values(None) == []
