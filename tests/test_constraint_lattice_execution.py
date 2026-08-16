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
    EXPECTED_SOURCE_HASHES,
    aggregate,
    load_expected_artifact_ledger,
)
from run_constraint_lattice_scorefree import (  # noqa: E402
    FORBIDDEN_QUERY_TOKENS,
    FORENSIC_MANIFEST_SHA256,
    PLAYER_SQL,
    PROTOCOL_SHA256,
    SOURCE_AMENDMENT,
    SOURCE_AMENDMENT_SHA256,
    SOURCE_PANELS,
    SOURCE_SQL,
    validate_local_sources,
)
from nfl_dfs.analysis.constraint_lattice import (  # noqa: E402
    CELL_ORDER,
    REGISTERED_BLOCKS,
    REPORT_THRESHOLDS,
    VERSION,
    protocol_receipt,
)


def _rosters(prefix, count=80):
    return [[f"{prefix}-{row}-{slot}" for slot in range(9)] for row in range(count)]


def _fold(season, week, block):
    training = [value for value in REGISTERED_BLOCKS if value != block]
    rosters = _rosters(f"{season}-{week}-{block}")
    counts = {f"{value:g}": 1 for value in REPORT_THRESHOLDS}
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "season": season,
        "week": week,
        "heldout_block": block,
        "worlds": 10_000,
        "control_entries": 80,
        "treatment_entries": 80,
        "exception_counts": {cell: 0 for cell in CELL_ORDER},
        "new_exception_entries": 0,
        "shared_rosters": 80,
        "maximum_treatment_pairwise_roster_overlap": 0,
        "threshold_counts": {"control": counts, "treatment": dict(counts)},
        "book_maximum": {
            book: {"mean": 180.0, "q90": 200.0, "q95": 210.0, "q99": 230.0}
            for book in ("control", "treatment")
        },
        "structure": {
            book: {
                "unique_players": 720,
                "unique_player_pairs": 1000,
                "unique_qb_stack_cores": 80,
                "unique_dominant_games": 12,
            }
            for book in ("control", "treatment")
        },
        "training_blocks": training,
        "candidate_budget": 80,
        "training_union_candidates": 80,
        "candidate_source_aggregation": [
            {"roster": roster, "sources": training, "tags": ["lev"]}
            for roster in rosters
        ],
        "raw_exception_candidates": 0,
        "retained_exception_candidates": 0,
        "control_candidate_rosters": rosters,
        "control_rosters": rosters,
        "treatment_rosters": rosters,
        "generation": [
            {
                "cell": cell,
                "source_block": source,
                "attempted_worlds": 1,
                "duplicate_world_solutions": 0,
                "structurally_infeasible": True,
                "elapsed_seconds": 0.1,
                "retained": [],
            }
            for cell in CELL_ORDER for source in training
        ],
        "candidate_ranking": [],
        "admission": {
            "admitted": [], "rejected": [],
            "control_coverage_world_counts": {},
            "treatment_coverage_world_counts": {},
        },
        "elapsed_seconds": 2.0,
    }


def _shard(season, week):
    ledger = load_expected_artifact_ledger()
    return {
        "version": "constraint-lattice-scorefree-shard-v1",
        "run_id": "20260816-constraint-lattice-scorefree-v1",
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
        "protocol_receipt": protocol_receipt(),
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
        "slate": {
            "version": VERSION,
            "uses_realized_outcomes": False,
            "season": season,
            "week": week,
            "elapsed_seconds": 10.0,
            "folds": [_fold(season, week, block) for block in REGISTERED_BLOCKS],
        },
    }


def _write_population(tmp_path):
    paths = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            path = tmp_path / f"slate-{season}-{week}.json"
            path.write_text(json.dumps(_shard(season, week)), encoding="utf-8")
            paths.append(path)
    return paths


