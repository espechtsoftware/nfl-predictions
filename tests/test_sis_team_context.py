import csv
import json
from dataclasses import asdict

import pytest

from nfl_dfs.ingest import sis_team_context as sis
from nfl_dfs.ops.sis_downloads import ExportSpec


def _write_artifact(tmp_path, report, header, values, identities):
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
    manifest = artifact.with_suffix(".manifest.json")
    manifest.write_text(json.dumps({
        "artifact": artifact.name,
        "sha256": sis._sha256(artifact),
        "rows": 1,
        "spec": asdict(spec),
        "identities": identities,
    }), encoding="utf-8")
    return artifact, manifest


def test_blocking_duplicate_headers_are_preserved(tmp_path):
    header, _ = sis.SCHEMAS["blocking-totals"]
    values = [
        "1", "2025", "Cardinals", "1", "Saints", "1",
        "60", "3", "1", "40", "2", "1", "20", "1", "0",
    ]
    artifact, manifest = _write_artifact(
        tmp_path, "blocking-totals", header, values, [{
            "season": 2025, "week": 1, "games": 1,
            "team": "Cardinals", "opp": "Saints", "teamId": 1,
        }])
    frame = sis._read_artifact(
        artifact, manifest, "blocking-totals")
    row = frame.iloc[0]
    assert row.block_blown_blocks == 3
    assert row.pass_block_blown_blocks == 2
    assert row.run_block_blown_blocks == 1
    assert row.team_id == 1


def test_csv_and_api_identity_universe_must_match(tmp_path):
    header, _ = sis.SCHEMAS["pass-rush-value"]
    values = [
        "1", "2025", "Cardinals", "1", "Saints",
        "1", "0.1", "2", "0.2", "50%", "1", "0.1",
    ]
    artifact, manifest = _write_artifact(
        tmp_path, "pass-rush-value", header, values, [{
            "season": 2025, "week": 1, "games": 1,
            "team": "Cardinals", "opp": "Panthers", "teamId": 1,
        }])
    with pytest.raises(ValueError, match="lacks stable SIS ID"):
        sis._read_artifact(artifact, manifest, "pass-rush-value")


def test_percentages_are_normalized():
    assert sis._number("25.0%") == 0.25
    assert sis._number("1,234") == 1234
