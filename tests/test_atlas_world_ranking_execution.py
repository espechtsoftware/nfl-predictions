import importlib.util
from pathlib import Path


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