def test_source_binding_is_frozen_scorefree_and_packaged():
    assert hashlib.sha256(SOURCE_AMENDMENT.read_bytes()).hexdigest() == (
        SOURCE_AMENDMENT_SHA256
    )
    assert PROTOCOL_SHA256 == (
        "f8591d24dd56749e5b56235f9636687fd41bd1a78991fdb60cfbb092ee65bf62"
    )
    assert not [
        token for token in FORBIDDEN_QUERY_TOKENS
        if token in f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    ]
    validate_local_sources()
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    for name in (
        "run_constraint_lattice_scorefree.py",
        "aggregate_constraint_lattice_scorefree.py",
    ):
        assert f"COPY scripts/{name} ./scripts/{name}" in docker
        assert f"python scripts/{name} --help" in cloudbuild


def test_cloud_transport_is_exact_sharded_and_queue_gated():
    launcher = (ROOT / "scripts/cloud_constraint_lattice_scorefree.sh").read_text(
        encoding="utf-8"
    )
    finisher = (
        ROOT / "scripts/cloud_finish_constraint_lattice_scorefree.sh"
    ).read_text(encoding="utf-8")
    assert 'for SEASON in 2023 2024 2025' in launcher
    assert 'for WEEK in $(seq 1 18)' in launcher
    assert '--cpu 4 --memory 16Gi' in launcher
    assert '--max-retries 0 --task-timeout 12h' in launcher
    assert 'wc -l < "$EXECUTIONS")" = 54' in launcher
    assert 'git -C "$ROOT" show "$CODE_SHA:$RELATIVE"' in launcher
    assert "constraint-lattice queue awaits ATLAS preflight" in launcher
    assert "repair5-valid-historical-closed" in launcher
    assert "repair5-failed-parity-closed" in launcher
    assert 'gcloud run jobs executions list --job "$JOB"' in finisher
    assert 'task.get("maxRetries")!=0' in finisher
    assert '"heldout_folds":270' in finisher
    assert 'CONSTRAINT_LATTICE_STRICT_AGGREGATE_VALIDATED' in finisher


def test_complete_population_aggregates_once_and_fails_valid_null(tmp_path):
    result = aggregate(_write_population(tmp_path))
    assert result["mechanical"] == {
        "seasons": [2023, 2024, 2025],
        "slates": 54,
        "heldout_folds": 270,
        "source_artifacts": 270,
        "all_valid": True,
    }
    assert result["gate"]["passes_scorefree_gate"] is False
    assert result["gate"]["disposition"] == "constraint-lattice-scorefree-fails"
    assert result["production_change_licensed"] is False
    assert result["historical_scoring_licensed"] is False


def test_aggregate_rejects_outcome_field_and_incomplete_grid(tmp_path):
    paths = _write_population(tmp_path)
    bad = json.loads(paths[0].read_text(encoding="utf-8"))
    bad["actual_score"] = 200.0
    paths[0].write_text(json.dumps(bad), encoding="utf-8")
    try:
        aggregate(paths)
    except ValueError as exc:
        assert "outcome field" in str(exc)
    else:
        raise AssertionError("constraint-lattice outcome field was accepted")
    clean = copy.deepcopy(bad)
    clean.pop("actual_score")
    paths[0].write_text(json.dumps(clean), encoding="utf-8")
    try:
        aggregate(paths[:-1])
    except ValueError as exc:
        assert "54 unique shards" in str(exc)
    else:
        raise AssertionError("constraint-lattice incomplete grid was accepted")


def test_aggregate_rejects_source_ledger_and_fold_receipt_tampering(tmp_path):
    paths = _write_population(tmp_path)
    bad = json.loads(paths[0].read_text(encoding="utf-8"))
    bad["artifact_receipts"][0]["source_panel"] = SOURCE_PANELS[1]
    paths[0].write_text(json.dumps(bad), encoding="utf-8")
    try:
        aggregate(paths)
    except ValueError as exc:
        assert "artifact receipt differs" in str(exc)
    else:
        raise AssertionError("constraint-lattice source-panel swap was accepted")

    bad = _shard(2023, 1)
    bad["slate"]["folds"][0]["candidate_source_aggregation"][0][
        "roster"
    ] = _rosters("tampered", 1)[0]
    paths[0].write_text(json.dumps(bad), encoding="utf-8")
    try:
        aggregate(paths)
    except ValueError as exc:
        assert "source receipt is malformed" in str(exc)
    else:
        raise AssertionError("constraint-lattice roster/source mismatch was accepted")
