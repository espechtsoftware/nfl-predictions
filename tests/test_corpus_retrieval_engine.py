from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from itertools import combinations
import math
from typing import Any

import numpy as np
import pytest

from nfl_dfs.research import corpus_retrieval_engine as retrieval


class MemoryObjects:
    def __init__(self) -> None:
        self._raw: dict[tuple[str, str], bytes] = {}
        self._latest: dict[str, int] = {}

    def add(self, uri: str, raw: bytes) -> dict[str, object]:
        generation = self._latest.get(uri, 0) + 1
        self._latest[uri] = generation
        self._raw[(uri, str(generation))] = raw
        return retrieval.object_identity_for_bytes(
            uri=uri, generation=str(generation), raw=raw
        )

    def read(self, identity: dict[str, object]) -> bytes:
        return self._raw[(str(identity["uri"]), str(identity["generation"]))]

    def publish(self, uri: str, raw: bytes, media_type: str) -> dict[str, object]:
        assert media_type in {"application/json", "application/octet-stream"}
        if uri in self._latest:
            retained = self._raw[(uri, str(self._latest[uri]))]
            if retained != raw:
                raise RuntimeError("create-once collision")
            return retrieval.object_identity_for_bytes(
                uri=uri, generation=str(self._latest[uri]), raw=retained
            )
        return self.add(uri, raw)


def _source_npz(
    player_ids: np.ndarray,
    player_draws: np.ndarray,
    rosters: list[tuple[str, ...]],
) -> bytes:
    by_id = {str(value): index for index, value in enumerate(player_ids)}
    totals = np.stack([
        player_draws[[by_id[player_id] for player_id in roster]].sum(
            axis=0, dtype=np.float32
        )
        for roster in rosters
    ]).astype(np.float32)
    buffer = BytesIO()
    np.savez_compressed(
        buffer,
        cand_ix=np.arange(len(rosters), dtype=np.int32),
        totals=totals,
        tail_line=np.asarray(194.0, dtype=np.float32),
        player_ids=player_ids,
        player_draws=player_draws,
    )
    return buffer.getvalue()


def _query_receipt(
    *, job_id: str, sql_sha256: str, row_count: int, rows_sha256: str,
    normalized_rows_sha256: str,
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "project": "fixture-project",
        "location": "US",
        "sql_sha256": sql_sha256,
        "snapshot_at_utc": "2026-08-21T12:00:00Z",
        "created": "2026-08-21T12:00:01+00:00",
        "started": "2026-08-21T12:00:02+00:00",
        "ended": "2026-08-21T12:00:03+00:00",
        "total_bytes_processed": 1,
        "cache_hit": False,
        "error_result": None,
        "row_count": row_count,
        "rows_sha256": rows_sha256,
        "normalized_rows_sha256": normalized_rows_sha256,
    }


