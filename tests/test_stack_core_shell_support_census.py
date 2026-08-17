from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from aggregate_stack_core_shell_support_census import (  # noqa: E402
    AGGREGATE_MINIMUM,
    POSITIVE_SLATE_MINIMUM,
    aggregate,
    load_expected_artifact_ledger,
)
from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS  # noqa: E402
from run_stack_core_shell_support_census import (  # noqa: E402
    RUN_ID,
    SUPPORT_THRESHOLDS,
)
from stack_core_shell_sources import (  # noqa: E402
    FORBIDDEN_QUERY_TOKENS,
    EXECUTION_PROTOCOL,
    EXECUTION_PROTOCOL_SHA256,
    PLAYER_SQL,
    PROTOCOL,
    PROTOCOL_SHA256,
    REPAIR_PANEL,
    SOURCE_PANELS,
    SOURCE_SQL,
    validate_local_sources,
)


def _support_shard(season: int, week: int, *, events: int = 10) -> dict:
    ledger = load_expected_artifact_ledger()
    return {
        "version": "stack-core-shell-control-support-shard-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": season,
        "week": week,
        "code_sha": "a" * 40,
        "analysis_image": "example/image@sha256:" + "b" * 64,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_hashes": validate_local_sources(),
        "source_panels": list(SOURCE_PANELS),
        "artifact_receipts": [
            {
                "block": block,
                "source_panel": (
                    REPAIR_PANEL
                    if (season, week, block) == (2025, 1, "R3")
                    else SOURCE_PANELS[index]
                ),
                "canonical_panel": SOURCE_PANELS[index],
                "candidate_rows": int(
                    ledger[(season, week, block)]["candidate_rows"]
                ),
                "uri": ledger[(season, week, block)]["uri"],
                "sha256": ledger[(season, week, block)]["sha256"],
                "generation": str(ledger[(season, week, block)]["generation"]),
                "updated": ledger[(season, week, block)]["updated"],
                "bytes": int(ledger[(season, week, block)]["bytes"]),
            }
            for index, block in enumerate(REGISTERED_BLOCKS)
        ],
        "folds": [
            {
                "heldout_block": block,
                "training_blocks": [
                    name for name in REGISTERED_BLOCKS if name != block
                ],
                "worlds": 10_000,
                "control_entries": 80,
                "candidate_budget": 100,
                "training_union_candidates": 120,
                "threshold_counts": {
                    layer: {
                        str(int(line)): events
                        for line in SUPPORT_THRESHOLDS
                    }
                    for layer in ("candidate", "selected")
                },
            }
            for block in REGISTERED_BLOCKS
        ],
    }


def _write_population(tmp_path: Path, *, events: int = 10) -> list[Path]:
    paths = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            path = tmp_path / f"slate-{season}-{week}.json"
            path.write_text(
                json.dumps(_support_shard(season, week, events=events)),
                encoding="utf-8",
            )
            paths.append(path)
    return paths


