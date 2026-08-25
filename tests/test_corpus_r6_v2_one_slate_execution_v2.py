from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_matchup_source_v1 as matchup_source
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution_v1
from nfl_dfs.research import corpus_r6_v2_one_slate_execution_v2 as execution
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import _score_matrix_sha256


SLATE = {
    "season": 2023,
    "week": 1,
    "slate_id": "2023-w01",
    "task_id": "slate-2023-w1",
}
PROVENANCE_SLATE = {
    key: SLATE[key] for key in ("season", "week", "slate_id")
}
LOCK_TIME = "2023-09-10T17:00:00Z"
OBSERVED_AT = "2026-08-25T11:58:00Z"
COMPONENTS = ("component_a", "component_b")
PLAYERS = (
    ("00-001", "qb", "QB", "AAA", "BBB", True, 0.2),
    ("00-002", "rb", "RB", "AAA", "BBB", None, 0.4),
    ("00-003", "receiver", "WR", "AAA", "BBB", None, 0.6),
    ("00-004", "receiver", "TE", "BBB", "AAA", None, 0.8),
)
DST_PLAYER = {
    "id": "00-005",
    "name": "00-005",
    "pos": "DST",
    "team": "BBB",
    "opp": "AAA",
    "game_id": "AAA|BBB",
    "salary": 3000,
    "proj": 7.0,
}


def _raw(value: object) -> bytes:
    return matchup_source.canonical_json_bytes(value)


