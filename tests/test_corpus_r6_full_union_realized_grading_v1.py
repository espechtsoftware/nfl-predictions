"""Synthetic contract tests for the post-freeze R6 score-once grader.

These fixtures replace only the already-tested exact-read validators.  They
retain the authoritative 54 slate x 6 scope x 8 strategy x 80-rank geometry so
the grader's own census, coordinate, prefix, outcome-key, and operation-budget
checks are exercised at production shape without opening any external data.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import corpus_r6_full_union_task0_smoke_v1 as task0_smoke
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


_UNION_COUNT = 84
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TASK0_RECEIPT = (
    _REPO_ROOT
    / "reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index"
    / "panel-index-live/full-union-task0-smoke-2023-w01/receipt.json"
)


def _sha(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity(label: str) -> dict[str, object]:
    return {
        "uri": f"gs://synthetic-r6/{label}.json",
        "generation": "1",
        "sha256": _sha(f"identity:{label}"),
        "bytes": 1,
    }


def _with_hash(value: dict[str, object], field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = grading.canonical_sha256(result)
    return result


def _rehash(value: dict[str, object], field: str) -> dict[str, object]:
    return _with_hash(
        {key: item for key, item in value.items() if key != field}, field
    )


@dataclass
class _SyntheticPanel:
    root: dict[str, object]
    root_identity: dict[str, object]
    leaves_by_uri: dict[
        str,
        tuple[
            dict[str, object], dict[str, object], dict[str, object]
        ],
    ]
    projection: dict[str, object]
    projection_identity: dict[str, object]
    source: dict[str, object]
    source_identity: dict[str, object]
    snapshot: dict[str, object]
    snapshot_identity: dict[str, object]
    player_scores: dict[tuple[int, str], int]
    population_ids: dict[int, list[str]]


class _MemoryStore:
    def __init__(self) -> None:
        self.generation = 0
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.current: dict[str, tuple[dict[str, object], bytes]] = {}
        self.publication_order: list[str] = []

    @staticmethod
    def _key(identity: object) -> tuple[str, str, str, int]:
        row = dict(identity)  # type: ignore[arg-type]
        return (
            str(row["uri"]), str(row["generation"]),
            str(row["sha256"]), int(row["bytes"]),
        )

    def read_exact(self, identity: object) -> bytes:
        return self.values[self._key(identity)]

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        existing = self.current.get(uri)
        if existing is not None:
            if existing[1] != raw:
                raise RuntimeError("create-once collision differs")
            return existing[0]
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.values[self._key(identity)] = bytes(raw)
        self.current[uri] = (identity, bytes(raw))
        self.publication_order.append(uri)
        return identity

    def seed(self, uri: str, raw: bytes) -> dict[str, object]:
        return self.publish_create_once(uri, raw)


def _prefix_descriptors(
    selected_ids: list[str], selected_rosters: list[list[str]],
) -> list[dict[str, object]]:
    rank_payload = {
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
    }
    rank_sha = grading.canonical_sha256(rank_payload)
    result: list[dict[str, object]] = []
    for entry_count in grading.PREFIX_SIZES:
        ids = selected_ids[:entry_count]
        rosters = selected_rosters[:entry_count]
        result.append(_with_hash({
            "schema_version": grading.freeze.PREFIX_DESCRIPTOR_SCHEMA,
            "entry_count": entry_count,
            "prefix_of_rank_80": True,
            "rank_80_payload_sha256": rank_sha,
            "prefix_payload_sha256": grading.canonical_sha256({
                "selected_lineup_ids": ids,
                "selected_rosters": rosters,
            }),
            "selected_lineup_ids_sha256": grading.canonical_sha256(ids),
            "selected_rosters_sha256": grading.canonical_sha256(rosters),
        }, "prefix_descriptor_sha256"))
    return result


def _synthetic_panel(*, reuse_book_ids_across_scopes: bool = False) -> _SyntheticPanel:
    root_identity = _identity("panel-freeze")
    manifest_identity = _identity("execution-manifest")
    panel_identity = _identity("panel-index")
    projection_identity = _identity("outcome-key-projection")
    source_identity = _identity("realized-source")
    snapshot_identity = _identity("outcome-snapshot")
    later_source_identity = _identity("later-source")
    strategies = [{
        "ordinal": strategy_ordinal,
        "strategy_id": f"strategy-{strategy_ordinal}",
        "strategy_sha256": _sha(f"strategy-{strategy_ordinal}"),
    } for strategy_ordinal in range(grading.STRATEGIES_PER_SCOPE)]
    root_rows: list[dict[str, object]] = []
    leaves_by_uri: dict[
        str,
        tuple[dict[str, object], dict[str, object], dict[str, object]],
    ] = {}
    player_scores: dict[tuple[int, str], int] = {}
    population_ids: dict[int, list[str]] = {}
    total_union_count = 0

    for source_ordinal in range(grading.SOURCE_SLATE_COUNT):
        season = 2020 + source_ordinal // 18
        week = source_ordinal % 18 + 1
        slate_id = f"{season}-w{week:02d}"
        slate = {"season": season, "week": week, "slate_id": slate_id}
        core_players = [
            f"s{source_ordinal:02d}-core-{index:02d}" for index in range(8)
        ]
        pairs: list[tuple[str, list[str], str]] = []
        for candidate_index in range(_UNION_COUNT):
            unique_player = f"s{source_ordinal:02d}-unique-{candidate_index:02d}"
            roster = sorted([*core_players, unique_player])
            pairs.append((canonical_lineup_id(slate, roster), roster, unique_player))
        pairs.sort(key=lambda row: row[0])
        population_lineup_ids = [row[0] for row in pairs]
        population_rosters = [row[1] for row in pairs]
        population_ids[source_ordinal] = population_lineup_ids
        total_union_count += len(pairs)

        for player_id in core_players:
            player_scores[(source_ordinal, player_id)] = 20 * MICRO_DK_PER_POINT
        special_unique_scores = {
            0: 40 * MICRO_DK_PER_POINT,
            1: 40 * MICRO_DK_PER_POINT + 1,
            2: 70 * MICRO_DK_PER_POINT,
            3: 70 * MICRO_DK_PER_POINT + 1,
        }
        for population_index, (_, _, unique_player) in enumerate(pairs):
            player_scores[(source_ordinal, unique_player)] = (
                special_unique_scores.get(
                    population_index, 10 * MICRO_DK_PER_POINT
                )
            )

        candidate_rows = [{
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
        } for lineup_id, roster, _ in pairs]
        scope_rows: list[dict[str, object]] = []
        descriptors: list[dict[str, object]] = []
        global_book_ordinal = 0
        for scope_ordinal, fit_scope_id in enumerate(grading.freeze.FIT_SCOPE_IDS):
            scope_books: list[dict[str, object]] = []
            for strategy_ordinal, strategy in enumerate(strategies):
                book_id = (
                    f"book-{strategy_ordinal}"
                    if reuse_book_ids_across_scopes
                    else f"book-{scope_ordinal}-{strategy_ordinal}"
                )
                book_sha = _sha(
                    f"book-sha-{source_ordinal}-{scope_ordinal}-{strategy_ordinal}"
                )
                offset = (
                    scope_ordinal * grading.STRATEGIES_PER_SCOPE
                    + strategy_ordinal
                ) % _UNION_COUNT
                selected_indices = [
                    (offset + index) % _UNION_COUNT
                    for index in range(grading.lane.ENTRY_BUDGET)
                ]
                selected_ids = [
                    population_lineup_ids[index] for index in selected_indices
                ]
                selected_rosters = [
                    population_rosters[index] for index in selected_indices
                ]
                book = {
                    "book_id": book_id,
                    "book_sha256": book_sha,
                    "fit_scope_id": fit_scope_id,
                    "strategy_id": strategy["strategy_id"],
                    "strategy_sha256": strategy["strategy_sha256"],
                    "entry_count": grading.lane.ENTRY_BUDGET,
                    "selected_lineup_ids": list(selected_ids),
                    "selected_rosters": deepcopy(selected_rosters),
                }
                scope_books.append(book)
                rank_payload = {
                    "selected_lineup_ids": selected_ids,
                    "selected_rosters": selected_rosters,
                }
                descriptors.append({
                    "global_book_ordinal": global_book_ordinal,
                    "scope_ordinal": scope_ordinal,
                    "scope_book_ordinal": strategy_ordinal,
                    "fit_scope_id": fit_scope_id,
                    "book_id": book_id,
                    "book_sha256": book_sha,
                    "strategy_ordinal": strategy_ordinal,
                    "strategy_id": strategy["strategy_id"],
                    "strategy_sha256": strategy["strategy_sha256"],
                    "entry_count": grading.lane.ENTRY_BUDGET,
                    "rank_80_payload_sha256": grading.canonical_sha256(rank_payload),
                    "selected_lineup_ids_sha256": grading.canonical_sha256(
                        selected_ids
                    ),
                    "selected_rosters_sha256": grading.canonical_sha256(
                        selected_rosters
                    ),
                    "prefix_count": len(grading.PREFIX_SIZES),
                    "prefixes": _prefix_descriptors(
                        selected_ids, selected_rosters
                    ),
                })
                global_book_ordinal += 1
            scope: dict[str, object] = {
                "fit_scope_id": fit_scope_id,
                "heldout_block": (
                    grading.rw.WORLD_BLOCKS[scope_ordinal]
                    if scope_ordinal < len(grading.rw.WORLD_BLOCKS)
                    else None
                ),
                "book_count": grading.STRATEGIES_PER_SCOPE,
                "books": scope_books,
            }
            if scope_ordinal == grading.SCOPES_PER_SLATE - 1:
                scope["candidate_view"] = {
                    "eligible_candidates": candidate_rows,
                    "eligible_count": len(candidate_rows),
                    "excluded_count": 0,
                }
                scope["admission"] = {
                    "admitted_lineup_ids": population_lineup_ids,
                    "admitted_count": len(population_lineup_ids),
                }
            scope_rows.append(scope)

        population_payload = [{
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
        } for lineup_id, roster, _ in pairs]
        union_descriptor = {
            "lineup_count": len(pairs),
            "ordered_lineup_ids_sha256": grading.canonical_sha256(
                population_lineup_ids
            ),
            "ordered_rosters_sha256": grading.canonical_sha256(
                population_rosters
            ),
            "ordered_population_sha256": grading.canonical_sha256(
                population_payload
            ),
            "eligible_equals_admitted": True,
            "excluded_count": 0,
            "population_descriptor_sha256": _sha(
                f"population-{source_ordinal}"
            ),
        }
        result_identity = _identity(f"task-result-{source_ordinal}")
        leaf_identity = _identity(f"slate-freeze-{source_ordinal}")
        result = {
            "task_result_sha256": _sha(f"task-result-sha-{source_ordinal}"),
            "full_union_surface": {
                "scope_count": grading.SCOPES_PER_SLATE,
                "books_per_scope": grading.STRATEGIES_PER_SCOPE,
                "book_count": grading.BOOKS_PER_SLATE,
                "prefix_sizes": list(grading.PREFIX_SIZES),
                "strategy_registry": deepcopy(strategies),
                "slate": slate,
                "scopes": scope_rows,
            },
        }
        leaf = {
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "slate_freeze_sha256": _sha(f"slate-freeze-sha-{source_ordinal}"),
            "manifest_identity": manifest_identity,
            "task_result_identity": result_identity,
            "all_block_union": union_descriptor,
            "book_count": grading.BOOKS_PER_SLATE,
            "prefix_count": grading.BOOKS_PER_SLATE * len(grading.PREFIX_SIZES),
            "book_descriptors": descriptors,
        }
        root_rows.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "slate_freeze_identity": leaf_identity,
            "slate_freeze_sha256": leaf["slate_freeze_sha256"],
            "task_result_identity": result_identity,
            "task_result_sha256": result["task_result_sha256"],
            "scope_count": grading.SCOPES_PER_SLATE,
            "book_count": grading.BOOKS_PER_SLATE,
            "prefix_count": grading.BOOKS_PER_SLATE * len(grading.PREFIX_SIZES),
        })
        leaves_by_uri[str(leaf_identity["uri"])] = (
            leaf, result, leaf_identity
        )

    root = {
        "panel_freeze_sha256": _sha("panel-freeze-sha"),
        "execution_manifest_sha256": _sha("execution-manifest-sha"),
        "manifest_identity": manifest_identity,
        "panel_index_identity": panel_identity,
        "panel_index_sha256": _sha("panel-index-sha"),
        "later_source_freeze_identity": later_source_identity,
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "fit_scope_ids": list(grading.freeze.FIT_SCOPE_IDS),
        "strategy_registry": deepcopy(strategies),
        "strategy_registry_sha256": grading.canonical_sha256(strategies),
        "prefix_sizes": list(grading.PREFIX_SIZES),
        "rank_80_book_count": grading.PANEL_BOOK_COUNT,
        "prefix_count": grading.PANEL_PREFIX_COUNT,
        "complete": True,
        "outcome_key_projection_inputs_frozen": True,
        "union_lineup_count": total_union_count,
        "slate_freezes": root_rows,
    }
    projection = {
        "panel_freeze_identity": root_identity,
        "panel_freeze_sha256": root["panel_freeze_sha256"],
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "required_player_count": len(player_scores),
        "outcome_key_count": len(player_scores),
        "all_block_union_lineup_count": total_union_count,
        "outcome_key_projection_sha256": _sha("projection-sha"),
    }
    source = {"realized_source_sha256": _sha("realized-source-sha")}
    snapshot = {
        "panel_freeze_identity": root_identity,
        "panel_freeze_sha256": root["panel_freeze_sha256"],
        "outcome_key_projection_identity": projection_identity,
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "later_source_freeze_identity": later_source_identity,
        "later_source_freeze_sha256": _sha("later-source-sha"),
        "realized_source_identity": source_identity,
        "realized_source_sha256": source["realized_source_sha256"],
        "outcome_snapshot_sha256": _sha("outcome-snapshot-sha"),
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "row_count": len(player_scores),
        "exact_union_coverage": True,
        "lineup_scoring_performed": False,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
    }
    return _SyntheticPanel(
        root=root,
        root_identity=root_identity,
        leaves_by_uri=leaves_by_uri,
        projection=projection,
        projection_identity=projection_identity,
        source=source,
        source_identity=source_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        player_scores=player_scores,
        population_ids=population_ids,
    )


def _install_validators(
    monkeypatch: pytest.MonkeyPatch,
    panel: _SyntheticPanel,
    *,
    player_scores: dict[tuple[int, str], int] | None = None,
) -> None:
    monkeypatch.setattr(
        grading.freeze,
        "reopen_panel_freeze_v1",
        lambda panel_freeze_identity, *, read_exact: (
            panel.root, panel.root_identity
        ),
    )

    def reopen_slate(identity: object, *, read_exact: object) -> tuple[Any, ...]:
        uri = str(dict(identity)["uri"])  # type: ignore[arg-type]
        leaf, result, retained_identity = panel.leaves_by_uri[uri]
        return leaf, {}, {}, [], result, retained_identity

    monkeypatch.setattr(
        grading.freeze, "reopen_slate_freeze_v1", reopen_slate
    )
    monkeypatch.setattr(
        grading.outcomes,
        "validate_outcome_snapshot_v1",
        lambda value, **kwargs: (
            panel.snapshot,
            panel.snapshot_identity,
            panel.player_scores if player_scores is None else player_scores,
        ),
    )


def _grade(panel: _SyntheticPanel) -> tuple[dict[str, object], list[dict[str, object]]]:
    return grading.grade_r6_full_union_realized_v1(
        panel_freeze_identity=panel.root_identity,
        outcome_key_projection=panel.projection,
        outcome_key_projection_identity=panel.projection_identity,
        realized_source=panel.source,
        realized_source_identity=panel.source_identity,
        outcome_snapshot=panel.snapshot,
        outcome_snapshot_identity=panel.snapshot_identity,
        read_exact=lambda _: b"not-called-by-synthetic-validator",
    )


def _publish(
    panel: _SyntheticPanel, store: _MemoryStore,
    *, publish_create_once: Any | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    return grading.grade_and_publish_r6_full_union_realized_v1(
        panel_freeze_identity=panel.root_identity,
        outcome_key_projection=panel.projection,
        outcome_key_projection_identity=panel.projection_identity,
        realized_source=panel.source,
        realized_source_identity=panel.source_identity,
        outcome_snapshot=panel.snapshot,
        outcome_snapshot_identity=panel.snapshot_identity,
        output_prefix="gs://synthetic-r6/realized-grade-v1",
        read_exact=store.read_exact,
        publish_create_once=(
            store.publish_create_once
            if publish_create_once is None else publish_create_once
        ),
    )


def test_complete_grade_scores_union_once_and_builds_exact_54_by_144(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    _install_validators(monkeypatch, panel)
    original = grading._RosterSumCounter.score
    calls = 0

    def counted(self: object, **kwargs: object) -> int:
        nonlocal calls
        calls += 1
        return original(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(grading._RosterSumCounter, "score", counted)
    root, shards = _grade(panel)

    coverage = root["coverage"]
    assert len(shards) == 54
    assert root["aggregate_cell_count"] == 144
    assert len(root["aggregate_cells"]) == 144
    assert all(len(cell["slate_rows"]) == 54 for cell in root["aggregate_cells"])
    assert coverage["rank_80_book_count"] == 54 * 48
    assert coverage["prefix_grade_count"] == 54 * 48 * 3
    assert calls == coverage["unique_final_union_roster_count"]
    assert calls == coverage["roster_sum_operation_count"]
    assert calls == coverage["roster_sum_operation_ceiling"]
    assert coverage["roster_sum_operation_ceiling_equals_final_union_count"] is True
    assert [row["threshold_dk"] for row in root["threshold_registry"]] == [
        187, 194, 200, 210, 220, 230, 240
    ]
    assert root["contest_metrics"]["rank"] is None
    assert root["contest_metrics"]["roi_micro_usd"] is None

    first = shards[0]
    assert first["union_lineup_count"] == _UNION_COUNT
    assert len(first["book_grades"][0]["rank_80_score_rows"]) == 80
    assert (
        first["book_grades"][0]["rank_80_score_rows"]
        != first["book_grades"][1]["rank_80_score_rows"]
    )
    assert (
        shards[0]["book_grades"][0]["book_id"]
        == shards[1]["book_grades"][0]["book_id"]
    )
    tails = {
        row["tail_id"]: row for row in first["union_metrics"]["tail_identity_subsets"]
    }
    assert tails["ge-200"]["lineup_count"] == 4
    assert tails["gt-200"]["lineup_count"] == 3
    assert tails["gt-230"]["lineup_count"] == 1
    assert tails["ge-200"]["lineup_ids"] == panel.population_ids[0][:4]
    book = first["book_grades"][0]
    assert [row["entry_count"] for row in book["prefixes"]] == [4, 14, 80]
    assert all("rank_80_score_rows" not in row for row in book["prefixes"])
    assert all(row["roster_sum_operation_count"] == 0 for row in book["prefixes"])


def test_reused_bare_book_ids_across_scopes_cannot_overwrite_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel(reuse_book_ids_across_scopes=True)
    _install_validators(monkeypatch, panel)
    root, shards = _grade(panel)

    scope_zero_book = shards[0]["book_grades"][0]
    scope_one_book = shards[0]["book_grades"][8]
    assert scope_zero_book["book_id"] == scope_one_book["book_id"]
    assert (
        scope_zero_book["book_coordinate_sha256"]
        != scope_one_book["book_coordinate_sha256"]
    )
    cell_coordinates = {
        (cell["scope_ordinal"], cell["strategy_ordinal"], cell["entry_count"])
        for cell in root["aggregate_cells"]
    }
    assert (0, 0, 4) in cell_coordinates
    assert (1, 0, 4) in cell_coordinates
    assert len(cell_coordinates) == 144


def test_root_last_publisher_binds_54_shard_identities_and_replays_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    store = _MemoryStore()
    _install_validators(monkeypatch, panel)
    persisted, persisted_identity = _publish(panel, store)

    assert persisted["schema_version"] == grading.PERSISTED_ROOT_SCHEMA
    assert persisted["source_slate_count"] == 54
    assert len(persisted["slate_grade_objects"]) == 54
    assert store.publication_order[-1] == persisted["target_uri"]
    assert all(
        uri != persisted["target_uri"] for uri in store.publication_order[:-1]
    )
    assert len(store.publication_order) == 55
    replayed, replayed_identity, logical, shards = (
        grading.validate_persisted_realized_grade_v1(
            persisted,
            identity=persisted_identity,
            panel_freeze_identity=panel.root_identity,
            outcome_key_projection=panel.projection,
            outcome_key_projection_identity=panel.projection_identity,
            realized_source=panel.source,
            realized_source_identity=panel.source_identity,
            outcome_snapshot=panel.snapshot,
            outcome_snapshot_identity=panel.snapshot_identity,
            read_exact=store.read_exact,
        )
    )
    assert replayed == persisted
    assert replayed_identity == persisted_identity
    assert logical == persisted["logical_grade_root"]
    assert len(shards) == 54


def test_partial_publication_retry_recovers_equal_bytes_and_finishes_root_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    store = _MemoryStore()
    _install_validators(monkeypatch, panel)
    calls = 0

    def interrupted(uri: str, raw: bytes) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 12:
            raise RuntimeError("synthetic interruption")
        return store.publish_create_once(uri, raw)

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        _publish(panel, store, publish_create_once=interrupted)
    assert len(store.publication_order) == 11

    persisted, _ = _publish(panel, store)
    assert len(store.publication_order) == 55
    assert store.publication_order[-1] == persisted["target_uri"]


def test_equal_byte_recovery_identity_must_exact_open_intended_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    store = _MemoryStore()
    _install_validators(monkeypatch, panel)

    def ambiguous(uri: str, raw: bytes) -> dict[str, object]:
        identity = store.publish_create_once(uri, raw)
        bad = dict(identity)
        bad["generation"] = "999999"
        store.values[store._key(bad)] = b"x" * len(raw)
        return bad

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="exact-read bytes differ",
    ):
        _publish(panel, store, publish_create_once=ambiguous)


def test_differing_create_once_collision_fails_before_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    store = _MemoryStore()
    _install_validators(monkeypatch, panel)
    first_uri = "gs://synthetic-r6/realized-grade-v1/slate-grades/00-2020-w01.json"
    store.seed(first_uri, b"different-existing-bytes")

    with pytest.raises(RuntimeError, match="create-once collision differs"):
        _publish(panel, store)
    assert not any(uri.endswith("realized-grade-root.json")
                   for uri in store.publication_order)


def test_publisher_exact_opens_terminal_root_before_returning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    store = _MemoryStore()
    _install_validators(monkeypatch, panel)
    original_read_exact = store.read_exact

    def corrupt_root_read(identity: object) -> bytes:
        raw = original_read_exact(identity)
        if str(dict(identity)["uri"]).endswith("realized-grade-root.json"):
            return b"x" * len(raw)
        return raw

    monkeypatch.setattr(store, "read_exact", corrupt_root_read)
    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="exact-read bytes differ",
    ):
        _publish(panel, store)


@pytest.mark.parametrize("field", ["uri", "generation", "sha256", "bytes"])
def test_persisted_root_identity_splice_is_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str,
) -> None:
    panel = _synthetic_panel()
    store = _MemoryStore()
    _install_validators(monkeypatch, panel)
    persisted, identity = _publish(panel, store)
    spliced = dict(identity)
    spliced[field] = (
        int(spliced[field]) + 1 if field == "bytes" else "spliced"
    )

    with pytest.raises((KeyError, grading.CorpusR6FullUnionRealizedGradingV1Error)):
        grading.validate_persisted_realized_grade_v1(
            persisted,
            identity=spliced,
            panel_freeze_identity=panel.root_identity,
            outcome_key_projection=panel.projection,
            outcome_key_projection_identity=panel.projection_identity,
            realized_source=panel.source,
            realized_source_identity=panel.source_identity,
            outcome_snapshot=panel.snapshot,
            outcome_snapshot_identity=panel.snapshot_identity,
            read_exact=store.read_exact,
        )


@pytest.mark.parametrize("field", ["uri", "generation", "sha256", "bytes"])
def test_persisted_shard_identity_splice_is_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str,
) -> None:
    panel = _synthetic_panel()
    store = _MemoryStore()
    _install_validators(monkeypatch, panel)
    persisted, _ = _publish(panel, store)
    forged = deepcopy(persisted)
    row = forged["slate_grade_objects"][0]
    shard_identity = row["slate_grade_identity"]
    shard_identity[field] = (
        int(shard_identity[field]) + 1 if field == "bytes" else "spliced"
    )
    forged["slate_grade_objects"][0] = _rehash(
        row, "slate_grade_object_sha256"
    )
    forged["slate_grade_objects_sha256"] = grading.canonical_sha256(
        forged["slate_grade_objects"]
    )
    forged = _rehash(forged, "persisted_grade_root_sha256")
    forged_raw = grading.canonical_json_bytes(forged)
    forged_identity = {
        "uri": forged["target_uri"],
        "generation": "forged",
        "sha256": sha256(forged_raw).hexdigest(),
        "bytes": len(forged_raw),
    }
    store.values[store._key(forged_identity)] = forged_raw

    with pytest.raises((KeyError, grading.CorpusR6FullUnionRealizedGradingV1Error)):
        grading.validate_persisted_realized_grade_v1(
            forged,
            identity=forged_identity,
            panel_freeze_identity=panel.root_identity,
            outcome_key_projection=panel.projection,
            outcome_key_projection_identity=panel.projection_identity,
            realized_source=panel.source,
            realized_source_identity=panel.source_identity,
            outcome_snapshot=panel.snapshot,
            outcome_snapshot_identity=panel.snapshot_identity,
            read_exact=store.read_exact,
        )


def test_scope_coordinate_collision_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    first_leaf, first_result, _ = next(iter(panel.leaves_by_uri.values()))
    first_result["full_union_surface"]["scopes"][1]["fit_scope_id"] = (
        grading.freeze.FIT_SCOPE_IDS[0]
    )
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match=r"scope\[1\] lattice differs",
    ):
        _grade(panel)


def test_heldout_block_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    _, first_result, _ = next(iter(panel.leaves_by_uri.values()))
    first_result["full_union_surface"]["scopes"][0]["heldout_block"] = "R4"
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match=r"scope\[0\] lattice differs",
    ):
        _grade(panel)


def test_wrong_first_4_14_80_prefix_order_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    first_leaf, _, _ = next(iter(panel.leaves_by_uri.values()))
    prefixes = first_leaf["book_descriptors"][0]["prefixes"]
    prefixes[0], prefixes[1] = prefixes[1], prefixes[0]
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="first-4 prefix differs",
    ):
        _grade(panel)


def test_selected_roster_substitution_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    _, first_result, _ = next(iter(panel.leaves_by_uri.values()))
    first_book = first_result["full_union_surface"]["scopes"][0]["books"][0]
    first_book["selected_rosters"][0] = deepcopy(
        first_book["selected_rosters"][1]
    )
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="roster/coordinate binding differs",
    ):
        _grade(panel)


def test_duplicate_rank_80_lineup_id_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    _, first_result, _ = next(iter(panel.leaves_by_uri.values()))
    first_book = first_result["full_union_surface"]["scopes"][0]["books"][0]
    first_book["selected_lineup_ids"][0] = first_book["selected_lineup_ids"][1]
    first_book["selected_rosters"][0] = deepcopy(
        first_book["selected_rosters"][1]
    )
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="roster/coordinate binding differs",
    ):
        _grade(panel)


def test_root_strategy_to_result_splice_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    panel.root["strategy_registry"][0]["strategy_id"] = "spliced-strategy"
    panel.root["strategy_registry_sha256"] = grading.canonical_sha256(
        panel.root["strategy_registry"]
    )
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="root/result strategy splice differs",
    ):
        _grade(panel)


def test_book_descriptor_sha_splice_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    first_leaf, _, _ = next(iter(panel.leaves_by_uri.values()))
    first_leaf["book_descriptors"][0]["book_sha256"] = _sha("spliced-book")
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="roster/coordinate binding differs",
    ):
        _grade(panel)


def test_coherently_rehashed_rank_and_prefix_descriptor_splice_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    first_leaf, first_result, _ = next(iter(panel.leaves_by_uri.values()))
    first_book = first_result["full_union_surface"]["scopes"][0]["books"][0]
    descriptor = first_leaf["book_descriptors"][0]
    selected_ids = list(reversed(first_book["selected_lineup_ids"]))
    selected_rosters = list(reversed(first_book["selected_rosters"]))
    descriptor["rank_80_payload_sha256"] = grading.canonical_sha256({
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
    })
    descriptor["selected_lineup_ids_sha256"] = grading.canonical_sha256(
        selected_ids
    )
    descriptor["selected_rosters_sha256"] = grading.canonical_sha256(
        selected_rosters
    )
    descriptor["prefixes"] = _prefix_descriptors(
        selected_ids, selected_rosters
    )
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="rank-80 descriptor binding differs",
    ):
        _grade(panel)


def test_snapshot_to_root_identity_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    panel.snapshot["panel_freeze_identity"] = _identity("wrong-panel-root")
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="snapshot/root authority binding differs",
    ):
        _grade(panel)


@pytest.mark.parametrize("missing_part", ["slate", "book"])
def test_incomplete_54_by_48_is_rejected(
    monkeypatch: pytest.MonkeyPatch, missing_part: str,
) -> None:
    panel = _synthetic_panel()
    if missing_part == "slate":
        panel.root["slate_freezes"].pop()
    else:
        first_leaf, first_result, _ = next(iter(panel.leaves_by_uri.values()))
        first_result["full_union_surface"]["scopes"][0]["books"].pop()
        first_leaf["book_descriptors"].pop(0)
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match=(
            r"complete 54x48|scope\[0\] lattice differs|"
            r"does not contain complete 48-book coverage"
        ),
    ):
        _grade(panel)


@pytest.mark.parametrize("mismatch", ["missing", "extra"])
def test_outcome_key_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch, mismatch: str,
) -> None:
    panel = _synthetic_panel()
    altered = dict(panel.player_scores)
    if mismatch == "missing":
        altered.pop(next(iter(altered)))
    else:
        altered[(0, "not-in-final-union")] = 1
    _install_validators(monkeypatch, panel, player_scores=altered)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="does not exactly equal the final-union player set",
    ):
        _grade(panel)


def test_contest_rank_or_roi_input_is_rejected_without_field_payout_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _synthetic_panel()
    _install_validators(monkeypatch, panel)

    with pytest.raises(
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        match="contest rank/ROI is unavailable",
    ):
        grading.grade_r6_full_union_realized_v1(
            panel_freeze_identity=panel.root_identity,
            outcome_key_projection=panel.projection,
            outcome_key_projection_identity=panel.projection_identity,
            realized_source=panel.source,
            realized_source_identity=panel.source_identity,
            outcome_snapshot=panel.snapshot,
            outcome_snapshot_identity=panel.snapshot_identity,
            read_exact=lambda _: b"not-called",
            contest_field={"rank": 1},
        )


def test_real_task0_freeze_structure_scores_with_synthetic_outcomes() -> None:
    receipt = batch.parse_canonical_json_bytes(
        _TASK0_RECEIPT.read_bytes(), label="real task0 smoke receipt"
    )
    receipt = task0_smoke.validate_receipt_v1(receipt)
    result = receipt["execution_result"]
    union_descriptor, _, book_descriptors = grading.freeze._derive_descriptors(
        result
    )
    task_result_identity = _identity("real-task0-result")
    leaf_identity = _identity("real-task0-leaf")
    leaf = {
        "source_ordinal": 0,
        "slate_id": result["slate_id"],
        "slate_freeze_sha256": _sha("real-task0-leaf-sha"),
        "task_result_identity": task_result_identity,
        "all_block_union": union_descriptor,
        "book_count": grading.BOOKS_PER_SLATE,
        "prefix_count": grading.BOOKS_PER_SLATE * len(grading.PREFIX_SIZES),
        "book_descriptors": book_descriptors,
    }
    population, roster_by_lineup, _, scopes, strategies = (
        grading._population_from_result(
            source_ordinal=0, result=result, leaf=leaf
        )
    )
    books = grading._books_from_result(
        source_ordinal=0,
        scopes=scopes,
        strategies=strategies,
        leaf=leaf,
        roster_by_lineup=roster_by_lineup,
    )
    prepared = grading._PreparedSlate(
        source_ordinal=0,
        slate_id=str(result["slate_id"]),
        leaf=leaf,
        leaf_identity=leaf_identity,
        result=result,
        population=population,
        books=books,
    )
    player_scores = {
        (0, player_id): MICRO_DK_PER_POINT
        for _, roster in population
        for player_id in roster
    }
    root_identity = _identity("real-task0-root")
    root = {"panel_freeze_sha256": _sha("real-task0-root-sha")}
    snapshot_identity = _identity("real-task0-snapshot")
    snapshot = {"outcome_snapshot_sha256": _sha("real-task0-snapshot-sha")}
    shard = grading._slate_grade(
        prepared=prepared,
        root=root,
        root_identity=root_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        player_scores=player_scores,
    )

    assert shard["union_lineup_count"] == 3_815
    assert shard["roster_sum_operation_count"] == 3_815
    assert shard["roster_sum_operation_ceiling"] == 3_815
    assert shard["book_grade_count"] == 48
    assert all(
        book["roster_sum_operation_count"] == 0
        for book in shard["book_grades"]
    )