def test_stack_core_shell_sources_are_frozen_and_outcome_free() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert hashlib.sha256(EXECUTION_PROTOCOL.read_bytes()).hexdigest() == \
        EXECUTION_PROTOCOL_SHA256
    assert validate_local_sources()[str(PROTOCOL)] == PROTOCOL_SHA256
    assert validate_local_sources()[str(EXECUTION_PROTOCOL)] == \
        EXECUTION_PROTOCOL_SHA256
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    assert not [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    assert SOURCE_PANELS == tuple(
        f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
    )
    assert SUPPORT_THRESHOLDS == (194.0, 210.0, 220.0, 230.0)
    assert AGGREGATE_MINIMUM == 540
    assert POSITIVE_SLATE_MINIMUM == 41


def test_support_launcher_uses_real_path_canary_and_atlas_queue() -> None:
    launcher = (
        ROOT / "scripts/cloud_stack_core_shell_support_census.sh"
    ).read_text(encoding="utf-8")
    canary = (
        ROOT / "scripts/cloud_wait_stack_core_shell_support_canary.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_stack_core_shell_support_census.sh"
    ).read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile.stack-support").read_text(encoding="utf-8")
    cloudbuild = (
        ROOT / "cloudbuild.stack-support.yaml"
    ).read_text(encoding="utf-8")
    watcher = (
        ROOT / "scripts/watch_stack_core_shell_support_queue.sh"
    ).read_text(encoding="utf-8")
    assert "stack-core/shell support awaits ATLAS preflight" in launcher
    assert "repair5-valid-historical-closed" in launcher
    assert "repair5-failed-parity-closed" in launcher
    assert "stack-shell-support-s2023-w1-v1" in canary
    assert '--cpu 4 --memory 16Gi' in launcher
    assert '--max-retries 0 --task-timeout 2h' in launcher
    assert launcher.index('bash "$CANARY"') < launcher.index(
        "for SEASON in 2023 2024 2025"
    )
    assert 'gcloud run jobs executions list --job "$JOB"' in canary
    assert '"remaining_cells_released=false"' in canary
    assert '"treatment_constructed=false"' in canary
    assert "gcloud storage cp" not in canary
    assert "attempt_manager_sha256=" in launcher
    assert "manage_stack_core_shell_support_attempts.py" in launcher
    assert '"$ATTEMPTS" validate' in finisher
    assert "stack-core/shell job attempt population differs" in finisher
    assert "STACK_CORE_SHELL_SUPPORT_STRICTLY_VALIDATED" in finisher
    assert finisher.index('gcloud storage objects describe "$URI"') < \
        finisher.index('gcloud storage cp "$URI"')
    assert "treatment_constructed=false" in finisher
    assert "Dockerfile.stack-support cloudbuild.stack-support.yaml" in launcher
    assert "sha256:51782451d1850ba213cb1fb374f25fe5f53d1d518bcae6a521811719ef8a8179" \
        in docker
    for name in (
        "stack_core_shell_sources.py",
        "run_stack_core_shell_support_census.py",
        "aggregate_stack_core_shell_support_census.py",
    ):
        assert f"COPY scripts/{name} ./scripts/{name}" in docker
    assert "PYTHONPATH=. pytest" in cloudbuild
    for step in (
        "smoke-stack-core-shell-source-loader",
        "smoke-stack-core-shell-support-runner",
        "smoke-stack-core-shell-support-aggregator",
    ):
        assert f"id: {step}" in cloudbuild
    assert 'IMAGE="${TAG%:*}@${DIGEST}"' in watcher
    assert 'bash "$ROOT/scripts/cloud_stack_core_shell_support_census.sh"' \
        in watcher
    assert 'bash "$ROOT/scripts/cloud_finish_stack_core_shell_support_census.sh"' \
        in watcher
    assert "manage_stack_core_shell_support_attempts.py" in watcher
    assert "cloud_finish_stack_core_shell_support_census.sh" in watcher
    assert "accepted-population-with-platform-replacements" in watcher


def test_support_shell_embedded_python_compiles() -> None:
    paths = (
        ROOT / "scripts/cloud_stack_core_shell_support_census.sh",
        ROOT / "scripts/cloud_wait_stack_core_shell_support_canary.sh",
        ROOT / "scripts/cloud_finish_stack_core_shell_support_census.sh",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", source, flags=re.DOTALL)
        assert blocks, path
        for index, block in enumerate(blocks):
            compile(block, f"{path.name}:heredoc-{index}", "exec")


def test_distributed_support_licenses_p230_treatment(tmp_path: Path) -> None:
    result = aggregate(_write_population(tmp_path, events=10))
    assert result["mechanical"]["heldout_folds"] == 270
    assert result["adequate_by_threshold"] == {
        "230": True, "220": True, "210": True,
    }
    assert result["selected_anchor"] == 230
    assert result["disposition"] == \
        "p230-supported-stack-core-shell-treatment-licensed"
    assert result["treatment_constructed"] is False
    for layer in ("candidate", "selected"):
        distribution = result[
            "counts_by_layer_and_block"
        ][layer]["R0"]["230"]
        assert distribution["positive_slates"] == 54
        assert math.isclose(distribution["effective_slates"], 54.0)
        assert distribution["top_5_event_share"] == 50 / 540
        assert len(distribution["slate_counts"]) == 54
        correlation = result[
            "fold_correlation_by_layer_and_threshold"
        ][layer]["230"]
        assert len(correlation["pairs"]) == 10
        assert correlation["finite_pairs"] == 0
        assert correlation["folds_are_independent"] is False


def test_sparse_selected_p230_uses_predeclared_p220(tmp_path: Path) -> None:
    paths = _write_population(tmp_path, events=10)
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        value["folds"][0]["threshold_counts"]["selected"]["230"] = 0
        path.write_text(json.dumps(value), encoding="utf-8")
    result = aggregate(paths)
    assert result["adequate_by_threshold"]["230"] is False
    assert result["adequate_by_threshold"]["220"] is True
    assert result["selected_anchor"] == 220
    assert result["disposition"] == \
        "p220-supported-stack-core-shell-treatment-licensed"


def test_concentrated_support_and_treatment_fields_fail_closed(
    tmp_path: Path,
) -> None:
    paths = _write_population(tmp_path, events=0)
    for path in paths[:5]:
        value = json.loads(path.read_text(encoding="utf-8"))
        for fold in value["folds"]:
            for layer in ("candidate", "selected"):
                for line in ("230", "220", "210"):
                    fold["threshold_counts"][layer][line] = 540
        path.write_text(json.dumps(value), encoding="utf-8")
    result = aggregate(paths)
    assert result["selected_anchor"] is None
    assert result["disposition"] == \
        "terminal-insufficient-stack-core-shell-support"
    distribution = result[
        "counts_by_layer_and_block"
    ]["selected"]["R0"]["230"]
    assert distribution["positive_slates"] == 5
    assert distribution["top_5_event_share"] == 1.0
    assert math.isclose(distribution["effective_slates"], 5.0)

    bad = copy.deepcopy(json.loads(paths[0].read_text(encoding="utf-8")))
    bad["proposals"] = []
    paths[0].write_text(json.dumps(bad), encoding="utf-8")
    try:
        aggregate(paths)
    except ValueError as exc:
        assert "forbidden field" in str(exc)
    else:
        raise AssertionError("support census accepted treatment construction")
