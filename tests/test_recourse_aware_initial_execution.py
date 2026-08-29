from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd
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
import run_recourse_aware_initial_scorefree as scorefree_runner  # noqa: E402
from run_recourse_aware_initial_scorefree import (  # noqa: E402
    EXECUTION_PROTOCOL,
    EXECUTION_PROTOCOL_SHA256,
    FORBIDDEN_QUERY_TOKENS,
    FORENSIC_MANIFEST_SHA256,
    KICKOFF_AMENDMENT,
    KICKOFF_AMENDMENT_SHA256,
    KICKOFF_POPULATION_AMENDMENT,
    KICKOFF_POPULATION_AMENDMENT_SHA256,
    KICKOFF_SQL,
    RUN_ID,
    SCIENCE_PROTOCOL,
    SCIENCE_PROTOCOL_SHA256,
    SOURCE_PANELS,
    validate_local_sources,
)
from validate_recourse_aware_initial_canary import validate as validate_canary  # noqa: E402
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
        "decision_time": scorefree_runner.decision_instant(
            scorefree_runner._sunday_main_date(season, week)
        ).isoformat(),
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
    assert RUN_ID == "20260829-recourse-aware-initial-book-scorefree-kickoff-v3"
    assert sha256(SCIENCE_PROTOCOL.read_bytes()).hexdigest() == (
        SCIENCE_PROTOCOL_SHA256
    )
    assert sha256(EXECUTION_PROTOCOL.read_bytes()).hexdigest() == (
        EXECUTION_PROTOCOL_SHA256
    )
    assert sha256(KICKOFF_AMENDMENT.read_bytes()).hexdigest() == (
        KICKOFF_AMENDMENT_SHA256
    )
    assert sha256(KICKOFF_POPULATION_AMENDMENT.read_bytes()).hexdigest() == (
        KICKOFF_POPULATION_AMENDMENT_SHA256
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


def _kickoff_rows(rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "manifest_sha256": FORENSIC_MANIFEST_SHA256,
            "player_id": player_id,
            "kickoff_time": kickoff,
        }
        for player_id, kickoff in rows
    ])


def test_kickoff_query_filters_exact_sorted_expected_player_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def query(_client, sql, params):
        observed["sql"] = sql
        observed["params"] = params
        return _kickoff_rows([
            ("p-a", "13:00"),
            ("p-b", "16:25"),
        ])

    monkeypatch.setattr(scorefree_runner, "_query", query)
    kickoffs, decision = scorefree_runner._slate_kickoffs(
        object(), season=2023, week=1, expected_player_ids={"p-b", "p-a"},
    )
    assert "player_id IN UNNEST(@player_ids)" in str(observed["sql"])
    player_parameter = next(
        value for value in observed["params"] if value.name == "player_ids"
    )
    assert player_parameter.values == ["p-a", "p-b"]
    assert set(kickoffs) == {"p-a", "p-b"}
    assert kickoffs["p-a"].isoformat() == "2023-09-10T13:00:00-04:00"
    assert kickoffs["p-b"].isoformat() == "2023-09-10T16:25:00-04:00"
    assert decision.isoformat() == "2023-09-10T15:55:00-04:00"


@pytest.mark.parametrize(
    ("season", "week", "expected_date", "expected_offset"),
    [
        (2023, 1, "2023-09-10", "-04:00"),
        (2023, 9, "2023-11-05", "-05:00"),
        (2024, 18, "2025-01-05", "-05:00"),
        (2025, 18, "2026-01-04", "-05:00"),
    ],
)
def test_kickoff_wall_clock_uses_fixed_sunday_and_preserves_dst(
    monkeypatch: pytest.MonkeyPatch,
    season: int,
    week: int,
    expected_date: str,
    expected_offset: str,
) -> None:
    monkeypatch.setattr(
        scorefree_runner,
        "_query",
        lambda *_args, **_kwargs: _kickoff_rows([
            ("p-a", "13:00"), ("p-b", "16:25"),
        ]),
    )
    kickoffs, decision = scorefree_runner._slate_kickoffs(
        object(),
        season=season,
        week=week,
        expected_player_ids={"p-a", "p-b"},
    )
    assert kickoffs["p-a"].isoformat() == (
        f"{expected_date}T13:00:00{expected_offset}"
    )
    assert kickoffs["p-b"].isoformat() == (
        f"{expected_date}T16:25:00{expected_offset}"
    )
    assert decision.isoformat() == f"{expected_date}T15:55:00{expected_offset}"


@pytest.mark.parametrize(
    ("season", "week"),
    [(2022, 1), (2023, 0), (2023, 19), (2023, True)],
)
def test_sunday_main_date_rejects_out_of_grid_coordinates(
    season: int,
    week: int,
) -> None:
    with pytest.raises(RuntimeError, match="Sunday-main coordinate differs"):
        scorefree_runner._sunday_main_date(season, week)


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [
                ("p-a", "13:00"),
                ("p-b", "16:25"),
                ("p-extra", "16:25"),
            ],
            "population differs",
        ),
        ([("p-a", "13:00")], "population differs"),
        (
            [
                ("p-a", "13:00"),
                ("p-a", "13:00"),
                ("p-b", "16:25"),
            ],
            "population differs",
        ),
        (
            [("p-a", "not-a-time"), ("p-b", "16:25")],
            "not strict HH:MM",
        ),
        (
            [
                ("p-a", "2023-09-10T13:00:00-04:00"),
                ("p-b", "2023-09-11T16:25:00-04:00"),
            ],
            "not strict HH:MM",
        ),
        (
            [
                ("p-a", "13:00"),
                ("p-b", "14:00"),
            ],
            "lacks early/late games",
        ),
        (
            [("p-a", "13:00:00"), ("p-b", "16:25")],
            "not strict HH:MM",
        ),
        (
            [("p-a", " 13:00"), ("p-b", "16:25")],
            "not strict HH:MM",
        ),
    ],
)
def test_kickoff_query_fails_closed_on_population_time_and_split_drift(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[tuple[str, str]],
    message: str,
) -> None:
    monkeypatch.setattr(
        scorefree_runner, "_query", lambda *_args, **_kwargs: _kickoff_rows(rows)
    )
    with pytest.raises(RuntimeError, match=message):
        scorefree_runner._slate_kickoffs(
            object(),
            season=2023,
            week=1,
            expected_player_ids={"p-a", "p-b"},
        )