def _identity(uri: str, raw: bytes, generation: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _self_hash(
    body: Mapping[str, object], field: str
) -> dict[str, object]:
    result = deepcopy(dict(body))
    result[field] = matchup_source.canonical_sha256(result)
    return result


class ExactObjectStore:
    """Injected create-once, generation-aware storage for corrected sources."""

    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.next_generation = 1000

    def seed(self, uri: str, raw: bytes) -> dict[str, object]:
        identity = _identity(uri, raw, "900")
        self.objects[uri] = {"identity": identity, "raw": raw}
        return deepcopy(identity)

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.objects:
            raise matchup_source.CorpusR6MatchupSourceV1Error(
                "create-once collision"
            )
        identity = _identity(uri, raw, str(self.next_generation))
        self.next_generation += 1
        self.objects[uri] = {"identity": identity, "raw": raw}
        return deepcopy(identity)

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        retained = self.objects.get(str(identity["uri"]))
        if retained is None or retained["identity"] != identity:
            raise matchup_source.CorpusR6MatchupSourceV1Error(
                "exact identity/generation differs"
            )
        return bytes(retained["raw"])


def _family_definition(family: str, role: str) -> dict[str, object]:
    role_schema = matchup_source.build_source_role_schema_v1(
        role=role,
        row_fields=sorted({
            "role",
            "source_season",
            "source_week",
            "source_event_time_utc",
            "observed_at_utc",
            "target_season",
            "target_week",
            "target_slate_id",
            "target_task_id",
            "gsis_id",
            "family",
            "team",
            "opponent",
            "game_id",
            "component",
            "component_value",
            "component_supported",
            "missing_reason_code",
        }),
        source_period_kind="prior-season-full",
        population_role="component",
    )
    return _self_hash({
        "schema_version": matchup_source.FAMILY_DEFINITION_SCHEMA,
        "family_id": f"{family}-matchup",
        "version": 2,
        "provisional": True,
        "source_roles": [role],
        "fields": [
            {
                "name": component,
                "field_type": "percentile",
                "nullable": True,
                "description": f"outcome-blind fixture {component}",
            }
            for component in COMPONENTS
        ],
        "missing_reason_codes": ["source-absent"],
        "description": "corrected one-slate executor fixture",
        "source_role_schemas": {role: role_schema},
        "component_source_roles": {
            component: [role] for component in COMPONENTS
        },
    }, "family_definition_sha256")


def _extract(
    *,
    role: str,
    schema_sha256: str,
    rows: list[dict[str, object]],
    period_kind: str,
    period: dict[str, object],
    maximum_event: str,
) -> dict[str, object]:
    rows_sha = matchup_source.canonical_sha256(rows)
    return {
        "role": role,
        "relation_or_object": (
            "bq://fixture_project.fixture_dataset."
            f"{role.replace('-', '_')}"
        ),
        "source_identity_or_extract_sha256": rows_sha,
        "source_role_schema_sha256": schema_sha256,
        "rows": rows,
        "rows_sha256": rows_sha,
        "row_count": len(rows),
        "source_period_kind": period_kind,
        "source_season_week_min": period,
        "source_season_week_max": period,
        "maximum_source_event_time_utc": maximum_event,
        "observed_at_utc": OBSERVED_AT,
        "observed_at_basis": "historical-source-period-only",
        "evidence_class": matchup_source.EVIDENCE_RETROSPECTIVE,
        "missingness_reason": None,
    }


def _base_catalog_players(
    skill_players: tuple[
        tuple[str, str, str, str, str, bool | None, float], ...
    ] = PLAYERS,
) -> list[dict[str, object]]:
    return [
        {
            "id": player_id,
            "name": player_id,
            "pos": position,
            "team": team,
            "opp": opponent,
            "game_id": "AAA|BBB",
            "salary": 6000,
            "proj": 15.0,
        }
        for player_id, _, position, team, opponent, _, _ in skill_players
    ] + [deepcopy(DST_PLAYER)]


def _capture_corrected_matchup_source(
    *,
    slate: Mapping[str, object] = SLATE,
    skill_players: tuple[
        tuple[str, str, str, str, str, bool | None, float], ...
    ] = PLAYERS,
    catalog_players: list[dict[str, object]] | None = None,
    catalog_transform: Callable[
        [list[dict[str, object]]], list[dict[str, object]]
    ] | None = None,
) -> tuple[
    ExactObjectStore,
    dict[str, Mapping[str, object]],
]:
    families = {
        family: _family_definition(family, f"{family}-prior-context")
        for family in matchup_source.ELIGIBLE_FAMILIES
    }
    extracts: list[dict[str, object]] = []
    annotations: list[dict[str, object]] = []
    for family in matchup_source.ELIGIBLE_FAMILIES:
        role = f"{family}-prior-context"
        rows: list[dict[str, object]] = []
        for player_id, player_family, position, team, opponent, depth, edge in skill_players:
            if player_family != family:
                continue
            for component in COMPONENTS:
                rows.append({
                    "role": role,
                    "source_season": 2022,
                    "source_week": None,
                    "source_event_time_utc": "2023-02-12T23:00:00Z",
                    "observed_at_utc": OBSERVED_AT,
                    "target_season": slate["season"],
                    "target_week": slate["week"],
                    "target_slate_id": slate["slate_id"],
                    "target_task_id": slate["task_id"],
                    "gsis_id": player_id,
                    "family": family,
                    "team": team,
                    "opponent": opponent,
                    "game_id": "AAA|BBB",
                    "component": component,
                    "component_value": edge,
                    "component_supported": True,
                    "missing_reason_code": None,
                })
            bound = {
                "source_roles": [role],
                "source_season_week_min": {"season": 2022, "week": None},
                "source_season_week_max": {"season": 2022, "week": None},
                "maximum_source_event_time_utc": "2023-02-12T23:00:00Z",
                "evidence_class": matchup_source.EVIDENCE_RETROSPECTIVE,
            }
            annotations.append({
                "gsis_id": player_id,
                "family": family,
                "position": position,
                "qb_depth1": depth,
                "qb_depth_evidence_class": (
                    matchup_source.EVIDENCE_RETROSPECTIVE
                    if family == "qb"
                    else "not-applicable"
                ),
                "component_values": {
                    component: edge for component in COMPONENTS
                },
                "component_support": {
                    component: True for component in COMPONENTS
                },
                "component_source_bounds": {
                    component: bound for component in COMPONENTS
                },
                "component_missing_reason_codes": {
                    component: [] for component in COMPONENTS
                },
                "matchup_component_count": len(COMPONENTS),
                "matchup_edge_score": edge,
            })
        rows.sort(key=lambda row: (str(row["gsis_id"]), str(row["component"])))
        extracts.append(_extract(
            role=role,
            schema_sha256=str(
                families[family]["source_role_schemas"][role][
                    "source_role_schema_sha256"
                ]
            ),
            rows=rows,
            period_kind="prior-season-full",
            period={"season": 2022, "week": None},
            maximum_event="2023-02-12T23:00:00Z",
        ))
    annotations.sort(key=lambda row: str(row["gsis_id"]))

    infrastructure = matchup_source.infrastructure_source_role_schemas_v1()
    schedule_rows = [
        {
            "role": matchup_source.SCHEDULE_SOURCE_ROLE,
            "source_season": 2023,
            "source_week": 1,
            "source_event_time_utc": "2023-09-01T12:00:00Z",
            "observed_at_utc": OBSERVED_AT,
            "season": 2023,
            "week": 1,
            "slate_id": slate["slate_id"],
            "task_id": slate["task_id"],
            "game_id": "AAA|BBB",
            "team": team,
            "opponent": opponent,
            "kickoff_time_utc": LOCK_TIME,
            "lock_time_utc": LOCK_TIME,
        }
        for team, opponent in (("AAA", "BBB"), ("BBB", "AAA"))
    ]
    extracts.append(_extract(
        role=matchup_source.SCHEDULE_SOURCE_ROLE,
        schema_sha256=str(
            infrastructure[matchup_source.SCHEDULE_SOURCE_ROLE][
                "source_role_schema_sha256"
            ]
        ),
        rows=schedule_rows,
        period_kind="prelock-snapshot",
        period={"season": 2023, "week": 1},
        maximum_event="2023-09-01T12:00:00Z",
    ))
    depth_rows = [
        {
            "role": matchup_source.QB_DEPTH_SOURCE_ROLE,
            "source_season": 2023,
            "source_week": 1,
            "source_event_time_utc": "2023-09-10T16:00:00Z",
            "observed_at_utc": OBSERVED_AT,
            "season": 2023,
            "week": 1,
            "slate_id": slate["slate_id"],
            "task_id": slate["task_id"],
            "gsis_id": player_id,
            "team": team,
            "game_id": "AAA|BBB",
            "depth1": depth,
            "missingness_reason": None if depth is not None else "source-absent",
        }
        for player_id, family, _, team, _, depth, _ in skill_players
        if family == "qb"
    ]
    depth_rows.sort(key=lambda row: str(row["gsis_id"]))
    extracts.append(_extract(
        role=matchup_source.QB_DEPTH_SOURCE_ROLE,
        schema_sha256=str(
            infrastructure[matchup_source.QB_DEPTH_SOURCE_ROLE][
                "source_role_schema_sha256"
            ]
        ),
        rows=depth_rows,
        period_kind="prelock-snapshot",
        period={"season": 2023, "week": 1},
        maximum_event="2023-09-10T16:00:00Z",
    ))
    extracts.sort(key=lambda row: str(row["role"]))

    catalog_players = deepcopy(
        _base_catalog_players(skill_players)
        if catalog_players is None
        else catalog_players
    )
    if catalog_transform is not None:
        catalog_players = catalog_transform(deepcopy(catalog_players))
    catalog_players.sort(key=lambda row: str(row["id"]))
    catalog = _self_hash({
        "schema_version": matchup_source.PLAYER_CATALOG_SCHEMA,
        "task_id": slate["task_id"],
        "source_authority": _identity(
            "gs://fixture/catalog-authority.json", b"catalog-authority", "800"
        ),
        "players": catalog_players,
    }, "player_catalog_sha256")
    catalog_raw = _raw(catalog)
    store = ExactObjectStore()
    catalog_identity = store.seed(
        "gs://fixture/r6-executor-v2/player-catalog.json", catalog_raw
    )
    relations = [
        {
            "role": str(extract["role"]),
            "table_or_object": str(extract["relation_or_object"]),
            "schema_sha256": str(extract["source_role_schema_sha256"]),
            "etag_or_generation": f"etag-{ordinal}",
            "modified_or_created_at_utc": OBSERVED_AT,
            "exact_extract_sha256": str(extract["rows_sha256"]),
            "row_count": int(extract["row_count"]),
        }
        for ordinal, extract in enumerate(extracts)
    ]
    identities = matchup_source.capture_matchup_source_v1(
        slate=slate,
        lock_time_utc=LOCK_TIME,
        player_catalog_identity=catalog_identity,
        player_catalog_raw=catalog_raw,
        rendered_sql_raw=matchup_source.build_rendered_sql_v1(relations),
        query_job_receipt={
            "created_at_utc": "2026-08-25T12:05:00Z",
            "query_parameters": {
                "season": slate["season"],
                "week": slate["week"],
                "slate_id": slate["slate_id"],
                "task_id": slate["task_id"],
                "lock_time_utc": LOCK_TIME,
                "source_roles": sorted(
                    str(extract["role"]) for extract in extracts
                ),
            },
            "query_snapshot_at_utc": "2026-08-25T11:59:00Z",
            "query_job": {
                "project": "fixture-project",
                "location": "US",
                "job_id": "r6_executor_v2_fixture",
                "created": "2026-08-25T12:00:00Z",
                "started": "2026-08-25T12:01:00Z",
                "ended": "2026-08-25T12:02:00Z",
                "cache_hit": False,
                "error_result": None,
                "total_bytes_processed": 1234,
            },
            "source_relations": relations,
            "player_catalog_evidence": {
                "maximum_source_event_time_utc": "2023-09-10T16:00:00Z",
                "observed_at_utc": OBSERVED_AT,
                "observed_at_basis": "historical-source-period-only",
                "evidence_class": matchup_source.EVIDENCE_RETROSPECTIVE,
            },
        },
        component_extracts=extracts,
        annotation_rows=annotations,
        family_definition_identities=families,
        code_identity={
            "schema_version": "r6-matchup-source-code/v1",
            "source_commit": "b" * 40,
            "uses_realized_outcomes": False,
        },
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
        output_prefix="gs://fixture/r6-executor-v2/corrected-source",
    )
    identities = {
        **identities,
        "player_catalog_identity": catalog_identity,
    }
    matchup_source.reopen_matchup_source_snapshot(
        source_export_identity=identities["source_export_identity"],
        query_receipt_identity=identities["query_receipt_identity"],
        player_catalog_identity=identities["player_catalog_identity"],
        read_exact=store.read_exact,
        expected_slate=slate,
        required_evidence_class=matchup_source.EVIDENCE_RETROSPECTIVE,
    )
    return store, identities


def _placeholder_identity(name: str) -> dict[str, object]:
    raw = name.encode("utf-8")
    return _identity(f"gs://fixture/{name}.json", raw, "1")


def _accepted_reconstruction() -> execution_v1.AcceptedV12SlateReconstruction:
    imported = SimpleNamespace(
        compatibility_receipt={
            "compatibility_import_sha256": "1" * 64,
        }
    )
    reconstructed = SimpleNamespace(
        prepared=SimpleNamespace(
            season=SLATE["season"],
            week=SLATE["week"],
            slate_id=SLATE["slate_id"],
            players=tuple(
                SimpleNamespace(
                    player_id=row["id"],
                    position=row["pos"],
                    team=row["team"],
                    opponent=row["opp"],
                    game_id=row["game_id"],
                    salary=row["salary"],
                )
                for row in _base_catalog_players()
            ),
        ),
        provenance={
            "slate": dict(PROVENANCE_SLATE),
            "candidate_provenance_sha256": "2" * 64,
        },
        union_scores=np.zeros((1, 1), dtype=np.float64),
        reconstruction_receipt={
            "reconstruction_sha256": "3" * 64,
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        },
    )
    return execution_v1.AcceptedV12SlateReconstruction(
        slate_id=str(SLATE["slate_id"]),
        panel_index_identity=_placeholder_identity("panel-index"),
        panel_index_sha256="a" * 64,
        accepted_slate_membership={
            "slate_id": SLATE["slate_id"],
            "task_ordinal": 0,
            "source_task_ordinal": 0,
        },
        task_acceptance_identity=_placeholder_identity("task-acceptance"),
        carrier_identity=_placeholder_identity("task-carrier"),
        later_source_freeze_identity=_placeholder_identity("source-freeze"),
        world_artifact_identities={
            role: _placeholder_identity(f"world-{role}")
            for role in batch.TASK_WORLD_SOURCE_ROLES
        },
        imported=imported,
        reconstructed=reconstructed,
    )


def _real_runner_accepted_reconstruction() -> tuple[
    execution_v1.AcceptedV12SlateReconstruction,
    tuple[tuple[str, str, str, str, str, bool | None, float], ...],
    list[dict[str, object]],
]:
    """Build a small-dose but otherwise real 5-fold/7-law runner fixture."""
    candidate_count = 108
    candidates: list[dict[str, object]] = []
    skill_players: list[
        tuple[str, str, str, str, str, bool | None, float]
    ] = []
    catalog_players: list[dict[str, object]] = []
    positions = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST")
    for index in range(candidate_count):
        roster = [f"real-{index:03d}-{slot}" for slot in range(9)]
        for slot, (player_id, position) in enumerate(zip(
            roster, positions, strict=True
        )):
            is_dst = position == "DST"
            team = "BBB" if is_dst else "AAA"
            opponent = "AAA" if is_dst else "BBB"
            catalog_players.append({
                "id": player_id,
                "name": player_id,
                "pos": position,
                "team": team,
                "opp": opponent,
                "game_id": "AAA|BBB",
                "salary": 3000 if is_dst else 6000,
                "proj": 7.0 if is_dst else 15.0,
            })
            if is_dst:
                continue
            family = (
                "qb" if position == "QB"
                else "rb" if position == "RB"
                else "receiver"
            )
            skill_players.append((
                player_id,
                family,
                position,
                team,
                opponent,
                True if position == "QB" else None,
                round(
                    (index * 8 + slot + 1) / (candidate_count * 8 + 1),
                    12,
                ),
            ))
        lineup_id = v12_import.canonical_lineup_id(
            PROVENANCE_SLATE, roster
        )
        block = (
            "R4" if index == candidate_count - 1
            else rw.WORLD_BLOCKS[index % 4]
        )
        arm_ordinal = index % len(batch.PARAMETER_SET_ORDER)
        arm_id = batch.PARAMETER_SET_ORDER[arm_ordinal]
        occurrence = {
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": arm_id,
            "visit_ordinal": index,
            "block_id": block,
            "objective_world_index": index % 2,
        }
        candidates.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "origin_blocks": [block],
            "source_arms": [arm_id],
            "occurrence_counts_by_block": {
                value: int(value == block) for value in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": {
                value: [arm_id] if value == block else []
                for value in rw.WORLD_BLOCKS
            },
            "occurrence_count": 1,
            "occurrences": [occurrence],
        })
    candidates.sort(key=lambda row: str(row["lineup_id"]))
    catalog_players.sort(key=lambda row: str(row["id"]))
    skill_players.sort(key=lambda row: row[0])
    provenance: dict[str, object] = {
        "schema_version": v12_import.PROVENANCE_SCHEMA,
        "slate": dict(PROVENANCE_SLATE),
        "visit_schedule_sha256": "a" * 64,
        "visits_per_block": 2,
        "arm_count": len(batch.PARAMETER_SET_ORDER),
        "visit_occurrence_count": candidate_count,
        "candidate_count": candidate_count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": candidates,
        "uses_realized_outcomes": False,
    }
    provenance["candidate_provenance_sha256"] = batch.canonical_sha256(
        provenance
    )
    row = np.arange(candidate_count, dtype=np.float64)[:, None]
    column = np.arange(10, dtype=np.float64)[None, :]
    scores = np.ascontiguousarray(180.0 + (row % 31) + column * 0.75)
    r4_only_index = next(
        offset for offset, candidate in enumerate(candidates)
        if candidate["origin_blocks"] == ["R4"]
    )
    scores[r4_only_index] = 400.0 + column
    lineup_ids = [str(candidate["lineup_id"]) for candidate in candidates]
    matrix_binding: dict[str, object] = {
        "schema_version": v12_import.MATRIX_BINDING_SCHEMA,
        "slate": dict(PROVENANCE_SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": batch.canonical_sha256(lineup_ids),
        "world_ids_sha256": "9" * 64,
        "shape": list(scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(scores),
        "uses_realized_outcomes": False,
    }
    matrix_binding["matrix_binding_sha256"] = batch.canonical_sha256(
        matrix_binding
    )
    reconstruction_receipt: dict[str, object] = {
        "schema_version": v12_import.RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": "1" * 64,
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": matrix_binding,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": arm_id,
                "candidate_score_sha256": f"{ordinal + 1:x}" * 64,
                "selected_score_sha256": f"{ordinal + 8:x}" * 64,
                "unique_count": candidate_count,
                "selected_count": 80,
                "verified": True,
            }
            for ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    reconstruction_receipt["reconstruction_sha256"] = batch.canonical_sha256(
        reconstruction_receipt
    )
    prepared_players = tuple(
        SimpleNamespace(
            player_id=player["id"],
            position=player["pos"],
            team=player["team"],
            opponent=player["opp"],
            game_id=player["game_id"],
            salary=player["salary"],
        )
        for player in catalog_players
    )
    reconstructed = SimpleNamespace(
        prepared=SimpleNamespace(
            season=SLATE["season"],
            week=SLATE["week"],
            slate_id=SLATE["slate_id"],
            players=prepared_players,
        ),
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=reconstruction_receipt,
    )
    accepted = execution_v1.AcceptedV12SlateReconstruction(
        slate_id=str(SLATE["slate_id"]),
        panel_index_identity=_placeholder_identity("real-panel-index"),
        panel_index_sha256="a" * 64,
        accepted_slate_membership={
            "slate_id": SLATE["slate_id"],
            "task_ordinal": 0,
            "source_task_ordinal": 0,
        },
        task_acceptance_identity=_placeholder_identity("real-task-acceptance"),
        carrier_identity=_placeholder_identity("real-task-carrier"),
        later_source_freeze_identity=_placeholder_identity("real-source-freeze"),
        world_artifact_identities={
            role: _placeholder_identity(f"real-world-{role}")
            for role in batch.TASK_WORLD_SOURCE_ROLES
        },
        imported=SimpleNamespace(
            compatibility_receipt={"compatibility_import_sha256": "1" * 64}
        ),
        reconstructed=reconstructed,
    )
    return accepted, tuple(skill_players), catalog_players


def _surface_fixture(
    *,
    summary: Mapping[str, object],
    export_sha: str,
    neutral_replicates: int,
    require_authoritative: bool,
    admission_m: int,
    worlds_per_block: int | None,
) -> dict[str, object]:
    book_count = 14 + neutral_replicates

    def scope(heldout: str | None) -> dict[str, object]:
        books = [
            _self_hash({
                "schema_version": runner.BOOK_SCHEMA,
                "book_id": f"{heldout or 'final'}-book-{ordinal}",
                "ordinal": ordinal,
                "uses_realized_outcomes": False,
                "promotion_authority": False,
            }, "book_sha256")
            for ordinal in range(book_count)
        ]
        return _self_hash({
            "schema_version": runner.SCOPE_SCHEMA,
            "heldout_block": heldout,
            "training_blocks": (
                list(rw.WORLD_BLOCKS)
                if heldout is None
                else [block for block in rw.WORLD_BLOCKS if block != heldout]
            ),
            "strategy_registry": [
                {"ordinal": ordinal, "strategy_id": f"law-{ordinal}"}
                for ordinal in range(7)
            ],
            "book_count": book_count,
            "books": books,
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        }, "fit_scope_sha256")

    folds = [scope(block) for block in rw.WORLD_BLOCKS]
    return _self_hash({
        "schema_version": runner.RUNNER_SCHEMA,
        "slate": dict(PROVENANCE_SLATE),
        "matchup_summary_sha256": summary["matchup_summary_sha256"],
        "matchup_source_snapshot_sha256": export_sha,
        "folds": folds,
        "final_fit": scope(None),
        "fold_count": len(folds),
        "books_per_scope": book_count,
        "cross_fit_book_count": len(folds) * book_count,
        "final_fit_book_count": book_count,
        "neutral_replicate_count": neutral_replicates,
        "worlds_per_block": (
            rw.WORLDS_PER_BLOCK
            if worlds_per_block is None
            else worlds_per_block
        ),
        "admission_cap": admission_m,
        "dose_authority": (
            runner.AUTHORITATIVE_DOSE
            if require_authoritative
            else runner.FIXTURE_DOSE
        ),
        "require_authoritative": require_authoritative,
        "final_fit_is_distinct_all-block-refit": True,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }, "retrieval_surface_sha256")


def _install_execution_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    accepted: execution_v1.AcceptedV12SlateReconstruction,
) -> list[str]:
    calls: list[str] = []

    def reconstruct(**kwargs):
        calls.append("reconstruct")
        return accepted

    def build_summary(**kwargs):
        calls.append("build-summary")
        authority = kwargs["matchup_source"]
        assert isinstance(authority, runner.MatchupSourceExactReopen)
        reopened = matchup_source.reopen_matchup_source_snapshot(
            source_export_identity=authority.source_export_identity,
            query_receipt_identity=authority.query_receipt_identity,
            player_catalog_identity=authority.player_catalog_identity,
            read_exact=authority.read_exact,
            expected_slate=authority.expected_slate,
            required_evidence_class=authority.required_evidence_class,
        )
        return {
            "schema_version": runner.MATCHUP_SUMMARY_SCHEMA,
            "matchup_summary_sha256": "4" * 64,
            "matchup_source_snapshot_sha256": reopened[
                "source_export_identity"
            ]["sha256"],
            "matchup_source_schema_version": reopened["schema_version"],
            "player_catalog_identity": reopened["player_catalog_identity"],
            "annotation_query_receipt_identity": reopened[
                "query_receipt_identity"
            ],
            "uses_realized_outcomes": False,
        }

    def run_surface(**kwargs):
        calls.append("run-surface")
        authority = kwargs["matchup_source"]
        assert isinstance(authority, runner.MatchupSourceExactReopen)
        return _surface_fixture(
            summary=kwargs["matchup_summary"],
            export_sha=str(authority.source_export_identity["sha256"]),
            neutral_replicates=kwargs["neutral_replicates"],
            require_authoritative=kwargs["require_authoritative"],
            admission_m=kwargs["admission_m"],
            worlds_per_block=kwargs["worlds_per_block"],
        )

    def validate_surface(value, **kwargs):
        calls.append("validate-surface")
        authority = kwargs["matchup_source"]
        expected = _surface_fixture(
            summary=kwargs["matchup_summary"],
            export_sha=str(authority.source_export_identity["sha256"]),
            neutral_replicates=kwargs["neutral_replicates"],
            require_authoritative=kwargs["require_authoritative"],
            admission_m=kwargs["admission_m"],
            worlds_per_block=kwargs["worlds_per_block"],
        )
        if batch.canonical_json_bytes(value) != batch.canonical_json_bytes(
            expected
        ):
            raise runner.CorpusBatchRetrievalV2Error(
                "retained retrieval surface canonical replay differs"
            )
        return expected

    monkeypatch.setattr(
        execution_v1, "reconstruct_one_accepted_v12_slate", reconstruct
    )
    monkeypatch.setattr(runner, "build_matchup_lineup_summaries", build_summary)
    monkeypatch.setattr(runner, "run_retrieval_surface_v2", run_surface)
    monkeypatch.setattr(
        runner, "validate_retrieval_surface_v2", validate_surface
    )
    return calls


def _execute(
    *,
    store: ExactObjectStore,
    identities: Mapping[str, Mapping[str, object]],
    **overrides: object,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "validated_panel_index": {"fixture": True},
        "panel_index_identity": _placeholder_identity("panel-input"),
        "accepted_slate_membership": {
            "slate_id": SLATE["slate_id"],
            "task_ordinal": 0,
            "source_task_ordinal": 0,
        },
        "task_acceptance_identity": _placeholder_identity("acceptance-input"),
        "carrier_identity": _placeholder_identity("carrier-input"),
        "matchup_source_export_identity": identities[
            "source_export_identity"
        ],
        "matchup_query_receipt_identity": identities[
            "query_receipt_identity"
        ],
        "matchup_player_catalog_identity": identities[
            "player_catalog_identity"
        ],
        "expected_matchup_slate": dict(SLATE),
        "read_exact": store.read_exact,
        "require_authoritative": True,
    }
    kwargs.update(overrides)
    return execution.execute_one_slate_r6_v2(**kwargs)


def test_corrected_executor_binds_exact_source_and_full_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, identities = _capture_corrected_matchup_source()
    accepted = _accepted_reconstruction()
    calls = _install_execution_stubs(monkeypatch, accepted=accepted)
    result = _execute(store=store, identities=identities)

    assert calls == [
        "reconstruct",
        "build-summary",
        "run-surface",
        "validate-surface",
    ]
    assert result["schema_version"] == execution.RESULT_SCHEMA
    assert result["matchup_source_identities"] == {
        "source_export": identities["source_export_identity"],
        "query_receipt": identities["query_receipt_identity"],
        "player_catalog": identities["player_catalog_identity"],
    }
    assert result["matchup_source_export_sha256"] == identities[
        "source_export_identity"
    ]["sha256"]
    assert result["matchup_source_export_schema_version"] == (
        matchup_source.SOURCE_EXPORT_SCHEMA
    )
    assert result["matchup_source_schema_version"] == (
        matchup_source.REOPENED_SOURCE_SCHEMA
    )
    assert result["matchup_evidence_class"] == (
        matchup_source.EVIDENCE_RETROSPECTIVE
    )
    assert result["required_matchup_evidence_class"] == (
        matchup_source.EVIDENCE_RETROSPECTIVE
    )
    assert result["accepted_task_binding"] == {
        "task_id": "slate-2023-w1",
        "slate_id": SLATE["slate_id"],
        "task_ordinal": 0,
        "source_task_ordinal": 0,
    }
    assert result["accepted_task_binding_sha256"] == batch.canonical_sha256(
        result["accepted_task_binding"]
    )
    assert result["accepted_player_catalog_structural_sha256"] == result[
        "matchup_player_catalog_structural_sha256"
    ]
    assert result["verification"][
        "full_seven_law_fold_final_surface_canonical_replay_verified"
    ] is True
    assert result["retrieval_surface"]["fold_count"] == len(rw.WORLD_BLOCKS)
    assert result["retrieval_surface"]["final_fit"]["heldout_block"] is None
    for field in execution._FALSE_RESULT_AUTHORITY_FIELDS:
        assert result[field] is False
    for field in execution._FALSE_MATCHUP_SOURCE_AUTHORITY_FIELDS:
        assert result["matchup_source_authority"][field] is False
    retained = result["task_result_sha256"]
    assert retained == batch.canonical_sha256({
        key: value for key, value in result.items()
        if key != "task_result_sha256"
    })


def test_real_runner_module_executes_and_canonically_replays_full_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, skill_players, catalog_players = (
        _real_runner_accepted_reconstruction()
    )
    store, identities = _capture_corrected_matchup_source(
        skill_players=skill_players,
        catalog_players=catalog_players,
    )
    calls: list[str] = []

    def reconstruct(**kwargs):
        calls.append("reconstruct")
        return accepted

    monkeypatch.setattr(
        execution_v1, "reconstruct_one_accepted_v12_slate", reconstruct
    )
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    result = _execute(
        store=store,
        identities=identities,
        require_authoritative=False,
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        minimum_completeness=1.0,
    )

    assert calls == ["reconstruct"]
    surface = result["retrieval_surface"]
    assert surface["schema_version"] == runner.RUNNER_SCHEMA
    assert [fold["heldout_block"] for fold in surface["folds"]] == list(
        rw.WORLD_BLOCKS
    )
    assert surface["final_fit"]["training_blocks"] == list(rw.WORLD_BLOCKS)
    assert surface["books_per_scope"] == 15
    assert result["verification"][
        "full_seven_law_fold_final_surface_canonical_replay_verified"
    ] is True
    assert result["task_result_sha256"] == batch.canonical_sha256({
        key: value for key, value in result.items()
        if key != "task_result_sha256"
    })


@pytest.mark.parametrize(
    "identity_key",
    [
        "source_export_identity",
        "query_receipt_identity",
        "player_catalog_identity",
    ],
)
def test_each_matchup_identity_drift_fails_before_selector_execution(
    monkeypatch: pytest.MonkeyPatch,
    identity_key: str,
) -> None:
    store, identities = _capture_corrected_matchup_source()
    calls = _install_execution_stubs(
        monkeypatch, accepted=_accepted_reconstruction()
    )
    drifted = deepcopy(identities)
    drifted[identity_key] = dict(drifted[identity_key])
    drifted[identity_key]["generation"] = "999999"
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="exact reopen failed.*identity/generation differs",
    ):
        _execute(store=store, identities=drifted)
    assert calls == ["reconstruct"]


