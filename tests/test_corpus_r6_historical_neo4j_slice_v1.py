from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as candidate_v1
from nfl_dfs.research import corpus_r6_historical_neo4j_slice_v1 as subject
from scripts import run_corpus_r6_historical_neo4j_slice_v1 as runner


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _players(prefix: str) -> tuple[list[str], list[dict[str, object]]]:
    positions = ("QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "DST")
    rows: list[dict[str, object]] = []
    ids: list[str] = []
    for ordinal, position in enumerate(positions):
        player_id = f"{prefix}-{ordinal}"
        ids.append(player_id)
        rows.append({
            "id": player_id,
            "pos": position,
            "team": "AAA" if ordinal < 5 else "BBB",
            "opp": "BBB" if ordinal < 5 else "AAA",
            "game_id": "AAA-BBB",
            "salary": 5_000,
        })
    return ids, rows


def _lineage(
    candidate_id: str,
    roster: list[str],
    occurrences: list[dict[str, object]],
    *,
    arms: tuple[str, ...],
    blocks: tuple[str, ...],
) -> dict[str, object]:
    arm_ordinals = sorted({int(row["arm_ordinal"]) for row in occurrences})
    counts = {
        block: sum(row["block_id"] == block for row in occurrences)
        for block in blocks
    }
    arms_by_block = {
        block: sorted({
            str(row["parameter_set_id"])
            for row in occurrences
            if row["block_id"] == block
        })
        for block in blocks
    }
    return {
        "candidate_id": candidate_id,
        "player_ids": roster,
        "roster_sha256": subject.canonical_sha256(roster),
        "source_arm_ordinals": arm_ordinals,
        "source_arms": [arms[ordinal] for ordinal in arm_ordinals],
        "origin_blocks": [block for block in blocks if counts[block]],
        "occurrence_counts_by_block": counts,
        "source_arms_by_block": arms_by_block,
        "occurrence_count": len(occurrences),
        "occurrences": occurrences,
    }


def _fixture() -> tuple[
    subject._Expectations,
    list[dict[str, object]],
    list[list[dict[str, object]]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    arms = ("arm-a", "arm-b")
    blocks = ("B0", "B1")
    roster_a, players_a = _players("a")
    roster_b, players_b = _players("b")
    candidate_rows = [
        {
            "candidate_id": "lineup-a",
            "player_ids": roster_a,
            "roster_sha256": subject.canonical_sha256(roster_a),
        },
        {
            "candidate_id": "lineup-b",
            "player_ids": roster_b,
            "roster_sha256": subject.canonical_sha256(roster_b),
        },
    ]
    occurrences_a = [
        {
            "arm_ordinal": 0,
            "parameter_set_id": arms[0],
            "visit_ordinal": 0,
            "block_id": blocks[0],
            "objective_world_index": 0,
        },
        {
            "arm_ordinal": 1,
            "parameter_set_id": arms[1],
            "visit_ordinal": 1,
            "block_id": blocks[1],
            "objective_world_index": 1,
        },
    ]
    occurrences_b = [
        {
            "arm_ordinal": 0,
            "parameter_set_id": arms[0],
            "visit_ordinal": 1,
            "block_id": blocks[1],
            "objective_world_index": 1,
        },
        {
            "arm_ordinal": 1,
            "parameter_set_id": arms[1],
            "visit_ordinal": 0,
            "block_id": blocks[0],
            "objective_world_index": 0,
        },
    ]
    lineages = [
        _lineage(
            "lineup-a", roster_a, occurrences_a, arms=arms, blocks=blocks
        ),
        _lineage(
            "lineup-b", roster_b, occurrences_b, arms=arms, blocks=blocks
        ),
    ]
    slate = {"season": 2024, "week": 1, "slate_id": "2024-w01"}
    artifact = {
        "source_task_ordinal": 0,
        "task_id": "task-0",
        "slate": slate,
        "rows": candidate_rows,
        "candidate_count": 2,
        "candidate_row_manifest_sha256": subject.canonical_sha256(candidate_rows),
    }
    catalog = {
        "source_task_ordinal": 0,
        "slate": slate,
        "players": [*players_a, *players_b],
        "player_count": 18,
    }

    def lineup_row(
        candidate: dict[str, object],
        lineage: dict[str, object],
        score: int,
        rank: int,
    ) -> dict[str, object]:
        return {
            "lineup_id": candidate["candidate_id"],
            "roster_player_ids": candidate["player_ids"],
            "roster_identity_sha256": subject.canonical_sha256(
                candidate["player_ids"]
            ),
            "realized_score_micro": score,
            "realized_union_rank": rank,
            "regret_to_union_maximum_micro": 200_000_000 - score,
            "at_or_above_thresholds_dk": [200] if score >= 200_000_000 else [],
            "training_origin_blocks": lineage["origin_blocks"],
            "training_source_arms": lineage["source_arms"],
            "training_occurrence_counts_by_block": lineage[
                "occurrence_counts_by_block"
            ],
            "training_source_arms_by_block": lineage["source_arms_by_block"],
            "training_occurrence_count": lineage["occurrence_count"],
        }

    lineup_rows = [
        lineup_row(candidate_rows[0], lineages[0], 200_000_000, 0),
        lineup_row(candidate_rows[1], lineages[1], 199_000_000, 1),
    ]
    selections = [
        {
            "scope_ordinal": 0,
            "fit_scope_id": "all-block-final-fit",
            "book_id": "book-a",
            "selection_rank": 0,
            "lineup_id": "lineup-a",
            "realized_score_micro": 200_000_000,
        },
        {
            "scope_ordinal": 0,
            "fit_scope_id": "all-block-final-fit",
            "book_id": "book-b",
            "selection_rank": 0,
            "lineup_id": "lineup-b",
            "realized_score_micro": 199_000_000,
        },
    ]
    books = [
        {
            "scope_ordinal": 0,
            "fit_scope_id": "all-block-final-fit",
            "strategy_ordinal": ordinal,
            "strategy_id": f"strategy-{ordinal}",
            "book_id": f"book-{'a' if ordinal == 0 else 'b'}",
            "eligible_lineup_count": 2,
            "selected_lineup_count": 1,
            "selected_lineup_ids_sha256": subject.canonical_sha256(
                ["lineup-a" if ordinal == 0 else "lineup-b"]
            ),
            "eligible_maximum_score_micro": 200_000_000,
            "selected_maximum_score_micro": (
                200_000_000 if ordinal == 0 else 199_000_000
            ),
            "selector_regret_micro": 0 if ordinal == 0 else 1_000_000,
            "threshold_capture": [],
        }
        for ordinal in range(2)
    ]
    shard = {
        "source_ordinal": 0,
        "slate_id": slate["slate_id"],
        "lineup_rows": lineup_rows,
        "lineup_rows_sha256": subject.canonical_sha256(lineup_rows),
        "scope_membership_count": 2,
        "scope_membership_rows_sha256": "0" * 64,
        "book_count": 2,
        "book_rows": books,
        "book_rows_sha256": subject.canonical_sha256(books),
        "selection_count": 2,
        "selection_rows": selections,
        "selection_rows_sha256": subject.canonical_sha256(selections),
    }
    expectations = subject._Expectations(
        slate_count=1,
        candidate_count=2,
        visit_count=4,
        player_slate_count=18,
        scope_membership_count=2,
        book_count=2,
        selection_count=2,
        final_book_count=2,
        final_selection_count=2,
        high_score_count=1,
        selected_high_score_count=1,
        missed_high_score_count=0,
        opportunity_slate_count=1,
        converted_slate_count=1,
        arms=arms,
        blocks=blocks,
        visits_per_arm_block=1,
        strategies_per_scope=2,
        selections_per_book=1,
        final_scope_ordinal=0,
        final_fit_scope_id="all-block-final-fit",
    )
    return expectations, [artifact], [lineages], [catalog], [shard]


def _root_identities() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for role in ("candidate_v2", "catalog_outer", "attribution_release"):
        raw = subject.canonical_json_bytes({"role": role})
        result[role] = _identity(f"fixture://{role}", raw)
    return result


def test_exact_store_requires_identity_canonical_bytes_and_complete_consumption() -> None:
    raw = subject.canonical_json_bytes({"value": 1})
    identity = _identity("fixture://one", raw)
    store = subject._ExactObjectStore([
        subject.ExactJsonObjectV1(identity=identity, raw=raw)
    ])
    assert store.read(identity, role="fixture", source_ordinal=0) == {"value": 1}
    assert len(store.finish(expected_count=1)) == 1

    with pytest.raises(subject.CorpusR6HistoricalNeo4jSliceV1Error):
        subject._ExactObjectStore([
            subject.ExactJsonObjectV1(identity=identity, raw=b"{}")
        ])

    noncanonical = b'{"value": 1}'
    noncanonical_identity = _identity("fixture://noncanonical", noncanonical)
    noncanonical_store = subject._ExactObjectStore([
        subject.ExactJsonObjectV1(
            identity=noncanonical_identity, raw=noncanonical
        )
    ])
    with pytest.raises(subject.CorpusR6HistoricalNeo4jSliceV1Error):
        noncanonical_store.read(
            noncanonical_identity, role="fixture", source_ordinal=0
        )


def test_exact_store_revalidates_caller_selected_local_file(tmp_path: Path) -> None:
    raw = subject.canonical_json_bytes({"value": 1})
    path = tmp_path / "exact.json"
    path.write_bytes(raw)
    identity = _identity("fixture://local", raw)
    store = subject._ExactObjectStore([
        subject.ExactJsonFileV1(identity=identity, path=path)
    ])
    assert store.read(identity, role="fixture", source_ordinal=0) == {"value": 1}

    path.write_bytes(subject.canonical_json_bytes({"value": 2}))
    changed = subject._ExactObjectStore([
        subject.ExactJsonFileV1(identity=identity, path=path)
    ])
    with pytest.raises(
        subject.CorpusR6HistoricalNeo4jSliceV1Error,
        match="bytes differ",
    ):
        changed.read(identity, role="fixture", source_ordinal=0)


def test_production_acceptance_totals_lock_selected_missed_union() -> None:
    assert subject.EXPECTED_HIGH_SCORE_LINEUP_COUNT == 279
    assert subject.EXPECTED_SELECTED_HIGH_SCORE_LINEUP_COUNT == 38
    assert subject.EXPECTED_MISSED_HIGH_SCORE_LINEUP_COUNT == 241
    assert (
        subject.EXPECTED_SELECTED_HIGH_SCORE_LINEUP_COUNT
        + subject.EXPECTED_MISSED_HIGH_SCORE_LINEUP_COUNT
        == subject.EXPECTED_HIGH_SCORE_LINEUP_COUNT
    )
    assert subject.EXPECTED_OPPORTUNITY_SLATE_COUNT == 29
    assert subject.EXPECTED_CONVERTED_SLATE_COUNT == 10


def test_projection_is_deterministic_and_preserves_high_score_decisions() -> None:
    expectations, artifacts, lineages, catalogs, shards = _fixture()
    kwargs = {
        "candidate_artifacts": artifacts,
        "candidate_lineages": lineages,
        "catalogs": catalogs,
        "attribution_shards": shards,
        "source_root_identities": _root_identities(),
        "source_manifest": [],
        "expectations": expectations,
    }
    first = subject._project_graph_from_validated_sources(**kwargs)
    second = subject._project_graph_from_validated_sources(**kwargs)
    assert first.plan_sha256 == second.plan_sha256
    assert first.nodes == second.nodes
    assert first.relationships == second.relationships
    assert first.manifest["reconciliation"] == {
        "source_slate_count": 1,
        "candidate_count": 2,
        "visit_occurrence_count": 4,
        "player_slate_count": 18,
        "scope_membership_count": 2,
        "book_count": 2,
        "selection_count": 2,
        "final_fit_book_count": 2,
        "final_fit_selection_count": 2,
        "high_score_lineup_count": 1,
        "selected_high_score_lineup_count": 1,
        "missed_high_score_lineup_count": 0,
        "opportunity_slate_count": 1,
        "converted_slate_count": 1,
        "candidate_attribution_roster_equality": True,
        "exact_nine_player_catalog_join": True,
        "candidate_lineage_recurrence_reconciled": True,
        "full_population_denominators_retained": True,
    }
    relationship_counts = {}
    for row in first.relationships:
        relationship_counts[row["relationship_type"]] = (
            relationship_counts.get(row["relationship_type"], 0) + 1
        )
    assert relationship_counts["CONTAINS_PLAYER"] == 9
    assert relationship_counts["SELECTED_HIGH_SCORER"] == 1
    assert relationship_counts["MISSED_HIGH_SCORER"] == 1
    assert relationship_counts["GENERATED_IN_CELL"] == 2
    assert all(node["kind"] != "Winner" for node in first.nodes)
    assert first.manifest["promotion_authority"] is False
    assert first.manifest["policy_feedback_authority"] is False


def test_projection_fails_on_roster_mismatch_before_slicing() -> None:
    expectations, artifacts, lineages, catalogs, shards = _fixture()
    broken = deepcopy(shards)
    broken[0]["lineup_rows"][1]["roster_player_ids"] = list(
        broken[0]["lineup_rows"][0]["roster_player_ids"]
    )
    with pytest.raises(
        subject.CorpusR6HistoricalNeo4jSliceV1Error,
        match="roster equality",
    ):
        subject._project_graph_from_validated_sources(
            candidate_artifacts=artifacts,
            candidate_lineages=lineages,
            catalogs=catalogs,
            attribution_shards=broken,
            source_root_identities=_root_identities(),
            source_manifest=[],
            expectations=expectations,
        )


def test_projection_treats_source_arm_summary_as_an_unordered_set() -> None:
    expectations, artifacts, lineages, catalogs, shards = _fixture()
    reordered = deepcopy(shards)
    reordered[0]["lineup_rows"][0]["training_source_arms"] = list(reversed(
        reordered[0]["lineup_rows"][0]["training_source_arms"]
    ))
    result = subject._project_graph_from_validated_sources(
        candidate_artifacts=artifacts,
        candidate_lineages=lineages,
        catalogs=catalogs,
        attribution_shards=reordered,
        source_root_identities=_root_identities(),
        source_manifest=[],
        expectations=expectations,
    )
    assert result.manifest["reconciliation"][
        "candidate_lineage_recurrence_reconciled"
    ] is True


def test_lineage_validator_rebuilds_recurrence_not_just_hash() -> None:
    expectations, artifacts, lineages, _catalogs, _shards = _fixture()
    sidecar = {
        "schema_version": candidate_v1.LINEAGE_SIDECAR_SCHEMA,
        "source_task_ordinal": 0,
        "task_id": artifacts[0]["task_id"],
        "slate": artifacts[0]["slate"],
        "arm_count": 2,
        "visits_per_block": 1,
        "visit_occurrence_count": 4,
        "candidate_count": 2,
        "candidates": lineages[0],
        "candidate_lineage_manifest_sha256": subject.canonical_sha256(
            lineages[0]
        ),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "graph_mutation_licensed": False,
    }
    sidecar["candidate_lineage_sidecar_sha256"] = subject.canonical_sha256(
        sidecar
    )
    assert len(subject._validate_lineage_sidecar(
        sidecar, artifact=artifacts[0], expectations=expectations
    )) == 2

    broken = deepcopy(sidecar)
    broken["candidates"][0]["occurrence_counts_by_block"]["B0"] = 2
    broken["candidate_lineage_manifest_sha256"] = subject.canonical_sha256(
        broken["candidates"]
    )
    broken.pop("candidate_lineage_sidecar_sha256")
    broken["candidate_lineage_sidecar_sha256"] = subject.canonical_sha256(broken)
    with pytest.raises(
        subject.CorpusR6HistoricalNeo4jSliceV1Error,
        match="recurrence summary",
    ):
        subject._validate_lineage_sidecar(
            broken, artifact=artifacts[0], expectations=expectations
        )


def test_cypher_is_parameterized_and_conflict_rejecting() -> None:
    assert "$rows" in subject.NODE_UPSERT_CYPHER
    assert "$rows" in subject.RELATIONSHIP_UPSERT_CYPHER
    assert "ON CREATE SET" in subject.NODE_UPSERT_CYPHER
    assert "accepted_count" in subject.NODE_UPSERT_CYPHER
    assert "accepted_count" in subject.RELATIONSHIP_UPSERT_CYPHER
    assert "LineupCandidate" not in subject.NODE_UPSERT_CYPHER
    assert json.loads(subject.canonical_json_bytes({"x": 1})) == {"x": 1}


def test_local_receipt_is_compact_deterministic_and_non_authoritative() -> None:
    expectations, artifacts, lineages, catalogs, shards = _fixture()
    plan = subject._project_graph_from_validated_sources(
        candidate_artifacts=artifacts,
        candidate_lineages=lineages,
        catalogs=catalogs,
        attribution_shards=shards,
        source_root_identities=_root_identities(),
        source_manifest=[],
        expectations=expectations,
    )
    identities = _root_identities()
    receipt = runner._receipt(
        plan,
        candidate_identity=identities["candidate_v2"],
        catalog_identity=identities["catalog_outer"],
        funnel_identity=identities["attribution_release"],
    )
    assert receipt["receipt_sha256"] == subject.canonical_sha256({
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    })
    assert receipt["neo4j_mutation_performed"] is False
    assert receipt["network_access_performed"] is False
    assert receipt["promotion_authority"] is False