def _canary_metadata(execution: str) -> dict:
    image = "example/image@sha256:" + "b" * 64
    uri = (
        "gs://nfl-predictions-503414-raw/research/"
        f"recourse-aware-initial-book-runs/{RUN_ID}/slate-2023-1.json"
    )
    return {
        "metadata": {"name": execution},
        "spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": image,
                    "command": ["python"],
                    "args": [
                        "scripts/run_recourse_aware_initial_scorefree.py",
                        "--season", "2023", "--week", "1",
                        "--output-uri", uri,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": "a" * 40},
                        {"name": "ANALYSIS_IMAGE", "value": image},
                    ],
                    "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                }],
                "maxRetries": 0,
                "timeoutSeconds": "14400",
                "serviceAccountName": (
                    "817589974517-compute@developer.gserviceaccount.com"
                ),
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "failedCount": 0,
            "retriedCount": 0,
            "completionTime": "2026-08-17T12:00:00Z",
        },
    }


def test_actual_final_path_canary_validates_without_aggregate_disclosure(
    tmp_path: Path,
) -> None:
    execution = "recourse-initial-s2023-w1-kickoff-v3-example"
    uri = (
        "gs://nfl-predictions-503414-raw/research/"
        f"recourse-aware-initial-book-runs/{RUN_ID}/slate-2023-1.json"
    )
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("\n".join((
        f"run_id={RUN_ID}",
        f"output_prefix={uri.rsplit('/', 1)[0]}",
        f"science_protocol_sha256={SCIENCE_PROTOCOL_SHA256}",
        f"execution_protocol_sha256={EXECUTION_PROTOCOL_SHA256}",
        "kickoff_population_amendment_sha256="
        f"{KICKOFF_POPULATION_AMENDMENT_SHA256}",
        "kickoff_time_reconstruction_amendment_sha256="
        f"{KICKOFF_AMENDMENT_SHA256}",
        "cbwu_report_sha256=556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33",
        f"forensic_manifest_sha256={FORENSIC_MANIFEST_SHA256}",
        "cpu=4", "memory=16Gi", "timeout_seconds=14400", "max_retries=0",
        "uses_realized_outcomes=false", "production_change_licensed=false",
        "historical_scoring_licensed=false", "code_sha=" + "a" * 40,
        "image=example/image@sha256:" + "b" * 64,
    )) + "\n", encoding="utf-8")
    ledger = tmp_path / "executions.txt"
    ledger.write_text(
        f"2023 1 recourse-initial-s2023-w1-kickoff-v3 {execution} {uri}\n",
        encoding="utf-8",
    )
    execution_path = tmp_path / "execution.json"
    execution_path.write_text(
        json.dumps(_canary_metadata(execution)), encoding="utf-8",
    )
    shard_path = tmp_path / "shard.json"
    shard_path.write_text(json.dumps(_shard(2023, 1)), encoding="utf-8")
    object_path = tmp_path / "object.json"
    object_path.write_text(json.dumps({
        "generation": "123", "size": shard_path.stat().st_size,
    }), encoding="utf-8")
    result = validate_canary(
        manifest, ledger, execution_path, object_path, shard_path,
    )
    assert result["disposition"] == "actual-final-path-canary-passes"
    assert result["remaining_cells_released"] is False
    assert result["outcome_fields_inspected"] is False
    assert result["effect_fields_inspected"] is False


def test_cloud_transport_is_exact_canary_gated_and_zero_retry() -> None:
    launcher = (
        ROOT / "scripts/cloud_recourse_aware_initial_scorefree.sh"
    ).read_text(encoding="utf-8")
    waiter = (
        ROOT / "scripts/cloud_wait_recourse_aware_initial_canary.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_recourse_aware_initial_scorefree.sh"
    ).read_text(encoding="utf-8")
    assert launcher.index("\ndeploy_and_run 2023 1\n") < launcher.index(
        '\n"$CANARY_WAITER"\n'
    ) < launcher.index("\nfor SEASON in 2023 2024 2025")
    assert '--cpu 4 --memory 16Gi' in launcher
    assert '--max-retries 0 --task-timeout 4h' in launcher
    assert '"$(wc -l < "$EXECUTIONS")" = 54' in launcher
    assert "queue awaits ATLAS historical closure" in launcher
    assert "remaining_cells_released" in waiter
    assert 'gcloud storage cp "$URI"' in waiter
    assert 'retriedCount' in finisher
    assert 'RECOURSE_INITIAL_STRICT_AGGREGATE_VALIDATED' in finisher
    assert 'leave_one_slate_out_influence' in finisher


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
