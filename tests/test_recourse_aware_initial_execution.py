from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from aggregate_constraint_lattice_scorefree import (  # noqa: E402
    load_expected_artifact_ledger,
)
from aggregate_recourse_aware_initial_scorefree import (  # noqa: E402
    EXPECTED_SOURCE_HASHES,
    aggregate,
)
from run_recourse_aware_initial_scorefree import (  # noqa: E402
    EXECUTION_PROTOCOL,
    EXECUTION_PROTOCOL_SHA256,
    FORBIDDEN_QUERY_TOKENS,
    FORENSIC_MANIFEST_SHA256,
    KICKOFF_SQL,
    RUN_ID,
    SCIENCE_PROTOCOL,
    SCIENCE_PROTOCOL_SHA256,
    SOURCE_PANELS,
    validate_local_sources,
)
from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS  # noqa: E402
from nfl_dfs.analysis.recourse_aware_initial import (  # noqa: E402
    TAILS,
    VERSION,
)


def _coverage(events: dict[int, int]) -> dict[str, dict[str, float | int]]:
    return {
        str(threshold): {"events": value, "rate": value / 10_000}
        for threshold, value in events.items()
    }


def _rosters(season: int, week: int) -> list[list[str]]:
    return [
        sorted(f"{season}-{week}-{entry}-{slot}" for slot in range(9))
        for entry in range(80)
    ]


def _metrics(reachable_p230: int) -> dict:
    events = {240: 1, 230: reachable_p230, 220: 20, 210: 30,
              200: 50, 194: 100, 187: 200}
    locked_counts = {str(index): 80 if index == 0 else 0 for index in range(10)}
    slot_counts = {str(index): 0 for index in range(9)}
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "entries": 80,
        "worlds": 10_000,
        "initial_coverage": _coverage({**events, 230: 10}),
        "reachable_union_coverage": _coverage(events),
        "reachable_alternatives": 80,
        "alternatives_per_entry": {
            "minimum": 1, "median": 1.0, "mean": 1.0, "maximum": 1,
        },
        "distinct_locked_slot_signatures": 1,
        "locked_slot_count_distribution": locked_counts,
        "locked_slot_index_distribution": slot_counts,
        "locked_player_frequency": [],
        "locked_signature_frequency": [{"signature": [], "entries": 80}],
    }


def _fold(season: int, week: int, block: str) -> dict:
    rosters = _rosters(season, week)
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "season": season,
        "week": week,
        "heldout_block": block,
        "training_blocks": [
            value for value in REGISTERED_BLOCKS if value != block
        ],
        "candidate_budget": 100,
        "alternative_cap": 24,
        "control": _metrics(10),
        "treatment": _metrics(11),
        "selected_identity_overlap": 80,
        "selected_identity_jaccard": 1.0,
        "control_selected_rosters": rosters,
        "treatment_selected_rosters": rosters,
    }


def _shard(season: int, week: int) -> dict:
    ledger = load_expected_artifact_ledger()
    return {
        "version": "recourse-aware-initial-book-scorefree-shard-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": season,
        "week": week,
        "code_sha": "a" * 40,
        "analysis_image": "example/image@sha256:" + "b" * 64,
        "source_hashes": EXPECTED_SOURCE_HASHES,
        "source_panels": list(SOURCE_PANELS),
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "cbwu_report_sha256": (
            "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
        ),
        "decision_time": "2026-09-13T15:55:00-04:00",
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
            _fold(season, week, block) for block in REGISTERED_BLOCKS
        ],
    }


def _write_population(tmp_path: Path) -> list[Path]:
    paths = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            path = tmp_path / f"slate-{season}-{week}.json"
            path.write_text(json.dumps(_shard(season, week)), encoding="utf-8")
            paths.append(path)
    return paths


def test_execution_sources_are_frozen_outcome_free_and_packaged() -> None:
    assert sha256(SCIENCE_PROTOCOL.read_bytes()).hexdigest() == (
        SCIENCE_PROTOCOL_SHA256
    )
    assert sha256(EXECUTION_PROTOCOL.read_bytes()).hexdigest() == (
        EXECUTION_PROTOCOL_SHA256
    )
    assert not [
        token for token in FORBIDDEN_QUERY_TOKENS if token in KICKOFF_SQL.lower()
    ]
    validate_local_sources()
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    for name in (
        "run_recourse_aware_initial_scorefree.py",
        "aggregate_recourse_aware_initial_scorefree.py",
    ):
        assert f"COPY scripts/{name} ./scripts/{name}" in docker
        assert f"python scripts/{name} --help" in cloudbuild


def test_complete_population_strictly_aggregates(tmp_path: Path) -> None:
    paths = _write_population(tmp_path)
    result = aggregate(paths)
    assert result["mechanical"] == {
        "slates": 54,
        "folds": 270,
        "worlds_per_fold": 10_000,
        "all_valid": True,
    }
    assert result["gate_diagnostics"]["reachable_p230_event_gain"] == 270
    assert result["passed"] is True
    assert len(result["source_artifacts"]) == 270
    assert len(result["leave_one_slate_out_influence"]) == 54


def test_aggregate_rejects_incomplete_or_outcome_facing_population(
    tmp_path: Path,
) -> None:
    paths = _write_population(tmp_path)
    with pytest.raises(ValueError, match="54 unique shards"):
        aggregate(paths[:-1])
    changed = copy.deepcopy(json.loads(paths[0].read_text(encoding="utf-8")))
    changed["actual_score"] = 200
    paths[0].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="outcome field"):
        aggregate(paths)
