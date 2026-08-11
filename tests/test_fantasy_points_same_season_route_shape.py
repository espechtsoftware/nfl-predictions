import csv
import hashlib
import json

import pandas as pd
import pytest

from nfl_dfs.analysis import fantasy_points_same_season_route_shape as diagnostic
from nfl_dfs.ingest import fantasy_points_same_season_route_shape as route_import


def _route_shape(**overrides):
    row = {
        "season": 2025,
        "target_week": 9,
        "gsis_id": "wr-1",
        "resolution_status": "resolved",
        "fp_route_shape_l4_partition_valid": True,
        "fp_route_shape_l4_supported": True,
        "source_week_start": 5,
        "source_week_end": 8,
        "source_run_id": (
            "20260811T000000Z__same-season-route-shape-last-four-v1"),
        **{feature: 0.2 for feature in route_import.ROUTE_SHAPE_FEATURES},
    }
    row.update(overrides)
    return row


def test_same_season_route_shape_join_is_strictly_prior():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "gsis_id": "wr-1", "pos": "WR",
    }])
    row = diagnostic.attach_same_season_route_shape(
        targets, pd.DataFrame([_route_shape()])).iloc[0]
    assert row.fp_route_shape_l4_supported
    assert row.route_shape_source_week_start == 5
    assert row.route_shape_source_week_end == 8


def test_same_season_route_shape_rejects_target_week_in_source():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "gsis_id": "wr-1", "pos": "WR",
    }])
    with pytest.raises(ValueError, match="PIT/position"):
        diagnostic.attach_same_season_route_shape(
            targets,
            pd.DataFrame([_route_shape(source_week_end=9)]),
        )


def test_same_season_route_shape_gate_is_aggregate_tail_first():
    aggregate = {"control_brier_30": 0.03, "treatment_brier_30": 0.029}
    coverage = {2023: 0.30, 2024: 0.40, 2025: 0.35}
    assert diagnostic.route_shape_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.29
    assert not diagnostic.route_shape_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.40
    aggregate["treatment_brier_30"] = 0.031
    assert not diagnostic.route_shape_gate(aggregate, coverage)["passes"]


def test_route_shape_manifest_requires_complete_strict_prior_grid(tmp_path):
    payload = b"a,b\n1,2\n"
    digest = hashlib.sha256(payload).hexdigest()
    exports = []
    for season in route_import.SEASONS:
        for target_week in route_import.TARGET_WEEKS:
            name = f"route-shape-{season}-{target_week}.csv"
            (tmp_path / name).write_bytes(payload)
            exports.append({
                "status": "downloaded",
                "report": route_import.REPORT,
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
            "20260811T000000Z__same-season-route-shape-last-four-v1"),
        "exports": exports,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    _, keyed = route_import.validate_manifest(tmp_path)
    assert len(keyed) == 56
    exports[0]["weeks"][-1] = exports[0]["target_week"]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="source weeks"):
        route_import.validate_manifest(tmp_path)


def _write_grouped_route_file(path, season, *, horizontal=30):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Player Details", "", "", "", "", "", "Overall",
            "Horizontally Breaking", "Vertically Breaking", "Static",
            "Shallow/Underneath", "Backfield",
        ])
        writer.writerow([
            "Rank", "Name", "Team", "POS", "G", "Season", "RTE",
            "RTE", "RTE", "RTE", "RTE", "RTE",
        ])
        writer.writerow([
            1, "Sample Receiver", "HST", "WR", 4, season, 100,
            horizontal, 20, 25, 25, "",
        ])


def test_route_shape_parser_validates_partition_and_blank_zero(tmp_path):
    artifacts = {}
    for season in route_import.SEASONS:
        path = tmp_path / f"route-shape-{season}.csv"
        _write_grouped_route_file(path, season)
        for target_week in route_import.TARGET_WEEKS:
            artifacts[(season, target_week)] = {
                "local_path": path,
                "path": path.name,
                "sha256": f"hash-{season}",
            }
    snapshots = pd.DataFrame([{
        "season": season,
        "gsis_id": "wr-1",
        "name": "Sample Receiver",
        "pos": "WR",
        "team": "HOU",
    } for season in route_import.SEASONS])
    manifest = {"run_id": "run-1"}
    rows, audit = route_import.read_windows(manifest, artifacts, snapshots)
    assert len(rows) == 56
    assert audit["supported_rows"] == 56
    assert audit["partition_valid_source_rows"] == 56
    first = rows.iloc[0]
    assert first.backfield_routes == 0
    assert first.fp_route_shape_l4_horizontal_share == pytest.approx(0.30)
    assert first.fp_route_shape_l4_shallow_share == pytest.approx(0.25)

    bad_path = tmp_path / "bad.csv"
    _write_grouped_route_file(bad_path, 2022, horizontal=31)
    artifacts[(2022, 5)] = {
        "local_path": bad_path, "path": bad_path.name, "sha256": "bad",
    }
    with pytest.raises(ValueError, match="partition Overall"):
        route_import.read_windows(manifest, artifacts, snapshots)
