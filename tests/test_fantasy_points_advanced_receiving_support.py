import csv
import hashlib
import json

import pandas as pd
import pytest

from nfl_dfs.ingest import fantasy_points_advanced_receiving_support as support


def test_advanced_receiving_support_windows_are_exact_and_strictly_prior():
    windows = support.expected_windows()
    assert len(windows) == 108
    assert windows[(2022, 5, "cumulative")] == (1, 2, 3, 4)
    assert windows[(2025, 6, "cumulative")] == (1, 2, 3, 4, 5)
    assert windows[(2025, 6, "last_four")] == (2, 3, 4, 5)
    assert all(max(weeks) < key[1] for key, weeks in windows.items())


def test_advanced_receiving_support_manifest_requires_complete_grid(tmp_path):
    payload = b"a,b\n1,2\n"
    digest = hashlib.sha256(payload).hexdigest()
    exports = []
    for (season, target_week, window_type), weeks in support.expected_windows().items():
        name = f"advanced-{season}-{target_week}-{window_type}.csv"
        (tmp_path / name).write_bytes(payload)
        exports.append({
            "status": "downloaded",
            "report": "advanced-receiving",
            "season": season,
            "weeks": list(weeks),
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
        "status": "complete",
        "run_id": f"20260811T000000Z__{support.PLAN_NAME}",
        "plan_sha256": support.PLAN_SHA256,
        "selected_target_week": None,
        "exports": exports,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    _, keyed = support.validate_manifest(tmp_path)
    assert len(keyed) == 108

    exports[0]["weeks"][-1] = exports[0]["target_week"]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unlicensed source window"):
        support.validate_manifest(tmp_path)


def _write_receiving(path, season):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Player Details", "", "", "", "", "",
            "Receiving", "", "", "", "", "Advanced", "FPTS",
        ])
        writer.writerow([
            "Rank", "Name", "Team", "POS", "G", "Season",
            "RTE", "TPRR", "aDOT", "AY Share", "YPRR", "1READ %",
            "XFP/RR",
        ])
        writer.writerow([
            1, "Sample Receiver", "HST", "WR", 4, season,
            80, 0.25, 11.0, 30.0, 2.1, 28.0, 0.45,
        ])


def test_advanced_receiving_support_parser_and_summaries(tmp_path):
    paths = {}
    for season in support.SEASONS:
        path = tmp_path / f"advanced-{season}.csv"
        _write_receiving(path, season)
        paths[season] = path
    artifacts = {
        key: {
            "local_path": paths[key[0]],
            "path": paths[key[0]].name,
            "sha256": f"hash-{key[0]}",
            "weeks": list(weeks),
        }
        for key, weeks in support.expected_windows().items()
    }
    snapshots = pd.DataFrame([{
        "season": season,
        "gsis_id": f"wr-{season}",
        "name": "Sample Receiver",
        "pos": "WR",
        "team": "HOU",
    } for season in support.SEASONS])
    rows, audit = support.read_windows(
        {"run_id": "run-1"}, artifacts, snapshots)
    assert len(rows) == 108
    assert audit["resolved_rows"] == 108
    assert rows.fp_adv_rec_air_yard_share.eq(0.30).all()
    assert rows.fp_adv_rec_first_read_rate.eq(0.28).all()
    summaries = support.support_summary(rows)
    assert len(summaries) == 108
    assert summaries[0]["route_floors"]["80"]["rate"] == 1.0
    overlap = support.window_overlap(rows)
    assert len(overlap) == 52
    assert overlap[0]["common_resolved_players"] == 1


def test_redundancy_summary_refuses_outcomes_and_uses_predictors_only():
    rows = pd.DataFrame([
        {
            "season": 2025,
            "target_week": 6,
            "window_type": "cumulative",
            "gsis_id": f"wr-{index}",
            **{metric: float(index) for metric in support.METRICS},
        }
        for index in range(1, 4)
    ])
    existing = pd.DataFrame([
        {
            "season": 2025,
            "target_week": 6,
            "gsis_id": f"wr-{index}",
            **{feature: float(index) for feature in support.EXISTING_FEATURES},
        }
        for index in range(1, 4)
    ])
    summary = support.redundancy_summary(rows, existing)
    matching = [
        item for item in summary
        if item["window_type"] == "cumulative"
        and item["season"] == 2025
        and item["vendor_metric"] == support.METRICS[0]
        and item["existing_feature"] == support.EXISTING_FEATURES[0]
    ][0]
    assert matching["paired_rows"] == 3
    assert matching["spearman"] == pytest.approx(1.0)

    with pytest.raises(ValueError, match="outcome-bearing"):
        support.redundancy_summary(rows, existing.assign(actual=0.0))
