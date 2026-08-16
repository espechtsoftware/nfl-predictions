from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from aggregate_constraint_lattice_scorefree import (  # noqa: E402
    load_expected_artifact_ledger,
)
from aggregate_constraint_lattice_support_census import (  # noqa: E402
    AGGREGATE_MINIMUM,
    POSITIVE_SLATE_MINIMUM,
    _expected_source_hashes,
    aggregate,
)
from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS  # noqa: E402
from run_constraint_lattice_scorefree import (  # noqa: E402
    FORENSIC_MANIFEST_SHA256,
    SOURCE_PANELS,
)
from run_constraint_lattice_support_census import (  # noqa: E402
    PROTOCOL,
    PROTOCOL_SHA256,
    RUN_ID,
    SUPPORT_THRESHOLDS,
)


def _support_shard(season: int, week: int, *, events: int = 10) -> dict:
    ledger = load_expected_artifact_ledger()
    return {
        "version": "constraint-lattice-control-support-shard-v1",
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
        "source_hashes": _expected_source_hashes(),
        "source_panels": list(SOURCE_PANELS),
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "artifact_receipts": [
            {
                "block": block,
                "source_panel": ledger[(season, week, block)]["panel_run_id"],
                "candidate_rows": int(
                    ledger[(season, week, block)]["candidate_rows"]
                ),
                "uri": ledger[(season, week, block)]["uri"],
                "sha256": ledger[(season, week, block)]["sha256"],
                "generation": str(ledger[(season, week, block)]["generation"]),
                "updated": ledger[(season, week, block)]["updated"],
                "bytes": int(ledger[(season, week, block)]["bytes"]),
            }
            for block in REGISTERED_BLOCKS
        ],
        "folds": [
            {
                "heldout_block": block,
                "training_blocks": [name for name in REGISTERED_BLOCKS if name != block],
                "worlds": 10_000,
                "control_entries": 80,
                "candidate_budget": 100,
                "training_union_candidates": 120,
                "threshold_counts": {
                    str(int(threshold)): events for threshold in SUPPORT_THRESHOLDS
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


def test_support_protocol_and_thresholds_are_frozen() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert PROTOCOL_SHA256 == (
        "11e97d5e94a11808b4838396c6fe59ff327a65a9ae260223138657db8d2a1a17"
    )
    assert SUPPORT_THRESHOLDS == (194.0, 210.0, 220.0, 230.0)
    assert AGGREGATE_MINIMUM == 540
    assert POSITIVE_SLATE_MINIMUM == 41


def test_support_cloud_transport_is_strict_and_atlas_queue_gated() -> None:
    launcher = (
        ROOT / "scripts/cloud_constraint_lattice_support_census.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_constraint_lattice_support_census.sh"
    ).read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    for name in (
        "run_constraint_lattice_support_census.py",
        "aggregate_constraint_lattice_support_census.py",
        "run_constraint_lattice_resource_preflight.py",
    ):
        assert f"COPY scripts/{name} ./scripts/{name}" in docker
        assert f"python scripts/{name} --help" in cloudbuild
    assert 'for SEASON in 2023 2024 2025' in launcher
    assert 'for WEEK in $(seq 1 18)' in launcher
    assert "lattice support awaits repair5 historical closure" in launcher
    assert "repair5-failed-parity-closed" in launcher
    assert '--cpu 4 --memory 16Gi' in launcher
    assert '--max-retries 0 --task-timeout 2h' in launcher
    assert 'gcloud run jobs executions list --job "$JOB"' in finisher
    assert 'task.get("maxRetries")!=0' in finisher
    assert '"treatment_constructed") is not False' in finisher
    assert "CONSTRAINT_LATTICE_SUPPORT_STRICTLY_VALIDATED" in finisher


def test_resource_preflight_is_exact_full_cell_and_effect_blind() -> None:
    protocol = (
        ROOT / "reports/2026-08-16-constraint-lattice-resource-preflight-protocol.md"
    )
    launcher = (
        ROOT / "scripts/cloud_constraint_lattice_resource_preflight.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_constraint_lattice_resource_preflight.sh"
    ).read_text(encoding="utf-8")
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "9e04ebcbcb2def607e28c5f8fa046ba4456f40e2e8a654182f654318ca579d7b"
    )
    assert "source_artifact_bytes=163064634" in launcher
    assert "constraint-lattice-resource-2023-w1-v1" in launcher
    assert '--cpu 4 --memory 16Gi' in launcher
    assert '--max-retries 0 --task-timeout 12h' in launcher
    assert "run_constraint_lattice_resource_preflight.py" in launcher
    assert "gcloud storage cp" not in finisher
    assert "CONSTRAINT_LATTICE_FOLD_COMPLETE 2023 1" in finisher
    assert "object_content_inspected=false" in finisher
    assert "effect_fields_inspected=false" in finisher


def test_complete_distributed_p230_support_keeps_original_gate(tmp_path: Path) -> None:
    result = aggregate(_write_population(tmp_path, events=10))
    assert result["mechanical"]["heldout_folds"] == 270
    assert result["adequate_by_threshold"] == {
        "230": True, "220": True, "210": True,
    }
    assert result["selected_anchor"] == 230
    assert result["disposition"] == "p230-supported-original-gate-complete"
    assert result["treatment_constructed"] is False


def test_sparse_p230_uses_predeclared_p220_branch(tmp_path: Path) -> None:
    paths = _write_population(tmp_path, events=10)
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        value["folds"][0]["threshold_counts"]["230"] = 0
        path.write_text(json.dumps(value), encoding="utf-8")
    result = aggregate(paths)
    assert result["adequate_by_threshold"]["230"] is False
    assert result["adequate_by_threshold"]["220"] is True
    assert result["selected_anchor"] == 220
    assert result["disposition"] == "reanchor-required-p220"


def test_concentrated_events_fail_positive_slate_support(tmp_path: Path) -> None:
    paths = _write_population(tmp_path, events=0)
    for path in paths[:5]:
        value = json.loads(path.read_text(encoding="utf-8"))
        for fold in value["folds"]:
            fold["threshold_counts"]["230"] = 540
            fold["threshold_counts"]["220"] = 540
            fold["threshold_counts"]["210"] = 540
        path.write_text(json.dumps(value), encoding="utf-8")
    result = aggregate(paths)
    assert result["global_counts"]["230"]["events"] == 13_500
    assert result["adequate_by_threshold"] == {
        "230": False, "220": False, "210": False,
    }
    assert result["selected_anchor"] is None
    assert result["disposition"] == "terminal-insufficient-support"


def test_support_aggregate_rejects_treatment_or_incomplete_population(
    tmp_path: Path,
) -> None:
    paths = _write_population(tmp_path, events=10)
    bad = json.loads(paths[0].read_text(encoding="utf-8"))
    bad["treatment_rosters"] = []
    paths[0].write_text(json.dumps(bad), encoding="utf-8")
    try:
        aggregate(paths)
    except ValueError as exc:
        assert "forbidden field" in str(exc)
    else:
        raise AssertionError("constraint-lattice support accepted treatment data")
    clean = copy.deepcopy(bad)
    clean.pop("treatment_rosters")
    paths[0].write_text(json.dumps(clean), encoding="utf-8")
    try:
        aggregate(paths[:-1])
    except ValueError as exc:
        assert "54 unique shards" in str(exc)
    else:
        raise AssertionError("constraint-lattice support accepted incomplete grid")
