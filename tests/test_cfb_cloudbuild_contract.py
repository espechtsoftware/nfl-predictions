"""Fail-closed contract for the scoped CFB collection release image."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "cloudbuild.cfb-collection-repair.yaml"
DOCKERFILE = ROOT / "Dockerfile.cfb-collection-repair"
BUILDER = ROOT / "scripts/build_cfb_collection_repair_image.sh"

FOCUSED_MODULES = (
    "tests/test_cfb_job.py",
    "tests/test_dk_client.py",
    "tests/test_bq_load.py",
    "tests/test_cfb_deployment_contract.py",
)


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _step(step_id: str) -> dict:
    matches = [step for step in _config()["steps"] if step.get("id") == step_id]
    assert len(matches) == 1
    return matches[0]


def _script(step_id: str) -> str:
    return _step(step_id)["args"][-1]


def test_validation_step_runs_exact_34_test_boundary() -> None:
    script = _script("cfb-focused-validation")

    start = script.index("PYTHONPATH=src pytest \\")
    end = script.index("\n\n", start)
    focused_command = script[start:end]
    assert all(module in focused_command for module in FOCUSED_MODULES)
    assert focused_command.count("tests/test_") == len(FOCUSED_MODULES)
    assert "tests/test_cfb_cloudbuild_contract.py" not in focused_command
    assert "PYTHONPATH=src pytest\n" not in script


def test_image_build_is_commit_bound_and_dedicated() -> None:
    config = _config()
    build = _step("build-cfb-collection-image")
    args = build["args"]

    assert "Dockerfile.cfb-collection-repair" in args
    assert "SOURCE_COMMIT_SHA=${_CODE_SHA}" in args
    assert "${_CFB_IMAGE}" in args
    assert config["images"] == ["${_CFB_IMAGE}"]
    assert config["substitutions"]["_CODE_SHA"] == "0" * 40
    assert config["substitutions"]["_CFB_IMAGE"] == "unset"


def test_image_smoke_is_offline_and_checks_runtime_assets() -> None:
    script = _script("smoke-cfb-collection-image")

    assert "org.opencontainers.image.revision" in script
    assert "from nfl_dfs.ingest import cfb_job, dk_client" in script
    assert "sql/raw/005_dk_contests.sql" in script
    assert "sql/raw/006_cfb_dk_salaries.sql" in script
    assert "nfl-dfs --help" in script
    assert "INGEST_CFB_ENABLED=" in script
    assert "nfl-dfs ingest-cfb" in script


def test_exact_archive_excludes_unrelated_heavy_inputs() -> None:
    source = BUILDER.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "git -C \"$SOURCE_ROOT\" archive" in source
    assert source.count('fetch --quiet origin main') == 2
    assert 'trap cleanup EXIT' in source
    assert 'FULL_PUSHED_CODE_SHA must equal local origin/main' in source
    assert 'build context unexpectedly contains reports' in source
    assert "COPY reports" not in dockerfile
    assert "COPY src ./src" in dockerfile
    assert 'CMD ["nfl-dfs", "ingest-cfb"]' in dockerfile
