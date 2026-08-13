import csv
import json
from dataclasses import asdict

import pytest

from nfl_dfs.ingest import sis_team_context as shared
from nfl_dfs.ingest import sis_team_run_context as sis
from nfl_dfs.ops.sis_downloads import ExportSpec


def _write_artifact(tmp_path, report, header, values):
    spec = ExportSpec(
        entity="teams", report=report, season=2025,
        start_week=1, end_week=1,
    )
    artifact = tmp_path / (
        f"teams__{report}__season-2025__weeks-01-01__all-teams__game.csv")
    with artifact.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(values)
    artifact.with_suffix(".manifest.json").write_text(json.dumps({
        "artifact": artifact.name,
        "sha256": shared._sha256(artifact),
        "rows": 1,
        "spec": asdict(spec),
        "identities": [{
            "season": 2025, "week": 1, "games": 1,
            "team": "Cardinals", "opp": "Saints", "teamId": 1,
        }],
    }), encoding="utf-8")
    return artifact


def test_run_context_percentages_and_tail_fields_are_preserved(tmp_path):
    header, _ = shared.SCHEMAS["rushing-value"]
    values = [
        "1", "2025", "Cardinals", "1", "Saints", "20", "3", "0.15",
        "2", "0.10", "1", "0.05", "55%", "1", "0.1", "18%", "7%",
    ]
    artifact = _write_artifact(tmp_path, "rushing-value", header, values)
    frame = shared._read_artifact(
        artifact, artifact.with_suffix(".manifest.json"), "rushing-value")
    row = frame.iloc[0]
    assert row.rush_points_earned_per_play == pytest.approx(0.15)
    assert row.rush_positive_rate == pytest.approx(0.55)
    assert row.rush_boom_rate == pytest.approx(0.18)
    assert row.rush_bust_rate == pytest.approx(0.07)


def test_passing_value_quarantine_requires_totals_bytes(tmp_path):
    totals_header, _ = shared.SCHEMAS["passing-totals"]
    values = [
        "1", "2025", "Cardinals", "1", "Saints", "1", "40", "35", "20",
        "25", "22", "250", "240", "300", "350", "2", "1", "2", "8",
    ]
    totals = _write_artifact(tmp_path, "passing-totals", totals_header, values)
    value = tmp_path / totals.name.replace(
        "__passing-totals__", "__passing-value__")
    value.write_bytes(totals.read_bytes())
    value.with_suffix(".manifest.json").write_text(json.dumps({
        "artifact": value.name,
        "sha256": shared._sha256(value),
        "rows": 1,
        "identities": [],
    }), encoding="utf-8")
    spec = ExportSpec(
        entity="teams", report="passing-value", season=2025,
        start_week=1, end_week=1,
    )
    assert sis._validate_excluded_passing_value(tmp_path, [spec]) == [
        shared._sha256(value)]
    value.write_text("not the stale totals view\n", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        sis._validate_excluded_passing_value(tmp_path, [spec])