def test_legacy_caller_mapping_cannot_replace_source_export_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, identities = _capture_corrected_matchup_source()
    calls = _install_execution_stubs(
        monkeypatch, accepted=_accepted_reconstruction()
    )
    legacy = {
        "schema_version": runner.MATCHUP_SOURCE_SCHEMA,
        "rows": [],
        "uses_realized_outcomes": False,
    }
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="source export identity fields differ",
    ):
        _execute(
            store=store,
            identities=identities,
            matchup_source_export_identity=legacy,
        )
    assert calls == ["reconstruct"]


def test_retrospective_evidence_floor_cannot_be_downgraded_before_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, identities = _capture_corrected_matchup_source()
    calls = _install_execution_stubs(
        monkeypatch, accepted=_accepted_reconstruction()
    )
    reads: list[str] = []

    def forbidden_read(identity: Mapping[str, object]) -> bytes:
        reads.append(str(identity["uri"]))
        return store.read_exact(identity)

    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="exact retrospective prior-period evidence floor",
    ):
        _execute(
            store=store,
            identities=identities,
            required_matchup_evidence_class=(
                matchup_source.EVIDENCE_NON_PIT
            ),
            read_exact=forbidden_read,
        )
    assert reads == []
    assert calls == ["reconstruct"]


def test_exact_source_content_drift_fails_before_selector_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, identities = _capture_corrected_matchup_source()
    calls = _install_execution_stubs(
        monkeypatch, accepted=_accepted_reconstruction()
    )
    source_identity = identities["source_export_identity"]
    store.objects[str(source_identity["uri"])]["raw"] += b" "
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="exact reopen failed.*content identity differs",
    ):
        _execute(store=store, identities=identities)
    assert calls == ["reconstruct"]


