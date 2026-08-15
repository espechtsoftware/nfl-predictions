from pathlib import Path

import pytest

from nfl_dfs.research.source_preflight import (
    resolve_panel_artifacts,
    validate_execution_identity,
    verify_local_sha256,
)


DIGEST = "a" * 64


def _rows():
    rows = []
    for panel in ("R0", "R1"):
        for season, week in ((2024, 1), (2025, 2)):
            for candidate in range(2):
                rows.append({
                    "panel_run_id": panel,
                    "season": season,
                    "week": week,
                    "score_artifact_uri": (
                        f"gs://bucket/{panel}/{season}/{week}.npz"
                    ),
                    "score_artifact_sha256": DIGEST,
                    "candidate": candidate,
                })
    return rows


def test_resolve_panel_artifacts_requires_complete_unique_grid():
    result = resolve_panel_artifacts(
        _rows(), panel_ids=("R0", "R1"), expected_slates=2,
    )
    assert result["artifact_count"] == 4
    assert result["slates"] == [[2024, 1], [2025, 2]]
    assert all(row["source_rows"] == 2 for row in result["artifacts"])

    missing = _rows()[:-2]
    with pytest.raises(ValueError, match="grid is incomplete"):
        resolve_panel_artifacts(
            missing, panel_ids=("R0", "R1"), expected_slates=2,
        )


def test_resolve_panel_artifacts_rejects_ambiguous_or_invalid_identity():
    rows = _rows()
    rows[0]["score_artifact_uri"] = "gs://bucket/different.npz"
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_panel_artifacts(
            rows, panel_ids=("R0", "R1"), expected_slates=2,
        )

    rows = _rows()
    rows[0]["score_artifact_sha256"] = "short"
    with pytest.raises(ValueError, match="identity is invalid"):
        resolve_panel_artifacts(
            rows, panel_ids=("R0", "R1"), expected_slates=2,
        )


def test_execution_and_local_source_identity(tmp_path: Path):
    validate_execution_identity("b" * 40, "repo/image@sha256:" + "c" * 64)
    with pytest.raises(ValueError, match="full code SHA"):
        validate_execution_identity("short", "repo/image@sha256:" + "c" * 64)

    source = tmp_path / "source.txt"
    source.write_text("frozen\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert verify_local_sha256({"protocol": (source, digest)}) == {
        "protocol": digest,
    }
    with pytest.raises(ValueError, match="differs"):
        verify_local_sha256({"protocol": (source, "d" * 64)})