@pytest.fixture(scope="module")
def completed_run() -> dict[str, Any]:
    store = MemoryObjects()
    player_ids = np.asarray([f"p{index:02d}" for index in range(18)])
    players = [{
        "id": player_id,
        "name": f"Player {index}",
        "pos": "QB" if index == 0 else (
            "RB" if index < 5 else "WR" if index < 13 else "TE"
        ),
        "team": f"T{index % 6}",
        "opp": f"T{(index % 6 + 1) % 6}",
        "game_id": f"G{index % 3}",
        "salary": 4_000 + index * 100,
        "proj": 10.0 + index / 10,
    } for index, player_id in enumerate(player_ids.tolist())]
    roster_universe = [
        tuple(player_ids[list(indices)].tolist())
        for indices in list(combinations(range(len(player_ids)), 9))[:90]
    ]
    candidate_rows: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []
    rng = np.random.default_rng(20_260_821)
    for ordinal, block_id in enumerate(retrieval.WORLD_BLOCKS):
        panel_id = f"panel-r{ordinal}"
        rosters = [roster_universe[ordinal * 2 + index] for index in range(80)]
        draws = rng.normal(15.0 + ordinal / 10, 8.0, size=(18, 10_000)).astype(
            np.float32
        )
        raw = _source_npz(player_ids, draws, rosters)
        artifact_identity = store.add(
            f"gs://fixture/source/{block_id}.npz", raw
        )
        blocks.append({
            "ordinal": ordinal,
            "block_id": block_id,
            "panel_id": panel_id,
            "artifact_object": artifact_identity,
            "format": retrieval.NPZ_FORMAT,
            "expected_candidate_count": 80,
            "expected_player_count": 18,
            "expected_world_count": 10_000,
        })
        for cand_ix, roster in enumerate(rosters):
            candidate_rows.append({
                "panel_id": panel_id,
                "season": 2023,
                "week": 1,
                "cand_ix": cand_ix,
                "tag": "boom" if cand_ix % 2 else "lev",
                "all_tags": ["boom" if cand_ix % 2 else "lev", block_id.lower()],
                "players": list(roster),
            })
    normalized_candidate_rows = retrieval.normalize_candidate_query_rows(
        candidate_rows
    )
    normalized_player_rows = retrieval.normalize_player_query_rows(players)
    candidate_query = _query_receipt(
        job_id="fixture-candidate-query",
        sql_sha256="c" * 64,
        row_count=len(normalized_candidate_rows),
        rows_sha256=retrieval.canonical_sha256(candidate_rows),
        normalized_rows_sha256=retrieval.canonical_sha256(
            normalized_candidate_rows
        ),
    )
    player_query = _query_receipt(
        job_id="fixture-player-query",
        sql_sha256="e" * 64,
        row_count=len(normalized_player_rows),
        rows_sha256=retrieval.canonical_sha256(players),
        normalized_rows_sha256=retrieval.canonical_sha256(
            normalized_player_rows
        ),
    )
    query_authority = retrieval.build_input_query_authority(
        task_id="slate-2023-w1",
        snapshot_at_utc="2026-08-21T12:00:00Z",
        candidate_query=candidate_query,
        player_query=player_query,
    )
    source_authority = store.add(
        "gs://fixture/source/source-authority.json",
        retrieval.canonical_json_bytes(query_authority),
    )
    producer_authority = store.add(
        "gs://fixture/source/producer-authority.json", b'{"producer":"fixture"}'
    )
    player_body = retrieval.build_player_catalog_object(
        task_id="slate-2023-w1",
        source_authority=source_authority,
        players=normalized_player_rows,
    )
    player_identity = store.add(
        "gs://fixture/snapshots/players.json",
        retrieval.canonical_json_bytes(player_body),
    )
    candidate_body = retrieval.build_candidate_rows_object(
        task_id="slate-2023-w1",
        source_authority=source_authority,
        source_sql_sha256="c" * 64,
        source_query_receipt=candidate_query,
        rows=normalized_candidate_rows,
    )
    candidate_identity = store.add(
        "gs://fixture/snapshots/candidates.json",
        retrieval.canonical_json_bytes(candidate_body),
    )
    snapshot = retrieval.build_snapshot_manifest(
        snapshot_id="fixture-current-money-2023-w1-v1",
        created_at_utc="2026-08-21T12:30:00Z",
        producer={
            "producer_id": "fixture-producer",
            "producer_version": "fixture-v1",
            "producer_run_id": "fixture-producer-run-v1",
            "producer_authority": producer_authority,
        },
        tasks=[{
            "task_index": 0,
            "task_id": "slate-2023-w1",
            "slate": {"season": 2023, "week": 1, "slate_id": "main-2023-w1"},
            "candidate_rows_object": candidate_identity,
            "player_catalog_object": player_identity,
            "world_blocks": blocks,
        }],
    )
    snapshot_identity = store.add(
        "gs://fixture/snapshots/snapshot.json",
        retrieval.canonical_json_bytes(snapshot),
    )
    image_digest = f"sha256:{'a' * 64}"
    suite = retrieval.build_suite_manifest(
        run_id="fixture-retrieval-v1",
        created_at_utc="2026-08-21T12:31:00Z",
        output_prefix="gs://fixture/research/fixture-retrieval-v1/",
        snapshot_manifest=snapshot,
        snapshot_manifest_identity=snapshot_identity,
        entry_budget=80,
        engine_release={
            "engine_version": "corpus-retrieval-engine-v1",
            "code_repository": "fixture/repository",
            "code_commit": "b" * 40,
            "image_uri": f"registry.example/fixture@{image_digest}",
            "image_digest": image_digest,
        },
        strategies=retrieval.frozen_retrieval_strategies(80),
    )
    suite_identity = store.add(
        str(suite["suite_manifest_uri"]), retrieval.canonical_json_bytes(suite)
    )
    published = retrieval.run_retrieval_task(
        suite_manifest=suite,
        suite_manifest_identity=suite_identity,
        snapshot_manifest=snapshot,
        snapshot_manifest_identity=snapshot_identity,
        task_index=0,
        execution={
            "execution_id": "fixture-execution",
            "execution_name": "fixture-execution",
            "task_index": 0,
            "attempt": 0,
            "retry_count": 0,
            "mode": "local-real-smoke",
            "code_commit": "b" * 40,
            "image_uri": f"registry.example/fixture@{image_digest}",
            "image_digest": image_digest,
        },
        read_object=store.read,
        publish_create_once=store.publish,
    )
    return {
        "store": store,
        "snapshot": snapshot,
        "snapshot_identity": snapshot_identity,
        "suite": suite,
        "suite_identity": suite_identity,
        "published": published,
        "source_authority": source_authority,
        "player_body": player_body,
    }


