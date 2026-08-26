"""Focused offline contract tests for the post-freeze R6 outcome snapshot."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as snapshot
from scripts import run_corpus_r6_full_union_outcome_snapshot_v1 as snapshot_cli


_ACTUAL_ROOT_FIXTURE_ENV = "R6_FULL_UNION_ACTUAL_ROOT_FIXTURE_DIR"


def test_mandatory_actual_root_smoke_api_is_public() -> None:
    expected = {
        "ACTUAL_ROOT_SMOKE_RECEIPT_SCHEMA",
        "build_actual_root_smoke_receipt_v1",
        "validate_actual_root_smoke_receipt_v1",
    }
    assert expected <= set(snapshot.__all__)
    assert all(hasattr(snapshot, name) for name in expected)


def _identity(value: object, name: str, generation: int = 1) -> dict[str, object]:
    return batch.object_identity_for_json(
        value, uri=f"gs://fixture/{name}.json", generation=str(generation)
    )


def _identity_key(value: object) -> tuple[str, str, str, int]:
    normalized = batch.normalize_object_identity(value, label="fixture identity")
    return (
        str(normalized["uri"]),
        str(normalized["generation"]),
        str(normalized["sha256"]),
        int(normalized["bytes"]),
    )


@dataclass
class _Fixture:
    root: dict[str, Any]
    root_identity: dict[str, object]
    source: dict[str, Any]
    source_identity: dict[str, object]
    leaves: list[dict[str, Any]]
    leaf_identities: list[dict[str, object]]
    results: list[dict[str, Any]]
    exact_values: dict[tuple[str, str, str, int], bytes]

    def read_exact(self, identity: object) -> bytes:
        return self.exact_values[_identity_key(identity)]


def _placeholder_unit_fixture(monkeypatch: pytest.MonkeyPatch) -> _Fixture:
    source_slates: list[dict[str, Any]] = []
    leaves: list[dict[str, Any]] = []
    leaf_identities: list[dict[str, object]] = []
    results: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    union_lineup_count = 0

    for source_ordinal in range(snapshot.AUTHORITATIVE_SLATE_COUNT):
        season = 2023 + source_ordinal // 18
        week = source_ordinal % 18 + 1
        slate_id = f"{season}-w{week:02d}"
        player_ids = [
            f"DST-{source_ordinal:02d}",
            *[f"p{source_ordinal:02d}-{ordinal:02d}" for ordinal in range(9)],
        ]
        first_roster = sorted([player_ids[0], *player_ids[1:9]])
        second_roster = sorted([player_ids[0], *player_ids[2:10]])
        candidates: list[dict[str, Any]] = []
        population: list[dict[str, Any]] = []
        for candidate_ordinal in range(80):
            roster = first_roster if candidate_ordinal % 2 == 0 else second_roster
            lineup_id = f"lineup-{source_ordinal:02d}-{candidate_ordinal:03d}"
            candidates.append({
                "lineup_id": lineup_id,
                "roster_player_ids": roster,
                "training_origin_blocks": list(snapshot.WORLD_BLOCKS),
                "training_occurrence_counts_by_block": {
                    block: 1 for block in snapshot.WORLD_BLOCKS
                },
                "training_occurrence_count": len(snapshot.WORLD_BLOCKS),
            })
            population.append({
                "lineup_id": lineup_id,
                "roster_player_ids": roster,
            })
        lineup_ids = [row["lineup_id"] for row in population]
        rosters = [row["roster_player_ids"] for row in population]
        population_descriptor: dict[str, Any] = {
            "fit_scope_id": snapshot.ALL_BLOCK_FIT_SCOPE_ID,
            "lineup_count": len(population),
            "ordered_lineup_ids_sha256": snapshot.canonical_sha256(lineup_ids),
            "ordered_rosters_sha256": snapshot.canonical_sha256(rosters),
            "ordered_population_sha256": snapshot.canonical_sha256(population),
            "eligible_equals_admitted": True,
            "excluded_count": 0,
        }
        population_descriptor["population_descriptor_sha256"] = (
            snapshot.canonical_sha256(population_descriptor)
        )

        world_identities: dict[str, dict[str, object]] = {}
        artifact_receipts: list[dict[str, Any]] = []
        for block in snapshot.WORLD_BLOCKS:
            role = f"world_artifact_{block.lower()}"
            artifact_body = {
                "source_ordinal": source_ordinal,
                "block": block,
            }
            artifact_identity = _identity(
                artifact_body,
                f"world-{source_ordinal:02d}-{block.lower()}",
                1_000 + source_ordinal * 5 + snapshot.WORLD_BLOCKS.index(block),
            )
            world_identities[role] = artifact_identity
            artifact_receipts.append({
                **artifact_identity,
                "block": block,
                "season": season,
                "week": week,
            })

        catalog = [{
            "id": player_id,
            "pos": "DST" if player_id.startswith("DST-") else "WR",
            "team": (
                f"T{source_ordinal:02d}"
                if player_id.startswith("DST-")
                else f"S{source_ordinal:02d}"
            ),
            "opp": "OPP",
            "game_id": f"game-{source_ordinal:02d}",
            "salary": 5_000,
        } for player_id in sorted(player_ids)]
        source_slates.append({
            "season": season,
            "week": week,
            "slate_id": slate_id,
            "catalog": catalog,
            "catalog_sha256": snapshot.canonical_sha256(catalog),
            "artifact_receipts": artifact_receipts,
        })

        final_scope = {
            "fit_scope_id": snapshot.ALL_BLOCK_FIT_SCOPE_ID,
            "training_blocks": list(snapshot.WORLD_BLOCKS),
            "heldout_block": None,
            "candidate_view": {
                "fit_scope_id": snapshot.ALL_BLOCK_FIT_SCOPE_ID,
                "training_blocks": list(snapshot.WORLD_BLOCKS),
                "heldout_block": None,
                "eligible_candidates": candidates,
                "eligible_count": len(candidates),
                "excluded_count": 0,
            },
        }
        result = {
            "full_union_surface": {
                "slate": {
                    "season": season,
                    "week": week,
                    "slate_id": slate_id,
                },
                "scopes": [{}, {}, {}, {}, {}, final_scope],
            },
            "world_artifact_identities": world_identities,
        }
        result_identity = _identity(
            {"source_ordinal": source_ordinal, "kind": "task-result"},
            f"task-result-{source_ordinal:02d}",
            2_000 + source_ordinal,
        )
        leaf = {
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "task_result_identity": result_identity,
            "later_source_freeze_identity": None,
            "all_block_union": population_descriptor,
        }
        leaf_identity = _identity(
            {"source_ordinal": source_ordinal, "kind": "slate-freeze"},
            f"slate-freeze-{source_ordinal:02d}",
            3_000 + source_ordinal,
        )
        leaves.append(leaf)
        leaf_identities.append(leaf_identity)
        results.append(result)
        root_rows.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "slate_freeze_identity": leaf_identity,
            "task_result_identity": result_identity,
        })
        union_lineup_count += len(population)

    source: dict[str, Any] = {
        "slate_count": snapshot.AUTHORITATIVE_SLATE_COUNT,
        "world_blocks": list(snapshot.WORLD_BLOCKS),
        "slates": source_slates,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
    }
    source["freeze_sha256"] = snapshot.canonical_sha256(source)
    source_identity = _identity(source, "later-source", 9_001)
    for leaf in leaves:
        leaf["later_source_freeze_identity"] = source_identity

    root: dict[str, Any] = {
        "schema_version": snapshot.freeze.PANEL_FREEZE_SCHEMA,
        "source_slate_count": snapshot.AUTHORITATIVE_SLATE_COUNT,
        "complete": True,
        "structural_freeze_only": True,
        "outcome_key_projection_inputs_frozen": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "later_source_freeze_identity": source_identity,
        "slate_freezes": root_rows,
        "union_lineup_count": union_lineup_count,
        "panel_freeze_sha256": "a" * 64,
        "execution_manifest_sha256": "b" * 64,
        "panel_index_identity": _identity(
            {"kind": "panel-index"}, "panel-index", 9_002
        ),
        "panel_index_sha256": "c" * 64,
    }
    root_identity = _identity(root, "panel-freeze", 9_003)
    exact_values = {
        _identity_key(source_identity): batch.canonical_json_bytes(source),
    }
    fixture = _Fixture(
        root=root,
        root_identity=root_identity,
        source=source,
        source_identity=source_identity,
        leaves=leaves,
        leaf_identities=leaf_identities,
        results=results,
        exact_values=exact_values,
    )

    def _reopen_root(identity: object, *, read_exact: object):
        assert batch.normalize_object_identity(
            identity, label="root identity"
        ) == fixture.root_identity
        return fixture.root, fixture.root_identity

    leaf_by_uri = {
        str(identity["uri"]): ordinal
        for ordinal, identity in enumerate(fixture.leaf_identities)
    }

    def _reopen_leaf(identity: object, *, read_exact: object):
        normalized = batch.normalize_object_identity(identity, label="leaf identity")
        ordinal = leaf_by_uri[str(normalized["uri"])]
        return (
            fixture.leaves[ordinal],
            {},
            {},
            [],
            fixture.results[ordinal],
            fixture.leaf_identities[ordinal],
        )

    def _validate_source(value: object, *, expected_freeze_sha256: str):
        assert isinstance(value, dict)
        assert value["freeze_sha256"] == expected_freeze_sha256
        return dict(value)

    monkeypatch.setattr(snapshot.freeze, "reopen_panel_freeze_v1", _reopen_root)
    monkeypatch.setattr(snapshot.freeze, "reopen_slate_freeze_v1", _reopen_leaf)
    monkeypatch.setattr(
        snapshot.later_source, "validate_source_freeze", _validate_source
    )
    return fixture


def _projection(
    fixture: _Fixture,
) -> tuple[dict[str, object], dict[str, object]]:
    projection = snapshot.project_required_outcome_keys_v1(
        panel_freeze_identity=fixture.root_identity,
        read_exact=fixture.read_exact,
    )
    return projection, _identity(projection, "outcome-key-projection", 10_001)


def _rows(projection: dict[str, object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for ordinal, raw_key in enumerate(projection["outcome_keys"]):
        assert isinstance(raw_key, dict)
        result.append({
            "source_ordinal": raw_key["source_ordinal"],
            "season": raw_key["season"],
            "week": raw_key["week"],
            "slate_id": raw_key["slate_id"],
            "source_kind": raw_key["source_kind"],
            "source_key": raw_key["source_key"],
            "player_id": raw_key["player_id"],
            "realized_score_micro": ordinal - 10,
        })
    return result


def test_required_actual_root_outcome_blind_smoke_uses_real_freeze_replayers(
) -> None:
    """Replay the canonical complete CAS fixture without validator patches.

    Required fixture layout is ``panel-freeze-identity.json``, the published
    ``outcome-key-projection.json`` and its explicit ``*-identity.json``, an
    ``actual-root-smoke-inputs.json`` carrying reviewed commit/image and four
    code/test SHA-256 values, plus an ``objects/`` directory containing every
    exact predecessor as ``<sha256>.json``.  Populate it from the actual root and set
    ``R6_FULL_UNION_ACTUAL_ROOT_FIXTURE_DIR`` before the mandatory
    outcome-blind production smoke.  This path must pass before any realized
    outcome query opens.
    """
    raw_root = os.environ.get(_ACTUAL_ROOT_FIXTURE_ENV)
    if raw_root is None:
        pytest.skip(
            "required future actual-root outcome-blind smoke fixture is not "
            "materialized yet"
        )
    fixture_root = Path(raw_root).resolve(strict=True)
    reader = snapshot_cli._LocalExactReader(fixture_root / "objects")
    root_identity = snapshot_cli._canonical_value(
        fixture_root / "panel-freeze-identity.json",
        label="actual panel-freeze identity",
    )

    root, retained_root_identity = snapshot.freeze.reopen_panel_freeze_v1(
        root_identity, read_exact=reader
    )
    assert retained_root_identity == root_identity
    assert root["source_slate_count"] == snapshot.AUTHORITATIVE_SLATE_COUNT
    assert root["complete"] is True
    assert root["outcome_key_projection_inputs_frozen"] is True
    assert root["uses_realized_outcomes"] is False
    root_rows = root["slate_freezes"]
    assert isinstance(root_rows, list)
    assert len(root_rows) == snapshot.AUTHORITATIVE_SLATE_COUNT

    for source_ordinal, root_row in enumerate(root_rows):
        leaf, _, _, _, result, leaf_identity = (
            snapshot.freeze.reopen_slate_freeze_v1(
                root_row["slate_freeze_identity"], read_exact=reader
            )
        )
        assert leaf_identity == root_row["slate_freeze_identity"]
        assert leaf["source_ordinal"] == source_ordinal
        scopes = result["full_union_surface"]["scopes"]
        assert len(scopes) == len(snapshot.WORLD_BLOCKS) + 1
        final_scope = scopes[-1]
        assert final_scope["fit_scope_id"] == snapshot.ALL_BLOCK_FIT_SCOPE_ID
        final_candidates = final_scope["candidate_view"]["eligible_candidates"]
        assert final_candidates
        final_ids = {row["lineup_id"] for row in final_candidates}
        assert len(final_ids) == len(final_candidates)
        for candidate in final_candidates:
            origins = candidate["training_origin_blocks"]
            assert origins
            assert set(origins) <= set(snapshot.WORLD_BLOCKS)

        for block, scope in zip(
            snapshot.WORLD_BLOCKS, scopes[:-1], strict=True
        ):
            assert scope["heldout_block"] == block
            scope_candidates = scope["candidate_view"]["eligible_candidates"]
            assert scope_candidates
            scope_ids = {row["lineup_id"] for row in scope_candidates}
            assert scope_ids <= final_ids
            assert set(scope["training_blocks"]) <= set(snapshot.WORLD_BLOCKS)
            for candidate in scope_candidates:
                origins = candidate["training_origin_blocks"]
                assert origins
                assert set(origins) <= set(scope["training_blocks"])
            books = scope["books"]
            assert books
            for book in books:
                selected = book["selected_lineup_ids"]
                assert selected
                assert set(selected) <= scope_ids

    projection = snapshot_cli._canonical_value(
        fixture_root / "outcome-key-projection.json",
        label="actual outcome-key projection",
    )
    projection_identity = snapshot_cli._canonical_value(
        fixture_root / "outcome-key-projection-identity.json",
        label="explicit actual outcome-key projection identity",
    )
    smoke_inputs = snapshot_cli._canonical_value(
        fixture_root / "actual-root-smoke-inputs.json",
        label="explicit actual-root smoke inputs",
    )
    assert isinstance(smoke_inputs, dict)
    snapshot.validate_outcome_key_projection_v1(
        projection,
        identity=projection_identity,
        read_exact=reader,
    )
    assert projection["source_slate_count"] == 54
    assert projection["all_block_union_lineup_count"] == root[
        "union_lineup_count"
    ]
    assert projection["outcome_key_count"] > 0
    assert projection["uses_realized_outcomes"] is False
    receipt = snapshot.build_actual_root_smoke_receipt_v1(
        panel_freeze_identity=root_identity,
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        expected_reviewed_source_commit_sha=smoke_inputs[
            "reviewed_source_commit_sha"
        ],
        expected_runtime_immutable_image=smoke_inputs[
            "runtime_immutable_image"
        ],
        snapshot_module_sha256=smoke_inputs["snapshot_module_sha256"],
        snapshot_cli_sha256=smoke_inputs["snapshot_cli_sha256"],
        snapshot_test_sha256=smoke_inputs["snapshot_test_sha256"],
        snapshot_cli_test_sha256=smoke_inputs[
            "snapshot_cli_test_sha256"
        ],
        read_exact=reader,
    )
    receipt_identity = _identity(
        receipt, "actual-root-smoke-receipt", 50_001
    )
    retained, retained_identity = (
        snapshot.validate_actual_root_smoke_receipt_v1(
            receipt,
            identity=receipt_identity,
            expected_panel_freeze_identity=root_identity,
            outcome_key_projection=projection,
            expected_outcome_key_projection_identity=projection_identity,
            expected_reviewed_source_commit_sha=smoke_inputs[
                "reviewed_source_commit_sha"
            ],
            expected_runtime_immutable_image=smoke_inputs[
                "runtime_immutable_image"
            ],
            expected_snapshot_module_sha256=smoke_inputs[
                "snapshot_module_sha256"
            ],
            expected_snapshot_cli_sha256=smoke_inputs[
                "snapshot_cli_sha256"
            ],
            expected_snapshot_test_sha256=smoke_inputs[
                "snapshot_test_sha256"
            ],
            expected_snapshot_cli_test_sha256=smoke_inputs[
                "snapshot_cli_test_sha256"
            ],
            read_exact=reader,
        )
    )
    assert retained == receipt
    assert retained_identity == receipt_identity
    assert receipt["root_leaf_result_replay_count"] == 54
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["query_executed"] is False


def test_projection_uses_every_final_fit_candidate_and_maps_dst_to_team(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _placeholder_unit_fixture(monkeypatch)
    projection, projection_identity = _projection(fixture)

    assert projection["source_slate_count"] == 54
    assert projection["all_block_union_lineup_count"] == 54 * 80
    assert projection["required_player_count"] == 54 * 10
    assert projection["outcome_key_count"] == 54 * 10
    assert projection["uses_realized_outcomes"] is False
    keys = projection["outcome_keys"]
    assert isinstance(keys, list)
    dst = [row for row in keys if row["source_kind"] == "dst"]
    skill = [row for row in keys if row["source_kind"] == "skill"]
    assert len(dst) == 54
    assert all(row["source_key"] == row["team"] for row in dst)
    assert all(row["source_key"] == row["player_id"] for row in skill)
    assert any(row["player_id"].endswith("-08") for row in skill)

    retained, retained_identity, parsed = (
        snapshot.validate_outcome_key_projection_v1(
            projection,
            identity=projection_identity,
            read_exact=fixture.read_exact,
        )
    )
    assert retained == projection
    assert retained_identity == projection_identity
    assert len(parsed) == 54 * 10


def test_projection_rejects_r0_r4_origin_and_artifact_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _placeholder_unit_fixture(monkeypatch)
    candidate = fixture.results[0]["full_union_surface"]["scopes"][-1][
        "candidate_view"
    ]["eligible_candidates"][0]
    candidate["training_origin_blocks"] = ["R0", "R5"]
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="R0-R4 containment",
    ):
        snapshot.project_required_outcome_keys_v1(
            panel_freeze_identity=fixture.root_identity,
            read_exact=fixture.read_exact,
        )

    fixture = _placeholder_unit_fixture(monkeypatch)
    fixture.results[0]["world_artifact_identities"]["world_artifact_r4"] = (
        _identity({"drift": True}, "drifted-r4", 20_001)
    )
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="result/later-source R4 identity differs",
    ):
        snapshot.project_required_outcome_keys_v1(
            panel_freeze_identity=fixture.root_identity,
            read_exact=fixture.read_exact,
        )


def test_realized_source_requires_exact_integer_micro_union_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _placeholder_unit_fixture(monkeypatch)
    projection, projection_identity = _projection(fixture)
    rows = _rows(projection)

    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="missing projected outcome keys",
    ):
        snapshot.build_realized_source_v1(
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            realized_rows=rows[:-1],
            read_exact=fixture.read_exact,
        )

    duplicated = [*rows, deepcopy(rows[-1])]
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="duplicate outcome keys",
    ):
        snapshot.build_realized_source_v1(
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            realized_rows=duplicated,
            read_exact=fixture.read_exact,
        )

    extra = deepcopy(rows)
    extra[0]["source_key"] = "EXTRA-NON-UNION"
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="extra non-union",
    ):
        snapshot.build_realized_source_v1(
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            realized_rows=extra,
            read_exact=fixture.read_exact,
        )

    inexact = deepcopy(rows)
    inexact[0]["realized_score_micro"] = 1.5
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="exact integer",
    ):
        snapshot.build_realized_source_v1(
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            realized_rows=inexact,
            read_exact=fixture.read_exact,
        )


def test_registered_micro_adapter_maps_query_keys_without_decimal_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _placeholder_unit_fixture(monkeypatch)
    projection, projection_identity = _projection(fixture)
    _, _, keys = snapshot.validate_outcome_key_projection_v1(
        projection,
        identity=projection_identity,
        read_exact=fixture.read_exact,
    )
    registered_rows = [{
        "season": key.season,
        "week": key.week,
        "source_kind": key.source_kind,
        "source_key": key.source_key,
        "realized_score_micro": ordinal,
    } for ordinal, key in enumerate(keys)]
    normalized = snapshot.normalize_registered_integer_micro_rows_v1(
        registered_rows, outcome_keys=keys
    )
    assert len(normalized) == 54 * 10
    assert normalized[0]["source_ordinal"] == keys[0].source_ordinal
    assert normalized[0]["player_id"] == keys[0].player_id
    assert type(normalized[0]["realized_score_micro"]) is int
    registered_source = snapshot.build_realized_source_from_registered_rows_v1(
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        registered_integer_micro_rows=registered_rows,
        read_exact=fixture.read_exact,
    )
    assert registered_source["row_count"] == 54 * 10

    duplicate = [*registered_rows, deepcopy(registered_rows[-1])]
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="duplicate outcome keys",
    ):
        snapshot.normalize_registered_integer_micro_rows_v1(
            duplicate, outcome_keys=keys
        )
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="missing projected outcome keys",
    ):
        snapshot.normalize_registered_integer_micro_rows_v1(
            registered_rows[:-1], outcome_keys=keys
        )
    inexact = deepcopy(registered_rows)
    inexact[0]["realized_score_micro"] = "1"
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="exact integer",
    ):
        snapshot.normalize_registered_integer_micro_rows_v1(
            inexact, outcome_keys=keys
        )


def test_source_and_snapshot_are_identity_bound_and_replay_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _placeholder_unit_fixture(monkeypatch)
    projection, projection_identity = _projection(fixture)
    rows = _rows(projection)
    source = snapshot.build_realized_source_v1(
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        realized_rows=rows,
        read_exact=fixture.read_exact,
    )
    source_identity = _identity(source, "realized-source", 30_001)
    result = snapshot.build_outcome_snapshot_v1(
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        realized_source=source,
        realized_source_identity=source_identity,
        read_exact=fixture.read_exact,
    )
    result_identity = _identity(result, "outcome-snapshot", 30_002)
    retained, retained_identity, score_map = snapshot.validate_outcome_snapshot_v1(
        result,
        identity=result_identity,
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        realized_source=source,
        realized_source_identity=source_identity,
        read_exact=fixture.read_exact,
    )
    assert retained == result
    assert retained_identity == result_identity
    assert len(score_map) == 54 * 10
    assert result["score_unit"] == "micro_dk"
    assert result["lineup_scoring_performed"] is False

    forged = deepcopy(result)
    forged["rows"][0]["realized_score_micro"] += 1
    forged["rows_sha256"] = snapshot.canonical_sha256(forged["rows"])
    forged["outcome_snapshot_sha256"] = snapshot.canonical_sha256({
        key: value
        for key, value in forged.items()
        if key != "outcome_snapshot_sha256"
    })
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="canonical replay differs",
    ):
        snapshot.validate_outcome_snapshot_v1(
            forged,
            identity=_identity(forged, "forged-outcome-snapshot", 30_003),
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            realized_source=source,
            realized_source_identity=source_identity,
            read_exact=fixture.read_exact,
        )


def test_projection_rejects_skill_dst_key_forgery_before_source_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _placeholder_unit_fixture(monkeypatch)
    projection, _ = _projection(fixture)
    forged = deepcopy(projection)
    dst = next(
        row for row in forged["outcome_keys"] if row["source_kind"] == "dst"
    )
    dst["source_key"] = dst["player_id"]
    forged["outcome_keys_sha256"] = snapshot.canonical_sha256(
        forged["outcome_keys"]
    )
    forged["outcome_key_projection_sha256"] = snapshot.canonical_sha256({
        key: value
        for key, value in forged.items()
        if key != "outcome_key_projection_sha256"
    })
    with pytest.raises(
        snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error,
        match="skill/player or DST/team",
    ):
        snapshot.build_realized_source_v1(
            outcome_key_projection=forged,
            outcome_key_projection_identity=_identity(
                forged, "forged-key-projection", 40_001
            ),
            realized_rows=[],
            read_exact=fixture.read_exact,
        )
