import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import fantasy_points_route as historical
from nfl_dfs.ingest import fantasy_points_route_weekly as weekly


def _csv(path: Path, *, source_week: int = 1, value: float = 75.0) -> None:
    row = {
        "Rank": 1,
        "Name": "Test Player",
        "Team": "BLT",
        "POS": "WR",
        "G": 1,
        "Season": 2026,
        **{column: None for column in historical.WEEK_COLUMNS},
        "TM RTE %": value,
    }
    row[f"W{source_week}"] = value
    pd.DataFrame([row], columns=historical.EXPECTED_COLUMNS).to_csv(
        path, index=False
    )


def _manifest(root: Path, *, target_week: int = 2) -> tuple[dict, dict]:
    artifact = root / (
        "route-share__season-2026__weeks-01__target-week-02.csv"
    )
    _csv(artifact, source_week=target_week - 1)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with artifact.open(newline="", encoding="utf-8-sig") as handle:
        import csv

        csv_rows = list(csv.reader(handle))
    export = {
        "status": "downloaded",
        "report": "route-share",
        "vendor_property": "receivingRouteShareReport",
        "season": 2026,
        "weeks": [target_week - 1],
        "include_group_headers": False,
        "context": None,
        "target_week": target_week,
        "retrieved_at_utc": "2026-09-15T15:00:00+00:00",
        "source_url": (
            "https://data.fantasypoints.com/nfl/tools/player/"
            "receiving-route-share-report"
        ),
        "path": artifact.name,
        "bytes": artifact.stat().st_size,
        "csv_rows_including_headers": len(csv_rows),
        "max_csv_columns": max(map(len, csv_rows)),
        "sha256": digest,
    }
    manifest = {
        "schema_version": 1,
        "run_id": "20260915T150000Z__2026-route-share-weekly-v1",
        "plan_sha256": weekly.PLAN_SHA256,
        "started_at_utc": "2026-09-15T14:59:00+00:00",
        "finished_at_utc": "2026-09-15T15:01:00+00:00",
        "selected_target_week": target_week,
        "status": "complete",
        "exports": [export],
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    return manifest, export


def _snapshots() -> pd.DataFrame:
    return pd.DataFrame([{
        "season": 2026,
        "gsis_id": "00-1",
        "name": "Test Player",
        "pos": "WR",
        "team": "BAL",
    }])


def test_weekly_manifest_and_normalization_are_strict_prior(tmp_path):
    manifest, _ = _manifest(tmp_path)
    found_manifest, artifact = weekly.validate_manifest(tmp_path, target_week=2)
    assert found_manifest == manifest
    rows, audit = weekly.normalize_artifact(
        found_manifest, artifact, _snapshots()
    )
    assert rows[["season", "week", "source_target_week"]].values.tolist() == [
        [2026, 1, 2]
    ]
    assert rows.gsis_id.tolist() == ["00-1"]
    assert rows.route_share.tolist() == pytest.approx([0.75])
    assert audit["resolved_rows"] == 1


def test_weekly_manifest_rejects_target_or_hash_drift(tmp_path):
    _manifest(tmp_path)
    with pytest.raises(ValueError, match="target week"):
        weekly.validate_manifest(tmp_path, target_week=3)
    payload = json.loads((tmp_path / "manifest.json").read_text())
    payload["exports"][0]["sha256"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="hash differs"):
        weekly.validate_manifest(tmp_path, target_week=2)


def test_weekly_normalization_rejects_non_source_week(tmp_path):
    _, export = _manifest(tmp_path)
    artifact = tmp_path / export["path"]
    frame = pd.read_csv(artifact)
    frame["W2"] = 50.0
    frame.to_csv(artifact, index=False)
    export["local_path"] = artifact
    export["source_week"] = 1
    export["retrieved_at"] = pd.Timestamp("2026-09-15T15:00:00Z")
    manifest = {"run_id": "run"}
    with pytest.raises(ValueError, match="non-source week"):
        weekly.normalize_artifact(manifest, export, _snapshots())


def test_rows_to_append_is_idempotent_and_conflicts_fail(tmp_path):
    manifest, _ = _manifest(tmp_path)
    _, artifact = weekly.validate_manifest(tmp_path, target_week=2)
    rows, _ = weekly.normalize_artifact(manifest, artifact, _snapshots())
    existing = rows[[
        "season", "week", "gsis_id", "normalized_name", "pos",
        "canonical_teams", "route_share_pct", "source_sha256",
    ]].copy()
    assert weekly.rows_to_append(rows, existing).empty
    changed = existing.copy()
    changed.loc[0, "route_share_pct"] = 74.0
    with pytest.raises(RuntimeError, match="conflicts with stored rows"):
        weekly.rows_to_append(rows, changed)


def test_rows_to_append_keeps_unresolved_identity_stable():
    row = pd.DataFrame([{
        "season": 2026,
        "week": 1,
        "gsis_id": None,
        "normalized_name": "testplayer",
        "pos": "WR",
        "canonical_teams": "BAL",
        "route_share_pct": 75.0,
        "source_sha256": "abc",
    }])
    assert weekly.rows_to_append(row, row.copy()).empty