def test_manifest_and_transport_binding(completed_run: dict[str, Any]) -> None:
    suite = retrieval.validate_suite_manifest(completed_run["suite"])
    binding = retrieval.task_transport_binding(suite, 0)
    assert binding == {
        "output_prefix": "gs://fixture/research/fixture-retrieval-v1/",
        "snapshot_manifest_identity": completed_run["snapshot_identity"],
        "task_index": 0,
        "task_id": "slate-2023-w1",
        "result_uri": (
            "gs://fixture/research/fixture-retrieval-v1/tasks/0000/result.json"
        ),
    }


def test_task_result_has_complete_equal_budget_score_coverage(
    completed_run: dict[str, Any],
) -> None:
    authority = completed_run["published"]["authority"]
    assert authority["coverage"]["source_candidate_rows"] == 400
    assert authority["coverage"]["unique_lineup_count"] == 88
    assert authority["coverage"]["discovery_eligible_lineup_count"] == 86
    assert authority["coverage"]["heldout_only_lineup_count"] == 2
    assert authority["coverage"]["world_count"] == 50_000
    assert authority["coverage"]["lineup_world_score_count"] == 4_400_000
    assert authority["coverage"]["every_unique_lineup_scored_in_every_world"] is True
    assert [row["entry_budget"] for row in authority["strategy_results"]] == [80] * 4
    assert all(len(row["selected_lineup_indices"]) == 80 for row in authority["strategy_results"])
    assert authority["licenses"]["corpus_fill_authority"] is False
    assert authority["licenses"]["live_money_policy_authority"] is False
    roles = [row["role"] for row in authority["sidecars"]]
    assert "enrichment-discovery" in roles
    assert "enrichment-all-worlds" in roles
    discovery = retrieval.parse_canonical_json_bytes(
        completed_run["store"].read(next(
            row["object_identity"]
            for row in authority["sidecars"]
            if row["role"] == "enrichment-discovery"
        )),
        label="discovery enrichment",
    )
    fill = retrieval.parse_canonical_json_bytes(
        completed_run["store"].read(authority["fill_insight_object"]),
        label="fill insight",
    )
    assert discovery["world_blocks"] == ["R0", "R1", "R2", "R3"]
    assert discovery["lineup_count"] == 86
    assert discovery["heldout_worlds_used"] is False
    assert fill["source_enrichment_sha256"] == discovery["enrichment_sha256"]
    assert fill["source_enrichment_object"] == next(
        row["object_identity"]
        for row in authority["sidecars"]
        if row["role"] == "enrichment-discovery"
    )
    assert "r4" not in {row["tag"] for row in discovery["tags"]}


def test_primary_event_is_strict_and_bound_to_full_matrix(
    completed_run: dict[str, Any],
) -> None:
    authority = completed_run["published"]["authority"]
    summary = authority["primary_event_summary"]
    assert summary["operator"] == ">"
    assert summary["threshold"] == 200.0
    assert sum(summary["event_count_by_block"]) == summary["event_count"]
    assert summary["lineup_world_count"] == 88 * 50_000
    assert summary["lineup_world_event_rate"] == pytest.approx(
        summary["event_count"] / (88 * 50_000)
    )


def test_full_replay_and_completion(completed_run: dict[str, Any]) -> None:
    authority = retrieval.validate_retrieval_task_result(
        published_result=completed_run["published"],
        suite_manifest=completed_run["suite"],
        suite_manifest_identity=completed_run["suite_identity"],
        snapshot_manifest=completed_run["snapshot"],
        snapshot_manifest_identity=completed_run["snapshot_identity"],
        read_object=completed_run["store"].read,
        replay=True,
    )
    assert authority["task_result_sha256"]
    completion = retrieval.build_retrieval_batch_completion(
        suite_manifest=completed_run["suite"],
        suite_manifest_identity=completed_run["suite_identity"],
        snapshot_manifest=completed_run["snapshot"],
        snapshot_manifest_identity=completed_run["snapshot_identity"],
        published_results=[completed_run["published"]],
        read_object=completed_run["store"].read,
    )
    validated = retrieval.validate_retrieval_batch_completion(
        completion,
        suite_manifest=completed_run["suite"],
        suite_manifest_identity=completed_run["suite_identity"],
        snapshot_manifest=completed_run["snapshot"],
        snapshot_manifest_identity=completed_run["snapshot_identity"],
        published_results=[completed_run["published"]],
        read_object=completed_run["store"].read,
    )
    assert validated["coverage"] == {
        "task_count": 1,
        "strategy_count": 4,
        "task_strategy_cell_count": 4,
        "all_tasks_complete": True,
        "all_strategies_equal_budget": True,
    }
    assert validated["licenses"]["analytical_graph_projection_ready"] is True
    assert validated["licenses"]["production_default_change_authority"] is False