@pytest.mark.parametrize(
    "variant",
    ["player-addition", "player-removal", "context-change", "salary-change"],
)
def test_alternate_exact_catalog_cannot_replace_accepted_v12_catalog(
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
) -> None:
    def transform(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if variant == "player-addition":
            extra = deepcopy(DST_PLAYER)
            extra["id"] = "00-006"
            extra["name"] = "00-006"
            rows.append(extra)
        elif variant == "player-removal":
            rows = [row for row in rows if row["id"] != DST_PLAYER["id"]]
        elif variant == "context-change":
            target = next(row for row in rows if row["id"] == DST_PLAYER["id"])
            target["team"] = "AAA"
            target["opp"] = "BBB"
        elif variant == "salary-change":
            target = next(row for row in rows if row["id"] == DST_PLAYER["id"])
            target["salary"] = int(target["salary"]) + 100
        else:  # pragma: no cover - parametrization is closed
            raise AssertionError(variant)
        return rows

    store, identities = _capture_corrected_matchup_source(
        catalog_transform=transform
    )
    calls = _install_execution_stubs(
        monkeypatch, accepted=_accepted_reconstruction()
    )
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="matchup player catalog differs from accepted v12 catalog",
    ):
        _execute(store=store, identities=identities)
    assert calls == ["reconstruct"]


