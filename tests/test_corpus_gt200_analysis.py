from __future__ import annotations

from hashlib import sha256
from typing import Any

import numpy as np
import pytest

from nfl_dfs.research import corpus_retrieval_engine as engine
from nfl_dfs.research.corpus_gt200_analysis import (
    ANNOTATION_SCHEMA,
    CorpusGt200AnalysisError,
    build_gt200_analysis,
)


def _identity(uri: str, generation: int, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _placeholder(name: str, generation: int) -> dict[str, object]:
    return _identity(f"gs://fixture-authority/{name}", generation, f"body:{name}".encode())


def _hashed(body: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(body)
    result[field] = engine.canonical_sha256(result)
    return result


def _bundle(*, annotations: bool = True):
    generation = 100
    objects: dict[tuple[str, str], bytes] = {}

    def retain(name: str, value: object, *, raw: bytes | None = None):
        nonlocal generation
        body = engine.canonical_json_bytes(value) if raw is None else raw
        identity = _identity(f"gs://fixture-research/{name}", generation, body)
        generation += 1
        objects[(str(identity["uri"]), str(identity["generation"]))] = body
        return identity, body

    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    players = []
    for index in range(18):
        team = "A" if index < 5 else "B" if index < 9 else "C" if index < 14 else "D"
        opp = "B" if team == "A" else "A" if team == "B" else "D" if team == "C" else "C"
        game = "A|B" if team in {"A", "B"} else "C|D"
        players.append({
            "id": f"p{index:02d}", "name": f"Player {index}",
            "pos": positions[index % 9], "team": team, "opp": opp,
            "game_id": game, "salary": 3_000 + index * 100, "proj": 5.0 + index,
        })
    player_catalog = engine.build_player_catalog_object(
        task_id="slate-test-w1", source_authority=_placeholder("player-source", 1),
        players=players,
    )
    player_identity, _ = retain("inputs/player-catalog.json", player_catalog)

    world_blocks = []
    for ordinal, block in enumerate(engine.WORLD_BLOCKS):
        world_blocks.append({
            "ordinal": ordinal, "block_id": block, "panel_id": f"atlas-panel-{block.lower()}",
            "artifact_object": _placeholder(f"world-{block}.npz", 10 + ordinal),
            "format": engine.NPZ_FORMAT, "expected_candidate_count": 80,
            "expected_player_count": len(players), "expected_world_count": 10_000,
        })
    snapshot = engine.build_snapshot_manifest(
        snapshot_id="fixture-snapshot-v1", created_at_utc="2026-08-22T12:00:00Z",
        producer={
            "producer_id": "fixture", "producer_version": "v1",
            "producer_run_id": "fixture-run-v1",
            "producer_authority": _placeholder("producer", 2),
        },
        tasks=[{
            "task_index": 0, "task_id": "slate-test-w1",
            "slate": {"season": 2023, "week": 1, "slate_id": "test-main"},
            "candidate_rows_object": _placeholder("candidate-rows", 3),
            "player_catalog_object": player_identity, "world_blocks": world_blocks,
        }],
    )
    snapshot_identity, _ = retain("inputs/snapshot.json", snapshot)

    roster_indices = [list(range(9)), list(range(1, 10)), list(range(9, 18))]
    lineups = []
    for index, roster in enumerate(roster_indices):
        roster_players = [players[value] for value in roster]
        team_counts: dict[str, int] = {}
        game_counts: dict[str, int] = {}
        pos_counts: dict[str, int] = {}
        for player in roster_players:
            team_counts[player["team"]] = team_counts.get(player["team"], 0) + 1
            game_counts[player["game_id"]] = game_counts.get(player["game_id"], 0) + 1
            pos_counts[player["pos"]] = pos_counts.get(player["pos"], 0) + 1
        tag = ["boom", "lev", "dark"][index]
        lineups.append({
            "lineup_index": index, "lineup_id": f"lineup:{index}",
            "roster_player_ids": sorted(player["id"] for player in roster_players),
            "source_memberships": [{
                "block_id": ["R0", "R1", "R4"][index],
                "panel_id": f"atlas-panel-{index}", "cand_ix": index,
                "tag": tag, "all_tags": [tag],
            }],
            "tags": [tag],
            "features": {
                "salary": sum(player["salary"] for player in roster_players),
                "projection": sum(player["proj"] for player in roster_players),
                "positions": pos_counts, "teams": sorted(team_counts),
                "team_count": len(team_counts), "team_player_counts": team_counts,
                "games": sorted(game_counts), "game_count": len(game_counts),
                "game_player_counts": game_counts,
                "max_players_same_team": max(team_counts.values()),
                "max_players_same_game": max(game_counts.values()),
                "qb_stack_teammates": 2 if index == 0 else 1,
                "bring_back_players": 1 if index == 0 else 0,
            },
        })
    lineup_table = _hashed({
        "schema_version": engine.LINEUP_TABLE_SCHEMA, "task_id": "slate-test-w1",
        "lineup_count": 3, "roster_size": 9,
        "lineup_index_law": "canonical roster-player-id tuple ascending",
        "lineups": lineups,
    }, "lineup_table_sha256")
    lineup_identity, _ = retain("runs/task0/unique-lineups.json", lineup_table)

    event_raw, descriptors = engine.canonical_npz_bytes((
        ("lineup_index", np.asarray([0, 1, 0, 2], dtype=np.int32)),
        ("block_index", np.asarray([0, 0, 4, 4], dtype=np.uint8)),
        ("world_index", np.asarray([0, 0, 1, 2], dtype=np.int32)),
        ("score", np.asarray([210.0, 220.0, 205.0, 230.0], dtype=np.float32)),
    ))
    event_identity, _ = retain("runs/task0/strict-events.npz", {}, raw=event_raw)

    sidecars: list[dict[str, object]] = [
        {
            "role": "unique-lineups", "strategy_id": "", "format": "canonical-json-v1",
            "object_identity": lineup_identity,
            "semantic": {"schema_version": engine.LINEUP_TABLE_SCHEMA, "canonical_json_sha256": lineup_identity["sha256"]},
        },
        {
            "role": "strict-gt-200-events", "strategy_id": "", "format": "canonical-compressed-npz-v1",
            "object_identity": event_identity,
            "semantic": {"arrays": descriptors, "npz_sha256": event_identity["sha256"]},
        },
    ]
    strategy_results = []
    for ordinal, (strategy_id, selected) in enumerate((
        ("coverage", [0, 1]), ("mean", [1, 2]),
    )):
        selection = _hashed({
            "schema_version": engine.SELECTION_SCHEMA, "task_id": "slate-test-w1",
            "selected_lineup_indices": selected,
            "selected_lineup_ids": [f"lineup:{value}" for value in selected],
        }, "selection_sha256")
        selection_identity, _ = retain(f"runs/task0/{strategy_id}/selection.json", selection)
        sidecars.append({
            "role": "strategy-selection", "strategy_id": strategy_id,
            "format": "canonical-json-v1", "object_identity": selection_identity,
            "semantic": {"schema_version": engine.SELECTION_SCHEMA, "canonical_json_sha256": selection_identity["sha256"]},
        })
        strategy_results.append({
            "ordinal": ordinal, "strategy_id": strategy_id,
            "selected_lineup_indices": selected, "selection_object": selection_identity,
        })

    task_result = _hashed({
        "schema_version": engine.TASK_RESULT_SCHEMA, "task_id": "slate-test-w1",
        "snapshot_manifest_identity": snapshot_identity,
        "coverage": {
            "every_unique_lineup_scored_in_every_world": True,
            "unique_lineup_count": 3,
        },
        "licenses": {
            "analytics_authority": True,
            "historical_outcome_read_authority": False,
        },
        "primary_event_summary": {"event_count": 4},
        "sidecars": sidecars, "strategy_results": strategy_results,
    }, "task_result_sha256")
    task_identity, task_raw = retain("runs/task0/result.json", task_result)

    context = None
    if annotations:
        context = {
            "schema_version": ANNOTATION_SCHEMA, "task_id": "slate-test-w1",
            "world_law": {"family": "Atlas production-law panels"},
            "pit_vendor_annotations": [{"vendor": "fixture", "active_in_matrix": False}],
            "player_features": [
                {"player_id": "p03", "easy_coverage": True, "ownership_projection": 0.1}
            ],
            "game_features": [{"game_id": "A|B", "game_environment": "high"}],
            "world_features": [{"block_id": "R0", "world_index": 0, "seed": "seed-0"}],
        }

    def reader(identity: dict[str, object]) -> bytes:
        return objects[(str(identity["uri"]), str(identity["generation"]))]

    return task_raw, task_identity, reader, context, objects


def test_builds_partitioned_phenotypes_and_neo4j_projection() -> None:
    task_raw, task_identity, reader, context, _ = _bundle()
    result = build_gt200_analysis(
        task_result_raw=task_raw, task_result_identity=task_identity,
        read_object=reader, analysis_id="fixture-analysis-v1",
        created_at_utc="2026-08-22T13:00:00Z", context_annotations=context,
        max_association_rows=1_000, max_redundancy_rows=10, max_top_worlds=2,
    )

    assert result["summary"] == {
        "lineup_count": 3,
        "simulated_world_count": 50_000,
        "strict_gt_200_event_count": 4,
        "lineups_with_event": 3,
        "association_universe_count": result["summary"]["association_universe_count"],
        "association_retained_count": result["summary"]["association_retained_count"],
        "redundancy_pair_universe_count": 3,
        "redundancy_pair_retained_count": 3,
    }
    assert result["evidence"]["full_score_matrix_read"] is False
    assert result["outcome_semantics"]["realized_contest_outcomes_read"] is False
    assert result["phenotype_preset"]["retrieval_filter_ranker_view"]["forbidden_inputs"] == [
        "R4 evaluation", "realized outcomes"
    ]
    assert result["availability"]["easy_coverage"]["available"] is True
    assert result["simulated_gt200_events"][0]["seed"] == "seed-0"
    assert len(result["simulated_gt200_events"]) == 4
    assert any("easy_coverage=True" in row["phenotype_tokens"] for row in result["lineups"])

    player_pair = next(row for row in result["associations"] if row["category"] == "player-pair" and row["key"] == "p01|p02")
    assert player_pair["scopes"]["discovery-r0-r3"]["reference_lineup_count"] == 2
    assert player_pair["scopes"]["discovery-r0-r3"]["strict_gt_200_event_count"] == 2
    assert player_pair["scopes"]["evaluation-r4"]["strict_gt_200_event_count"] == 1
    assert player_pair["selector_membership"]["coverage"]["selected_support_lineup_count"] == 2
    assert result["neo4j_projection"]["node_count"] == len(result["neo4j_projection"]["nodes"])
    assert sum(edge["type"] == "SIMULATED_GT200_IN" for edge in result["neo4j_projection"]["edges"]) == 4
    replay = dict(result)
    retained = replay.pop("analysis_sha256")
    assert retained == engine.canonical_sha256(replay)


def test_absent_optional_features_are_diagnostic_not_fabricated() -> None:
    task_raw, task_identity, reader, _, _ = _bundle(annotations=False)
    result = build_gt200_analysis(
        task_result_raw=task_raw, task_result_identity=task_identity,
        read_object=reader, analysis_id="fixture-analysis-v2",
        created_at_utc="2026-08-22T13:00:00Z",
        max_association_rows=100, max_redundancy_rows=3, max_top_worlds=1,
    )
    assert result["availability"]["easy_coverage"]["available"] is False
    assert result["availability"]["ownership_projection"]["available"] is False
    assert result["availability"]["realized_contest_outcomes"]["available"] is False
    assert all(row["optional_features"]["easy_coverage_player_count"] is None for row in result["lineups"])
    assert result["world_provenance"]["declared_context_annotations"] == {}


def test_rejects_task_result_identity_drift() -> None:
    task_raw, task_identity, reader, context, _ = _bundle()
    drifted = dict(task_identity)
    drifted["sha256"] = "0" * 64
    with pytest.raises(CorpusGt200AnalysisError, match="task result content identity differs"):
        build_gt200_analysis(
            task_result_raw=task_raw, task_result_identity=drifted,
            read_object=reader, analysis_id="fixture-analysis-v3",
            created_at_utc="2026-08-22T13:00:00Z", context_annotations=context,
        )