def test_heldout_block_cannot_change_selection() -> None:
    rng = np.random.default_rng(7)
    scores = rng.normal(size=(82, 50_000)).astype(np.float32)
    # Global index 1 represents an R4-only candidate interleaved in canonical
    # roster order.  Even an overwhelming discovery score cannot admit it.
    scores[1, :40_000] = np.float32(10_000.0)
    discovery_indices = [0, *range(2, 82)]
    ids = [f"lineup:{index:064x}" for index in range(82)]
    strategy = retrieval.frozen_retrieval_strategies(80)[3]
    first, first_trace = retrieval._run_discovery_strategy(
        strategy,
        full_scores=scores,
        discovery_indices=discovery_indices,
        lineup_ids=ids,
    )
    altered = scores.copy()
    altered[:, 40_000:] *= np.float32(-1_000.0)
    second, second_trace = retrieval._run_discovery_strategy(
        strategy,
        full_scores=altered,
        discovery_indices=discovery_indices,
        lineup_ids=ids,
    )
    assert first == second
    assert first_trace == second_trace
    assert 1 not in first
    assert [row["lineup_index"] for row in first_trace] == first
    assert [row["lineup_id"] for row in first_trace] == [ids[index] for index in first]


def test_heldout_block_cannot_change_fill_insight(
    completed_run: dict[str, Any],
) -> None:
    authority = completed_run["published"]["authority"]
    sidecars = {row["role"]: row for row in authority["sidecars"]}
    lineup_body = retrieval.parse_canonical_json_bytes(
        completed_run["store"].read(
            sidecars["unique-lineups"]["object_identity"]
        ),
        label="fixture lineups",
    )
    matrix_raw = completed_run["store"].read(
        sidecars["unique-lineup-scores"]["object_identity"]
    )
    with np.load(BytesIO(matrix_raw), allow_pickle=False) as archive:
        scores = np.asarray(archive["scores"]).copy()
    lineups = lineup_body["lineups"]
    discovery_indices, discovery_lineups = retrieval._discovery_lineup_view(
        lineups
    )
    discovery_stop = len(retrieval.DISCOVERY_BLOCKS) * retrieval.WORLDS_PER_BLOCK
    first_discovery = retrieval._build_enrichment(
        lineup_rows=discovery_lineups,
        scores=scores[discovery_indices, :discovery_stop],
        analysis_scope="discovery-r0-r3",
        world_blocks=retrieval.DISCOVERY_BLOCKS,
    )
    altered = scores.copy()
    altered[:, discovery_stop:] += np.float32(1_000.0)
    second_discovery = retrieval._build_enrichment(
        lineup_rows=discovery_lineups,
        scores=altered[discovery_indices, :discovery_stop],
        analysis_scope="discovery-r0-r3",
        world_blocks=retrieval.DISCOVERY_BLOCKS,
    )
    discovery_identity = retrieval.object_identity_for_bytes(
        uri="gs://fixture/discovery-enrichment.json",
        generation="1",
        raw=retrieval.canonical_json_bytes(first_discovery),
    )
    first_fill = retrieval._build_fill_insight(
        enrichment=first_discovery,
        source_enrichment_object=discovery_identity,
        task_id="slate-2023-w1",
    )
    second_fill = retrieval._build_fill_insight(
        enrichment=second_discovery,
        source_enrichment_object=discovery_identity,
        task_id="slate-2023-w1",
    )
    assert retrieval.canonical_json_bytes(first_fill) == retrieval.canonical_json_bytes(
        second_fill
    )
    first_full = retrieval._build_enrichment(
        lineup_rows=lineups,
        scores=scores,
        analysis_scope="all-r0-r4-descriptive",
        world_blocks=retrieval.WORLD_BLOCKS,
    )
    second_full = retrieval._build_enrichment(
        lineup_rows=lineups,
        scores=altered,
        analysis_scope="all-r0-r4-descriptive",
        world_blocks=retrieval.WORLD_BLOCKS,
    )
    assert first_full["enrichment_sha256"] != second_full["enrichment_sha256"]