def test_legacy_catalog_name_and_projection_extras_are_not_science_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def transform(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        for row in rows:
            row["name"] = f"renamed-{row['id']}"
            row["proj"] = float(row["proj"]) + 99.0
        return rows

    store, identities = _capture_corrected_matchup_source(
        catalog_transform=transform
    )
    calls = _install_execution_stubs(
        monkeypatch, accepted=_accepted_reconstruction()
    )
    result = _execute(store=store, identities=identities)
    assert result["accepted_player_catalog_structural_sha256"] == result[
        "matchup_player_catalog_structural_sha256"
    ]
    assert calls[-1] == "validate-surface"


def test_caller_cannot_substitute_an_alternate_same_slate_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alternate_slate = {**SLATE, "task_id": "alternate-same-slate-task"}
    store, identities = _capture_corrected_matchup_source(
        slate=alternate_slate
    )
    calls = _install_execution_stubs(
        monkeypatch, accepted=_accepted_reconstruction()
    )
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="caller expected matchup slate differs from accepted v12 task",
    ):
        _execute(
            store=store,
            identities=identities,
            expected_matchup_slate=alternate_slate,
        )
    assert calls == ["reconstruct"]


@pytest.mark.parametrize(
    "membership",
    [
        {"slate_id": SLATE["slate_id"], "source_task_ordinal": 0},
        {
            "slate_id": SLATE["slate_id"],
            "task_ordinal": True,
            "source_task_ordinal": 0,
        },
        {
            "slate_id": SLATE["slate_id"],
            "task_ordinal": 0,
            "source_task_ordinal": -1,
        },
    ],
)
def test_accepted_panel_task_ordinals_are_exact_retained_authority(
    monkeypatch: pytest.MonkeyPatch,
    membership: Mapping[str, object],
) -> None:
    store, identities = _capture_corrected_matchup_source()
    accepted = replace(
        _accepted_reconstruction(), accepted_slate_membership=membership
    )
    calls = _install_execution_stubs(monkeypatch, accepted=accepted)
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="accepted (?:source )?task ordinal must be a nonnegative exact integer",
    ):
        _execute(store=store, identities=identities)
    assert calls == ["reconstruct"]


