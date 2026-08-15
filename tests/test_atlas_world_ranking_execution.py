import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def _runner():
    path = ROOT / "scripts/run_atlas_world_ranking.py"
    spec = importlib.util.spec_from_file_location("atlas_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_atlas_runner_queries_are_score_free_and_scope_is_exact():
    runner = _runner()
    runner.validate_scorefree_queries()
    combined = (runner.SOURCE_SQL + runner.PLAYER_SQL).lower()
    assert "actual_score" not in combined
    assert "actual_rank" not in combined
    assert "actual_ownership" not in combined
    assert runner.SOURCE_PANEL_IDS == tuple(
        f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
    )
    assert runner.FORENSIC_MANIFEST_SHA256 == (
        "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
    )


def test_atlas_cloud_contract_is_create_only_and_packaged():
    launch = (ROOT / "scripts/cloud_atlas_world_ranking.sh").read_text()
    docker = (ROOT / "Dockerfile").read_text()
    assert "20260815-atlas-world-ranking-scorefree-v1/result.json" in launch
    assert "gcloud storage objects describe" in launch
    assert "--memory 32Gi" in launch
    assert "--max-retries 0" in launch
    assert "COPY scripts/run_atlas_world_ranking.py" in docker
    assert "manifest.txt" in launch
    assert "execution.txt" in launch
    finish = (ROOT / "scripts/cloud_finish_atlas_world_ranking.sh").read_text()
    assert "len(report.get(\"source_artifacts\", [])) != 270" in finish
    assert "gate.get(\"rows\") != 270" in finish
    assert "uses_realized_outcomes" in finish


def test_atlas_player_catalog_may_include_authoritative_only_rows():
    runner = _runner()
    catalog = pd.DataFrame([
        {
            "player_id": "p1", "player_name": "One", "position": "QB",
            "team": "A", "opponent": "B", "game_id": "A@B",
            "salary": 6000, "mean_projection": 20.0,
        },
        {
            "player_id": "p2", "player_name": "Two", "position": "WR",
            "team": "A", "opponent": "B", "game_id": "A@B",
            "salary": 5000, "mean_projection": 15.0,
        },
        {
            "player_id": "catalog-only", "player_name": "Extra",
            "position": "WR", "team": "C", "opponent": "D",
            "game_id": "C@D", "salary": 3000, "mean_projection": 0.0,
        },
    ])
    rows = runner._player_rows(catalog, np.asarray(["p2", "p1"]))
    assert [row["id"] for row in rows] == ["p2", "p1"]
    with pytest.raises(RuntimeError, match="missing from the player catalog"):
        runner._player_rows(catalog, np.asarray(["p1", "missing"]))