def test_r4_only_candidate_identities_cannot_be_selected_or_feed_fill(
    completed_run: dict[str, Any],
) -> None:
    authority = completed_run["published"]["authority"]
    sidecars = {row["role"]: row for row in authority["sidecars"]}
    lineup_body = retrieval.parse_canonical_json_bytes(
        completed_run["store"].read(
            sidecars["unique-lineups"]["object_identity"]
        ),
        label="fixture lineups",
    )
    lineups = lineup_body["lineups"]
    discovery_indices, discovery_rows = retrieval._discovery_lineup_view(lineups)
    heldout_only = set(range(len(lineups))) - set(discovery_indices)
    assert heldout_only == {86, 87}
    assert "r4" not in {tag for row in discovery_rows for tag in row["tags"]}
    for result in authority["strategy_results"]:
        assert heldout_only.isdisjoint(result["selected_lineup_indices"])
    discovery = retrieval.parse_canonical_json_bytes(
        completed_run["store"].read(
            sidecars["enrichment-discovery"]["object_identity"]
        ),
        label="discovery enrichment",
    )
    full = retrieval.parse_canonical_json_bytes(
        completed_run["store"].read(
            sidecars["enrichment-all-worlds"]["object_identity"]
        ),
        label="full enrichment",
    )
    assert discovery["lineup_count"] == len(discovery_indices)
    assert "r4" not in {row["tag"] for row in discovery["tags"]}
    assert "r4" in {row["tag"] for row in full["tags"]}


def test_semantically_corrupt_graph_is_rejected(
    completed_run: dict[str, Any],
) -> None:
    store = completed_run["store"]
    authority = deepcopy(completed_run["published"]["authority"])
    graph_sidecar = next(
        row for row in authority["sidecars"] if row["role"] == "graph-projection"
    )
    graph = retrieval.parse_canonical_json_bytes(
        store.read(graph_sidecar["object_identity"]), label="fixture graph"
    )
    task_node = next(
        row for row in graph["nodes"] if row["kind"] == "RetrievalTask"
    )
    task_node["properties"]["heldout_content_is_descriptive_only"] = False
    graph_without_hash = {
        key: value
        for key, value in graph.items()
        if key != "graph_projection_sha256"
    }
    graph["graph_projection_sha256"] = retrieval.canonical_sha256(
        graph_without_hash
    )
    graph_identity = store.add(
        str(graph_sidecar["object_identity"]["uri"]),
        retrieval.canonical_json_bytes(graph),
    )
    graph_sidecar["object_identity"] = graph_identity
    graph_sidecar["semantic"]["canonical_json_sha256"] = graph_identity["sha256"]
    authority["graph_projection_object"] = graph_identity
    authority_without_hash = {
        key: value for key, value in authority.items() if key != "task_result_sha256"
    }
    authority["task_result_sha256"] = retrieval.canonical_sha256(
        authority_without_hash
    )
    result_identity = store.add(
        str(completed_run["published"]["object_identity"]["uri"]),
        retrieval.canonical_json_bytes(authority),
    )
    with pytest.raises(
        retrieval.CorpusRetrievalError,
        match="analytics or graph semantic replay differs",
    ):
        retrieval.validate_retrieval_task_result(
            published_result={
                "authority": authority,
                "object_identity": result_identity,
            },
            suite_manifest=completed_run["suite"],
            suite_manifest_identity=completed_run["suite_identity"],
            snapshot_manifest=completed_run["snapshot"],
            snapshot_manifest_identity=completed_run["snapshot_identity"],
            read_object=store.read,
            replay=False,
        )


def test_strategy_registry_and_attempt_fail_closed(
    completed_run: dict[str, Any],
) -> None:
    suite = deepcopy(completed_run["suite"])
    suite["strategies"][1]["parameters"]["operator"] = ">="
    suite_body = {key: value for key, value in suite.items() if key != "suite_manifest_sha256"}
    suite["suite_manifest_sha256"] = retrieval.canonical_sha256(suite_body)
    with pytest.raises(retrieval.CorpusRetrievalError, match="differs from registry"):
        retrieval.validate_suite_manifest(suite)

    valid_suite = completed_run["suite"]
    execution = dict(completed_run["published"]["authority"]["execution"])
    execution["attempt"] = 1
    with pytest.raises(retrieval.CorpusRetrievalError, match="attempt=0"):
        retrieval._normalize_execution(execution, suite=valid_suite, task_index=0)


@pytest.mark.parametrize("budget", [79, 81])
def test_v1_rejects_non_exact_80_budget(budget: int) -> None:
    with pytest.raises(retrieval.CorpusRetrievalError, match="exact-80"):
        retrieval.frozen_retrieval_strategies(budget)


def test_candidate_source_rejects_outcome_fields() -> None:
    with pytest.raises(retrieval.CorpusRetrievalError, match="score-free schema"):
        retrieval.build_candidate_rows_object(
            task_id="slate-2023-w1",
            source_authority=retrieval.object_identity_for_bytes(
                uri="gs://fixture/source/query-authority.json",
                generation="1",
                raw=b"{}",
            ),
            source_sql_sha256="d" * 64,
            source_query_receipt={"job_id": "bad"},
            rows=[{
                "panel_id": "panel-r0",
                "season": 2023,
                "week": 1,
                "cand_ix": 0,
                "tag": "boom",
                "all_tags": ["boom"],
                "players": [f"p{index}" for index in range(9)],
                "actual_score": 250.0,
            }],
        )