@pytest.mark.parametrize(
    "mutation",
    [
        "coherent-fake-surface",
        "reordered-registry",
        "substituted-registry",
        "bad-fold-complement",
        "altered-scope-hash",
        "altered-book-hash",
        "extra-nested-authority",
    ],
)
def test_only_canonical_full_surface_replay_is_retained(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    store, identities = _capture_corrected_matchup_source()
    accepted = _accepted_reconstruction()
    _install_execution_stubs(monkeypatch, accepted=accepted)
    original = runner.run_retrieval_surface_v2

    def noncanonical(**kwargs):
        value = original(**kwargs)
        fold = value["folds"][0]
        if mutation == "coherent-fake-surface":
            value["books_per_scope"] += 1
            value["retrieval_surface_sha256"] = batch.canonical_sha256({
                key: nested for key, nested in value.items()
                if key != "retrieval_surface_sha256"
            })
        elif mutation == "reordered-registry":
            fold["strategy_registry"][0], fold["strategy_registry"][1] = (
                fold["strategy_registry"][1],
                fold["strategy_registry"][0],
            )
        elif mutation == "substituted-registry":
            fold["strategy_registry"][0]["strategy_id"] = "substituted-law"
        elif mutation == "bad-fold-complement":
            fold["training_blocks"].append(fold["heldout_block"])
        elif mutation == "altered-scope-hash":
            fold["fit_scope_sha256"] = "0" * 64
        elif mutation == "altered-book-hash":
            fold["books"][0]["book_sha256"] = "0" * 64
        elif mutation == "extra-nested-authority":
            fold["books"][0]["decision_authority"] = True
        else:  # pragma: no cover - parametrization is closed
            raise AssertionError(mutation)
        return value

    monkeypatch.setattr(runner, "run_retrieval_surface_v2", noncanonical)
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="retained retrieval surface canonical replay differs",
    ):
        _execute(store=store, identities=identities)


def test_authoritative_dose_override_fails_before_exact_reads() -> None:
    store, identities = _capture_corrected_matchup_source()
    reads: list[str] = []

    def forbidden_read(identity: Mapping[str, object]) -> bytes:
        reads.append(str(identity["uri"]))
        return store.read_exact(identity)

    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionV2Error,
        match="cannot override registered doses",
    ):
        _execute(
            store=store,
            identities=identities,
            read_exact=forbidden_read,
            admission_m=80,
        )
    assert reads == []