def test_candidate_source_rejects_same_count_normalized_row_substitution() -> None:
    rows = [{
        "panel_id": "panel-r0",
        "season": 2023,
        "week": 1,
        "cand_ix": 0,
        "tag": "boom",
        "all_tags": ["boom"],
        "players": [f"p{index}" for index in range(9)],
    }]
    receipt = _query_receipt(
        job_id="candidate-query",
        sql_sha256="a" * 64,
        row_count=1,
        rows_sha256="b" * 64,
        normalized_rows_sha256=retrieval.canonical_sha256(
            retrieval.normalize_candidate_query_rows(rows)
        ),
    )
    substituted = deepcopy(rows)
    substituted[0]["tag"] = "lev"
    substituted[0]["all_tags"] = ["lev"]
    with pytest.raises(retrieval.CorpusRetrievalError, match="query receipt"):
        retrieval.build_candidate_rows_object(
            task_id="slate-2023-w1",
            source_authority=retrieval.object_identity_for_bytes(
                uri="gs://fixture/source/query-authority.json",
                generation="1",
                raw=b"{}",
            ),
            source_sql_sha256="a" * 64,
            source_query_receipt=receipt,
            rows=substituted,
        )


def test_task_source_rejects_same_count_player_substitution(
    completed_run: dict[str, Any],
) -> None:
    store: MemoryObjects = completed_run["store"]
    mutated_players = deepcopy(completed_run["player_body"]["players"])
    mutated_players[0]["name"] = "Substituted Player"
    mutated_player_body = retrieval.build_player_catalog_object(
        task_id="slate-2023-w1",
        source_authority=completed_run["source_authority"],
        players=mutated_players,
    )
    mutated_player_identity = store.add(
        "gs://fixture/snapshots/substituted-players.json",
        retrieval.canonical_json_bytes(mutated_player_body),
    )
    task = deepcopy(completed_run["snapshot"]["tasks"][0])
    task.pop("task_sha256")
    task["player_catalog_object"] = mutated_player_identity
    mutated_snapshot = retrieval.build_snapshot_manifest(
        snapshot_id="fixture-player-substitution-v1",
        created_at_utc="2026-08-21T13:00:00Z",
        producer=completed_run["snapshot"]["producer"],
        tasks=[task],
    )
    with pytest.raises(
        retrieval.CorpusRetrievalError,
        match="candidate/player query authority differs",
    ):
        retrieval._prepare_task_sources(  # noqa: SLF001
            snapshot=mutated_snapshot,
            task_index=0,
            reader=store.read,
        )


def test_query_authority_rejects_realized_outcome_license() -> None:
    candidate = _query_receipt(
        job_id="candidate-query",
        sql_sha256="a" * 64,
        row_count=1,
        rows_sha256="b" * 64,
        normalized_rows_sha256="c" * 64,
    )
    player = _query_receipt(
        job_id="player-query",
        sql_sha256="c" * 64,
        row_count=1,
        rows_sha256="d" * 64,
        normalized_rows_sha256="e" * 64,
    )
    authority = retrieval.build_input_query_authority(
        task_id="slate-2023-w1",
        snapshot_at_utc="2026-08-21T12:00:00Z",
        candidate_query=candidate,
        player_query=player,
    )
    authority["uses_realized_outcomes"] = True
    body = {
        key: value
        for key, value in authority.items()
        if key != "query_authority_sha256"
    }
    authority["query_authority_sha256"] = retrieval.canonical_sha256(body)
    with pytest.raises(retrieval.CorpusRetrievalError, match="outcome policy"):
        retrieval.validate_input_query_authority(authority)


def test_npz_writer_is_deterministic() -> None:
    arrays = [
        ("lineup_index", np.arange(3, dtype=np.int32)),
        ("scores", np.arange(12, dtype=np.float32).reshape(3, 4)),
    ]
    first, first_semantic = retrieval.canonical_npz_bytes(arrays)
    second, second_semantic = retrieval.canonical_npz_bytes(arrays)
    assert first == second
    assert first_semantic == second_semantic


def test_redundancy_flags_exact_duplicate_score_vectors() -> None:
    lineup_rows = [{
        "lineup_id": f"lineup:{index:064x}",
        "roster_player_ids": [f"p{index}-{slot}" for slot in range(9)],
    } for index in range(3)]
    first = np.linspace(150.0, 250.0, 50_000, dtype=np.float32)
    scores = np.stack([first, first.copy(), first + np.float32(1.0)])
    redundancy = retrieval._build_redundancy(
        lineup_rows=lineup_rows, scores=scores
    )
    assert redundancy["correlation_scope"] == "retained-high-overlap-pairs-only"
    assert redundancy["exact_duplicate_score_vector_groups"] == [{
        "score_vector_sha256": sha256(
            np.ascontiguousarray(first, dtype="<f4").tobytes(order="C")
        ).hexdigest(),
        "lineup_indices": [0, 1],
        "lineup_ids": [lineup_rows[0]["lineup_id"], lineup_rows[1]["lineup_id"]],
    }]
    exact_pair = next(
        row for row in redundancy["pairs"]
        if {row["left_lineup_index"], row["right_lineup_index"]} == {0, 1}
    )
    assert exact_pair["exact_score_vector_duplicate"] is True


def test_redundancy_replay_allows_only_cross_blas_last_bit_drift() -> None:
    lineup_rows = [{
        "lineup_id": f"lineup:{index:064x}",
        "roster_player_ids": [f"p{index}-{slot}" for slot in range(9)],
    } for index in range(3)]
    first = np.linspace(150.0, 250.0, 50_000, dtype=np.float32)
    scores = np.stack([
        first,
        first + np.sin(np.arange(50_000, dtype=np.float32)),
        first + np.cos(np.arange(50_000, dtype=np.float32)),
    ])
    rebuilt = retrieval._build_redundancy(
        lineup_rows=lineup_rows, scores=scores
    )
    published = deepcopy(rebuilt)
    correlation = published["pairs"][0]["pearson_score_correlation"]
    published["pairs"][0]["pearson_score_correlation"] = math.nextafter(
        correlation, -math.inf
    )
    published["redundancy_sha256"] = retrieval.canonical_sha256({
        key: value for key, value in published.items()
        if key != "redundancy_sha256"
    })
    assert retrieval._redundancy_semantic_replay_equal(published, rebuilt) is True

    excessive = deepcopy(published)
    excessive["pairs"][0]["pearson_score_correlation"] = correlation - 1e-12
    excessive["redundancy_sha256"] = retrieval.canonical_sha256({
        key: value for key, value in excessive.items()
        if key != "redundancy_sha256"
    })
    assert retrieval._redundancy_semantic_replay_equal(excessive, rebuilt) is False

    structurally_changed = deepcopy(published)
    structurally_changed["pairs"][0]["strict_gt_200_event_union"] += 1
    structurally_changed["redundancy_sha256"] = retrieval.canonical_sha256({
        key: value for key, value in structurally_changed.items()
        if key != "redundancy_sha256"
    })
    assert (
        retrieval._redundancy_semantic_replay_equal(
            structurally_changed, rebuilt
        )
        is False
    )


def _block_scores(rows: int) -> np.ndarray:
    width = len(retrieval.DISCOVERY_BLOCKS) * retrieval.WORLDS_PER_BLOCK
    return np.zeros((rows, width), dtype=np.float32)


def test_v2_registry_extends_v1_byte_identically() -> None:
    v1 = retrieval.frozen_retrieval_strategies(80)
    v2 = retrieval.frozen_retrieval_strategies_v2(80)
    assert len(v1) == 4 and len(v2) == 7
    for ordinal, (old, new) in enumerate(zip(v1, v2[:4], strict=True)):
        assert retrieval.canonical_json_bytes(old) == (
            retrieval.canonical_json_bytes(new)
        )
        assert new["ordinal"] == ordinal
    assert [row["strategy_id"] for row in v2[4:]] == [
        "expected-max-v1",
        "block-supported-tail-ladder-v1",
        "regime-robust-ladder-v1",
    ]
    for ordinal, row in enumerate(v2):
        validated = retrieval.validate_retrieval_strategy_v2(
            row, expected_ordinal=ordinal, entry_budget=80
        )
        assert validated["ordinal"] == ordinal
    with pytest.raises(retrieval.CorpusRetrievalError, match="exactly four"):
        retrieval.validate_retrieval_strategy(
            v2[4], expected_ordinal=4, entry_budget=80
        )
    tampered = deepcopy(v2[5])
    tampered["parameters"]["support_scaling"] = "raw"
    with pytest.raises(retrieval.CorpusRetrievalError, match="differs"):
        retrieval.validate_retrieval_strategy_v2(
            tampered, expected_ordinal=5, entry_budget=80
        )
    with pytest.raises(retrieval.CorpusRetrievalError, match="exact-80"):
        retrieval.frozen_retrieval_strategies_v2(40)


def test_expected_max_greedy_prefers_complementary_worlds() -> None:
    scores = _block_scores(3)
    half = scores.shape[1] // 2
    scores[0, :half] = np.float32(100.0)
    scores[1, half:] = np.float32(100.0)
    scores[2, :] = np.float32(90.0)
    ids = [f"lineup:{index:064x}" for index in range(3)]
    selected, trace = retrieval._select_expected_max(
        scores, budget=2, lineup_ids=ids
    )
    # Highest mean first; then either complement adds exactly +5 expected
    # points, and the ascending-lineup-id law resolves the exact tie.
    assert selected == [2, 0]
    assert trace[0]["marginal_utility"] == pytest.approx(90.0)
    assert trace[1]["marginal_utility"] == pytest.approx(5.0)
    again, again_trace = retrieval._select_expected_max(
        scores, budget=2, lineup_ids=ids
    )
    assert again == selected and again_trace == trace
    full, full_trace = retrieval._select_expected_max(
        scores, budget=3, lineup_ids=ids
    )
    assert full == [2, 0, 1]
    assert full_trace[2]["marginal_utility"] == pytest.approx(5.0)
    book_max = scores[full].max(axis=0).astype(np.float64).mean()
    assert book_max == pytest.approx(90.0 + 5.0 + 5.0)


def test_block_supported_ladder_discounts_one_block_wonders() -> None:
    per_block = retrieval.WORLDS_PER_BLOCK
    scores = _block_scores(2)
    # Concentrated: 500 strict >200 worlds, all inside block R0, disjoint
    # from the spread lineup's worlds.
    scores[0, 1_000:1_500] = np.float32(201.0)
    # Spread: 400 strict >200 worlds, 100 in every discovery block.
    for block in range(4):
        scores[1, block * per_block:block * per_block + 100] = np.float32(201.0)
    ids = [f"lineup:{index:064x}" for index in range(2)]
    rungs = [{"threshold": 200.0, "operator": ">", "weight": 1}]
    plain, _ = retrieval._select_ladder(
        scores, budget=2, rungs=rungs, lineup_ids=ids
    )
    supported, trace = retrieval._select_block_supported_ladder(
        scores, budget=2, rungs=rungs, lineup_ids=ids
    )
    assert plain == [0, 1]
    assert supported == [1, 0]
    assert trace[0]["marginal_utility"] == 4 * 400
    assert trace[1]["marginal_utility"] == 1 * 500


def test_blockmin_ladder_balances_blocks_where_plain_ladder_does_not() -> None:
    per_block = retrieval.WORLDS_PER_BLOCK
    scores = _block_scores(5)
    placements = [
        (0, 0, 100),  # A: block 0
        (1, 0, 90),   # A2: block 0 again
        (2, 1, 60),   # B: block 1
        (3, 2, 50),   # C: block 2
        (4, 3, 40),   # D: block 3
    ]
    for row, block, count in placements:
        start = block * per_block + row * 200
        scores[row, start:start + count] = np.float32(201.0)
    ids = [f"lineup:{index:064x}" for index in range(5)]
    rungs = [{"threshold": 200.0, "operator": ">", "weight": 1}]
    plain, _ = retrieval._select_ladder(
        scores, budget=4, rungs=rungs, lineup_ids=ids
    )
    robust, trace = retrieval._select_blockmin_ladder(
        scores, budget=4, rungs=rungs, lineup_ids=ids
    )
    # Raw totals prefer the second block-0 lineup; the regime-robust law
    # completes all four blocks instead.
    assert plain == [0, 1, 2, 3]
    assert robust == [0, 2, 3, 4]
    assert [row["marginal_utility"] for row in trace] == [100, 60, 50, 40]


def test_v2_methods_dispatch_and_block_view_guards() -> None:
    rng = np.random.default_rng(11)
    width = len(retrieval.DISCOVERY_BLOCKS) * retrieval.WORLDS_PER_BLOCK
    scores = rng.normal(loc=150.0, scale=30.0, size=(82, width)).astype(
        np.float32
    )
    ids = [f"lineup:{index:064x}" for index in range(82)]
    for strategy in retrieval.frozen_retrieval_strategies_v2(80)[4:]:
        selected, trace = retrieval._run_strategy(
            strategy, discovery_scores=scores, lineup_ids=ids
        )
        assert len(selected) == 80 and len(set(selected)) == 80
        assert [row["lineup_index"] for row in trace] == selected
        assert [row["selection_rank"] for row in trace] == list(range(80))
    with pytest.raises(retrieval.CorpusRetrievalError, match="whole world"):
        retrieval._discovery_block_view(scores[:, :-1])
    with pytest.raises(retrieval.CorpusRetrievalError, match="at least two"):
        retrieval._discovery_block_view(
            scores[:, :retrieval.WORLDS_PER_BLOCK]
        )
